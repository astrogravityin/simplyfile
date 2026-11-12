"""Agents - the ONE generic agent runtime for every portal on this framework (2026-10-23 owner: "go with your pick" -
SteadyMove gets agents the AstroStage way: backend/services/agent_runtime.py). No per-agent code lives here or anywhere.

An agent = a recipe chip  agents.recipe.<id>  (inputs -> steps -> outputs, triggers). Each step names an ACTION a module
attached once:   agents.action("health.check", fn)     fn(args, ctx) -> dict      (ctx: phase, preview, by, run)
and chip agents.actions says what that action is: its words and its side effect (read | write | external | paid).

For every step chip agents.step_when (does its `when` hold for these inputs) and chip agents.step_gate (run / preview /
skip for this phase and side effect) decide - the AstroStage rules, unchanged:
  1. Dry run (phase "preview"): reads run for real, writes are only previewed (the action gets preview=True), paid skipped.
  2. Approve (phase "run"): the recipe runs again for real.
A trigger (a schedule in chip agents.settings cadences, or an event a module emits with agents.emit) starts a dry run;
chip agents.trigger_gate then says: tell, approve by itself (every write ticked trusted), wait for review, or tell an error.

  agents.sqlite3   runs(ref, agent, phase, status, by_id, trigger, inputs, steps, made, done, why)
                   trig(agent, key, on_state, last_at)   - the owner's on/off and when each schedule last fired

Bindings in a step's args: "@in.<key>" = an input, "@steps.<id>" / "@steps.<id>.<key>" = an earlier step's output.
Every number is chip agents.settings; every sentence chip agents.messages; the page's words ui.agents.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import APIRouter, Body, Depends, HTTPException

from core import access, bell, engine, store

router = APIRouter()
PREFIX = "agents.recipe."
ACTIONS: dict[str, Callable[[dict, dict], dict]] = {}
_LOCAL = threading.local()
_RECOVERED: set[str] = set()     # data files whose cut-short runs were marked stopped in this process
_WRITE = threading.Lock()
_STARTED: list = []

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(ref TEXT PRIMARY KEY, agent TEXT NOT NULL, phase TEXT NOT NULL, status TEXT NOT NULL, by_id TEXT NOT NULL,
  trigger TEXT NOT NULL DEFAULT '', inputs TEXT NOT NULL DEFAULT '{}', steps TEXT NOT NULL DEFAULT '[]', made REAL NOT NULL,
  done REAL NOT NULL DEFAULT 0, why TEXT NOT NULL DEFAULT '') WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS runs_agent ON runs(agent, made);
CREATE TABLE IF NOT EXISTS trig(agent TEXT NOT NULL, key TEXT NOT NULL, on_state INTEGER, last_at REAL NOT NULL DEFAULT 0,
  PRIMARY KEY(agent, key)) WITHOUT ROWID;
"""


def settings() -> dict:
    return engine.run("agents.settings")


def say(key: str, **values) -> str:
    return engine.say("agents.messages", key, **values)


def db() -> sqlite3.Connection:
    path = str(store.DATA / settings()["db"])
    c = getattr(_LOCAL, "c", None)
    if c is None or getattr(_LOCAL, "path", "") != path:
        store.DATA.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
        _LOCAL.c, _LOCAL.path = c, path
        if path not in _RECOVERED:   # 2026-11-12: a run the server stopped mid-way is stopped, never "running" for ever
            _RECOVERED.add(path)
            with _WRITE, c:
                st = settings()["run_states"]
                c.execute("UPDATE runs SET status=?, done=?, why=? WHERE status=?", (st["cut_short"], time.time(), say("stopped_restart"), st["live"]))
    return c


def action(action_id: str, fn: Callable[[dict, dict], dict]) -> None:
    """A module attaches one action. Its words and side effect are chip agents.actions (the page shows them)."""
    ACTIONS[action_id] = fn


# --- recipes and the catalog ------------------------------------------------------------------------------------------

def catalog() -> dict[str, dict]:
    return {a["id"]: a for a in engine.run("agents.actions")["actions"]}


def recipes() -> dict[str, dict]:
    """Every shipped agent of this portal: the recipe chips (core's and the portal's own)."""
    out = {}
    for cid in sorted(engine.chips()):
        if cid.startswith(PREFIX):
            r = (engine.run(cid) or {}).get("recipe") or {}
            if r.get("id"):
                out[r["id"]] = r
    return dict(sorted(out.items(), key=lambda kv: (kv[1].get("order", 999), kv[0])))   # the recipe's own order, then its id


def recipe(agent_id: str) -> dict:
    r = recipes().get(agent_id)
    if not r:
        raise HTTPException(404, say("no_agent"))
    return r


def problems(r: dict) -> list[str]:
    """What stops a recipe running here: an action no module attached, or one chip agents.actions does not describe."""
    cat = catalog()
    return [say("no_action", action=s.get("action")) for s in r.get("steps") or []
            if s.get("action") not in ACTIONS or s.get("action") not in cat]


def _bind(node: Any, ins: dict, outs: dict) -> Any:
    if isinstance(node, dict):
        return {k: _bind(v, ins, outs) for k, v in node.items()}
    if isinstance(node, list):
        return [_bind(v, ins, outs) for v in node]
    if isinstance(node, str) and node.startswith("@in."):
        return ins.get(node[4:])
    if isinstance(node, str) and node.startswith("@steps."):
        sid, _, key = node[7:].partition(".")
        got = outs.get(sid) or {}
        return got.get(key) if key else got
    return node


def inputs_of(r: dict, given: dict | None) -> dict:
    """The recipe's inputs: each one's default, overridden by what was given (unknown keys dropped)."""
    given = given or {}
    return {i["key"]: given.get(i["key"], i.get("default")) for i in r.get("inputs") or []}


# --- one run ----------------------------------------------------------------------------------------------------------

def _short(out: Any) -> Any:
    """What a run keeps of a step's answer: no "_" server-only keys, no long text (chip agents.settings keep_chars)."""
    most = int(settings()["keep_chars"])
    if isinstance(out, dict):
        return {k: _short(v) for k, v in out.items() if not str(k).startswith("_")}
    if isinstance(out, list):
        return [_short(v) for v in out[: int(settings()["keep_rows"])]]
    if isinstance(out, str):
        return out[:most]
    return out


def execute(agent_id: str, phase: str, by_id: str, given: dict | None = None, trigger: str = "") -> dict:
    """Run a recipe now, in this thread: every step through chips step_when + step_gate, kept as one row of runs."""
    r, cat = recipe(agent_id), catalog()
    bad = problems(r)
    if bad:
        raise HTTPException(400, say("cannot_run", why=" ".join(bad)))
    ins = inputs_of(r, given)
    ref = secrets.token_urlsafe(9)
    c = db()
    with _WRITE, c:
        c.execute("INSERT INTO runs(ref, agent, phase, status, by_id, trigger, inputs, made) VALUES(?,?,?,?,?,?,?,?)",
                  (ref, agent_id, phase, settings()["run_states"]["live"], by_id, trigger, json.dumps(ins, default=str), time.time()))
    outs: dict = {}
    steps: list = []
    why = ""
    for s in r.get("steps") or []:
        a = cat[s["action"]]
        when_ok = engine.run("agents.step_when", {"facts": ins, "when": s["when"]}) is True if s.get("when") else True
        gate = engine.run("agents.step_gate", {"facts": {"when_ok": when_ok, "side_effect": a["side_effect"], "phase": phase,
                                                          "explicit": False}})
        row = {"id": s["id"], "action": s["action"], "gate": gate, "side_effect": a["side_effect"],
               "trusted": bool(s.get("trusted")), "out": {}, "error": ""}
        if gate != "skip":
            try:
                outs[s["id"]] = ACTIONS[s["action"]](_bind(s.get("args") or {}, ins, outs),
                                                     {"phase": phase, "preview": gate == "preview", "by": by_id, "run": ref}) or {}
                row["out"] = _short(outs[s["id"]])
            except Exception as e:  # noqa: BLE001 - the step's own reason is what the owner reads
                row["error"] = why = str(getattr(e, "detail", "") or e)[:300]
        steps.append(row)
        if row["error"]:
            break
    status = settings()["run_states"]["failed" if why else "done"]
    with _WRITE, c:
        c.execute("UPDATE runs SET status=?, steps=?, done=?, why=? WHERE ref=?",
                  (status, json.dumps(steps, default=str, ensure_ascii=False), time.time(), why, ref))
    return view(c.execute("SELECT * FROM runs WHERE ref=?", (ref,)).fetchone())


def view(row) -> dict:
    d = dict(row)
    d["inputs"], d["steps"] = json.loads(d["inputs"] or "{}"), json.loads(d["steps"] or "[]")
    d["waiting"] = d["phase"] == "preview" and d["status"] == settings()["run_states"]["done"] and any(
        s["gate"] == "preview" for s in d["steps"]) and not d.get("approved")
    return d


def runs(agent_id: str = "", most: int = 0) -> list[dict]:
    most = most or int(settings()["history_rows"])
    q = "SELECT * FROM runs " + ("WHERE agent=? " if agent_id else "") + "ORDER BY made DESC LIMIT ?"
    return [view(r) for r in db().execute(q, ((agent_id,) if agent_id else ()) + (most,))]


def _owners() -> list[str]:
    return [u["id"] for u in store.users() if engine.run("people.is_owner", {"role": u.get("role") or ""}) is True]


def _after_trigger(agent_id: str, run: dict) -> str:
    """A triggered dry run: chip agents.trigger_gate says what happens next; the owners' bell hears it."""
    writes = [s for s in run["steps"] if s["gate"] == "preview"]
    verdict = engine.run("agents.trigger_gate", {"facts": {"failed": run["status"] == settings()["run_states"]["failed"], "blocked": False,
                                                           "has_writes": bool(writes), "all_writes_trusted": all(s["trusted"] for s in writes)}})
    name = engine.run("ui.agents").get(f"name_{agent_id}") or agent_id      # a recipe whose words are not written yet: its id
    if verdict == "approve":
        execute(agent_id, "run", run["by_id"], run["inputs"], run["trigger"])
    elif verdict in ("review", "tell_error"):
        for uid in _owners():
            bell.push(uid, say("bell_review" if verdict == "review" else "bell_failed", name=name, why=run["why"][:120]), "#/agents")
    return verdict


# --- triggers: a schedule, or an event a module emits -------------------------------------------------------------------

def trigger_on(agent_id: str, t: dict) -> bool:
    row = db().execute("SELECT on_state FROM trig WHERE agent=? AND key=?", (agent_id, t["key"])).fetchone()
    return bool(t.get("on")) if row is None or row["on_state"] is None else bool(row["on_state"])


def set_trigger(agent_id: str, key: str, on: bool) -> dict:
    r = recipe(agent_id)
    if not any(t["key"] == key for t in r.get("triggers") or []):
        raise HTTPException(404, say("no_trigger"))
    with _WRITE, db():
        db().execute("INSERT INTO trig(agent, key, on_state) VALUES(?,?,?) ON CONFLICT(agent, key) DO UPDATE SET on_state=excluded.on_state",
                     (agent_id, key, int(bool(on))))
    return {"message": say("trigger_on" if on else "trigger_off")}


def _last(agent_id: str, key: str) -> float:
    row = db().execute("SELECT last_at FROM trig WHERE agent=? AND key=?", (agent_id, key)).fetchone()
    return float(row["last_at"]) if row else 0.0


def is_due(t: dict, last: float, now: float) -> bool:
    """A schedule trigger is due: chip agents.schedule_due holds every rule (hour / day / week, the clock time, the day)."""
    at = datetime.fromtimestamp(now, timezone.utc)
    hh, mm = (int(x) for x in str(t.get("at") or settings()["default_at"]).split(":"))
    return engine.run("agents.schedule_due", {"every": t.get("every") or "day", "since_last_s": now - last if last else 1e12,
                                              "tick_seconds": float(t.get("seconds") or 0),   # 2026-10-24 "tick": every N seconds
                                              "hour_seconds": settings()["hour_seconds"],
                                              "minute_of_day": at.hour * 60 + at.minute, "at_minute": hh * 60 + mm,
                                              "weekday": at.weekday(), "want_weekday": int(t.get("weekday", at.weekday())),
                                              "day_of_month": at.day, "want_day": int(t.get("day", 1)),
                                              "same_day": bool(last) and datetime.fromtimestamp(last, timezone.utc).date() == at.date()}) is True


def due(now: float | None = None) -> int:
    now = now or time.time()
    n = 0
    for aid, r in recipes().items():
        for t in r.get("triggers") or []:
            if t.get("kind") == "schedule" and trigger_on(aid, t) and is_due(t, _last(aid, t["key"]), now) and not problems(r):
                with _WRITE, db():
                    db().execute("INSERT INTO trig(agent, key, last_at) VALUES(?,?,?) ON CONFLICT(agent, key) DO UPDATE SET last_at=excluded.last_at",
                                 (aid, t["key"], now))
                run = execute(aid, "preview", "", t.get("inputs") or {}, f"schedule:{t['key']}")
                _after_trigger(aid, run)
                n += 1
    return n


def emit(event: str, facts: dict) -> None:
    """A module says something happened (job.stopped, ...). Every agent with an event trigger for it whose `when` holds
    for these facts gets a dry run, in its own thread - the module never waits for an agent."""
    for aid, r in recipes().items():
        for t in r.get("triggers") or []:
            if t.get("kind") == "event" and t.get("event") == event and trigger_on(aid, t) and not problems(r) and (
                    not t.get("when") or engine.run("agents.step_when", {"facts": facts, "when": t["when"]}) is True):
                given = {k: facts.get(v[3:]) if isinstance(v, str) and v.startswith("@e.") else v for k, v in (t.get("inputs") or {}).items()}
                threading.Thread(target=lambda a=aid, g=given, k=t["key"]: _after_trigger(a, execute(a, "preview", "", g, f"event:{k}")),
                                 daemon=True, name=f"agent-{aid}").start()


def start() -> None:
    """The server's clock for schedule triggers. PORTAL_AGENTS_CLOCK=off (the test suite only) keeps it still, so a
    scheduled health check never talks through a test's fake voice (2026-10-24: tv/selfcheck sound test)."""
    import os  # noqa: PLC0415
    if _STARTED or os.environ.get("PORTAL_AGENTS_CLOCK") == "off":
        return

    def loop() -> None:
        while True:
            time.sleep(float(settings()["tick_seconds"]))
            try:
                due()
            except Exception as e:  # noqa: BLE001 - the clock outlives one bad agent
                print(f"agents: {e}", flush=True)
    _STARTED.append(threading.Thread(target=loop, name="agents", daemon=True))
    _STARTED[0].start()


# --- the screen (Agents, owner only - core/access.py) ---------------------------------------------------------------------

def card(aid: str, r: dict) -> dict:
    cat = catalog()
    last = runs(aid, 1)
    return {"id": aid, "icon": r.get("icon") or "spark", "problems": problems(r), "inputs": r.get("inputs") or [],
            "steps": [{"id": s["id"], "action": s["action"], "side_effect": (cat.get(s["action"]) or {}).get("side_effect", ""),
                       "trusted": bool(s.get("trusted"))} for s in r.get("steps") or []],
            "triggers": [{**t, "on": trigger_on(aid, t), "last_at": _last(aid, t["key"])} for t in r.get("triggers") or []],
            "last": last[0] if last else None}


@router.get("/api/core/agents")
def api_agents(_: dict = Depends(access.screen("agents"))):
    return {"agents": [card(aid, r) for aid, r in recipes().items()], "actions": catalog()}


@router.post("/api/core/agents/{agent_id}/run")
def api_agent_run(agent_id: str, body: dict = Body(default={}), u: dict = Depends(access.screen("agents"))):
    """Dry run (default) or, for a dry run that waits, approve = run it for real with the same inputs."""
    phase = "run" if (body or {}).get("approve") else "preview"
    given = (body or {}).get("inputs") or {}
    if phase == "run":
        prev = db().execute("SELECT * FROM runs WHERE ref=? AND agent=?", (str(body.get("ref") or ""), agent_id)).fetchone()
        if not prev or not view(prev)["waiting"]:
            raise HTTPException(400, say("nothing_waits"))
        given = view(prev)["inputs"]
        with _WRITE, db():
            db().execute("UPDATE runs SET why=? WHERE ref=?", (say("approved_by", name=u.get("name") or u.get("email") or ""), prev["ref"]))
    got = execute(agent_id, phase, u["id"], given)
    if phase == "run":
        with _WRITE, db():
            db().execute("UPDATE runs SET phase='preview_approved' WHERE ref=?", (str(body.get("ref")),))
    return {"run": got, "message": say("ran" if phase == "run" else "dry_ran")}


@router.get("/api/core/agents/{agent_id}/runs")
def api_agent_runs(agent_id: str, _: dict = Depends(access.screen("agents"))):
    recipe(agent_id)
    return {"runs": runs(agent_id)}


@router.put("/api/core/agents/{agent_id}/triggers/{key}")
def api_agent_trigger(agent_id: str, key: str, body: dict = Body(...), _: dict = Depends(access.screen("agents"))):
    return set_trigger(agent_id, key, bool((body or {}).get("on")))


if __name__ == "__main__":  # ponytail: one runnable self-check - dry run previews writes, approve writes, triggers, events
    import tempfile
    from pathlib import Path
    store.DATA = Path(tempfile.mkdtemp())
    wrote, rang = [], []
    bell.push = lambda uid, text, href="": rang.append(text)
    globals()["_owners"] = lambda: ["o"]
    action("t.read", lambda a, ctx: {"n": a["n"] * 2, "_secret": "x"})
    action("t.write", lambda a, ctx: {"would": a["v"]} if ctx["preview"] else (wrote.append(a["v"]) or {"wrote": a["v"]}))
    shipped = {"actions": [{"id": "t.read", "side_effect": "read"}, {"id": "t.write", "side_effect": "write"}]}
    real_run, real_chips = engine.run, engine.chips
    rec = {"id": "t", "inputs": [{"key": "n", "default": 2}], "steps": [
        {"id": "a", "action": "t.read", "args": {"n": "@in.n"}},
        {"id": "b", "action": "t.write", "args": {"v": "@steps.a.n"}, "trusted": True},
        {"id": "c", "action": "t.write", "args": {"v": 0}, "when": {"n": 99}}],
        "triggers": [{"key": "d", "kind": "schedule", "every": "day", "at": "06:00", "on": True},
                     {"key": "e", "kind": "event", "event": "x.stopped", "when": {"why": "hiccup"}, "inputs": {"n": "@e.n"}, "on": True}]}
    engine.chips = lambda: {**real_chips(), PREFIX + "t": {}}
    engine.run = lambda cid, args=None, *a: ({"recipe": rec} if cid == PREFIX + "t" else shipped if cid == "agents.actions"
                                             else real_run(cid, args, *a))
    dry = execute("t", "preview", "o")
    assert [s["gate"] for s in dry["steps"]] == ["run", "preview", "skip"] and not wrote, ("a dry run writes nothing", dry["steps"])
    assert dry["steps"][1]["out"] == {"would": 4} and "_secret" not in dry["steps"][0]["out"] and dry["waiting"], dry
    done = execute("t", "run", "o")
    assert wrote == [4] and done["steps"][1]["out"] == {"wrote": 4}, "approve writes for real"
    action("t.read", lambda a, ctx: (_ for _ in ()).throw(ValueError("no disk")))
    bad = execute("t", "preview", "o")
    assert bad["status"] == "failed" and bad["why"] == "no disk" and len(bad["steps"]) == 1, "a failed step stops the run"
    action("t.read", lambda a, ctx: {"n": a["n"] * 2})
    # schedule: due once a day after its clock time; the owner's switch wins over the recipe's default
    at7 = datetime(2026, 10, 23, 7, 0, tzinfo=timezone.utc).timestamp()
    assert is_due(rec["triggers"][0], 0, at7) and not is_due(rec["triggers"][0], at7 - 600, at7), "once a day"
    assert not is_due(rec["triggers"][0], 0, at7 - 2 * 3600), "not before its clock time"
    wrote.clear()
    assert due(at7) == 1 and wrote == [4] and due(at7 + 60) == 0, "all writes trusted: the trigger approves by itself, once"
    set_trigger("t", "d", False)
    assert not trigger_on("t", rec["triggers"][0]) and due(at7 + 86400) == 0, "switched off: never fires"
    # an event whose `when` holds starts a dry run in its own thread
    emit("x.stopped", {"why": "other", "n": 5})
    emit("x.stopped", {"why": "hiccup", "n": 5})
    for _ in range(50):
        if 10 in wrote:
            break
        time.sleep(0.05)
    assert 10 in wrote and wrote.count(10) == 1, ("only the matching event ran, with its own input", wrote)
    engine.run, engine.chips = real_run, real_chips
    print("agents self-check OK")
