"""Health check - is everything the portal needs working? (2026-10-15 owner: "I see email but they are too many. Can we
give a warning in the portal that replaces the message and does not add to the list continuously"; built 2026-10-23 as
the first agent, recipe agents.recipe.ag_health.)

A module attaches one probe:   health.probe("free_voice", fn)      fn() -> {"ok": bool, "say": "plain words"}
A probe that finds several separate things (security events) also returns "each": [{"key": k, "say": ...}] - one problem
per key, id "<probe>:<key>", so each one rings the bell once (2026-11-18 gap audit C1-19).
Core attaches the disk probe; the portal attaches the rest (its voice, its AI keys, YouTube, its own certificate).

Two agent actions (chip agents.actions):
  health.check  (read)   every probe once - a probe that raises is a problem in its own words, never a crash
  health.warn   (write)  the owners' warning bar becomes exactly this answer (replaced, never appended); the bell rings
                         ONCE for a problem that is new since the last check (feedback: alert once, not daily)
The shell shows the bar to owners on every page (bootstrap `health`); a fixed problem leaves it at the next check.
Every number is chip health.settings; every sentence chip health.messages.
"""
from __future__ import annotations

import shutil
import socket
import ssl
import time
from datetime import datetime, timezone
from typing import Callable

from fastapi import Request

from core import agents, bell, engine, store

PROBES: dict[str, Callable[[], dict]] = {}
BAR = "health_bar"


def settings() -> dict:
    return engine.run("health.settings")


def say(key: str, **values) -> str:
    return engine.say("health.messages", key, **values)


def probe(probe_id: str, fn: Callable[[], dict]) -> None:
    PROBES[probe_id] = fn


def disk() -> dict:
    free_gb = shutil.disk_usage(store.DATA if store.DATA.exists() else ".").free / 1024 ** 3
    ok = engine.run("health.disk_ok", {"free_gb": free_gb, "min_free_gb": settings()["min_free_gb"]}) is True
    return {"ok": ok, "say": say("disk_ok" if ok else "disk_low", gb=round(free_gb, 1))}


def work() -> dict:
    """2026-11-12 owner (from the VS standards: "silence is not acceptable for batch failures"): every agent whose latest run in the
    last chip health.settings work_hours failed or was cut short by a restart - until a later run of it finishes."""
    since = time.time() - float(settings()["work_hours"]) * 3600
    rows = agents.db().execute("SELECT agent, status FROM runs r WHERE made >= ? AND made = "
                               "(SELECT MAX(made) FROM runs WHERE agent = r.agent)", (since,)).fetchall()
    bad = sorted({r["agent"] for r in rows if r["status"] in {agents.settings()["run_states"][s] for s in settings()["alert_states"]}})
    words = engine.run("ui.agents") or {}
    names = ", ".join(str(words.get(f"name_{a}") or a) for a in bad)
    return {"ok": not bad, "say": say("work_bad", names=names) if bad else say("work_ok", n=len(rows))}


def ready() -> str:
    """GET /health (2026-11-12, from the VS standards: a health check tests what the portal depends on): "" when the data folder
    takes a write and every Postgres db answers, else the reason - the route then answers 503, so deploy and CC see it."""
    from core import sqlstore  # noqa: PLC0415
    try:
        store.DATA.mkdir(parents=True, exist_ok=True)
        k = settings()
        t = store.DATA / k["probe_file"]
        t.write_text(store.now(), encoding="utf-8")
        t.unlink(missing_ok=True)
    except OSError as e:
        return say("ready_disk", why=str(e)[:int(settings()["reason_chars"])])
    for db in sorted(sqlstore._SCHEMA):   # noqa: SLF001 - the dbs this portal registered
        if sqlstore.kind(db) == "postgres":
            try:
                sqlstore.one(db, settings()["db_probe"])
            except Exception as e:  # noqa: BLE001 - the driver's own reason is what the owner reads
                return say("ready_db", db=db, why=str(e)[:int(settings()["reason_chars"])])
    return ""


def cert_days(host: str) -> float:
    """Days until this host's https certificate ends (a refused or broken https raises - that is the problem)."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=float(settings()["timeout_s"])) as raw, ctx.wrap_socket(raw, server_hostname=host) as s:
        return (ssl.cert_time_to_seconds(s.getpeercert()["notAfter"]) - time.time()) / 86400


def certificates(hosts: list[str]) -> Callable[[], dict]:
    """The probe a portal attaches for its own hosts (its edition row names them)."""
    def run() -> dict:
        low = []
        for h in hosts:
            days = cert_days(h)
            if engine.run("health.cert_ok", {"days_left": days, "min_days": settings()["cert_min_days"]}) is not True:
                low.append(say("cert_host", host=h, days=max(0, int(days))))
        return {"ok": not low, "say": say("cert_ok", n=len(hosts)) if not low else say("cert_low", hosts=", ".join(low))}
    return run


def _age_days(at: str) -> float:
    try:
        then = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    return (datetime.now(timezone.utc) - (then if then.tzinfo else then.replace(tzinfo=timezone.utc))).total_seconds() / 86400


def drill(here: bool | None = None) -> dict:
    """2026-11-18 gap audit C1-13: tools/restore_drill.py (monthly cron) restores the newest backup into a temp folder, checks it
    and writes its result here. Red when the last drill failed or the last good one is older than chip health.settings
    drill_max_days. No record on a server (systemctl, as core server.py asks) = never drilled; on a PC there are no backups."""
    k = settings()
    rec = store.read(k["drill_record"], None)
    if not isinstance(rec, dict):
        here = bool(shutil.which("systemctl")) if here is None else here
        return {"ok": not here, "say": say("drill_never" if here else "drill_not_here")}
    at, days = str(rec.get("at") or ""), _age_days(str(rec.get("at") or ""))
    if not rec.get("ok"):
        return {"ok": False, "say": say("drill_failed", at=at, why=str(rec.get("why") or "")[:int(k["reason_chars"])])}
    if engine.run("health.recent_enough", {"age_days": days, "max_days": k["drill_max_days"]}) is not True:
        return {"ok": False, "say": say("drill_old", at=at, days=int(days), max=k["drill_max_days"])}
    return {"ok": True, "say": say("drill_ok", at=at, backup=rec.get("backup") or "-", checked=rec.get("checked") or 0)}


def _over(n: int, limit) -> bool:
    return engine.run("security.over_limit", {"count": n, "limit": limit}) is True


def _windows(rows: list, minutes) -> dict:
    """{who: the most rows any one window of `minutes` held} - rows are (who, iso time), oldest first (a sliding window)."""
    span = float(minutes) * 60
    seen: dict[str, list[float]] = {}
    best: dict[str, int] = {}
    for who, at in rows:
        t = datetime.fromisoformat(at).timestamp()
        q = [x for x in seen.get(who, []) if t - x < span] + [t]
        seen[who] = q
        best[who] = max(best.get(who, 0), len(q))
    return best


def security_events() -> dict:
    """2026-11-18 gap audit C1-19: the ledger's security events and request rows of the last look_back_hours (chip security.alerts)
    - a sign-in failure spike per network, bulk reads per person, a new MCP key, an owner/role change, the first account taken.
    Each is its own problem (key), so warn() rings the bell for it once and the bar keeps it until it leaves the look-back."""
    from core import ledger  # noqa: PLC0415 - ledger imports auth and access (the web layer)
    a = engine.run("security.alerts")
    since = datetime.fromtimestamp(time.time() - float(a["look_back_hours"]) * 3600, timezone.utc).isoformat(timespec="seconds")
    with ledger.db() as c:
        events = [dict(r) for r in c.execute("SELECT id, at, kind, by_id, target_id, ip FROM security WHERE at >= ? ORDER BY at, id", (since,))]
        reads = [(r[0], r[1]) for r in c.execute("SELECT user_id, at FROM activity WHERE at >= ? AND user_id IS NOT NULL AND method = ? "
                                                  "AND substr(path, 1, ?) = ? ORDER BY at, id", (since, a["reads_method"], len(a["reads_prefix"]), a["reads_prefix"]))]
    names = {u["id"]: u.get("name") or u.get("username") or u["id"] for u in store.users()}
    who = lambda uid: names.get(uid, uid) if uid else say("sec_shell")  # noqa: E731
    each = []
    fails = _windows([(e["ip"] or "-", e["at"]) for e in events if e["kind"] == a["signin_kind"]], a["signin_window_minutes"])
    each += [{"key": f"signin:{ip}", "say": say("sec_signin_fail", n=n, ip=ip, minutes=a["signin_window_minutes"])}
             for ip, n in sorted(fails.items()) if _over(n, a["signin_fail_limit"])]
    each += [{"key": f"reads:{uid}", "say": say("sec_reads", who=who(uid), n=n, minutes=a["reads_window_minutes"])}
             for uid, n in sorted(_windows(reads, a["reads_window_minutes"]).items()) if _over(n, a["reads_limit"])]
    each += [{"key": f"{e['kind']}:{e['id']}", "say": say(f"sec_{e['kind']}", who=who(e["by_id"]), target=who(e["target_id"]), at=e["at"])}
             for e in events if e["kind"] in a["event_kinds"]]
    return {"ok": not each, "each": each, "say": say("security_ok", n=len(events), hours=a["look_back_hours"])}


def check(_args: dict | None = None, _ctx: dict | None = None) -> dict:
    """Every probe once, each in its own words. One that raises says why - the check itself never fails."""
    rows = []
    for pid, fn in sorted(PROBES.items()):
        name = engine.run("health.messages").get(f"probe_{pid}") or pid
        try:
            got = fn() or {}
            each = [x for x in got.get("each") or [] if x.get("key")]
            rows += [{"id": f"{pid}:{x['key']}", "name": name, "ok": False, "say": str(x.get("say") or "")} for x in each]
            if not each:
                rows.append({"id": pid, "name": name, "ok": bool(got.get("ok")), "say": str(got.get("say") or "")})
        except Exception as e:  # noqa: BLE001 - the probe's own reason is the problem the owner reads
            rows.append({"id": pid, "name": name, "ok": False, "say": say("probe_failed", why=str(getattr(e, "detail", "") or e)[:200])})
    return {"checked": len(rows), "problems": [r for r in rows if not r["ok"]], "fine": [r for r in rows if r["ok"]], "at": store.now()}


def warn(args: dict, ctx: dict) -> dict:
    """The bar becomes this answer. A dry run only says what the bar would show."""
    problems = list((args.get("found") or {}).get("problems") or [])
    old = store.read(BAR, {}) or {}
    new_ids = sorted({p["id"] for p in problems} - set(old.get("told") or []))
    if ctx.get("preview"):
        return {"would_show": len(problems), "new": new_ids}
    store.write(BAR, {"at": store.now(), "problems": problems, "told": sorted(p["id"] for p in problems)})
    if new_ids:
        names = ", ".join(p["name"] for p in problems if p["id"] in new_ids)
        for uid in agents._owners():   # noqa: SLF001 - the one list of owners the runtime keeps
            bell.push(uid, say("bell_new", n=len(new_ids), names=names), "#/agents")
    return {"shown": len(problems), "new": new_ids}


def bootstrap_extra(request: Request, u: dict | None) -> dict:
    """Owners see the bar on every page; everyone else never does."""
    if not u or engine.run("people.is_owner", {"role": u.get("role") or ""}) is not True:
        return {}
    bar = store.read(BAR, {}) or {}
    problems = list(bar.get("problems") or [])
    # 2026-11-18 week class 34 (CodyFy G-65 / G-47: a silent machine's ticks read as live): a held answer is only as good as its
    # age. The bar keeps the LAST check's answer; when that check stopped running, an empty bar looked healthy for ever.
    hours = store.seconds_since(bar["at"]) / 3600 if bar.get("at") else 0
    if hours > float(settings()["stale_hours"]):
        problems.append({"id": "stale", "name": say("probe_stale"), "ok": False, "say": say("stale_say", days=int(hours // 24))})
    return {"health": {"at": bar.get("at", ""), "problems": problems}} if problems else {}


probe("disk", disk)
probe("work", work)
probe("drill", drill)
probe("security", security_events)
agents.action("health.check", check)
agents.action("health.warn", warn)


if __name__ == "__main__":  # ponytail: a probe that raises is a problem, the bar is replaced, the bell rings once per new problem
    import tempfile
    from pathlib import Path
    store.DATA = Path(tempfile.mkdtemp())
    rang = []
    bell.push = lambda uid, text, href="": rang.append(text)
    agents._owners = lambda: ["o"]   # noqa: SLF001
    PROBES.clear()
    state = {"voice": True}
    probe("voice", lambda: {"ok": state["voice"], "say": "voice"})
    probe("broken", lambda: (_ for _ in ()).throw(OSError("no route")))
    got = check()
    assert got["checked"] == 2 and [p["id"] for p in got["problems"]] == ["broken"] and "no route" in got["problems"][0]["say"]
    assert warn({"found": got}, {"preview": True}) == {"would_show": 1, "new": ["broken"]} and not store.read(BAR, {}), "a dry run writes nothing"
    warn({"found": got}, {"preview": False})
    assert len(rang) == 1 and len(store.read(BAR, {})["problems"]) == 1
    warn({"found": check()}, {"preview": False})
    assert len(rang) == 1, "the same problem the next day: the bar stays, the bell does not ring again"
    state["voice"] = False
    warn({"found": check()}, {"preview": False})
    assert len(rang) == 2 and len(store.read(BAR, {})["problems"]) == 2, "a new problem rings once"
    state["voice"] = True
    PROBES.pop("broken")
    warn({"found": check()}, {"preview": False})
    assert store.read(BAR, {})["problems"] == [] and len(rang) == 2, "fixed: the bar clears by itself, nothing piles up"
    assert bootstrap_extra(None, {"role": "owner"}) == {}, "an empty bar is not shown"
    store.write(BAR, store.read(BAR, {}) | {"at": "2026-01-01T00:00:00+00:00"})    # week class 34: the check stopped running
    _old = bootstrap_extra(None, {"role": "owner"}).get("health", {}).get("problems") or []  # type: ignore[arg-type]  # no request in a self-test
    assert [p["id"] for p in _old] == ["stale"] and "days" in _old[0]["say"], "an empty bar from a check that stopped running reads as healthy (no stale row)"
    assert bootstrap_extra(None, {"role": "member"}) == {}, "the stale row is for owners only"  # type: ignore[arg-type]
    assert engine.run("health.disk_ok", {"free_gb": 1, "min_free_gb": 5}) is False and disk()["say"]
    # 2026-11-12: an agent run cut short by a restart is stopped, and the warning bar names it until a later run finishes
    c = agents.db()
    now, rs = time.time(), agents.settings()["run_states"]
    c.execute("INSERT INTO runs(ref, agent, phase, status, by_id, made) VALUES('r1', 'ag_x', 'run', ?, '', ?)", (rs["live"], now - 60))
    c.commit()
    agents._RECOVERED.clear()   # noqa: SLF001 - as at the next start
    agents._LOCAL.c = None      # noqa: SLF001
    c = agents.db()
    row = c.execute("SELECT status, why FROM runs WHERE ref='r1'").fetchone()
    assert row["status"] == rs["cut_short"] and row["why"], "a run cut short by a restart stayed 'running'"
    assert not work()["ok"] and "ag_x" in work()["say"], "a cut-short run did not show on the bar"
    c.execute("INSERT INTO runs(ref, agent, phase, status, by_id, made) VALUES('r2', 'ag_x', 'run', ?, '', ?)", (rs["done"], now))
    c.commit()
    assert work()["ok"], "a later run that finished did not clear the bar"
    c.execute("INSERT INTO runs(ref, agent, phase, status, by_id, made) VALUES('r3', 'ag_y', 'run', ?, '', ?)", (rs["failed"], now - 999999))
    c.commit()
    assert work()["ok"], "a failure older than work_hours still shows"
    assert ready() == ""
    real, store.DATA = store.DATA, Path(tempfile.mkdtemp()) / "file"
    store.DATA.parent.mkdir(exist_ok=True)
    store.DATA.write_text("x")          # a file where the data folder should be: no write possible
    assert ready().startswith("not ready"), "a data folder that cannot be written passed the health check"
    store.DATA = real
    # 2026-11-18 gap audit C1-13: the restore drill's record turns the bar red when old or failed, and rings once
    from datetime import timedelta  # noqa: PLC0415
    k, iso = settings(), lambda days: (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
    assert not drill(here=True)["ok"] and "No restore drill" in drill(here=True)["say"], "a server that never drilled looked fine"
    assert drill(here=False)["ok"], "a PC with no backups was told to drill"
    store.write(k["drill_record"], {"at": iso(1), "ok": True, "backup": "hour-02.tar.gz", "checked": 9})
    assert drill()["ok"] and "hour-02.tar.gz" in drill()["say"]
    store.write(k["drill_record"], {"at": iso(k["drill_max_days"] + 5), "ok": True, "backup": "day-Mon.tar.gz", "checked": 9})
    old = drill()
    assert not old["ok"] and f"{k['drill_max_days'] + 5} days" in old["say"], ("an old drill did not warn", old)
    PROBES.clear()
    probe("drill", drill)
    store.write(BAR, {})
    rang.clear()
    store.write(k["drill_record"], {"at": iso(0), "ok": False, "why": "bootstrap answered 500"})
    warn({"found": check()}, {"preview": False})
    warn({"found": check()}, {"preview": False})
    assert len(rang) == 1 and "bootstrap answered 500" in store.read(BAR, {})["problems"][0]["say"], ("a failed drill: one bell", rang)
    # 2026-11-18 gap audit C1-19: synthetic security events - each alert rings exactly once, a quiet network/person never
    from core import ledger  # noqa: PLC0415
    a = engine.run("security.alerts")
    for _ in range(int(a["signin_fail_limit"])):
        ledger.security(a["signin_kind"], "", "", "203.0.113.9")
    for _ in range(int(a["signin_fail_limit"]) - 1):
        ledger.security(a["signin_kind"], "", "", "198.51.100.9")
    for i in range(int(a["reads_limit"])):
        ledger._put("INSERT INTO activity(at,user_id,method,path,status) VALUES(?,?,?,?,?)",   # noqa: SLF001
                    (ledger.now(), "u_bulk", a["reads_method"], f"{a['reads_prefix']}x/{i}", 200))
    for i in range(int(a["reads_limit"]) - 1):
        ledger._put("INSERT INTO activity(at,user_id,method,path,status) VALUES(?,?,?,?,?)",   # noqa: SLF001
                    (ledger.now(), "u_calm", a["reads_method"], f"{a['reads_prefix']}x/{i}", 200))
    for kind in a["event_kinds"]:
        ledger.security(kind, "o", "m")
    ledger.flush()
    PROBES.clear()
    probe("security", security_events)
    rang.clear()
    store.write(BAR, {})
    warn({"found": check()}, {"preview": False})
    ids = sorted(p["id"] for p in store.read(BAR, {})["problems"])
    want = {"security:signin:203.0.113.0/24", "security:reads:u_bulk"} | {f"security:{kd}:" for kd in a["event_kinds"]}
    assert len(ids) == 2 + len(a["event_kinds"]) and all(any(i.startswith(w) for i in ids) for w in want), ("security alerts", ids)
    assert len(rang) == 1 and str(len(ids)) in rang[0], ("one bell naming every new alert", rang)
    warn({"found": check()}, {"preview": False})
    assert len(rang) == 1, "the same security alerts rang again at the next check"
    ledger.security(a["event_kinds"][0], "o", "m2")
    ledger.flush()
    warn({"found": check()}, {"preview": False})
    assert len(rang) == 2 and len(store.read(BAR, {})["problems"]) == len(ids) + 1, "a new security event did not ring once"
    print("health self-check OK")
