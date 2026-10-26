"""Menu builder: the owner renames, regroups, reorders and re-icons every screen, and puts a new screen live.

The edits are data (store "menus": {screen_id: {label, group, icon, order, draft}}), never git, so a code push
never undoes the owner's menu. A catalog row may arrive with "draft": true (a screen the host found by itself,
e.g. a module written in another session): it stays the owner's alone - an admin screen in all but name - until
the owner ticks Live here. Going live it is a new screen like any other and joins Catch All once
(access.settings new_screens_to_catch_all); from then on Access Control decides who sees it.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from core import access, engine, store
from core.access import screen

router = APIRouter()
FIELDS = ("label", "group", "icon", "order", "draft", "hidden")   # hidden = off the menu; the page stays


def say(key: str, **values) -> str:
    return engine.say("menus.messages", key, **values)


def apply(base: list[dict]) -> list[dict]:
    """The catalog the menu, the guard and Access Control see: base rows with the owner's edits, in the owner's order."""
    edits = store.read("menus", {})
    rows = []
    for i, s in enumerate(base):
        e = edits.get(s["id"], {})
        r = dict(s) | {k: e[k] for k in FIELDS if k in e and k != "draft"}
        r.setdefault("order", i)
        if not s.get("admin"):                            # a framework admin screen is never a draft
            r["draft"] = bool(e.get("draft", s.get("draft", False)))
            r["admin"] = r["draft"]
        rows.append(r)
    return sorted(rows, key=lambda r: r["order"])


def clean(row: dict, known: dict) -> dict:
    k = engine.run("menus.settings")
    sid = str(row.get("id") or "")
    if sid not in known:
        raise HTTPException(404, say("no_screen", screen=sid[:40]))
    label = str(row.get("label") or "").strip()[:int(k["label_max"])]
    if not label:
        raise HTTPException(400, say("needs_label"))
    out = {"label": label, "group": str(row.get("group") or "").strip()[:int(k["group_max"])],
           "icon": str(row.get("icon") or "").strip()[:int(k["icon_max"])]}
    if not known[sid].get("admin"):
        out["draft"] = row.get("draft") is True
        out["hidden"] = row.get("hidden") is True         # 2026-10-26 owner: removing a menu entry never deletes its page
    return out


@router.get("/api/core/menus")
def listed(_: dict = Depends(screen("menus"))):
    base = {s["id"]: s for s in access.BASE}
    return {"rows": [r | {"core": bool(base[r["id"]].get("admin")),
                          "base": {k: base[r["id"]].get(k, "") for k in ("label", "group", "icon")}} for r in access.CATALOG]}


@router.put("/api/core/menus")
def save(body: dict = Body(...), _: dict = Depends(screen("menus"))):
    """The whole menu, in order: every row's label, group, icon and draft. Rows left out keep their edits."""
    known = {s["id"]: s for s in access.BASE}
    rows = [r for r in (body.get("rows") or []) if isinstance(r, dict)]
    with store._LOCK:                                     # noqa: SLF001
        edits = store.read("menus", {})
        for i, r in enumerate(rows):
            edits[str(r.get("id"))] = clean(r, known) | {"order": i}
        store.write("menus", edits)
    access.reapply()
    return listed()


@router.delete("/api/core/menus/{screen_id}")
def reset(screen_id: str, _: dict = Depends(screen("menus"))):
    """Back to how the host catalogues it (its order stays where it was)."""
    with store._LOCK:                                     # noqa: SLF001
        edits = store.read("menus", {})
        order = edits.get(screen_id, {}).get("order")
        edits[screen_id] = {} if order is None else {"order": order}
        store.write("menus", edits)
    access.reapply()
    return listed()


if __name__ == "__main__":  # ponytail: one runnable self-check of the merge, on a temp data folder
    import tempfile
    from pathlib import Path
    store.DATA = Path(tempfile.mkdtemp())
    base = [{"id": "a", "label": "A", "group": "G"}, {"id": "new", "label": "New", "draft": True},
            {"id": "access", "label": "People", "admin": True}]
    rows = {r["id"]: r for r in apply(base)}
    assert rows["new"]["admin"] and rows["new"]["draft"] and not rows["a"]["admin"], "a found screen is the owner's until live"
    assert rows["access"]["admin"] and "draft" not in rows["access"], "an admin screen is never a draft"
    store.write("menus", {"new": {"draft": False, "order": -1, "label": "Fresh"}, "access": {"draft": False}})
    rows = apply(base)
    assert rows[0]["id"] == "new" and rows[0]["label"] == "Fresh" and not rows[0]["admin"], "live, renamed and first"
    assert next(r for r in rows if r["id"] == "access")["admin"], "a framework admin screen cannot be opened here"
    store.write("menus", {"a": {"hidden": True}})
    a = next(r for r in apply(base) if r["id"] == "a")
    assert a["hidden"] and not a["admin"], "off the menu, still a page Access Control decides"
    print("core.menus self-check OK")
