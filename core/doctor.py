"""Error Doctor - 2026-10-20 owner: "an agent which can identify error and self fix almost all of them, and if it can't comes to us
and tells us what needs to be done ... one Error module across the portal, the same for all FY series".

ONE module, the same in every portal (core/):
  catch     every unhandled server error (middleware `catch`) and every screen error (core/static/ui.js reports to
            POST /api/core/doctor/report). Kept BODY-FREE: where (the route with ids blanked), the error type, our own code line,
            the message with e-mails / numbers / long ids masked - one row per fingerprint, counted, never a flood.
  decide    chip doctor.settings `rules`: the first row whose pattern matches says who acts -
              auto    a generic op this portal registered in FIXES fixes it (e.g. jobs_recover); nobody is bothered
              claude  a code fault: the portal's own Fix-request hook (TO_CLAUDE - CodyFy files it in its Code Editor);
                      a portal with no hook tells the owner instead
              owner   only a person can (a key, credit, a sign-in): one note with the steps
  tell      a NEW error is filed ONCE into Reported issues (the screen every portal has) with what was done or what to do, and
            the owner's bell rings once; a repeat only counts.
Every word: chip doctor.messages. Every rule, limit and op name: chip doctor.settings."""
from __future__ import annotations

import hashlib
import re
import threading
import traceback
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from core import bell, engine, limits, ops, store

router = APIRouter()
FILE = "doctor"
LOCK = threading.Lock()
FIXES: dict[str, Callable[[dict], bool]] = {}      # op name (chip rules `op`) -> fixes it; True = fixed
TO_CLAUDE: list[Callable[[dict, dict], str]] = []  # a portal that builds its own fixes: fn(row, rule) -> its request ref ('' = not filed)
ROOT = Path(__file__).resolve().parent.parent
SENDER = "doctor"      # 2026-10-21: the Doctor's notes are its own (the owner ANSWERS them; nobody may answer a note they sent)


def K() -> dict:
    return engine.run("doctor.settings")


def say(key: str, **v) -> str:
    return ops.template(engine.run("doctor.messages")[key], v)


def mask(text: str) -> str:
    """Never a person's data in the ledger: e-mails, long numbers and long ids become placeholders."""
    t = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<email>", str(text or ""))
    t = re.sub(r"\b[0-9a-f]{16,}\b", "<id>", t, flags=re.I)
    return re.sub(r"\d{4,}", "<n>", t)


def route_of(path: str) -> str:
    """/api/requests/86/to-claude -> /api/requests/{id}/to-claude (the place, never the record)."""
    return "/".join("{id}" if re.fullmatch(r"\d+|[0-9a-f]{8,}", p, re.I) else p for p in str(path or "").split("/"))[:200]


def our_line(exc: BaseException) -> str:
    """The last frame in this portal's own code (never a library's): file:line."""
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if ".venv" not in f.filename and "site-packages" not in f.filename]
    f = frames[-1] if frames else None
    if not f:
        return ""
    try:
        name = Path(f.filename).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        name = Path(f.filename).name
    return f"{name}:{f.lineno}"


def record(source: str, kind: str, message: str, where: str, line: str, extra: str = "") -> dict:
    """One error seen: counted under its fingerprint; a NEW one is treated (in the background, never slowing the page). `extra` (a
    picture's path) is kept with a new row but is NOT part of the fingerprint - 2026-10-21: a walk picture named by its run made the
    same finding new every night (REQ-0027 and REQ-0028 for one fault)."""
    k = K()
    msg = mask(message)[: int(k["text_chars"])]
    fp = hashlib.sha1(f"{source}|{kind}|{where}|{line}|{re.sub(r'<[a-z]+>', '', msg)[:120]}".encode()).hexdigest()[:12]
    with LOCK:
        rows = store.read(FILE, {})
        r = rows.get(fp)
        new = r is None
        if new:
            if len(rows) >= int(k["max_rows"]):             # the oldest goes - the ledger never grows without end
                rows.pop(min(rows, key=lambda x: rows[x]["last_at"]))
            r = {"fp": fp, "source": source, "kind": kind[:80], "message": (msg + (" " + extra[:200] if extra else "")).strip(), "where": where[:200], "line": line[:200],
                 "count": 0, "first_at": store.now(), "status": "new", "rule": "", "ref": ""}
        r["count"] += 1
        r["last_at"] = store.now()
        rows[fp] = r
        store.write(FILE, rows)
    if new:
        threading.Thread(target=treat, args=(fp,), daemon=True).start()
    return r


def rule_for(r: dict) -> dict:
    text = f"{r['kind']}: {r['message']} @ {r['where']} {r['line']}"
    return next((x for x in K()["rules"] if re.search(x["pattern"], text)), {"id": "", "who": "owner", "say": ""})


def treat(fp: str) -> dict:
    """Decide and act once: fix it here, send it to Claude, or tell the owner what to do - then one note in Reported issues."""
    with LOCK:
        r = dict(store.read(FILE, {}).get(fp) or {})
    if not r:
        return {}
    rule, status, ref = rule_for(r), "owner", ""
    if rule["who"] == "ignore":          # noise (a lost connection): counted, nobody told
        with LOCK:
            rows = store.read(FILE, {})
            if fp in rows:
                rows[fp].update(status="ignored", rule=rule.get("id", ""))
                store.write(FILE, rows)
        return r
    if rule["who"] == "auto" and rule.get("op") in FIXES:
        try:
            status = "fixed" if FIXES[rule["op"]](r) else "owner"
        except Exception:   # noqa: BLE001 - a fix that fails is told, never a second error
            status = "owner"
    if status != "fixed" and rule["who"] in ("auto", "claude") and TO_CLAUDE:
        try:
            ref = TO_CLAUDE[0](r, rule)
        except Exception:   # noqa: BLE001
            ref = ""
        status = "claude" if ref else "owner"
    r = r | {"status": status, "rule": rule.get("id", ""), "ref": ref}
    _tell(r, rule)                       # told first: once the row says it is handled, its note is there
    with LOCK:
        rows = store.read(FILE, {})
        if fp in rows:
            rows[fp].update(status=status, rule=r["rule"], ref=ref)
            store.write(FILE, rows)
            r = rows[fp]
    return r


def _owner() -> dict | None:
    return next((u for u in store.users() if u.get("role") == "owner"), None)


def _tell(r: dict, rule: dict) -> None:
    """One note in Reported issues (the screen every portal has), and the owner's bell once."""
    from core import issues  # noqa: PLC0415 - issues imports more of core; read late
    o = _owner()
    if not o:
        return
    title = say("title", kind=r["kind"], where=r["where"] or r["source"])
    text = say(f"status_{r['status']}", what=rule.get("say") or say("unknown"), ref=r.get("ref", ""), fp=r["fp"]) + "\n\n" + \
        say("facts", source=r["source"], kind=r["kind"], message=r["message"], where=r["where"], line=r["line"] or "-", first=r["first_at"])
    s = issues.settings("issue")
    with store._LOCK:   # noqa: SLF001 - the framework's own write lock, as issues.file uses it
        rows = issues._rows("issue", "")   # noqa: SLF001
        note = dict(s["new_row"]) | {"id": store.new_id(), "by": SENDER, "name": say("who"), "email": "", "title": limits.clip(title, 200),
                                     "text": limits.clip(text, int(s["text_max"])), "place": {}, "surface": "doctor", "context": r["fp"],
                                     "about": "", "link": "", "at": store.now(), "updated": store.now(), "answered_by": ""}
        if r["status"] == "fixed":
            note["status"] = K()["fixed_status"]
        store.write(issues._name("issue", ""), [*rows, note])   # noqa: SLF001
    bell.push(o["id"], say(f"bell_{r['status']}", title=title), K()["bell_link"])


def heal_notes() -> int:
    """Notes filed before 2026-10-21 carry the owner as their sender, and nobody may answer their own note - so no Error Doctor note
    could ever be resolved. Once, at start (inside the portal, under its lock): those notes are the Doctor's. Returns how many."""
    from core import issues  # noqa: PLC0415
    with store._LOCK:   # noqa: SLF001
        rows = issues._rows("issue", "")   # noqa: SLF001
        bad = [r for r in rows if r.get("surface") == "doctor" and r.get("by") != SENDER]
        for r in bad:
            r["by"] = SENDER
        if bad:
            store.write(issues._name("issue", ""), rows)   # noqa: SLF001
    return len(bad)


def jobs_recover(_r: dict) -> bool:
    """Op `jobs_recover`: a job left running by a stop is stopped cleanly (core/jobs.py)."""
    from core import jobs  # noqa: PLC0415
    jobs.recover()
    return True


FIXES["jobs_recover"] = jobs_recover


async def catch(request: Request, call_next):
    """Every unhandled server error: recorded (body-free), and the person sees plain words with its reference - never a stack."""
    try:
        return await call_next(request)
    except Exception as e:   # noqa: BLE001 - the one place every unexpected error is caught
        r = record("server", type(e).__name__, str(e), route_of(request.url.path), our_line(e))
        return JSONResponse({"detail": say("server_error", fp=r["fp"])}, status_code=500)


@router.post("/api/core/doctor/report")
def api_report(request: Request, body: dict = Body(default={})):
    """A screen error (core/static/ui.js) - anyone's browser may report; a few per minute per address, the rest dropped."""
    who = request.client.host if request.client else ""
    if not limits.allow(K()["report_rate"], f"doctor:{who}"):
        return {"ok": False}
    src = re.sub(r"^https?://[^/]+", "", str(body.get("source") or ""))[:200]
    record("screen", str(body.get("kind") or "Error")[:80], str(body.get("message") or ""), route_of(str(body.get("screen") or ""))[:200],
           f"{src}:{int(body.get('line') or 0)}")
    return {"ok": True}


if __name__ == "__main__":   # ponytail: the pure parts
    assert mask("a@b.co failed 1234567 at 0123456789abcdef0") == "<email> failed <n> at <id>", mask("a@b.co failed 1234567 at 0123456789abcdef0")
    assert route_of("/api/requests/86/to-claude") == "/api/requests/{id}/to-claude"
    row = {"kind": "", "message": "", "where": "/api/x", "line": "app.py:1"}
    assert rule_for(row | {"kind": "TypeError", "message": "Failed to fetch"})["who"] == "ignore", "noise is told"
    assert rule_for(row | {"kind": "HTTPError", "message": "invalid x-api-key"})["who"] == "owner", "a key problem is not the owner's"
    assert rule_for(row | {"kind": "KeyError", "message": "'name'"})["who"] == "claude", "a code fault is not sent to Claude"
    assert all(say(k) is not None for k in ("who", "unknown", "server_error"))
    print("doctor self-check OK")
