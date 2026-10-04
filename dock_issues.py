"""Issues on the bottom bar, as AstroStage has them (2026-10-04 owner): a person's own issues - searched, filtered by status,
counted - one issue with its pictures, voice notes and the portal admin's reply, and the badge of replies not yet opened.
Facts only: the notes live in core issues (the portal admin answers them in Reported issues); the list is chip
issues.mine_view; statuses and their colours chip page.dock; words chip ui.dock.
"""
from __future__ import annotations

from core import issues, store


def _mine(u: dict) -> list[dict]:
    kind = issues.frame()["queue_kind"]
    return [r for r in issues._my_rows(u, {}) if r["kind"] == kind]  # noqa: SLF001


def listed(u: dict, q: str = "", status: str = "") -> dict:
    from core import engine  # noqa: PLC0415
    v = engine.run("issues.mine_view", {"rows": _mine(u), "query": q, "status": status})
    return {"reports": v["reports"], "counts": {c["key"]: c["n"] for c in v["counts"]}}


def one(u: dict, iid: str) -> dict:
    r = next((x for x in _mine(u) if x["id"] == iid), None)
    if not r:
        from fastapi import HTTPException  # noqa: PLC0415
        raise HTTPException(404, issues.say("no_issue"))
    return r


def unseen(u: dict) -> int:
    """Own issues answered and not opened since (core issues keeps that list per person)."""
    return len(store.read(issues.frame()["unseen_store"].format(uid=u["id"]), []) or [])
