"""Resumable jobs: a long piece of work as a list of steps, written to disk one at a time.

2026-09-18 owner: a film can run out of money halfway. What was made must stay playable, the person must
be told exactly where it stopped and what the rest would cost, and pressing the same button again must
carry on - not start over and not pay twice. So:

- a job is a MANIFEST on disk (data/jobs/<id>.json): its steps in order, each pending | done | failed,
  with the file it made and what it cost;
- opening a job again keeps every step whose key still matches and whose file is still there;
- before a PAID step, chip `jobs.may_continue` decides whether the budget can take it; if not the job
  stops cleanly and says so (`jobs.messages`);
- a failed step is retried (`jobs.partial`), then the job stops with everything before it kept;
- a server restart in the middle leaves a job marked stopped, never "running" for ever;
- `ready` is how many steps from the start are done - what can be played right now.

Nothing here knows what a step IS. The caller (narration today, shorts and film shots later) passes a
`do_step(index, step)` that makes the step's part and returns {"out": path, "cost_usd": n}.
"""
from __future__ import annotations

from typing import Any
import json
import re
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from core import auth, engine, events, store


class OutOfCredit(RuntimeError):
    """The provider's account has no money left (2026-09-25 owner: "if the model runs out of money the user is told,
    and once they pay it resumes from that point"). Never retried: the job stops at once, keeps every finished step,
    and the same button carries on from this step after the top-up."""

router = APIRouter()
_ID = re.compile(r"^[a-z]+-[a-z0-9]{6,40}$")
_LOCK = threading.RLock()


def say(key: str, **values) -> str:
    return engine.say("jobs.messages", key, **values)


def settings() -> dict:
    return engine.run("jobs.partial")


def folder() -> Path:
    return store.DATA / "jobs"


def path_of(job_id: str) -> Path:
    if not _ID.match(job_id or ""):
        raise HTTPException(400, say("no_job"))
    return folder() / f"{job_id}.json"


def load(job_id: str) -> dict | None:
    """Under the same lock as save(): on Windows a file being replaced cannot be opened, and the page
    polls the manifest while the job rewrites it (2026-09-18, PermissionError in the self-check). A short
    retry covers another process (a virus scanner) holding it for a moment."""
    p = path_of(job_id)
    for attempt in range(5):
        with _LOCK:
            if not p.exists():
                return None
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except PermissionError:
                if attempt == 4:
                    raise
        time.sleep(0.05)
    return None


def save(m: dict) -> None:
    with _LOCK:
        folder().mkdir(parents=True, exist_ok=True)
        m["updated"] = store.now()
        p = path_of(m["id"])
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    # 2026-11-11 A20: progress is pushed (the work window paints it), never polled
    events.to_person(m.get("owner_id", ""), "job", {"url": f"/api/core/jobs/{m['id']}", "job": summary(m)})


def ready(m: dict) -> int:
    """Steps done from the very start, with no gap: what can be played right now."""
    n = 0
    for st in m["steps"]:
        if st["status"] != "done":
            break
        n += 1
    return n


def _whole(out) -> bool:
    """A step's file counts as made only when it holds something: a zero-byte file is a death mid-write."""
    p = Path(str(out))
    return p.is_file() and p.stat().st_size > 0


def open_job(job_id: str, owner_id: str, kind: str, steps: list[dict], resume: dict | None = None) -> dict:
    """The manifest for this run. A step whose key matches a DONE step of the last run, and whose file
    is still on disk, is kept as done - that is the whole of "resume".
    `resume`: {"module": "export", "args": {...}} - how to start this same work again by itself after a server
    restart. Only a job with nothing left to PAY for is ever restarted that way (see recover)."""
    old = load(job_id) or {}
    was = {s["key"]: s for s in old.get("steps", []) if s.get("status") == "done"}
    # 2026-09-28 owner: "even though the server restarted, what the user created must not be lost" - a step whose paid
    # request was already sent keeps the provider's ticket, so the next run collects that answer instead of paying again
    tickets = {s["key"]: s["ticket"] for s in old.get("steps", []) if s.get("status") != "done" and s.get("ticket")}
    rows = []
    for s in steps:
        prev = was.get(s["key"])
        keep = prev is not None and (not prev.get("out") or _whole(prev["out"]))
        # 2026-09-19 a step that names its own file (`out`) is done when that file is on disk, whatever the key:
        # five PAID clips vanished from a film when a wording change turned every key over. The file is the truth;
        # a caller that wants them made again deletes the files (fresh), never just the manifest.
        # 2026-09-23 ... and an EMPTY file is not the truth: a chunk half-written when the process died was kept for ever.
        if not keep and s.get("out") and _whole(s["out"]):
            keep, prev = True, {"out": str(s["out"]), "cost_usd": 0.0}
        rows.append({"key": s["key"], "label": s.get("label", ""), "estimate_usd": float(s.get("estimate_usd") or 0),
                     "group": s.get("group") or "", "status": "done" if keep else "pending",
                     "out": prev.get("out") if keep else None,
                     "cost_usd": float(prev.get("cost_usd") or 0) if keep else 0.0, "error": "",
                     "ticket": None if keep else tickets.get(s["key"])})
    m = {"id": job_id, "owner_id": owner_id, "kind": kind, "status": "ready", "reason": "",
         "steps": rows, "created": old.get("created") or store.now(),
         "resume": resume or old.get("resume") or None}
    save(m)
    return m


def remember(m: dict, st: dict, ticket: dict | None) -> None:
    """A paid request was just sent (or its ticket is spent): kept on the step and saved at once, so a restart from
    here on collects the answer instead of paying for the same work again."""
    with _LOCK:
        st["ticket"] = ticket
        save(m)


def _stop_flag(job_id: str) -> Path:
    # Its own file, not a field: the runner rewrites the manifest after every step and would wipe a
    # Stop pressed in between (2026-09-18: the self-check caught exactly that).
    return path_of(job_id).with_suffix(".stop")


def request_stop(job_id: str) -> None:
    m = load(job_id)
    if m and m["status"] == "running":
        _stop_flag(job_id).touch()


def run(m: dict, do_step, *, funds=None, log=lambda line: None, only=None, money=lambda usd: f"{usd:.2f}",
        lanes: int = 1) -> dict:
    """Takes every step not yet done, in order (or only the indexes in `only` - a test of one shot before paying
    for all; the rest stay pending). Returns the manifest with status done | stopped.

    `lanes` > 1 runs several steps AT THE SAME TIME (2026-09-20: a video model takes minutes per clip, and a
    ten-minute film is an afternoon of waiting one clip at a time). Steps that must follow each other carry the
    same `group` and stay in their own order; different groups run side by side. A step with no group is its own
    group. The budget question and the Stop flag are asked before EVERY step, under one lock, so two lanes can
    never spend the same last dollar twice."""
    k = settings()
    total = len(m["steps"])
    done_before = sum(1 for s in m["steps"] if s["status"] == "done")
    if 0 < done_before < total:
        first = next(i for i, s in enumerate(m["steps"]) if s["status"] != "done")
        log(say("resumed", n=first + 1, total=total, done=done_before))
    for i, st in enumerate(m["steps"]):
        if st["status"] == "done" and done_before:
            log(say("kept", n=i + 1, total=total))
    m["status"], m["reason"] = "running", ""
    _stop_flag(m["id"]).unlink(missing_ok=True)       # an old Stop never cancels a new run
    save(m)
    tries = int(k["max_retries"]) + 1
    gate = threading.Lock()
    halt: list = []                                   # the first reason a lane stopped: every other lane then stops too
    # 2026-10-02 (sm Ads, Veo 429 after 3 of 6 clips said "1 of 6 made"): a reason that counts what is ready is a
    # (key, values) pair, worded only when every lane has finished - parallel lanes were still landing their clips
    worded = lambda h: h if isinstance(h, str) else say(h[0], ready=ready(m), **h[1])   # noqa: E731

    def may_start(i: int, st: dict) -> str:
        """The reason this step must NOT start, or "" to go ahead. Asked under `gate`, so money is never
        promised twice."""
        if halt:
            return worded(halt[0])
        if _stop_flag(m["id"]).exists():
            return say("stopped_by_you", ready=ready(m), total=total)
        f = funds() if funds else {"has_budget": False, "left_usd": None}
        if engine.run("jobs.may_continue", {"has_budget": bool(f.get("has_budget")), "left_usd": f.get("left_usd"),
                                            "step_usd": st["estimate_usd"],
                                            "stop_when_left_usd": k["stop_when_left_usd"]}) is not True:
            rest = sum(s["estimate_usd"] for s in m["steps"] if s["status"] != "done")
            # `money` formats a dollar figure the way the PERSON sees money (the portal passes its currency formatter)
            return say("stopped_budget", n=i + 1, total=total, left=money(float(f.get("left_usd") or 0)),
                       need=money(st["estimate_usd"]), ready=ready(m), rest=money(rest))
        return ""

    def take(i: int, st: dict) -> bool:
        """One step, with its retries. False = this lane stops (the reason is in `halt`)."""
        with gate:
            no = may_start(i, st)
            if no:
                if not halt:
                    halt.append(no)
                return False
        for attempt in range(1, tries + 1):
            try:
                made = do_step(i, st) or {}
                st.update(status="done", out=str(made["out"]) if made.get("out") else None,
                          cost_usd=float(made.get("cost_usd") or 0), error="", ticket=None)
                break
            except Exception as e:  # noqa: BLE001 - the reason goes to the person, the job keeps its parts
                reason = str(e).splitlines()[0] if str(e) else type(e).__name__
                if isinstance(e, OutOfCredit):          # no money: retrying only fails again - stop and say how to go on
                    st.update(status="pending", error=reason)
                    with gate:
                        if not halt:
                            halt.append(("stopped_no_credit", {"n": i + 1, "total": total, "reason": reason}))
                    save(m)
                    return False
                if attempt < tries:
                    log(say("retrying", n=i + 1, reason=reason, attempt=attempt + 1, tries=tries))
                    time.sleep(float(k["retry_wait_s"]))
                    continue
                st.update(status="failed", error=reason)
                with gate:
                    if not halt:
                        halt.append(("stopped_error", {"n": i + 1, "total": total, "reason": reason}))
                save(m)
                return False
        save(m)
        return True

    todo = [i for i, st in enumerate(m["steps"])
            if st["status"] != "done" and (only is None or i in only)]
    groups: dict = {}
    for i in todo:
        groups.setdefault(m["steps"][i].get("group") or f"_{i}", []).append(i)
    lanes = max(1, min(int(lanes), len(groups)))
    if lanes > 1:
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415 - only a parallel run pays for it

        def lane(idxs):
            for i in idxs:
                if not take(i, m["steps"][i]):
                    return
        with ThreadPoolExecutor(max_workers=lanes, thread_name_prefix=f"job-{m['id']}") as pool:
            list(pool.map(lane, list(groups.values())))
    else:
        for idxs in groups.values():
            for i in idxs:
                if not take(i, m["steps"][i]):
                    break
            if halt:
                break
    if halt:
        return _stop(m, worded(halt[0]))
    m["status"] = "done" if all(s["status"] == "done" for s in m["steps"]) else "stopped"
    if m["status"] == "stopped":
        m["reason"] = say("stopped_partial", ready=ready(m), total=total)
    save(m)
    return m


def _stop(m: dict, reason: str) -> dict:
    m["status"], m["reason"] = "stopped", reason
    _stop_flag(m["id"]).unlink(missing_ok=True)
    save(m)
    return m


def summary(m: dict | None) -> dict | None:
    """What a screen needs: every step's state, how far it can be played, spent and still to spend."""
    if not m:
        return None
    return {"id": m["id"], "kind": m["kind"], "status": m["status"], "reason": m["reason"],
            "total": len(m["steps"]), "done": sum(1 for s in m["steps"] if s["status"] == "done"),
            "ready": ready(m), "spent_usd": round(sum(s["cost_usd"] for s in m["steps"]), 4),
            "rest_usd": round(sum(s["estimate_usd"] for s in m["steps"] if s["status"] != "done"), 4),
            "steps": [{"label": s["label"], "status": s["status"]} for s in m["steps"]]}


def recover() -> int:
    """At start-up: a job that was running when the server stopped is stopped, never running for ever.

    2026-09-20, the worker half: a job with NOTHING LEFT TO PAY FOR and a `resume` of its own is then started
    again by itself, in a thread, so a restart in the middle of an hour of joining, voicing or exporting does not
    cost the person that hour. A job with a paid step still pending is never restarted on its own - money is spent
    only when the person presses the button and has seen the cost."""
    n = 0
    if not folder().exists():
        return 0
    for p in folder().glob("*.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if m.get("status") == "running":
            _stop(m, say("stopped_restart", ready=ready(m), total=len(m["steps"])))
            n += 1
            if may_resume(m):
                threading.Thread(target=_resume, args=(m,), daemon=True, name=f"resume-{m['id']}").start()
    return n


def _noop(**_kw) -> None:
    """Does nothing; the self-check points a resume at it."""


def may_resume(m: dict) -> bool:
    """A stopped job that can start itself again: it knows how, and nothing left in it costs money."""
    r = m.get("resume") or {}
    if not r.get("module"):
        return False
    return not any(float(s.get("estimate_usd") or 0) > 0 for s in m.get("steps", []) if s.get("status") != "done")


def _resume(m: dict) -> None:
    import importlib  # noqa: PLC0415 - only a restart with work left pays for the import
    r = m["resume"]
    try:
        getattr(importlib.import_module(str(r["module"])), str(r.get("fn") or "make"))(**dict(r.get("args") or {}))
    except Exception:  # noqa: BLE001, S110 - the job is already marked stopped; the person can press the button
        pass


def _mine(job_id: str, u: dict) -> dict:
    m = load(job_id)
    if not m:
        raise HTTPException(404, say("no_job"))
    if m["owner_id"] != u["id"] and u.get("role") != "owner":
        raise HTTPException(403, say("not_yours"))
    return m


@router.get("/api/core/jobs/{job_id}")
def api_job(job_id: str, u: dict = Depends(auth.signed_in)):
    return summary(_mine(job_id, u))


@router.post("/api/core/jobs/{job_id}/stop")
def api_stop(job_id: str, u: dict = Depends(auth.signed_in)):
    _mine(job_id, u)
    request_stop(job_id)
    return {"ok": True}


if __name__ == "__main__":  # ponytail: one runnable self-check of stop, keep and carry on
    import tempfile
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        store.DATA = Path(tmp)
        parts = Path(tmp) / "parts"
        parts.mkdir()
        made: list[Any] = []

        def make(i, st):
            f = parts / f"{st['key']}.bin"
            f.write_text("x")
            made.append(st["key"])
            return {"out": f, "cost_usd": st["estimate_usd"]}

        import core.jobs as me  # noqa: PLC0415 - the retry wait is a chip; 0 keeps this check fast
        keep_settings = me.settings
        me.settings = lambda: {"stop_when_left_usd": 0.05, "max_retries": 1, "retry_wait_s": 0, "keep_days": 30}
        steps = [{"key": f"s{i}", "label": f"step {i}", "estimate_usd": 0.1} for i in range(1, 6)]
        # 1. money runs out before step 3: steps 1-2 made and kept, and told what the rest would cost
        wallet = {"left": 0.30}

        def funds():
            return {"has_budget": True, "left_usd": wallet["left"] - 0.1 * len(made)}
        m = me.run(me.open_job("render-abc123", "u1", "render", steps), make, funds=funds, money=lambda v: f"₹{v * 84:.2f}")
        assert m["status"] == "stopped" and me.ready(m) == 2 and made == ["s1", "s2"], (m["status"], made, m["reason"])
        # 2026-09-19 the figures in the reason come through the caller's money formatter (the person's currency)
        assert "top up" in m["reason"] and "₹25.20" in m["reason"] and "$" not in m["reason"], m["reason"]
        # 2. topped up: the same button carries on from step 3, and nothing is made twice
        wallet["left"] = 10.0
        lines: list[Any] = []
        m = me.run(me.open_job("render-abc123", "u1", "render", steps), make, funds=funds, log=lines.append)
        assert m["status"] == "done" and made == ["s1", "s2", "s3", "s4", "s5"], made
        assert any("carrying on from step 3" in x for x in lines), lines
        # 3. a step that keeps failing is tried again, then the job stops with what came before kept
        calls: list[Any] = []

        def flaky(i, st):
            calls.append(st["key"])
            if st["key"] == "x3":
                raise RuntimeError("network went away")
            return make(i, st)
        other = [{"key": f"x{i}", "label": f"step {i}", "estimate_usd": 0} for i in range(1, 6)]
        m = me.run(me.open_job("render-abc124", "u1", "render", other), flaky)
        assert m["status"] == "stopped" and calls.count("x3") == 2, calls
        assert me.ready(m) == 2 and "network went away" in m["reason"], m["reason"]
        # 3a. 2026-10-02 (Veo 429 after 3 of 6 clips said "1 of 6 made"): lanes side by side - step 4 fails while steps 2
        # and 3 are still landing; the reason counts what is ready AFTER every lane has finished
        import threading as _th  # noqa: PLC0415
        landed = _th.Event()

        def lanes_(i, st):
            if st["key"] == "l4":
                raise me.OutOfCredit("429 RESOURCE_EXHAUSTED")
            if st["key"] in ("l2", "l3"):
                landed.wait(2)                         # still landing when step 4 stops the job
            return make(i, st)
        par = [{"key": f"l{i}", "label": f"step {i}", "estimate_usd": 0, "group": f"g{i}"} for i in range(1, 7)]
        m = me.run(me.open_job("render-lanes1", "u1", "render", par), lambda i, st: (st["key"] == "l4" and landed.set()) or lanes_(i, st), lanes=4)
        assert m["status"] == "stopped" and me.ready(m) == 3 and "3 of 6" in m["reason"], (me.ready(m), m["reason"])
        # 3b. 2026-09-25 owner: "if the model runs out of money, the user is told; once they pay it resumes from that
        # point": the provider's "no credit" is never retried, the job stops at that step with what came before kept,
        # says what to do, and the same button carries on from exactly there once the account has money again
        broke = {"on": True}
        tried: list[Any] = []

        def paid(i, st):
            tried.append(st["key"])
            if st["key"] == "c3" and broke["on"]:
                raise me.OutOfCredit("Your OpenAI account has run out of credit (insufficient_quota).")
            return make(i, st)
        cred = [{"key": f"c{i}", "label": f"step {i}", "estimate_usd": 0.1} for i in range(1, 6)]
        m = me.run(me.open_job("render-credit1", "u1", "render", cred), paid)
        assert m["status"] == "stopped" and tried.count("c3") == 1, ("no credit is not retried", tried)
        assert me.ready(m) == 2 and "run out of credit" in m["reason"] and "step 3" in m["reason"] and "same button" in m["reason"], m["reason"]
        broke["on"] = False                                            # the person topped up
        tried.clear()
        m = me.run(me.open_job("render-credit1", "u1", "render", cred), paid)
        assert m["status"] == "done" and tried == ["c3", "c4", "c5"], ("carries on from step 3, nothing made twice", tried)
        # 4. a file that vanished is made again; the rest are kept
        (parts / "s2.bin").unlink()
        again = me.open_job("render-abc123", "u1", "render", steps)
        assert [x["status"] for x in again["steps"]] == ["done", "pending", "done", "done", "done"], again["steps"]
        # 4a. 2026-09-23 an EMPTY file is a death mid-write, not a step done: it is made again (a paid chunk could not be re-bought)
        (parts / "s2.bin").write_bytes(b"")
        assert me.open_job("render-abc123", "u1", "render", steps)["steps"][1]["status"] == "pending", "a zero-byte file is not the truth"
        (parts / "s2.bin").unlink()
        # 4b. 2026-09-19 the file is the truth: a manifest lost (or every key turned over) still finds its files
        me.path_of("render-abc123").unlink()
        named = [dict(x, key="new" + x["key"], out=str(parts / f"s{i + 1}.bin")) for i, x in enumerate(steps)]
        found = me.open_job("render-abc123", "u1", "render", named)
        assert [x["status"] for x in found["steps"]] == ["done", "pending", "done", "done", "done"], found["steps"]
        assert found["steps"][0]["out"] == str(parts / "s1.bin") and found["steps"][0]["cost_usd"] == 0.0
        again = found                                                  # the rest goes on from the recovered manifest
        # 5. a server restart mid-job leaves it stopped, never running for ever
        again["status"] = "running"
        me.save(again)
        assert me.recover() == 1 and me.load("render-abc123")["status"] == "stopped"
        # 5b. 2026-09-20 the worker half: free work starts itself again after a restart, PAID work never does
        free = me.open_job("render-free01", "u1", "render", [dict(x, key="w" + x["key"], estimate_usd=0) for x in other],
                           resume={"module": "core.jobs", "fn": "_noop", "args": {}})
        assert me.may_resume(free), "a job that costs nothing and knows how to start again may do so"
        paid = me.open_job("render-paid01", "u1", "film", [dict(x, key="p" + x["key"], estimate_usd=0.4) for x in other],
                           resume={"module": "core.jobs", "fn": "_noop", "args": {}})
        assert not me.may_resume(paid), "money is spent only when the person presses the button"
        blind = me.open_job("render-blind1", "u1", "render", [dict(x, key="b" + x["key"], estimate_usd=0) for x in other])
        assert not me.may_resume(blind), "a job that never said how to start again is left alone"
        sm = me.summary(me.load("render-abc123"))
        assert (sm["total"], sm["done"], sm["ready"]) == (5, 4, 1), sm
        # 6. Stop pressed on the screen while step 1 runs: honoured before step 2, step 1 kept
        def click_stop(i, st):
            me.request_stop("render-abc125")
            return make(i, st)
        m = me.run(me.open_job("render-abc125", "u1", "render", [dict(x, key="z" + x["key"]) for x in other]), click_stop)
        assert m["status"] == "stopped" and me.ready(m) == 1 and "Stopped by you" in m["reason"], m["reason"]
        # 7. 2026-09-20 lanes: steps of ONE group keep their order, groups run at the same time, and a lane that
        # fails stops the others - a long film is scene beside scene, never one clip at a time for an afternoon
        import threading as _th  # noqa: PLC0415
        order, live, peak, seen_lock = [], [0], [0], _th.Lock()

        def slow(i, st):
            with seen_lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
                order.append(st["key"])
            # ponytail: 0.3 s overlap - at 0.05 s a busy machine started the third lane after the first ended (TradyFy
            # 2026-10-10, 1 run in 2); a barrier if even this proves flaky
            time.sleep(0.3)
            with seen_lock:
                live[0] -= 1
            return make(i, st)
        grouped = [{"key": f"g{a}{b}", "label": f"{a}.{b}", "estimate_usd": 0, "group": a}
                   for a in ("A", "B", "C") for b in (1, 2)]
        m = me.run(me.open_job("render-lanes1", "u1", "render", grouped), slow, lanes=3)
        assert m["status"] == "done" and peak[0] == 3, ("three scenes side by side", peak[0], m["status"])
        for a in ("A", "B", "C"):
            assert order.index(f"g{a}1") < order.index(f"g{a}2"), ("a scene's shots keep their order", order)
        order.clear(); peak[0] = 0
        m = me.run(me.open_job("render-lanes2", "u1", "render", [dict(x, key="q" + x["key"]) for x in grouped]), slow, lanes=1)
        assert peak[0] == 1 and m["status"] == "done", ("lanes 1 = one at a time", peak[0])
        failed = [{"key": f"f{a}{b}", "label": f"{a}.{b}", "estimate_usd": 0, "group": a}
                  for a in ("A", "B") for b in (1, 2)]

        def breaks(i, st):
            if st["key"] == "fA1":
                raise RuntimeError("the model refused")
            time.sleep(0.05)
            return make(i, st)
        m = me.run(me.open_job("render-lanes3", "u1", "render", failed), breaks, lanes=2)
        assert m["status"] == "stopped" and "the model refused" in m["reason"], m["reason"]
        assert not any(s["status"] == "done" for s in m["steps"] if s["key"] == "fA2"), "a scene stops where it broke"
        # 2026-09-28 owner: a restart must not lose paid work - a step that SENT its paid request keeps the ticket; the
        # next run hands it back (collect, never pay again) and a done step drops it
        sent: list[Any] = []

        def dies(i, st):
            me.remember(m_, st, {"id": f"req-{st['key']}"})
            sent.append(st["key"])
            raise SystemExit                            # the server going down mid-request
        m_ = me.open_job("render-ticket", "u1", "film", [{"key": "t1", "label": "1", "estimate_usd": 0.5}])
        try:
            me.run(m_, dies)
        except SystemExit:
            pass
        got = []
        m_ = me.open_job("render-ticket", "u1", "film", [{"key": "t1", "label": "1", "estimate_usd": 0.5}])
        m_ = me.run(m_, lambda i, st: got.append(st.get("ticket")) or make(i, st), funds=lambda: {"has_budget": True, "left_usd": 5})
        assert got == [{"id": "req-t1"}] and sent == ["t1"], ("the paid request is collected after a restart", got)
        assert m_["steps"][0]["status"] == "done" and m_["steps"][0]["ticket"] is None
        me.settings = keep_settings
    print("core.jobs self-check OK")
