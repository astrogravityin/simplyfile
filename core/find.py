"""The top search: one box that reaches every screen and every action this person may open.

The list comes from the catalog, so a screen added tomorrow is searchable the moment it is in the
catalog — nothing here names a screen. What counts as a match and which hit comes first are the chips
`find.score` and `find.keywords`; how long the list is is `find.settings`; every word on the box is
`find.messages`. Python only gathers the rows and sorts them with the shared ops.

A person only ever searches what they may open: the rows are filtered through access.may, screen by
screen and action by action, so the box can never hint that a screen they cannot use exists.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request

from core import access, auth, engine, guide, ops

router = APIRouter()


def texts() -> dict:
    """Every word the box says: chip find.messages."""
    return engine.run("find.messages")


def settings() -> dict:
    """How many letters before searching and how long the list is: chip find.settings."""
    return engine.run("find.settings")


def keywords() -> dict:
    """{screen_id: other words that should find it}: chip find.keywords."""
    return {str(r.get("screen")): str(r.get("words") or "") for r in engine.run("find.keywords")["rows"]}


def tasks() -> list[dict]:
    """What people ask ("how do I change the storage size"), each answered by a screen and the part of it that does it:
    chip find.tasks (the framework's screens), chip find.portal_tasks (the portal's, when it has one), then every Guide me
    step - its title, its narration, its spotlight - so a tour written tomorrow is searchable the moment it is live."""
    have = engine.chips()
    out = [dict(r) for cid in ("find.tasks", "find.portal_tasks") if cid in have for r in engine.run(cid)["rows"]]
    for scr in guide.screens():
        try:
            t = guide.tour(scr.replace("_", "-"))
        except HTTPException:
            continue
        out += [{"screen": t["screen"], "at": str(s.get("target") or "").split("|")[0], "label": str(s.get("title") or ""),
                 "words": str(s.get("say") or "")} for s in t["steps"]]
    return out


#: Which screens THIS address's menu offers (a portal with several addresses: SteadyMove's own site and its Katha door).
#: The host registers `register_menu(lambda host: {screen ids} | None)`; None = every screen. Search = the menu.
_MENU: dict = {"of": None}


def register_menu(fn) -> None:
    _MENU["of"] = fn


def rows(u: dict | None, host: str = "") -> list[dict]:
    """Every screen, action and task this person may open, in menu order (tasks after) - only what this address's menu shows."""
    words, out = keywords(), []
    shown = _MENU["of"](host) if _MENU["of"] else None
    for s in access.CATALOG:
        if not access.may(u, s["id"]) or (shown is not None and s["id"] not in shown):
            continue
        icon = s.get("icon") or "right"
        out.append({"id": s["id"], "kind": "screen", "label": s["label"], "group": s.get("group", ""), "menu": s.get("group", ""),
                    "icon": icon, "href": f"#/{s['id']}", "keywords": f'{words.get(s["id"], "")} {s["id"]}'.strip()})
        for f in s.get("functions", []):
            if access.may(u, s["id"], f["id"]):
                out.append({"id": f'{s["id"]}:{f["id"]}', "kind": "action", "label": f["label"], "group": s["label"], "menu": s.get("group", ""),
                            "icon": icon, "href": f"#/{s['id']}",
                            "keywords": f'{s["label"]} {words.get(s["id"], "")}'.strip()})
    seen = {(r["href"], r["label"].lower()) for r in out}
    for n, t in enumerate(tasks()):
        s = access._BY_ID.get(str(t.get("screen") or ""))        # noqa: SLF001 - a task on a screen this edition lacks is skipped
        if not s or not t.get("label") or not access.may(u, s["id"], t.get("function")) or (shown is not None and s["id"] not in shown):
            continue
        if t.get("role") and (u or {}).get("role") != t["role"]:   # a part of a screen only its owner sees (the page checks the same)
            continue
        at = str(t.get("at") or "")
        href = f'#/{s["id"]}' + (f"?at={quote(at)}" if at else "")
        if (href, t["label"].lower()) in seen or (f'#/{s["id"]}', t["label"].lower()) in seen:
            continue
        seen.add((href, t["label"].lower()))
        out.append({"id": f'task:{s["id"]}:{n}', "kind": "task", "label": t["label"], "group": s["label"], "menu": s.get("group", ""),
                    "icon": s.get("icon") or "right", "href": href, "keywords": f'{t.get("words") or ""} {s["label"]}'.strip()})
    return out


def search(u: dict | None, query: str = "", host: str = "") -> dict:
    """The hits for what was typed. Nothing typed = the first screens of the menu, so the box is never empty."""
    k, q = settings(), str(query or "").strip()
    items = rows(u, host)
    if len(q) < int(k["min_query_length"]):
        return {"query": q, "searched": False, "results": [r for r in items if r["kind"] == "screen"][:int(k["idle_results"])]}
    # word by word too: a question ("how do I change the storage size") or a typo still finds its place (op fuzzy_rows)
    share = {r["id"]: r.get("_w", 0) for r in ops.fuzzy_rows(items, q, ["label", "keywords", "group", "menu"], 0, "_w", k["skip_words"], k["near_min"])}
    scored = [r | {"score": score} for r in items
              if (score := engine.run("find.score", {"label": r["label"], "group": f'{r["menu"]} {r["group"]}', "keywords": r["keywords"],
                                                     "q": q, "words": share.get(r["id"], 0)}))]
    # sorted() keeps the menu order inside one score, so equal hits stay in the order people know.
    return {"query": q, "searched": True,
            "results": ops.rank_rows(scored, by="score", descending=True, limit=int(k["max_results"]))}


def bootstrap_extra(request, u) -> dict:
    """The words for the box, once, so the top bar can draw itself before anyone types."""
    return {"find": texts()} if u else {}


@router.get("/api/core/find")
def api_find(request: Request, q: str = "", u: dict = Depends(auth.signed_in)):
    return search(u, q, request.headers.get("host") or "") | {"texts": texts()}


if __name__ == "__main__":  # ponytail: one runnable self-check of the search itself
    globals()["tasks"] = lambda: []                          # the search itself first; the real task rows grow every week
    access.CATALOG[:] = [
        {"id": "video", "label": "Videos", "group": "Work", "icon": "film",
         "functions": [{"id": "draft", "label": "Draft with AI"}]},
        {"id": "storage", "label": "Storage", "group": "Admin", "icon": "folder", "admin": True},
    ]
    access._BY_ID.clear()                                    # noqa: SLF001 - the self-check owns this catalog
    access._BY_ID.update({s["id"]: s for s in access.CATALOG})  # noqa: SLF001
    owner, member = {"id": "u1", "role": "owner"}, {"id": "u2", "role": "member"}
    found = lambda who, q: [r["label"] for r in search(who, q)["results"]]  # noqa: E731
    assert found(owner, "stor") == ["Storage"], found(owner, "stor")
    assert found(owner, "disk") == ["Storage"], "the words people type find a screen, not only its name"
    assert found(owner, "draft") == ["Draft with AI"], "an action inside a screen is searchable too"
    assert found(owner, "zzz") == [], "nothing matched is an empty list, never a guess"
    assert "Storage" not in found(member, "stor"), "a screen you may not open is never even hinted at"
    assert found(owner, "")[:1] == ["Videos"], "the box opens on the menu, not on emptiness"
    assert search(owner, "vid")["results"][0]["href"] == "#/video"
    # 2026-10-01 owner: "how to change the storage size" found nothing - the box matched the whole sentence against a name.
    # A question is searched word by word (its question words skipped), and a task opens its screen AT the part that answers it.
    assert "Storage" in found(owner, "how do i change the storage size"), "a typed question finds its screen"
    globals()["tasks"] = lambda: [{"screen": "storage", "at": "#st-limits", "label": "Change storage limits", "words": "quota size"},
                                  {"screen": "storage", "at": "", "label": "Storage", "words": "dup of the screen row"}]
    hits = search(owner, "how do I change storage limits")["results"]
    assert hits[0]["kind"] == "task" and hits[0]["href"] == "#/storage?at=%23st-limits", hits[:2]
    assert [r["label"] for r in rows(owner)].count("Storage") == 1, "a task named like its screen is not shown twice"
    assert not [r for r in rows(member) if r["kind"] == "task"], "a task on a screen you may not open is never offered"
    assert all(r["kind"] == "screen" for r in search(owner, "")["results"]), "the box opens on the menu's screens"
    assert hits[0]["menu"] == "Admin" and found(owner, "admin limits")[:1] == ["Change storage limits"], "a hit knows its menu, and the menu's name finds it"
    access._BY_ID["video"]["functions"] = []                                          # noqa: SLF001
    globals()["tasks"] = lambda: [{"screen": "video", "label": "Owner part", "words": "", "role": "owner"},
                                  {"screen": "video", "label": "Anyone part", "words": ""}]
    assert [r["label"] for r in rows(member) if r["kind"] == "task"] == ["Anyone part"], "an owner-only part is never offered to others"
    assert [r["label"] for r in rows(owner) if r["kind"] == "task"] == ["Owner part", "Anyone part"]
    # 2026-10-01 owner "I don't want Katha in sm's menu": search offers what THIS address's menu shows, tasks too
    register_menu(lambda host: {"storage"} if host == "door" else None)
    door_ = rows(owner, "door")
    assert [r["label"] for r in door_ if r["kind"] == "screen"] == ["Storage"], "a screen off this address's menu is not searched"
    assert not [r for r in door_ if r["href"].startswith("#/video")], "nor are its tasks"
    assert [r for r in rows(owner, "") if r["href"].startswith("#/video")], "an address with no menu of its own searches everything"
    register_menu(None)
    print("core.find self-check OK")
