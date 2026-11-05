"""Change log (2026-10-05 owner: "history / change log - field name, old value, new value, when, who did - for both
information and documents ... even earlier versions of a document").

The store tells this module the old and the new value of every watched write (core/store.py watch); this module lines them up
field by field and keeps one entry per changed field in the client's log (sf_changes/client-<cid>) or the firm's
(sf_changes/firm-<fid>). What is watched, what each store holds, what each field is called and which fields are left out are
chips (changes.watch, changes.fields, changes.settings); who is the person signed in on the request (set by app.py).
A document replaced or deleted is kept beside as <fid>.v<n><ext> (intake.py, recon.py), so its entry can offer the old file.
Words: ui.changes. The list: list.changes (core/lists.py).
"""
from __future__ import annotations

import fnmatch
import re
import threading
from contextvars import ContextVar

from fastapi import HTTPException

from core import demo, engine, lists, store

WHO: ContextVar = ContextVar("changes_who", default="")
_LOCK = threading.Lock()


def _product() -> str:
    """The portal's own name, for the system's own changes (chip edition.settings)."""
    import edition  # noqa: PLC0415 - edition imports the engine; changelog loads before it
    return edition.current().get("product_name", "")


def settings() -> dict:
    return engine.run("changes.settings")


def say(key: str, **v) -> str:
    return engine.say("ui.changes", key, **v)


def _watch() -> list[dict]:
    return engine.run("changes.watch")["rows"]


# --- lining up old and new ---------------------------------------------------------------------------------------------

def _flat(v, prefix: str = "", keys: list | None = None) -> dict:
    """{dotted path: scalar}. A list of records is keyed by each record's id (or n); any other list by position."""
    keys = keys or settings()["list_keys"]
    out: dict = {}
    if isinstance(v, dict):
        for k, x in v.items():
            out.update(_flat(x, f"{prefix}{k}.", keys))
    elif isinstance(v, list):
        for i, x in enumerate(v):
            key = next((x[k] for k in keys if isinstance(x, dict) and x.get(k) not in (None, "")), i)
            out.update(_flat(x, f"{prefix}{key}.", keys))
    else:
        out[prefix[:-1]] = v
    return out


def _skipped(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, p) for p in engine.run("changes.fields")["skip"])


def _label(area: str, path: str) -> str:
    """The chip's name for a field: patterns with * for any one part (ids and positions inside a path count as parts)."""
    labels = engine.run("changes.fields")["labels"].get(area) or {}
    generic = re.sub(r"(?<=\.)[^.]+(?=\.)|^[^.]+(?=\.)", "*", path)       # every part but the last may stand for '*'
    for pat, text in labels.items():
        if fnmatch.fnmatchcase(path, pat) or fnmatch.fnmatchcase(generic, pat) or path == pat:
            return text.replace("{path}", path)
    return path


def _value(v) -> str:
    s = "" if v is None else say("yes") if v is True else say("no") if v is False else str(v)
    n = int(settings()["value_max"])
    return s if len(s) <= n else s[: n - 1] + "…"


def _diff(old: dict, new: dict) -> list[tuple[str, object, object]]:
    a, b = _flat(old or {}), _flat(new or {})
    blank = settings()["blank"]          # missing, empty and No all read as nothing: a form filling in its defaults is no change
    return [(p, a.get(p), b.get(p)) for p in sorted(set(a) | set(b))
            if a.get(p) != b.get(p) and not (a.get(p) in blank and b.get(p) in blank) and not _skipped(p)]


# --- the watcher ---------------------------------------------------------------------------------------------------------

def _named(area: str, path: str, v):
    """An id shown by its name where the chip says where names live (a role, a stage, a status)."""
    src = (engine.run("changes.fields").get("value_names") or {}).get(area, {}).get(path)
    if not src or v in (None, ""):
        return v
    chip_id, key, idf, namef = src
    return next((r.get(namef) for r in engine.run(chip_id).get(key) or [] if r.get(idf) == v), v)


def _entry(w: dict, scope: str, field_path: str, old, new, cid: str = "", ay: str = "", file: dict | None = None, area_path: str = "") -> dict:
    old, new = (_named(w["id"], area_path or field_path, v) for v in (old, new))
    return {"id": store.new_id(), "batch": _BATCH.get(), "at": store.now(), "by": WHO.get() or settings()["system_by"].replace("{product}", _product()), "scope": scope, "cid": cid, "ay": ay,
            "area": w["id"], "kind": w["kind"], "path": field_path, "field": _label(w["id"], area_path or field_path),
            "old": _value(old), "new": _value(new), **({"file": file} if file else {})}


def _docs(w: dict, g: dict, old: list, new: list) -> list[dict]:
    """A document list: a file added, removed (kept as its last version), or replaced by a newer version (the older kept)."""
    k = w["list_key"]
    a = {x[k]: x for x in old or [] if isinstance(x, dict)}
    b = {x[k]: x for x in new or [] if isinstance(x, dict)}
    scope, out = f"client-{g['cid']}", []
    name = lambda x: f"{x.get(w['name_field'], '')}" + (f" (v{x.get(w['version_field'], 1)})" if w.get("version_field") else "")  # noqa: E731
    kept = lambda x: {"kept_in": w["kept_in"], "fid": x[k], "v": int(x.get(w["version_field"], 1) or 1)}  # noqa: E731
    titled = lambda e, r: e | ({"field": str(r[w["title_field"]])} if w.get("title_field") and r.get(w["title_field"]) else {})  # noqa: E731
    for fid in sorted(set(a) | set(b)):
        x, y = a.get(fid), b.get(fid)
        n = len(out)
        if x and not y:
            out.append(_entry(w, scope, fid, name(x), "", g["cid"], g["ay"], kept(x), "*"))
        elif y and not x:
            out.append(_entry(w, scope, fid, "", name(y), g["cid"], g["ay"], None, "*") | {"file_new": kept(y)})
        elif x and y and x.get(w.get("version_field", ""), 1) != y.get(w.get("version_field", ""), 1):
            out.append(_entry(w, scope, fid, name(x), name(y), g["cid"], g["ay"], kept(x), "*") | {"file_new": kept(y)})
        out[n:] = [titled(e, y or x) for e in out[n:]]      # the line is named by the document's own title, when the row has one
    return out


_BATCH: ContextVar = ContextVar("changes_batch", default="")


def on_write(name: str, old, new) -> None:
    _BATCH.set(store.new_id())            # every field one save changed belongs to one event on the History screen
    for w in _watch():
        m = re.search(w["pattern"], name)
        if not m:
            continue
        g = m.groupdict()
        if w.get("list_path"):                                 # the list sits inside a record (My return: {"docs": [...]})
            old, new = ((x or {}).get(w["list_path"]) if isinstance(x, dict) else x for x in (old, new))
        if w["kind"] == "doc":
            entries = _docs(w, g, old, new)
        elif w.get("list_key"):
            k = w["list_key"]
            a = {x[k]: x for x in old or [] if isinstance(x, dict) and k in x}
            b = {x[k]: x for x in new or [] if isinstance(x, dict) and k in x}
            entries = []
            for rid in sorted(set(a) | set(b)):
                if a.get(rid) == b.get(rid):        # untouched record: nothing to diff (2026-11-05 seed_large: each save flattened all of them)
                    continue
                x, y = a.get(rid) or {}, b.get(rid) or {}
                owner = (y or x).get(w["scope_field"]) or x.get(w["scope_field"]) or ""   # before narrowing to the watched fields
                if w.get("only"):
                    x, y = ({f: r.get(f) for f in w["only"]} for r in (x, y))
                if not owner:
                    continue
                item = ((b.get(rid) or a.get(rid) or {}).get(w["item_field"]) or "") if w.get("item_field") else ""
                cid = owner if w["scope"] == "client" else ""
                if w.get("named_by") and not (rid in a and rid in b):     # a whole record added or removed: one line, by its name
                    born = rid in b
                    name = next((str(r.get(f)) for f in w["named_by"] for r in (y if born else x,) if r.get(f)), "")
                    e = _entry(w, f"{w['scope']}-{owner}", "", "" if born else name, name if born else "", cid)
                    entries.append(e | {"field": w.get("added" if born else "removed") or say(f"{'add' if born else 'del'}_{w['id']}")})   # a domain's own words
                    continue
                for p, o, n in _diff(x, y):
                    yr = re.match(w["year_path"], p) if w.get("year_path") else None
                    rest, ay = (yr["rest"], yr["ay"]) if yr else (p, "")
                    e = _entry(w, f"{w['scope']}-{owner}", p, o, n, cid, ay, None, rest)
                    entries.append(e | {"field": say("field_of", field=e["field"], item=item)} if item else e)
        else:
            entries = [_entry(w, f"client-{g['cid']}", p, o, n, g["cid"], g.get("ay", ""), None, p) for p, o, n in _diff(old, new)]
        _keep(entries)


def _keep(entries: list[dict]) -> None:
    by: dict = {}
    for e in entries:
        by.setdefault(e["scope"], []).append(e)
    with _LOCK:
        for scope, es in by.items():
            (store.DATA / "sf_changes").mkdir(parents=True, exist_ok=True)
            rows = store.read(f"sf_changes/{scope}", []) + es
            store.write(f"sf_changes/{scope}", rows[-int(settings()["keep_max"]):])


def install() -> None:
    """Watch every store the chip names (app.py calls this once the portal's chips are loaded)."""
    for w in _watch():
        store.watch(w["pattern"], on_write)


# --- reading it ----------------------------------------------------------------------------------------------------------

def listed(u: dict, args: dict) -> list[dict]:
    """One client's log (args cid, optionally ay and kind) - or, with firm=1, the firm's own (its profile and its team)."""
    import clients  # noqa: PLC0415
    import firms  # noqa: PLC0415
    if args.get("firm"):
        if not u.get("firm_id"):
            return []
        rows = store.read(f"sf_changes/firm-{u['firm_id']}", [])
    else:
        cid = str(args.get("cid") or "")
        if cid not in {c["id"] for c in clients._mine(u)} and not firms.is_owner(u):  # noqa: SLF001 - only the firm's own clients
            raise HTTPException(404, say("none"))
        rows = store.read(f"sf_changes/client-{cid}", [])
    ay, kind = str(args.get("ay") or ""), str(args.get("kind") or "")
    every = settings()["yearless_in_every_year"]
    areas = {w["id"]: w.get("area") for w in _watch()}           # a domain's own area words (changes.watch area), else ui.changes
    return [r | {"area_label": areas.get(r["area"]) or say(f"a_{r['area']}")} for r in rows
            if r["old"] != r["new"] and (not ay or r.get("ay") == ay or (every and not r.get("ay"))) and (not kind or r["kind"] == kind)]


def who_of(u: dict) -> str:
    if demo.visitor(u):                    # visitors on a demo site never see each other's names
        return engine.say("ui.demo", "visitor")
    return next((str(u[f]) for f in settings()["who_fields"] if u.get(f)), "")


def kept_file(cid: str, ay: str, kept_in: str, fid: str, v: int):
    """A version of a document: an earlier one as kept beside the current one (<fid>.v<n><ext>), else - the version asked is
    the one in use - the current file (<fid><ext>), so History can offer the new version too."""
    if kept_in not in {w.get("kept_in") for w in _watch()} or not re.fullmatch(r"[0-9a-f]+", fid):
        raise HTTPException(404, say("none"))
    folder = store.DATA / kept_in / cid / ay
    hit = sorted(folder.glob(f"{fid}.v{int(v)}.*")) or [p for p in sorted(folder.glob(f"{fid}.*")) if not re.match(rf"{fid}\.v\d+\.", p.name)
                                                       and p.suffix != ".json"]
    if not hit:
        raise HTTPException(404, say("none"))
    return hit[0]


# 2026-10-07: a self-filer has My return, not Clients & years - their own History said "No such list" (listed() checks the client)
lists.source("changes", listed, screen="clients|myreturn")


if __name__ == "__main__":  # ponytail: a client edit and a replaced statement come out as one entry per field, named by the chip
    import store as _s  # noqa: F401 - registers this portal's chips
    w = next(x for x in _watch() if x["id"] == "client")
    d = _diff({"name": "A", "years": {"2026-27": {"form": "ITR-3", "updated_at": "x"}}}, {"name": "B", "years": {"2026-27": {"form": "ITR-5", "updated_at": "y"}}})
    assert [p for p, _o, _n in d] == ["name", "years.2026-27.form"], d
    assert _diff({"phone": "1"}, {"phone": "1", "father": "", "nri": False}) == []      # defaults filled in by a form save
    assert _label("client", "form") == "Return form" and _label("mapping", "Sheet1!12") == "SF Ref, row Sheet1!12"
    ws = next(x for x in _watch() if x["id"] == "statements")
    es = _docs(ws, {"cid": "c1", "ay": "2026-27"}, [{"id": "f1", "name": "books.xlsx", "version": 1}], [{"id": "f1", "name": "books.xlsx", "version": 2}])
    assert len(es) == 1 and es[0]["old"] == "books.xlsx (v1)" and es[0]["file"] == {"kept_in": "sf_files", "fid": "f1", "v": 1}, es
    assert es[0]["file_new"]["v"] == 2, "the new version is offered too"
    got = []
    _keep = lambda es: got.extend(es)  # noqa: E731 - catch what would be kept
    on_write("users", [{"id": "u1", "firm_id": "f1", "firm_role": "preparer", "password": "x"}],
             [{"id": "u1", "firm_id": "f1", "firm_role": "reviewer", "password": "y"}])
    assert [(e["scope"], e["field"], e["old"], e["new"]) for e in got] == [("firm-f1", "Role", "Tax preparer", "Reviewer")], got   # never the password
    got.clear()
    on_write("sf_clients.json", [], [{"id": "c9", "name": "Ramesh Iyer", "pan": "ABCPI1234K", "phone": "98400", "years": {"2026-27": {"form": "ITR-1"}}}])
    assert [(e["field"], e["old"], e["new"]) for e in got] == [("Client added", "", "Ramesh Iyer")], got           # one line, not one per field
    assert who_of({"demo": True, "name": "Anita Rao", "email": "a@x"}) == engine.say("ui.demo", "visitor")   # visitors never see each other
    print("changelog OK")
