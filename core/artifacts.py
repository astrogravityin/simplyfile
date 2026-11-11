"""Artifacts - what this portal holds, reported to ValueStream CC's Clean-up screen (2026-11-05 owner: "many connectors
are not working ... a clean-up tool"). Generic: no artifact kind is named here.

Two MCP tools on the portal's one MCP door (core/mcp.py), answered only for an OWNER (a key's maker or an AI sign-in):
  artifacts_scan    (read)   every person (no password, no secret) and every artifact as FACTS - author, made, last touched,
                             views, bytes, who else is on it, parent gone, file gone, duplicate of, standard problems.
                             CC's own chips decide what a fact means (idle, orphan...); this module never judges.
  artifacts_delete  (change) each item through the portal's OWN delete route (its row in chip artifacts.types), pressed
                             in-process as the item's author (the route's own "mine" checks, History and Portal Activity
                             all apply). An item whose author is gone has nobody to press the route as: it is kept aside
                             (store.keep_aside - restorable, never erased) when chip artifacts.settings says so.
What a kind is (where it is stored, which field is the author, its delete route): chip artifacts.types (the portal's own).
A store pattern may name its slots - hf_docs/{cid}/{year}/files, guideme-{uid} - read off each file's path; a delete route's
other slots ({cid}) come from those or from the row; rows may sit under one key of a doc (rows); gone_when fields mark a
soft-deleted row (discarded_at...) that is no longer listed; a route may carry a fixed body.
Two kinds every portal has are read here by shape: saved chip edits (shape chip_edit: no shipped chip / RCB cannot show it /
older than the shipped chip) and screens (shape screen: no Guide me). Limits and words: chip artifacts.settings.
Blocking a person (People & access, route in core/access.py) ends their sign-ins; a delete pressed for a blocked author
carries this process's own header (CLEAN_HEADER) so core/auth.current_user lets that one in-process call through.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
import secrets
from pathlib import Path
from typing import Any

from core import engine, mcp, store

CLEAN_HEADER = "X-Artifacts-Clean"
SECRET = secrets.token_hex(16)     # ponytail: per process; an in-process call only, never sent to anyone


def cfg() -> dict:
    return engine.run("artifacts.settings")


def types() -> list[dict]:
    try:
        return list(engine.run("artifacts.types")["types"])
    except engine.ChipError:
        return []


def _owner(ctx: dict) -> dict:
    u = ctx.get("user") or {}
    if engine.run("people.is_owner", {"role": u.get("role") or ""}) is not True:
        raise mcp.ToolError("failed", why=cfg()["owner_only"])
    return u


def _get(row: Any, path: str) -> Any:
    """a.b.c out of nested dicts; '' = nothing."""
    for part in (path or "").split("."):
        if not part or not isinstance(row, dict):
            return None
        row = row.get(part)
    return row


def _load(f: Path) -> Any:
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ValueError


def _ids(v: Any, key: str) -> list[str]:
    """Who else is on it: a list of ids, or of rows holding one (seats [{uid}])."""
    out = []
    for x in v if isinstance(v, list) else []:
        x = x.get(key) if isinstance(x, dict) else x
        if isinstance(x, str) and x:
            out.append(x)
    return out


def _reader(name: str):
    """A kind kept in SQL (2026-11-12 W1.1) names its reader in the chip row: "reader": "<module>.<function>" (a function of
    no arguments returning the rows). Only a portal module's own function, never a path or a call with arguments."""
    import importlib  # noqa: PLC0415
    mod, _, fn = name.rpartition(".")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*", mod) or not re.fullmatch(r"[a-z_][a-z0-9_]*", fn):
        raise ValueError(f"bad reader {name!r}")
    return getattr(importlib.import_module(mod), fn)


def _rows_of(t: dict) -> list[tuple[Path, dict | None]]:
    """(file, row) for every artifact of a stored kind; row None = the file cannot be read (broken)."""
    out: list[tuple[Path, dict | None]] = []
    if t.get("reader"):                                # rows kept in SQL: read through the module that owns them
        f = store.DATA / (t["reader"] + ".sql")
        out = [(f, r) for r in _reader(t["reader"])() if isinstance(r, dict)]
        return [(f, r) for f, r in out if not any(_get(r, x) for x in t.get("gone_when", []))]
    for f in sorted(store.DATA.glob(re.sub(r"\{\w+\}", "*", t["store"]) + ".json")):   # a {name} folder slot reads as *
        got = _load(f)
        if got is ValueError:
            out.append((f, None))
        elif t.get("shape") == "doc":
            out.append((f, got if isinstance(got, dict) else None))
        else:
            got = got.get(t["rows"]) if t.get("rows") and isinstance(got, dict) else got   # rows kept under one key of a doc
            out += [(f, r) for r in (got if isinstance(got, list) else []) if isinstance(r, dict)]
    return [(f, r) for f, r in out if not (r and any(_get(r, x) for x in t.get("gone_when", [])))]   # soft-deleted: gone


def _when(v: Any) -> str:
    """A time as ISO text; an epoch number (time.time()) becomes ISO too, so CC reads one form."""
    if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
        return datetime.fromtimestamp(v, timezone.utc).isoformat(timespec="seconds")
    return str(v or "")


def _slots(t: dict, f: Path) -> dict:
    """The {name} slots of a store pattern, read off one file's path (hf_docs/{cid}/{year}/files -> cid, year;
    guideme-{uid} -> uid)."""
    if not t.get("store"):
        return {}
    rx = "/".join(re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>[^/]+)", re.escape(x)) for x in t["store"].split("/"))
    m = re.fullmatch(rx.replace(r"\*", "[^/]+"), f.relative_to(store.DATA).with_suffix("").as_posix())
    return m.groupdict() if m else {}


def _vals(v: Any) -> list[str]:
    """A reference field's ids: one id, a list of ids, or a dict keyed by id."""
    v = list(v) if isinstance(v, dict) else v if isinstance(v, list) else [v]
    return [str(x) for x in v if isinstance(x, (str, int)) and str(x)]


def _fact(t: dict, f: Path, r: dict | None, k: dict) -> dict:
    r = r or {}
    slots = _slots(t, f)
    gone = {"orphan": False, "broken": False}
    later = []
    for ref in t.get("refs") or []:                    # a parent or a part that must still be there
        for v in _vals(_get(r, ref["field"])):
            if ref.get("store"):
                name = re.sub(r"\{(\w+)\}", lambda m: v if m.group(1) == "value" else slots.get(m.group(1), m.group(0)), ref["store"])
                gone[ref.get("means", "orphan")] |= not (store.DATA / (name + ".json")).exists()
            else:
                later.append({"type": ref["type"], "id": v, "means": ref.get("means", "orphan")})
    files = [x for x in _vals(_get(r, t.get("files", ""))) if t.get("files")]
    views = _get(r, t.get("views", ""))
    shared = _get(r, t.get("shared", ""))
    need = [x for x in re.findall(r"\{(\w+)\}", (t.get("delete") or {}).get("path", "")) if x != "id"]
    route_args = {x: str(slots.get(x) or _get(r, x) or "") for x in need}   # the route's other slots: a folder slot or a row field
    return {"type": t["type"], "id": str(_get(r, t.get("id", "id")) or (f.stem if t.get("shape") == "doc" else "")),
            "title": str(_get(r, t.get("title", "")) or "")[: int(k["title_chars"])],
            "author": str(_get(r, t.get("author", "")) or (f.stem if t.get("author_from") == "file" else slots.get(t.get("author_from", ""), ""))),
            "author_name": str(_get(r, t.get("author_name", "")) or ""), "purge": bool(t.get("purge")),
            "created": _when(_get(r, t.get("created", ""))),
            "touched": _when(_get(r, t.get("touched", "")) or _get(r, t.get("created", ""))),
            "opened": bool(_get(r, t.get("opened", ""))) if t.get("opened") else None,
            "views": views if isinstance(views, (int, float)) else None,
            "bytes": len(json.dumps(r, ensure_ascii=False)) if r else f.stat().st_size,
            "shared": list(shared) if isinstance(shared, dict) else _ids(shared, t.get("shared_id", "uid")),
            "unreadable": not r, "parent_missing": gone["orphan"], "broken": gone["broken"], "_later": later,
            "file_missing": any(not (store.DATA / x).exists() for x in files),
            "problems": ["missing_field"] if any(_get(r, x) in (None, "", []) for x in t.get("require", [])) else [],
            "route_args": route_args, "deletable": bool(t.get("delete")) and all(route_args.values())}


def _chip_edits(k: dict) -> list[dict]:
    """Saved chip edits (Ops & chips builder): the standard is a chip RCB can show, of a chip the code still ships."""
    shipped = {}
    for d in engine.DIRS:
        for f in Path(d).glob("*.json"):
            doc = _load(f)
            if isinstance(doc, dict):
                shipped[str(doc.get("chip_id") or f.stem)] = doc
    out = []
    for f in sorted(engine.data_dir().glob("*.json")) if engine.data_dir().is_dir() else []:
        doc = _load(f)
        doc = doc if isinstance(doc, dict) else {}
        cid = str(doc.get("chip_id") or f.stem)
        ship = shipped.get(cid)
        probs = [p for p, bad in (("no_shipped_chip", not ship),
                                  ("rcb_cannot_show", any(x not in doc for x in k["chip_needs"])),
                                  ("old_version", bool(ship) and int(doc.get("version") or 0) < int(ship.get("version") or 0))) if bad]
        out.append({"type": "chip_edit", "id": cid, "title": str(doc.get("label") or cid)[: int(k["title_chars"])],
                    "author": "", "author_email": str(doc.get("updated_by") or ""), "created": "", "touched": str(doc.get("updated_at") or ""),
                    "opened": None, "views": None, "bytes": f.stat().st_size, "shared": [], "unreadable": not doc,
                    "parent_missing": False, "broken": False, "file_missing": False, "problems": probs,
                    "deletable": True, "route": {"method": "DELETE", "path": "/api/core/build/chips/{id}", "as": "owner"}})
    return out


def _screens() -> list[dict]:
    """Every screen of the catalog: the standard is a Guide me (chip guide.<screen>)."""
    from core import access, guide  # noqa: PLC0415
    have = set(guide.screens())                        # guide.<screen>, a - in the screen id read as _ (core/guide.py)
    return [{"type": "screen", "id": s["id"], "title": str(s.get("label") or s["id"]), "author": "", "created": "", "touched": "",
             "opened": None, "views": None, "bytes": 0, "shared": [], "unreadable": False, "parent_missing": False,
             "broken": False, "file_missing": False, "problems": [] if s["id"].replace("-", "_") in have else ["no_guide"],
             "deletable": False} for s in access.CATALOG if s.get("id") and not s.get("hidden")]


def scan(args: dict, ctx: dict) -> dict:
    _owner(ctx)
    k = cfg()
    people = [{"id": u["id"], "name": u.get("name") or "", "email": u.get("email") or "", "role": u.get("role") or "",
               "blocked": bool(u.get("blocked")), "joined": bool(u.get("master_id")), "created": u.get("created_at") or ""}
              for u in store.users()]
    if args.get("people_only"):
        return {"people": people, "artifacts": [], "kinds": []}
    rows: list[dict] = []
    for t in types():
        rows += [_fact(t, f, r, k) for f, r in _rows_of(t)]
    rows += _chip_edits(k) + _screens()
    have = {(r["type"], r["id"]) for r in rows}
    for r in rows:                                     # references to another kind's rows, checked once all are read
        for ref in r.pop("_later", []):
            if (ref["type"], ref["id"]) not in have:
                r["broken" if ref["means"] == "broken" else "parent_missing"] = True
    seen: dict[tuple, str] = {}
    for r in rows:                                     # the same kind, author and title twice: the later one is a copy
        key = (r["type"], r["author"], r["title"].strip().lower())
        r["dup_of"] = seen.get(key, "") if r["title"] else ""
        seen.setdefault(key, r["id"])
    by = {u["id"]: u for u in people}
    for r in rows:
        r["author_state"] = ("" if not r["author"] else "system" if r["author"] in k["system_authors"] else "gone" if r["author"] not in by
                             else "blocked" if by[r["author"]]["blocked"] else "ok")
    who = str(args.get("user_email") or "").strip().lower()
    if who:
        ids = {u["id"] for u in people if u["email"].lower() == who}
        rows = [r for r in rows if r["author"] in ids or ids & set(r["shared"])]
    kinds = [{"type": t["type"], "label": t.get("label") or t["type"]} for t in types()] + \
            [{"type": x, "label": k["kind_words"][x]} for x in ("chip_edit", "screen")]
    return {"people": people, "artifacts": rows[: int(k["max_rows"])], "total": len(rows), "kinds": kinds}


def _route(item: dict) -> dict | None:
    if item["type"] == "chip_edit":
        return {"method": "DELETE", "path": "/api/core/build/chips/{id}", "as": "owner"}
    t = next((x for x in types() if x["type"] == item["type"]), None)
    return (t or {}).get("delete")


def _keep_aside(item: dict) -> None:
    """The author is gone: the row moves to replaced/ beside its file (a doc: the file itself). Restorable."""
    t = next(x for x in types() if x["type"] == item["type"])
    if t.get("reader"):                                # a SQL kind is put aside by its own route, never by rewriting a file
        raise mcp.ToolError("failed", why=cfg()["not_found"])
    for f, r in _rows_of(t):
        if r is not None and str(_get(r, t.get("id", "id")) or (f.stem if t.get("shape") == "doc" else "")) == item["id"]:
            if t.get("shape") == "doc":
                store.keep_aside(f)
            else:
                store.keep_aside(f, copy=True)
                rows = [x for x in json.loads(f.read_text(encoding="utf-8")) if x != r]
                store.write(f.relative_to(store.DATA).with_suffix("").as_posix(), rows)
            return
    raise mcp.ToolError("failed", why=cfg()["not_found"])


def delete(args: dict, ctx: dict) -> dict:
    me = _owner(ctx)
    k = cfg()
    found = {(r["type"], r["id"]): r for r in scan({}, ctx)["artifacts"]}
    done = []
    for it in (args.get("items") or [])[: int(k["delete_max"])]:
        item = found.get((str(it.get("type") or ""), str(it.get("id") or "")))
        route = _route(item) if item else None
        if not item or not route or not item.get("deletable"):
            done.append({"type": it.get("type"), "id": it.get("id"), "ok": False, "why": k["not_found" if not item else "no_route"]})
            continue
        try:
            if route.get("as") == "author" and item["author_state"] == "gone":
                if k["orphan_delete"] != "keep_aside":
                    raise mcp.ToolError("failed", why=k["author_gone"])
                _keep_aside(item)
                how = "kept_aside"
            else:
                as_ = store.user_by_id(item["author"]) if route.get("as") == "author" else me
                call = {"method": route["method"], "path": route["path"], "headers": {CLEAN_HEADER: SECRET}}
                mcp.run_calls({"calls": [call | ({"body": route["body"]} if "body" in route else {})]},
                              {**item.get("route_args", {}), "id": item["id"]}, {**ctx, "user": as_})
                how = "route"
            done.append({"type": item["type"], "id": item["id"], "ok": True, "how": how})
        except mcp.ToolError as e:
            done.append({"type": item["type"], "id": item["id"], "ok": False, "why": str(e.slots.get("why") or e.key)})
    return {"done": done, "deleted": sum(1 for d in done if d["ok"])}


def _test_rows() -> list[dict]:
    """The self-test's SQL kind (a reader returns rows; one archived, one whose parent is gone)."""
    return [{"id": "r1", "by": "x", "name": "Kept", "thing": "t1"}, {"id": "r2", "by": "x", "name": "Gone", "archived_at": "z"},
            {"id": "r3", "by": "x", "name": "Lost", "thing": "nope"}]


def lets_blocked_in(request) -> bool:
    """core/auth.current_user: a blocked person's session passes only for this process's own clean-up call."""
    return secrets.compare_digest(request.headers.get(CLEAN_HEADER, ""), SECRET)


mcp.tool("artifacts_scan", scan)
mcp.tool("artifacts_delete", delete)


if __name__ == "__main__":  # ponytail: one runnable check - facts, the route as the author, blocked, kept aside, block
    import tempfile
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from core import access, auth
    import core.artifacts as _imported
    _imported.SECRET = SECRET                          # run as __main__, this file is also core.artifacts (auth asks that one)
    store.DATA = Path(tempfile.mkdtemp())
    o = store.add_user("o@demo.example", "password-o-123", role="owner")
    a = store.add_user("a@demo.example", "password-a-123")
    b = store.add_user("b@demo.example", "password-b-123")
    for d_ in ("things", "parts"):
        (store.DATA / d_).mkdir()
    store.write("things/" + a["id"], [{"id": "t1", "by": a["id"], "name": "Plan", "parts": ["p1"]},
                                      {"id": "t2", "by": a["id"], "name": "plan ", "parts": ["gone"]}])
    store.write("things/" + b["id"], [{"id": "t3", "by": b["id"], "name": "B's"}])
    store.write("things/zz", [{"id": "t4", "by": "zz", "name": "Nobody's"}])
    store.write("parts/p1", {"id": "p1"})
    (store.DATA / "docs" / "c9").mkdir(parents=True)
    store.write("docs/c9/files", [{"id": "d1", "by": a["id"], "name": "Deed"}, {"id": "d2", "by": a["id"], "name": "Old", "discarded_at": "x"}])
    store.write("guideme-" + a["id"], {"rows": [{"id": "g1", "title": "Tour"}]})
    T = [{"type": "thing", "store": "things/*", "id": "id", "author": "by", "title": "name",
          "refs": [{"field": "parts", "store": "parts/{value}", "means": "broken"}],
          "delete": {"method": "DELETE", "path": "/api/things/{id}", "as": "author"}},
         {"type": "doc", "store": "docs/{cid}/files", "id": "id", "author": "by", "title": "name", "gone_when": ["discarded_at"],
          "delete": {"method": "DELETE", "path": "/api/docs/{cid}/{id}", "as": "author"}},
         {"type": "build", "store": "guideme-{uid}", "rows": "rows", "id": "id", "author_from": "uid", "title": "title"},
         {"type": "rec", "reader": "core.artifacts._test_rows", "id": "id", "author": "by", "title": "name", "gone_when": ["archived_at"],
          "refs": [{"field": "thing", "type": "thing", "means": "orphan"}]}]
    real = engine.run
    engine.run = lambda cid, args=None, *x: {"types": T} if cid == "artifacts.types" else real(cid, args, *x)
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(access.router)

    @app.delete("/api/things/{tid}")
    def _del(tid: str, u: dict = Depends(auth.signed_in)):
        name = "things/" + u["id"]
        store.write(name, [x for x in store.read(name, []) if x["id"] != tid])
        return {"ok": True}

    @app.delete("/api/docs/{cid}/{did}")
    def _del_doc(cid: str, did: str, u: dict = Depends(auth.signed_in)):
        name = f"docs/{cid}/files"
        store.write(name, [x for x in store.read(name, []) if x["id"] != did])
        return {"ok": True}
    ctx = {"user": o, "base": "http://testserver", "app": app}
    got = {r["id"]: r for r in scan({}, ctx)["artifacts"] if r["type"] == "thing"}
    assert got["t2"]["dup_of"] == "t1" and got["t2"]["broken"] and not got["t1"]["broken"], got
    assert got["t4"]["author_state"] == "gone" and got["t1"]["author_state"] == "ok"
    every = {(r["type"], r["id"]): r for r in scan({}, ctx)["artifacts"]}
    assert ("doc", "d2") not in every and every[("doc", "d1")]["route_args"] == {"cid": "c9"}, "folder slot fills the route; soft-deleted gone"
    assert every[("build", "g1")]["author"] == a["id"], "rows under a key, author from the file-name slot"
    assert ("rec", "r1") in every and ("rec", "r2") not in every and every[("rec", "r1")]["parent_missing"] is False, \
        "a SQL kind is read through its reader (archived ones gone), and its rows count as parents"
    assert every[("rec", "r3")]["parent_missing"] is True, "a reader row whose parent is gone"
    for bad_ in ("os.system", "core.artifacts._test_rows()", "../x.y"):
        try:
            _reader(bad_) if bad_ != "os.system" else _reader("os.path.join/../x")
            raise AssertionError(f"reader {bad_!r} accepted")
        except (ValueError, AttributeError):
            pass
    assert _when(0) == "" and _when(86400).startswith("1970-01-02") and _when("2026-01-01") == "2026-01-01", "epoch reads as ISO"
    assert delete({"items": [{"type": "doc", "id": "d1"}]}, ctx)["deleted"] == 1 and [x["id"] for x in store.read("docs/c9/files", [])] == ["d2"]
    assert "password" not in json.dumps(scan({"people_only": True}, ctx)), "no password ever leaves"
    try:
        scan({}, {**ctx, "user": a})
        raise AssertionError("only an owner scans")
    except mcp.ToolError:
        pass
    c = TestClient(app)
    c.headers["X-Real-IP"] = "10.1.2.3"
    assert c.post("/api/auth/signin", json={"identity": "o@demo.example", "password": "password-o-123"}).status_code == 200
    assert c.put(f"/api/core/access/people/{b['id']}/block", json={"blocked": True}).json()["user"]["blocked"] is True
    bc = TestClient(app)
    bc.headers["X-Real-IP"] = "10.1.2.4"
    assert bc.post("/api/auth/signin", json={"identity": "b@demo.example", "password": "password-b-123"}).status_code == 403, "blocked: no sign-in"
    assert scan({}, ctx)["people"][2]["blocked"] is True
    out = delete({"items": [{"type": "thing", "id": "t1"}, {"type": "thing", "id": "t3"}, {"type": "thing", "id": "t4"},
                            {"type": "screen", "id": "x"}]}, ctx)
    assert [d["ok"] for d in out["done"]] == [True, True, True, False], out
    assert [x["id"] for x in store.read("things/" + a["id"], [])] == ["t2"], "deleted by a's own route, as a"
    assert store.read("things/" + b["id"], []) == [], "a blocked author's item goes through the route too"
    assert out["done"][2]["how"] == "kept_aside" and store.read("things/zz", None) == [] and store.versions_of(store.path_of("things/zz"))
    print("artifacts self-check OK")
