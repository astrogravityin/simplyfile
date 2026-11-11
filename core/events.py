"""One push stream per signed-in page (portal-builder "Server tells, page never asks on a timer", owner 2026-11-08; A20).

  GET /api/core/events   Server-Sent Events for the signed-in person: their own news (key u:<id>) and their firm's
                         (key f:<firm id>). A heartbeat comment keeps proxies open; `retry:` tells the browser how long
                         to wait before it reconnects; a reconnect sends Last-Event-ID and gets what it missed (a short
                         replay log, chip events.settings replay_keep), so the page never asks on a timer.

Any module calls publish(person or firm, topic, data); nothing here knows what a topic means. Topic names, the heartbeat,
the retry and the replay size are chip events.settings. Business events (bell + mail + webhook) are core/notify.py.
"""
from __future__ import annotations

import asyncio
import collections
import itertools
import json
import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from core import auth, engine

router = APIRouter()
_LOCK = threading.Lock()
_SUBS: dict[str, set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = collections.defaultdict(set)
_LOG: collections.deque = collections.deque()          # (id, key, topic, data) - what a reconnect may have missed
_IDS = itertools.count(1)
HELLO: list = []                                         # fn(user) -> (topic, data) | None: the state a fresh stream starts from


def K() -> dict:
    return engine.run("events.settings")


def topic(name: str) -> str:
    """The wire name of a topic (chip events.settings topics)."""
    return K()["topics"][name]


def keys_of(u: dict) -> list[str]:
    return [f"u:{u['id']}"] + ([f"f:{u['firm_id']}"] if u.get("firm_id") else [])


def publish(key: str, name: str, data: dict | None = None) -> int:
    """One piece of news to everyone listening on `key` (u:<id> or f:<firm id>). Safe from any thread.
    ponytail: in-process fan-out - one uvicorn worker (start.sh); more workers need a shared bus (Postgres NOTIFY / Redis)."""
    if not key:
        return 0
    with _LOCK:
        eid = next(_IDS)
        _LOG.append((eid, key, topic(name), data or {}))
        while len(_LOG) > int(K()["replay_keep"]):
            _LOG.popleft()
        subs = list(_SUBS.get(key, ()))
    for loop, q in subs:
        try:
            loop.call_soon_threadsafe(q.put_nowait, (eid, topic(name), data or {}))
        except RuntimeError:                              # that page's loop is gone - its stream ends on its own
            pass
    return eid


def to_person(uid: str, name: str, data: dict | None = None) -> int:
    return publish(f"u:{uid}", name, data) if uid else 0


def _frame(eid, name: str, data: dict) -> str:
    return (f"id: {eid}\n" if eid else "") + f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def missed(keys: list[str], last: int) -> list[tuple]:
    with _LOCK:
        return [(e, t, d) for e, k, t, d in _LOG if e > last and k in keys]


@router.get("/api/core/events")
async def api_events(request: Request, u: dict = Depends(auth.signed_in)):
    k, keys = K(), keys_of(u)
    loop, q = asyncio.get_running_loop(), asyncio.Queue[tuple]()
    with _LOCK:
        for key in keys:
            _SUBS[key].add((loop, q))
    try:
        last = int(request.headers.get("last-event-id") or 0)
    except ValueError:
        last = 0

    async def body():
        try:
            yield f"retry: {int(k['retry_ms'])}\n\n"
            for fn in HELLO:                              # the state now - a reconnect never needs a fetch to catch up
                got = fn(u)
                if got:
                    yield _frame(0, topic(got[0]), got[1])
            for eid, name, data in missed(keys, last):
                yield _frame(eid, name, data)
            while True:
                try:
                    eid, name, data = await asyncio.wait_for(q.get(), timeout=float(k["heartbeat_s"]))
                    yield _frame(eid, name, data)
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        return
                    yield ": hb\n\n"
        finally:
            with _LOCK:
                for key in keys:
                    _SUBS[key].discard((loop, q))
    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def bootstrap_extra(request: Request, u: dict | None) -> dict:
    """The page's stream knobs and topic names (one source: chip events.settings)."""
    if not u:
        return {}
    return {"events": {"url": "/api/core/events", "topics": K()["topics"]}}


if __name__ == "__main__":  # ponytail: one runnable self-check - fan-out by key, replay after a gap, log capped
    async def _main():
        loop, q = asyncio.get_running_loop(), asyncio.Queue[tuple]()
        _SUBS["u:a"].add((loop, q))
        e1 = to_person("a", "bell", {"unread": 1})
        to_person("b", "bell", {"unread": 9})
        publish("f:x", "badge", {"id": "s", "n": 2})
        got = await asyncio.wait_for(q.get(), 1)
        assert got == (e1, topic("bell"), {"unread": 1}) and q.empty(), "only u:a's own news reaches u:a"
        assert [m[2] for m in missed(["u:a", "f:x"], 0)] == [{"unread": 1}, {"id": "s", "n": 2}], "replay = my keys, in order"
        assert missed(["u:a"], e1) == [], "nothing after the last id seen"
        for _ in range(int(K()["replay_keep"]) + 5):
            to_person("c", "bell", {})
        assert len(_LOG) == int(K()["replay_keep"]), "replay log capped"
        assert keys_of({"id": "a", "firm_id": "x"}) == ["u:a", "f:x"] and keys_of({"id": "a"}) == ["u:a"]
        assert to_person("", "bell") == 0 and publish("", "bell") == 0
        assert _frame(3, "bell", {"n": 1}) == 'id: 3\nevent: bell\ndata: {"n": 1}\n\n'
    asyncio.run(_main())
    print("events self-check OK")
