"""Portal activity and visitors: one SQLite file, written by a background thread, read by two screens.

Two writers, nothing else to remember when a page is added:
  1. the HTTP middleware — one row per request, signed in or not: who, method, path, status, time.
  2. the page-view beacon — every screen the browser shows (the shell sends it on each route), plus
     server-rendered pages (/m/…, /help/…) recorded here directly.

The ledger is BODY-FREE: names and ids only — never a query string, a request body, a token, a
script or a key. IP addresses are cut to their network (/24 for IPv4, /48 for IPv6) before they are
stored: enough to count and place visitors, not enough to name one.

SQLite, not JSON: this file takes a row on nearly every request, and a JSON file rewritten whole each
time is O(everything). sqlite3 is in the standard library.
"""
from __future__ import annotations

import hashlib
import json
import queue
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from core import auth, engine, geo, memwatch, rules, store
from core.access import screen

rules.subject("visit", "A page someone opened", [
    {"name": "path", "type": "text", "label": "Page (no query string)"},
    {"name": "signed_in", "type": "boolean", "label": "Signed in"},
    {"name": "country", "type": "text", "label": "Country code"},
    {"name": "region", "type": "text", "label": "State / region"},
    {"name": "city", "type": "text", "label": "City"},
    {"name": "device", "type": "text", "label": "desktop, mobile, tablet or bot"},
    {"name": "browser", "type": "text", "label": "Browser"},
    {"name": "os", "type": "text", "label": "System"},
    {"name": "referrer", "type": "text", "label": "Came from (site only)"}],
    "Every page view the Visitors screen counts.")
rules.trigger("page.view", "visit", "A page is viewed", ["banner", "notify"],
              "Every page view — use a cooldown on anything that tells a person.")

router = APIRouter()

SCHEMA = """
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, user_id TEXT, email TEXT, method TEXT, path TEXT,
  status INTEGER, ms INTEGER, ip TEXT, screen TEXT);
CREATE INDEX IF NOT EXISTS activity_at ON activity(at);
CREATE INDEX IF NOT EXISTS activity_user ON activity(user_id, at);
CREATE TABLE IF NOT EXISTS views (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, view_id TEXT UNIQUE, session_id TEXT, user_id TEXT,
  email TEXT, path TEXT, title TEXT, referrer TEXT, ip TEXT, country TEXT, region TEXT, city TEXT,
  tz TEXT, lang TEXT, device TEXT, browser TEXT, os TEXT, vw INTEGER, vh INTEGER, dwell_ms INTEGER);
CREATE INDEX IF NOT EXISTS views_at ON views(at);
CREATE TABLE IF NOT EXISTS security (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, kind TEXT NOT NULL, by_id TEXT, target_id TEXT, ip TEXT);
CREATE INDEX IF NOT EXISTS security_at ON security(at);
"""


def settings() -> dict:
    """Retention, repeat window, beacon limit and list sizes — chip ledger.settings."""
    return engine.run("ledger.settings")


def db_path():
    return store.DATA / "ledger.sqlite3"


def connect() -> sqlite3.Connection:
    store.DATA.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(db_path(), timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(SCHEMA)
    return c


@contextmanager
def db():
    """One transaction, and the file is let go afterwards — whatever happened inside."""
    c = connect()
    try:
        with c:
            yield c
    finally:
        c.close()


# --- the writer ---------------------------------------------------------------------------------
# A queue and one thread: the request never waits on the disk. Batches of up to 500 rows, one
# transaction each; the connection is closed between batches so nothing holds the file open.

_Q: queue.Queue = queue.Queue(maxsize=20_000)
_writer: threading.Thread | None = None
_pruned = 0.0


def _put(sql: str, args: tuple) -> None:
    global _writer
    if _writer is None or not _writer.is_alive():
        _writer = threading.Thread(target=_drain, name="ledger", daemon=True)
        _writer.start()
    try:
        _Q.put_nowait((sql, args))
    except queue.Full:
        pass              # ponytail: a flood drops ledger rows rather than slowing requests down


def _drain() -> None:
    global _pruned
    while True:
        batch = [_Q.get()]
        while len(batch) < 500:
            try:
                batch.append(_Q.get(timeout=0.2))
            except queue.Empty:
                break
        try:
            with db() as c:
                for sql, args in batch:
                    c.execute(sql, args)
                if time.time() - _pruned > 3600:  # ponytail: hourly prune, cheap enough to leave as the cadence
                    _pruned = time.time()
                    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days())).isoformat(timespec="seconds")
                    c.execute("DELETE FROM activity WHERE at < ?", (cutoff,))
                    c.execute("DELETE FROM views WHERE at < ?", (cutoff,))
                    c.execute("DELETE FROM security WHERE at < ?", (cutoff,))
        except sqlite3.Error:
            pass          # a locked or broken ledger must never take a request down with it
        finally:
            for _ in batch:
                _Q.task_done()


def flush() -> None:
    """Wait until everything queued is on disk (tests, and the export button)."""
    _Q.join()


def keep_days() -> int:
    kn, stored = settings(), store.read("settings", {}).get("ledger_days")
    return int(engine.run("ledger.keep_days", {"stored": stored if isinstance(stored, (int, float)) else None,
                                                "default_days": kn["keep_days_default"], "min_days": kn["keep_days_min"],
                                                "max_days": kn["keep_days_max"]}))


# --- what may be stored -------------------------------------------------------------------------

def cut_ip(ip: str) -> str:
    return engine.run("ledger.stored_ip", {"ip": ip or ""})


def clean_path(path: str) -> str:
    """Never a query string, never a token (chip ledger.stored_path)."""
    return engine.run("ledger.stored_path", {"path": str(path or "")})


def origin_only(url: str) -> str:
    return engine.run("ledger.stored_referrer", {"referrer": str(url or "")})


def device_of(ua: str) -> tuple[str, str, str]:
    d = engine.run("ledger.device", {"user_agent": ua or ""})
    return d["device"], d["browser"], d["os"]


def place(request: Request) -> tuple[str, str, str]:
    """Country, region and city. Facts: the CDN's headers and the local database's answer; which one wins
    is chip ledger.place_source. The database is looked up on the FULL address before it is cut."""
    h = request.headers
    cdn = ((h.get("cf-ipcountry") or h.get("x-vercel-ip-country") or "")[:8],
           (h.get("cf-region") or h.get("x-vercel-ip-country-region") or "")[:60],
           (h.get("cf-ipcity") or h.get("x-vercel-ip-city") or "")[:60])
    return cdn if engine.run("ledger.place_source", {"cdn_country": cdn[0]}) == "cdn" else geo.lookup(auth.client_ip(request))


def backfill_places() -> None:
    """Views stored before a database was available get a place from their stored /24 (or /48)
    network: the database is keyed by network, so a state-level answer is the same one."""
    with db() as c:
        nets = [r[0] for r in c.execute("SELECT DISTINCT ip FROM views WHERE COALESCE(country, '') = '' AND ip != ''")]
    for net in nets:
        country, region, city = geo.lookup(net.split("/")[0])
        if country:
            _put("UPDATE views SET country = ?, region = ?, city = ? WHERE ip = ? AND COALESCE(country, '') = ''",
                 (country, region, city, net))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- writer 3: security events (2026-11-18 gap audit C1-19) ----------------------------------------
# A failed sign-in, a new MCP key, an owner/role change, the first account taken: the kind, who did it, whom it touched (ids)
# and the cut network - never an address typed, a key, a password. core/health.py's `security` probe reads them.

def security(kind: str, by_id: str = "", target_id: str = "", ip: str = "") -> None:
    _put("INSERT INTO security(at,kind,by_id,target_id,ip) VALUES(?,?,?,?,?)",
         (now(), str(kind)[:40], str(by_id or "")[:40], str(target_id or "")[:40], cut_ip(ip)))


# --- writer 1: every request --------------------------------------------------------------------

_recent: dict[tuple, float] = {}


def _strip_base(path: str) -> str:
    return path[len(auth.BASE):] or "/" if auth.BASE and path.startswith(auth.BASE) else path


async def track(request: Request, call_next):
    path = _strip_base(request.url.path)
    if engine.run("ledger.skip_path", {"path": path}):
        return await call_next(request)
    t0, before = time.perf_counter(), memwatch.rss()
    response = await call_next(request)
    ms = int((time.perf_counter() - t0) * 1000)
    memwatch.note_request(request.method, path, before, response.status_code, ms)
    memwatch.count_bytes(request.headers.get("content-length"), response.headers.get("content-length"))

    u = getattr(request.state, "user", None)
    if u is None and request.cookies.get(auth.COOKIE):
        u = auth.current_user(request)
    ip = auth.client_ip(request)
    key = (u["id"] if u else ip, request.method, path)
    last = _recent.get(key)
    _recent[key] = time.time()
    if len(_recent) > 5000:
        _recent.clear()
    if engine.run("ledger.is_repeat", {"method": request.method, "status": response.status_code,
                                       "seconds_since_last": None if last is None else time.time() - last,
                                       "repeat_seconds": settings()["repeat_seconds"]}):
        return response
    _put("INSERT INTO activity(at,user_id,email,method,path,status,ms,ip,screen) VALUES(?,?,?,?,?,?,?,?,?)",
         (now(), u["id"] if u else None, u["email"] if u else None, request.method, clean_path(path),
          response.status_code, ms, cut_ip(ip), getattr(request.state, "screen", None)))

    # Server-rendered pages are visits too; the single-page shell reports its own.
    if engine.run("ledger.counts_as_view", {"method": request.method, "status": response.status_code, "path": path,
                                            "content_type": response.headers.get("content-type", "")}):
        _view(request, u, {"path": path, "view_id": uuid.uuid4().hex,
                           "session_id": hashlib.sha256(f"{cut_ip(ip)}|{request.headers.get('user-agent', '')}|"
                                                        f"{now()[:10]}".encode()).hexdigest()[:16]})
    return response


# --- writer 2: page views -----------------------------------------------------------------------

_BEACON_HITS: dict[str, list[float]] = {}


def _view(request: Request, u: dict | None, b: dict) -> None:
    device, browser, system = device_of(request.headers.get("user-agent", ""))
    country, region, city = place(request)
    if b.get("dwell_ms") in (None, ""):  # the leave beacon updates a view; only the arrival is a visit
        rules.fire("page.view", {"path": clean_path(b.get("path")), "signed_in": bool(u), "country": country,
                                 "region": region, "city": city, "device": device, "browser": browser, "os": system,
                                 "referrer": origin_only(b.get("referrer"))}, {"person": u})
    num = lambda k: int(b[k]) if str(b.get(k, "")).isdigit() else None  # noqa: E731
    s = lambda k, n=120: str(b.get(k) or "")[:n]  # noqa: E731
    _put("""INSERT INTO views(at,view_id,session_id,user_id,email,path,title,referrer,ip,country,region,city,
                              tz,lang,device,browser,os,vw,vh,dwell_ms)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(view_id) DO UPDATE SET dwell_ms = MAX(COALESCE(dwell_ms, 0), COALESCE(excluded.dwell_ms, 0))""",
         (now(), s("view_id", 40), s("session_id", 40), u["id"] if u else None, u["email"] if u else None,
          clean_path(b.get("path")), s("title"), origin_only(b.get("referrer")), cut_ip(auth.client_ip(request)),
          country, region, city, s("tz", 60), s("lang", 20), device, browser, system,
          num("vw"), num("vh"), num("dwell_ms")))


@router.post("/api/core/view")
def page_view(request: Request, body: dict = Body(...)):
    """Open to everyone — the landing page is a page too. Rate-limited per address, and it returns
    nothing, so it cannot be used to read anything back."""
    kn = settings()
    if not auth.rate_ok(auth.client_ip(request), int(kn["beacon_per_minute"]), _BEACON_HITS):
        return JSONResponse({"ok": False}, status_code=429)
    if not engine.run("ledger.is_view_id", {"view_id": str(body.get("view_id") or ""), "pattern": kn["view_id_pattern"]}):
        raise HTTPException(400, engine.say("ledger.messages", "bad_view_id"))
    _view(request, auth.current_user(request), body)
    return {"ok": True}


# --- reading ------------------------------------------------------------------------------------

def since(range_: str) -> str:
    hours = engine.run("ledger.range", {"range": range_})["hours"]
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds") if hours else ""


def rows(c: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in c.execute(sql, args).fetchall()]


@router.get("/api/core/activity")
def activity(q: str = "", outcome: str = "all", page: int = 1, size: int = 50,
             _: dict = Depends(screen("activity"))):
    flush()
    kn = settings()
    size = max(int(kn["activity_page_min"]), min(int(kn["activity_page_max"]), size))
    where, args = ["1=1"], []
    if q.strip():
        where.append("(email LIKE ? OR path LIKE ? OR screen LIKE ? OR ip LIKE ?)")
        args += [f"%{q.strip()}%"] * 4
    if outcome == "fail":
        where.append("status >= 400")
    elif outcome == "ok":
        where.append("status < 400")
    elif outcome == "anon":
        where.append("user_id IS NULL")
    sql = " AND ".join(where)
    with db() as c:
        total = c.execute(f"SELECT COUNT(*) FROM activity WHERE {sql}", args).fetchone()[0]
        out = rows(c, f"SELECT * FROM activity WHERE {sql} ORDER BY id DESC LIMIT ? OFFSET ?",
                   (*args, size, (max(1, page) - 1) * size))
    return {"rows": out, "total": total, "page": max(1, page), "size": size, "keep_days": keep_days()}


@router.get("/api/core/activity/report")
def report(range: str = "30d", _: dict = Depends(screen("activity"))):  # noqa: A002 - the query name
    flush()
    start = since(range)
    with db() as c:
        people = rows(c, """SELECT user_id, email, COUNT(*) AS requests, SUM(status >= 400) AS failed,
                                   COUNT(DISTINCT screen) AS screens, MAX(at) AS last_at
                            FROM activity WHERE user_id IS NOT NULL AND at >= ?
                            GROUP BY user_id ORDER BY requests DESC, user_id LIMIT ?""", (start, int(settings()["report_people_shown"])))
        screens = rows(c, """SELECT screen, COUNT(*) AS requests, COUNT(DISTINCT user_id) AS people,
                                    SUM(status >= 400) AS failed, CAST(AVG(ms) AS INTEGER) AS avg_ms
                             FROM activity WHERE screen IS NOT NULL AND at >= ?
                             GROUP BY screen ORDER BY requests DESC, screen""", (start,))
        signins = rows(c, """SELECT substr(at, 1, 10) AS day, SUM(status < 400) AS ok, SUM(status >= 400) AS failed
                             FROM activity WHERE method = 'POST' AND path = '/api/auth/signin' AND at >= ?
                             GROUP BY day ORDER BY day""", (start,))
        totals = dict(c.execute("""SELECT COUNT(*) AS requests, COUNT(DISTINCT user_id) AS people,
                                          SUM(user_id IS NULL) AS anonymous, SUM(status >= 500) AS errors
                                   FROM activity WHERE at >= ?""", (start,)).fetchone())
    joins: dict[str, int] = {}
    for u in store.users():
        if (u.get("created_at") or "") >= start:
            joins[u["created_at"][:10]] = joins.get(u["created_at"][:10], 0) + 1
    from core.access import label_of
    for s in screens:
        s["label"] = label_of(s["screen"])
    return {"range": range, "totals": totals, "people": people, "screens": screens, "signins": signins,
            "joins": [{"day": d, "count": n} for d, n in sorted(joins.items())]}


@router.get("/api/core/visitors")
def visitors(range: str = "7d", _: dict = Depends(screen("visitors"))):  # noqa: A002
    flush()
    start, kn = since(range), settings()
    by = "substr(at, 1, 13)" if engine.run("ledger.range", {"range": range})["bucket"] == "hour" else "substr(at, 1, 10)"
    not_people = [str(x) for x in kn["not_people"]] or [""]
    np_sql = ",".join("?" * len(not_people))
    top = lambda col, n: rows(c, f"""SELECT COALESCE(NULLIF({col}, ''), 'unknown') AS name, COUNT(*) AS views,
                                     COUNT(DISTINCT session_id) AS sessions FROM views WHERE at >= ?
                                     GROUP BY name ORDER BY views DESC, name LIMIT ?""", (start, int(n)))  # noqa: E731
    with db() as c:
        totals = dict(c.execute(f"""SELECT COUNT(*) AS views, COUNT(DISTINCT session_id) AS sessions,
                                           COUNT(DISTINCT user_id) AS people, SUM(user_id IS NULL) AS anonymous,
                                           CAST(AVG(NULLIF(dwell_ms, 0)) AS INTEGER) AS avg_dwell_ms
                                    FROM views WHERE at >= ? AND device NOT IN ({np_sql})""", (start, *not_people)).fetchone())
        out = {"range": range, "totals": totals,
               "pages": rows(c, """SELECT path AS name, COUNT(*) AS views, COUNT(DISTINCT session_id) AS sessions,
                                          CAST(AVG(NULLIF(dwell_ms, 0)) AS INTEGER) AS avg_dwell_ms
                                   FROM views WHERE at >= ? GROUP BY path ORDER BY views DESC, path LIMIT ?""",
                             (start, int(kn["visitor_pages_shown"]))),
               "countries": top("country", kn["visitor_top_shown"]), "cities": top("city", kn["visitor_top_shown"]),
               "devices": top("device", kn["visitor_devices_shown"]), "browsers": top("browser", kn["visitor_browsers_shown"]),
               "systems": top("os", kn["visitor_systems_shown"]), "referrers": top("referrer", kn["visitor_top_shown"]),
               "timezones": top("tz", kn["visitor_top_shown"]),
               "series": rows(c, f"""SELECT {by} AS bucket, COUNT(*) AS views, COUNT(DISTINCT session_id) AS sessions
                                     FROM views WHERE at >= ? GROUP BY bucket ORDER BY bucket""", (start,)),
               "latest": rows(c, """SELECT at, path, email, country, region, city, device, browser, os, referrer, dwell_ms
                                    FROM views ORDER BY id DESC LIMIT ?""", (int(kn["latest_shown"]),)),
               # The maps: EVERY country and every Indian state, not a top-N; people only (not_people left out).
               "map_countries": rows(c, f"""SELECT country AS name, COUNT(*) AS views FROM views
                                            WHERE at >= ? AND COALESCE(country, '') != '' AND device NOT IN ({np_sql})
                                            GROUP BY country""", (start, *not_people)),
               "india_regions": rows(c, f"""SELECT region AS name, COUNT(*) AS views FROM views
                                            WHERE at >= ? AND country = 'IN' AND COALESCE(region, '') != ''
                                            AND device NOT IN ({np_sql}) GROUP BY region""", (start, *not_people)),
               "geo": geo.status()}
    return out


# --- archive: download first, then clear --------------------------------------------------------

TABLES = {"activity", "views"}


def _before(body_or_q: str) -> str:
    try:
        return datetime.fromisoformat(body_or_q).date().isoformat()
    except ValueError:
        raise HTTPException(400, engine.say("ledger.messages", "pick_date"))


@router.get("/api/core/archive/{table}")
def export(table: str, before: str, _: dict = Depends(screen("activity"))):
    if table not in TABLES:
        raise HTTPException(404, engine.say("ledger.messages", "bad_table"))
    cutoff = _before(before)
    flush()

    def lines():
        c = connect()
        try:
            for r in c.execute(f"SELECT * FROM {table} WHERE at < ? ORDER BY id", (cutoff,)):
                yield json.dumps(dict(r), ensure_ascii=False) + "\n"
        finally:
            c.close()
    return StreamingResponse(lines(), media_type="application/x-ndjson", headers={
        "Content-Disposition": f'attachment; filename="{table}-before-{cutoff}.jsonl"'})


@router.post("/api/core/archive/{table}/clear")
def clear(table: str, body: dict = Body(...), _: dict = Depends(auth.owner)):
    """Owner only, and it says how many rows went: the download above is the only copy after this."""
    if table not in TABLES:
        raise HTTPException(404, engine.say("ledger.messages", "bad_table"))
    cutoff = _before(str(body.get("before") or ""))
    flush()
    with db() as c:
        gone = c.execute(f"DELETE FROM {table} WHERE at < ?", (cutoff,)).rowcount
    return {"deleted": gone}


@router.put("/api/core/archive/keep")
def set_keep(body: dict = Body(...), _: dict = Depends(auth.owner)):
    try:
        wanted = int(body.get("days"))
    except (TypeError, ValueError):
        raise HTTPException(400, engine.say("ledger.messages", "days_not_number"))
    kn = settings()
    days = int(engine.run("ledger.keep_days", {"stored": wanted, "default_days": kn["keep_days_default"],
                                               "min_days": kn["keep_days_min"], "max_days": kn["keep_days_max"]}))
    with store._LOCK:                                 # noqa: SLF001
        s = store.read("settings", {})
        s["ledger_days"] = days
        store.write("settings", s)
    return {"keep_days": days}


if __name__ == "__main__":  # ponytail: one runnable self-check of what may be stored
    assert cut_ip("203.0.113.77") == "203.0.113.0/24"
    assert cut_ip("2001:db8:abcd:12:1::5") == "2001:db8:abcd::/48"
    assert cut_ip("not an ip") == ""
    assert clean_path("#/reset?token=SECRET") == "#/reset" and "SECRET" not in clean_path("/x&token=SECRET")
    assert origin_only("https://www.google.com/search?q=me") == "https://www.google.com"
    assert origin_only("javascript:alert(1)") == ""
    assert device_of("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E148 Safari/604.1") == ("mobile", "Safari", "iOS")
    assert device_of("Mozilla/5.0 (Windows NT 10.0) Chrome/120.0 Safari/537.36 Edg/120.0")[1:] == ("Edge", "Windows")
    assert device_of("curl/8.0")[0] == "bot"
    print("core.ledger self-check OK")
