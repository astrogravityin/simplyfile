"""The bell: short notes for ONE person, shown under the bell in the top bar (2026-09-28 owner: a reader site = YouTube + Spotify
+ Scribd - "like, comment, subscribe, notify"). Any module pushes one; nothing here knows what a work or a comment is.

  bell/<user id>    that person's notes, newest first, capped at chip bell.settings keep - one small file per person,
                    never one file for everyone. A note is {id, text, href, at, seen}; text is already in words (the
                    pushing module's chip), href a screen link (#/watch?w=...).

Every size is chip bell.settings; every sentence is a chip.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from core import auth, engine, limits, store

router = APIRouter()


def settings() -> dict:
    return engine.run("bell.settings")


def _name(uid: str) -> str:
    name = f"bell/{uid}"
    store.path_of(name).parent.mkdir(parents=True, exist_ok=True)   # path_of reads the live data folder
    return name


def push(uid: str, text: str, href: str = "") -> None:
    """One note for one person. The oldest fall off past chip bell.settings keep."""
    if not uid or not text:
        return
    with store._LOCK:                                    # noqa: SLF001
        most = settings()["text_max"]
        rows = [{"id": store.new_id(), "text": limits.clip(text, most), "href": limits.clip(href, most), "at": store.now(), "seen": False}]
        rows += list(store.read(_name(uid), []) or [])
        store.write(_name(uid), limits.newest(rows, settings()["keep"]))   # chip limits.newest


def mine(uid: str) -> list[dict]:
    return list(store.read(_name(uid), []) or [])


def unread(uid: str) -> int:
    return sum(1 for r in mine(uid) if not r["seen"])


def seen(uid: str) -> dict:
    with store._LOCK:                                    # noqa: SLF001
        store.write(_name(uid), [r | {"seen": True} for r in mine(uid)])
    return {"ok": True}


def bootstrap_extra(request: Request, u: dict | None) -> dict:
    return {"bell_unread": unread(u["id"])} if u else {}


@router.get("/api/core/bell")
def api_bell(u: dict = Depends(auth.signed_in)):
    return {"rows": mine(u["id"])}


@router.post("/api/core/bell/seen")
def api_bell_seen(u: dict = Depends(auth.signed_in)):
    return seen(u["id"])


if __name__ == "__main__":  # ponytail: one runnable self-check - per person, capped, newest first, seen clears the count
    import tempfile
    from pathlib import Path
    store.DATA = Path(tempfile.mkdtemp())
    keep_n = int(settings()["keep"])
    for i in range(keep_n + 3):
        push("a", f"n{i}", "#/watch")
    assert len(mine("a")) == keep_n and mine("a")[0]["text"] == f"n{keep_n + 2}", "capped, newest first"
    assert unread("a") == keep_n and mine("b") == [] and unread("b") == 0, "one person's bell is theirs alone"
    seen("a")
    assert unread("a") == 0
    push("", "x")
    push("a", "")
    assert len(mine("a")) == keep_n, "no one / no words: nothing pushed"
    print("bell self-check OK")
