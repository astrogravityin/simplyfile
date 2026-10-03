"""A registered project: a name, a folder on this machine, its screens, and the training and video
links each screen carries.

This is the one place that knows anything about the product being documented — and all it knows is
what you typed and what Scan found. Nothing in this portal is specific to any application.

Key rules, field limits and link kinds are the chip `projects.settings`; which kind a link is follows
`projects.link_type`; every sentence is in `projects.messages`. Python reads and writes the rows.
"""
from __future__ import annotations

import re
from functools import lru_cache, wraps
from pathlib import Path

import store
from core import engine

engine.register_dir(Path(__file__).resolve().parent / "chips")

_rx = lru_cache(maxsize=32)(re.compile)   # a pattern from a chip, compiled once


def _cfg() -> dict:
    return engine.run("projects.settings")


def _no(key: str) -> ValueError:
    return ValueError(engine.say("projects.messages", key))


def _locked(fn):
    """2026-10-02 review: every read-change-write of the ONE shared projects file holds the store lock - two people
    saving at once never wipe each other's project (git token included)."""
    @wraps(fn)
    def run(*a, **k):
        with store._LOCK:                               # noqa: SLF001 - this portal's own store
            return fn(*a, **k)
    return run


def all_projects() -> list[dict]:
    return store.read("projects", [])


def get_project(project_id: str) -> dict | None:
    return next((p for p in all_projects() if p["id"] == project_id), None)


def by_key(key: str) -> dict | None:
    return next((p for p in all_projects() if p.get("key") == key), None)


def _unique(base: str, taken: set[str]) -> str:
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    return key


def _key_for(name: str, taken: set[str], cfg: dict | None = None) -> str:
    cfg = cfg or _cfg()
    fallback = cfg["project_key_fallback"]
    base = _rx(cfg["key_unsafe"]).sub("-", (name or fallback).lower()).strip("-") or fallback
    return _unique(base, taken)


@_locked
def save_project(project_id: str | None, name: str, folder: str, site_url: str, who: str,
                 source_kind: str = "local", git_url: str = "", git_branch: str = "",
                 git_token: str | None = None, owner_id: str = "") -> dict:
    """A project's code is either a folder on this machine or a Git repository the portal clones.
    `git_token` of None means "leave whatever is stored alone" — the browser never receives it."""
    cfg = _cfg()
    lim = cfg["limits"]
    name = (name or "").strip()
    if not name:
        raise _no("need_name")
    rows = all_projects()
    row = next((p for p in rows if p["id"] == project_id), None) if project_id else None
    if row is None:
        # owner_id is who this project belongs to. Everything else about it — its screens, its
        # links, its manuals, its videos — is visible to that person alone.
        row = {"id": store.new_id(), "key": _key_for(name, {p.get("key") for p in rows}, cfg),
               "screens": [], "links": {}, "created_at": store.now(), "owner_id": owner_id}
        rows.append(row)
    row["name"] = name[:lim["name"]]
    row["source_kind"] = cfg["source_git"] if source_kind == cfg["source_git"] else cfg["source_local"]
    row["folder"] = (folder or "").strip()
    row["git_url"] = (git_url or "").strip()[:lim["git_url"]]
    row["git_branch"] = (git_branch or "").strip()[:lim["git_branch"]]
    if git_token is not None and not str(git_token).startswith(cfg["masked_prefix"]):
        row["git_token"] = str(git_token).strip()[:lim["git_token"]]
    row["site_url"] = (site_url or "").strip()       # where the live app runs, for reference only
    row["updated_at"], row["updated_by"] = store.now(), who
    store.write("projects", rows)
    return row


def public_project(row: dict) -> dict:
    """What the browser is allowed to see: everything except the repository token."""
    out = {k: v for k, v in row.items() if k != "git_token"}
    out["git_token_set"] = bool(row.get("git_token"))
    return out


@_locked
def delete_project(project_id: str) -> None:
    import source
    source.forget(project_id)      # a cloned copy goes with the project that asked for it
    store.write("projects", [p for p in all_projects() if p["id"] != project_id])


@_locked
def set_screens(project_id: str, screens: list[dict]) -> dict:
    """What Setup saved after a scan. Screens are keyed, and a key is what everything else joins on,
    so renaming a LABEL is free but changing a KEY re-points that screen's links."""
    cfg = _cfg()
    lim, key_ok, unsafe = cfg["limits"], _rx(cfg["screen_key_pattern"]), _rx(cfg["key_unsafe"])
    rows = all_projects()
    row = next((p for p in rows if p["id"] == project_id), None)
    if row is None:
        raise _no("no_project")
    clean, taken = [], set()
    for s in screens or []:
        label = str(s.get("label") or "").strip()
        key = str(s.get("key") or "").strip().lower()
        if not label:
            continue
        if not key_ok.search(key):
            key = unsafe.sub("-", label.lower()).strip("-") or cfg["screen_key_fallback"]
        key = _unique(key, taken)
        taken.add(key)
        clean.append({"key": key, "label": label[:lim["screen_label"]],
                      "route": str(s.get("route") or "").strip()[:lim["screen_route"]],
                      "file": str(s.get("file") or "").strip()[:lim["screen_file"]],
                      "group": str(s.get("group") or "").strip()[:lim["screen_group"]]})
    row["screens"] = sorted(clean, key=lambda s: (s["group"].lower(), s["label"].lower()))
    row["scanned_at"], row["updated_at"] = store.now(), store.now()
    # Links whose screen no longer exists would be invisible for ever: drop them with the screen.
    row["links"] = {k: v for k, v in (row.get("links") or {}).items() if k in taken}
    store.write("projects", rows)
    return row


def clean_link(link: dict, cfg: dict | None = None) -> dict | None:
    url = str(link.get("url") or "").strip()
    if not url:
        return None
    cfg = cfg or _cfg()
    lim = cfg["limits"]
    kind = engine.run("projects.link_type", {"url": url, "given": str(link.get("type") or "").strip().lower()})
    out = {"label": str(link.get("label") or "").strip()[:lim["link_label"]], "url": url[:lim["link_url"]],
           "type": kind, "active": link.get("active", True) is not False}
    if link.get("manual_id"):
        out["manual_id"] = str(link["manual_id"])
    return out


@_locked
def set_links(project_id: str, screen_key: str, links: list[dict]) -> list[dict]:
    rows = all_projects()
    row = next((p for p in rows if p["id"] == project_id), None)
    if row is None:
        raise _no("no_project")
    if screen_key not in {s["key"] for s in row.get("screens", [])}:
        raise _no("no_screen")
    cfg = _cfg()
    clean = [x for x in (clean_link(l, cfg) for l in links or []) if x]
    row.setdefault("links", {})[screen_key] = clean
    row["updated_at"] = store.now()
    store.write("projects", rows)
    return clean


@_locked
def merge_manual_links(project_id: str, manual_id: str, targets: list[dict]) -> int:
    """Publishing a manual wires each of its screen pages into that screen's How to Use links.
    A manual's link replaces only ITS OWN earlier link — a YouTube link you added by hand stays.
    Matched on manual_id, so re-publishing never stacks copies."""
    rows = all_projects()
    row = next((p for p in rows if p["id"] == project_id), None)
    if row is None:
        return 0
    links = row.setdefault("links", {})
    known = {s["key"] for s in row.get("screens", [])}
    # Every screen loses this manual's old link first, so a page that stopped naming a screen
    # does not leave a stale link behind.
    for key, rows_ in list(links.items()):
        links[key] = [l for l in rows_ if l.get("manual_id") != manual_id]
    cfg = _cfg()
    added = 0
    for t in targets:
        if t["screen_key"] not in known:
            continue
        links.setdefault(t["screen_key"], []).append(clean_link(t, cfg))
        added += 1
    row["updated_at"] = store.now()
    store.write("projects", rows)
    return added


@_locked
def drop_manual_links(manual_id: str) -> None:
    rows = all_projects()
    for row in rows:
        for key, links in (row.get("links") or {}).items():
            row["links"][key] = [l for l in links if l.get("manual_id") != manual_id]
    store.write("projects", rows)


def public_links(project_key: str) -> dict:
    """What any application fetches to draw its own How to Use button — no login, no framework.
    Inactive links stay configured here but never reach a reader."""
    row = by_key(project_key)
    if not row:
        return {}
    return {key: [{k: l[k] for k in ("label", "url", "type")} for l in links if l.get("active", True) is not False]
            for key, links in (row.get("links") or {}).items() if links}


if __name__ == "__main__":  # ponytail: one runnable self-check
    assert clean_link({"url": "https://youtu.be/x"})["type"] == "youtube"
    assert clean_link({"url": "/m/guide#mp-2"})["type"] == "doc"
    assert clean_link({"url": "https://x.dev/a.MP4?t=1"})["type"] == "video"
    assert clean_link({"url": "https://x.dev/a.mp4", "type": "doc"})["type"] == "doc", "a valid chosen type stands"
    assert clean_link({"url": "https://x.dev", "type": "nonsense"})["type"] == "link"
    assert clean_link({"url": "  "}) is None
    assert _key_for("My App", {"my-app"}) == "my-app-2"
    assert _key_for("!!!", set()) == "project"
    print("projects self-check OK")
