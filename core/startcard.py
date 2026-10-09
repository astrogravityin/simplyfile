"""Start here - the first steps for someone who has just signed up and has no idea how to proceed (2026-10-09 owner).

A short numbered list on the landing screen (and on the domain's first work screen): each step links to its screen and is
ticked when it is done. Done is worked out HERE from real facts, never by the browser:
    firm / approved   the person's firm exists / is approved (firms.py)
    team              people in the firm;  records  the firm's records (clients._mine)
    stage_<id>        records with a period at that stage (the contract's years: {<period>: {stage}})
    area_<id>         History lines in that area (chip changes.watch ids) over the person's records and their firm
    seen_<screen>     times the person opened that screen (the page-view ledger, core/ledger.py)
    call              a step's `call` pattern over the person's own successful requests ("POST /api/watch")
    + the domain's own, from clients.start_facts(u) when the domain has one.
Which steps, their words, links and the fact each waits for are the domain's chip start.steps (a seam); whether a fact is
enough is chip start.done; the card's words are ui.start; the knobs start.settings. A step that needs a grant the person's
role lacks (an individual's desk has no "team") is left out, and so is a step whose `kinds` name other kinds of firm. A tick, once earned, stays; Hide is kept per person here (the
store), so it follows them to any browser; the name menu's Start here and Guide me bring it back.
"""
from __future__ import annotations

import re
import threading

from fastapi import APIRouter, Body, Depends

from core import auth, engine, ledger, store

router = APIRouter()
FILE = "start_card"
_LOCK = threading.Lock()


def settings() -> dict:
    return engine.run("start.settings")


def steps_chip() -> dict:
    return engine.run("start.steps") if "start.steps" in engine.chips() else {"rows": [], "screens": []}


def _who(u: dict) -> dict:
    return (store.read(FILE, {}) or {}).get(u["id"]) or {}


def _put(u: dict, **fields) -> dict:
    with _LOCK:
        allv = store.read(FILE, {}) or {}
        allv[u["id"]] = (allv.get(u["id"]) or {}) | fields
        store.write(FILE, allv)
        return allv[u["id"]]


def _shows_for(u: dict | None) -> bool:
    import firms  # noqa: PLC0415 - the portal's own tenant module
    return bool(u) and bool(steps_chip()["rows"]) and (bool(settings()["owner_sees"]) or not firms.is_owner(u))


def facts(u: dict) -> dict:
    """What the person has really done, counted - the steps' done tests read only these."""
    import clients  # noqa: PLC0415 - the domain contract
    import firms  # noqa: PLC0415
    k = settings()
    f = firms.firm_of(u)
    out: dict = {"firm": int(bool(f)), "approved": int(bool(f) and f.get("state") == firms.settings()["working_state"]),
                 "team": len(firms.team(u)) if f else 0}
    mine = [c for c in clients._mine(u) if not c.get("archived_at")] if f else []  # noqa: SLF001 - the domain contract
    out["records"] = len(mine)
    for c in mine:                                             # the contract's years: {<period>: {stage}} - a record per stage reached
        for st in {(y or {}).get("stage") for y in (c.get("years") or {}).values() if isinstance(y, dict)} - {None, ""}:
            out[f"stage_{st}"] = out.get(f"stage_{st}", 0) + 1
    scopes = [f"client-{c['id']}" for c in mine[: int(k["scan_most"])]] + ([f"firm-{f['id']}"] if f else [])
    for scope in scopes:
        for e in store.read(f"sf_changes/{scope}", []):          # changelog.py's History, one file per scope
            if e.get("old") != e.get("new"):
                out[f"area_{e.get('area')}"] = out.get(f"area_{e.get('area')}", 0) + 1
    try:
        ledger.flush()
        with ledger.db() as c:
            for r in c.execute("SELECT path, COUNT(*) n FROM views WHERE user_id = ? GROUP BY path", (u["id"],)).fetchall():
                out[f"seen_{str(r['path']).lstrip('#/').split('?')[0]}"] = int(r["n"])
    except Exception:  # noqa: BLE001 - a locked or missing ledger leaves the seen_* facts at 0, never breaks the card
        pass
    try:                                                       # what the person really asked the server to do (the activity ledger)
        with ledger.db() as c:
            calls = [f"{r['method']} {r['path']}" for r in c.execute(
                "SELECT method, path FROM activity WHERE user_id = ? AND status < 400 ORDER BY id DESC LIMIT ?", (u["id"], int(k["calls_most"]))).fetchall()]
    except Exception:  # noqa: BLE001
        calls = []
    out["_calls"] = calls
    extra = getattr(clients, "start_facts", None)
    if extra:
        out |= {str(a): b for a, b in (extra(u) or {}).items()}
    return out


def card(u: dict, screen: str = "") -> dict:
    """{show, steps: [{n, id, label, say, href, done}], done, total, hidden} for this person on this screen."""
    import firms  # noqa: PLC0415
    s, me = steps_chip(), _who(u)
    got = facts(u)
    f = firms.firm_of(u)
    grants = set(firms.role_of(u.get("firm_role", ""))["grants"]) if f else None
    kept, rows = set(me.get("done") or []), []
    for r in s["rows"]:
        if grants is not None and r.get("grant") and r["grant"] not in grants:
            continue                                           # a step this person's role cannot take (a desk of one: no team)
        if r.get("kinds") and (not f or f.get("kind") not in r["kinds"]):
            continue                                           # a step for one kind of firm only (an individual's own return)
        names = r["fact"] if isinstance(r.get("fact"), list) else [r.get("fact", "")] if r.get("fact") else []
        value = sum(int(got.get(n) or 0) for n in names)
        if r.get("call"):                                      # a request the step waits for, e.g. "^POST /api/watch$"
            value += sum(1 for c in got["_calls"] if re.search(r["call"], c))
        done = r["id"] in kept or engine.run("start.done", {"value": value, "at_least": r.get("at_least", 1)}) is True
        rows.append({"n": len(rows) + 1, "id": r["id"], "label": r["label"], "say": r.get("say", ""), "href": r.get("href", ""), "done": done})
    new = {x["id"] for x in rows if x["done"]} - kept
    if new and settings()["ticks_stay"]:
        _put(u, done=sorted(kept | new))
    n = sum(x["done"] for x in rows)
    hidden = bool(me.get("hidden"))
    here = not screen or screen in (s.get("screens") or [])
    return {"show": _shows_for(u) and here and not hidden and n < len(rows), "steps": rows, "done": n, "total": len(rows),
            "hidden": hidden, "all_done": bool(rows) and n == len(rows)}


@router.get("/api/start")
def api_card(screen: str = "", u: dict = Depends(auth.signed_in)):
    return card(u, screen)


@router.post("/api/start/hide")
def api_hide(_: dict = Body(default={}), u: dict = Depends(auth.signed_in)):
    _put(u, hidden=True)
    return {"ok": True, "message": engine.say("ui.start", "hidden_toast")}


@router.post("/api/start/show")
def api_show(_: dict = Body(default={}), u: dict = Depends(auth.signed_in)):
    _put(u, hidden=False)
    return card(u)


def bootstrap_extra(_request, u: dict | None) -> dict:
    """Where the card is drawn and the name menu's word for it - only for someone it is for."""
    if not _shows_for(u):
        return {}
    return {"start_card": {"screens": steps_chip().get("screens") or [], "menu": engine.say("ui.start", "menu")}}


def install(app) -> None:
    """app.py: `startcard.install(app)` once the portal's chips are registered."""
    app.include_router(router)
    auth.BOOTSTRAP_EXTRAS.append(bootstrap_extra)


if __name__ == "__main__":   # ponytail: the done test and the grant filter, on chip defaults
    assert engine.run("start.done", {"value": 0, "at_least": 1}) is False
    assert engine.run("start.done", {"value": 2, "at_least": 1}) is True
    print("startcard self-check OK")
