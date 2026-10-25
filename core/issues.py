"""Reports and feedback - ONE framework (2026-09-28 Report an issue; 2026-10-03 owner merged a sibling portal's feedback cycle into
it: "We already have Report Issue framework - why can't we use that ... chip ops only").

A KIND (chip issues.kinds) is everything that differs between notes: its settings chip (limits, statuses, where-fields,
screenshot types, a new note's marks, the marks an answer leaves), where its rows and screenshots live, its decision chips
(file / answer / see / remove), how each side hears (bell, balloon, banner) and its words. The module that owns what a
note is ABOUT registers one function, about(user, ref) -> facts (owner_id, title, link, answer_link, open, keeper) - facts
only; every yes / no is the kind's chip.
  issue           Report an issue from any screen -> whoever holds the Reported issues screen; the reply is a banner

  <store>/<ref>          the notes on one thing (an issue's store is one file, no ref)
  <shots>/<ref>/         their screenshots, beside the rows, never inline
  issues_by/<uid>        {"kind|ref": when} - where this person wrote: My reports (list my_reports) reads only those
  issues_unseen/<uid>    banner replies waiting for them - a page load never reads every report
"""
from __future__ import annotations

import base64
import html
import io
import json
import re
from collections.abc import Callable

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from core import access, auth, bell, engine, limits, lists, store

router = APIRouter()
_ABOUT: dict[str, Callable[[dict | None, str], dict]] = {}


def frame() -> dict:
    """The framework's own knobs (chip issues.kinds): default / queue kind, stores, field lists, patterns."""
    return engine.run("issues.kinds")


def kinds() -> dict:
    return frame()["kinds"]


def _kind(kind: str) -> dict:
    k = kinds().get(kind or frame()["default_kind"])
    if not k:
        raise HTTPException(404, say("no_issue"))
    return k


def settings(kind: str = "") -> dict:
    return engine.run(_kind(kind)["settings"])


def say(key: str, kind: str = "", **values) -> str:
    """The kind's own sentence when its row has one, else the shared one (chip issues.messages)."""
    own = (kinds().get(kind or frame()["default_kind"]) or {}).get("messages", {}).get(key)
    return own.format(**values) if own else engine.say("issues.messages", key, **values)


def about(kind: str, fn: Callable[[dict | None, str], dict]) -> None:
    """The owning module tells what a note is about: about(user, ref) -> {owner_id, title, link, answer_link, open, keeper}.
    It raises its own 404 when the person may not see the thing."""
    _ABOUT[kind] = fn


def _about(user: dict | None, kind: str, ref: str) -> dict:
    k = _kind(kind)
    if bool(k["per_ref"]) != bool(ref):
        raise HTTPException(404, say("no_issue", kind))
    if kind in _ABOUT:
        return _ABOUT[kind](user, ref)
    if k.get("about"):
        return dict(k["about"])                          # a kind about nothing in particular names its facts in its chip row
    raise HTTPException(404, say("no_issue", kind))


def _name(kind: str, ref: str) -> str:
    name = _kind(kind)["store"].format(ref=ref)
    store.path_of(name).parent.mkdir(parents=True, exist_ok=True)
    return name


def _shots(kind: str, ref: str):
    return store.DATA / _kind(kind)["shots"].format(ref=ref)


def _norm(r: dict) -> dict:
    """A row written before the merge reads as today's (chip issues.kinds legacy_keys)."""
    old = frame()["legacy_keys"]
    return {old.get(k, k): v for k, v in r.items()} if any(k in r for k in old) else r


def _rows(kind: str, ref: str) -> list[dict]:
    return [_norm(r) for r in store.read(_name(kind, ref), []) or []]


def _facts(user: dict | None, kind: str, a: dict, row: dict | None = None) -> dict:
    """Every fact a decision chip of any kind reads; each chip takes the ones it names."""
    uid = (user or {}).get("id") or ""
    scr = _kind(kind)["screen"]
    mine = bool(row) and bool(uid) and row["by"] == uid
    return {"signed_in": bool(uid), "is_maker": bool(uid) and a["owner_id"] == uid, "is_owner": engine.run("issues.is_owner", {"role": (user or {}).get("role") or ""}) is True,
            "is_giver": mine, "is_writer": mine, "is_keeper": bool(a.get("keeper")), "on": bool(a.get("open")),
            "may_screen": bool(scr) and bool(user) and access.may(user, scr)}


def _may(what: str, user: dict | None, kind: str, a: dict, row: dict | None = None) -> bool:
    f = _facts(user, kind, a, row)
    if what == "see":
        f["may_answer"] = _may("answer", user, kind, a, row)
    return bool(user) and engine.run(_kind(kind)["chips"][what], f) is True


def may(what: str, user: dict | None, kind: str, ref: str) -> bool:
    """For a page: may this person file / answer notes on this thing (no note in hand)."""
    return _may(what, user, kind, _about(user, kind, ref))


def _word(kind: str, word: str) -> str:
    return str(engine.run(_kind(kind)["words"]).get(word, word))


def _public(user: dict | None, kind: str, ref: str, a: dict, r: dict) -> dict:
    """A note as its giver or its answerer sees it: a name, never the account id (the email only where the kind shows it)."""
    k, s = _kind(kind), settings(kind)
    may_answer = _may("answer", user, kind, a, r)
    out = {x: r.get(x, "") for x in frame()["public_fields"]}
    out |= {"about": r.get("about") or a["title"], "link": r.get("link") or a["link"]}   # notes from before 2026-10-03 kept neither
    return out | {"kind": kind, "ref": ref, "place": r.get("place") or {}, "shot": bool(r.get("shot")),
                  "files": [{x: f.get(x, "") for x in ("n", "kind", "name", "transcript")} for f in r.get("files") or []],
                  "mine": bool(user) and r["by"] == user["id"], "may_answer": may_answer, "may_remove": _may("remove", user, kind, a, r),
                  "statuses": [st | {"label": _word(kind, st["word"])} for st in s["statuses"]],
                  "status_label": next((_word(kind, st["word"]) for st in s["statuses"] if st["id"] == r.get("status")), r.get("status", "")),
                  "kind_label": _word(kind, k["label_word"]),
                  "email": r.get("email", "") if engine.run("issues.shows_email", {"show_email": bool(k["show_email"]), "may_answer": may_answer}) is True else ""}


def _picture(data: str, s: dict, kind: str) -> tuple[bytes, str]:
    """A pasted screenshot (data URL): a real picture of an allowed type, within the size."""
    from PIL import Image  # noqa: PLC0415
    m = re.match(frame()["data_url_pattern"], data, re.S)
    if not m:
        raise HTTPException(400, say("shot_not_image", kind))
    raw = base64.b64decode(m.group(2), validate=False)
    if limits.too_big(len(raw), s["shot_max_mb"]):
        raise HTTPException(400, say("shot_too_big", kind, mb=s["shot_max_mb"]))
    try:
        ext = str(Image.open(io.BytesIO(raw)).format or "").lower()
    except Exception:  # noqa: BLE001 - not a picture at all
        ext = ""
    if not limits.one_of(ext, s["shot_types"]):
        raise HTTPException(400, say("shot_not_image", kind))
    return raw, ext


def _attachment(f: dict, s: dict, kind: str) -> tuple[str, str, bytes, str, str]:
    """One picture or voice note of a note: (kind, extension, bytes, name, the words written down while it was spoken)."""
    data = str(f.get("data") or "")
    if data.startswith("data:image/"):
        raw, ext = _picture(data, s, kind)
        return "image", ext, raw, limits.clip(f.get("name"), s["place_max"]), ""
    m = re.match(r"^data:audio/([a-z0-9]+)[^,]*;base64,(.+)$", data, re.S)
    if not m or not limits.one_of(m.group(1), s.get("voice_types", [])):
        raise HTTPException(400, say("shot_not_image", kind))
    raw = base64.b64decode(m.group(2), validate=False)
    if limits.too_big(len(raw), s.get("voice_max_mb", 0)):
        raise HTTPException(400, say("shot_too_big", kind, mb=s.get("voice_max_mb", 0)))
    return "audio", m.group(1), raw, limits.clip(f.get("name"), s["place_max"]), limits.clip(f.get("transcript"), s["text_max"])


def attachment(user: dict, iid: str, n: int, kind: str = "", ref: str = ""):
    a = _about(user, kind, ref)
    r = _find(_rows(kind, ref), iid, kind)
    f = next((x for x in r.get("files") or [] if x["n"] == n), None)
    if not f or not _may("see", user, kind, a, r):
        raise HTTPException(404, say("no_issue", kind))
    return _shots(kind, ref) / f["file"]


def _index(uid: str, key: str, at: str | None) -> None:
    """Where this person wrote (My reports): at = when, None = they have no note there any more."""
    with store._LOCK:                                    # noqa: SLF001
        d = dict(_where_i_wrote(uid))                   # RLock: the first time also finds notes written before the index
        if at is None:
            d.pop(key, None)
        else:
            d[key] = at
        _write(frame()["index_store"], uid, d)


def file(user: dict, body: dict) -> dict:
    """File one note of a kind. `ref` = what it is about (a work id); `surface` / `context` = the screen it came from."""
    kind, ref = str(body.get("kind") or frame()["default_kind"]), str(body.get("ref") or "")
    a, s, k = _about(user, kind, ref), settings(kind), _kind(kind)
    if not _may("file", user, kind, a):
        raise HTTPException(403, say("off", kind))
    title = limits.clip(" ".join(str(body.get("title") or "").split()), s["title_max"]) if "title_max" in s else ""
    if s["needs_title"] and not title:
        raise HTTPException(400, say("no_title", kind))
    text = limits.clip(str(body.get("text") or body.get("body") or "").strip(), s["text_max"])
    if not text:
        raise HTTPException(400, say("no_body", kind))
    if s["rate"] and not limits.allow(s["rate"], user["id"]):
        raise HTTPException(429, say("too_many", kind))
    shot = str(body.get("screenshot") or "").strip()
    raw, ext = _picture(shot, s, kind) if shot else (b"", "")
    files = [_attachment(f, s, kind) for f in (body.get("attachments") or [])[: int(s.get("files_max", 0))] if isinstance(f, dict) and f.get("data")]
    with store._LOCK:                                    # noqa: SLF001
        rows = _rows(kind, ref)
        mine = [r["at"] for r in rows if r["by"] == user["id"]]
        if mine and s["gap_seconds"] and limits.too_soon(store.seconds_since(max(mine)), s["gap_seconds"]):
            raise HTTPException(429, say("too_fast", kind, s=s["gap_seconds"]))
        r = dict(s["new_row"]) | {"id": store.new_id(), "by": user["id"], "name": user.get("name") or user.get("username") or "",
                                  "email": user.get("email") or "", "title": title, "text": text,
                                  "place": {p: limits.clip(body.get(p), s["place_max"]) for p in s["place_fields"]},
                                  "surface": limits.clip(body.get("surface"), s["place_max"]), "context": limits.clip(body.get("context"), s["place_max"]),
                                  "about": a["title"], "link": a["link"], "at": store.now(), "updated": store.now(), "answered_by": ""}
        if ext:
            r["shot"] = f"{r['id']}.{ext}"
            _shots(kind, ref).mkdir(parents=True, exist_ok=True)
            (_shots(kind, ref) / r["shot"]).write_bytes(raw)
        if files:   # 2026-10-04 the bottom bar's Issues: several pictures and voice notes, each with the words written down
            _shots(kind, ref).mkdir(parents=True, exist_ok=True)
            r["files"] = []
            for n, (fk, fext, fraw, fname, words) in enumerate(files, 1):
                (_shots(kind, ref) / f"{r['id']}-{n}.{fext}").write_bytes(fraw)
                r["files"].append({"n": n, "kind": fk, "file": f"{r['id']}-{n}.{fext}", "name": fname, "transcript": words})
        store.write(_name(kind, ref), [*rows, r])
    _index(user["id"], f"{kind}|{ref}", r["at"])
    if k["tell_answerer"] == "bell" and a["owner_id"]:
        bell.push(a["owner_id"], say("bell_new", kind, who=r["name"] or say("someone", kind), title=a["title"]), a["answer_link"].lstrip("/"))
    return _public(user, kind, ref, a, r) | {"message": say("filed", kind)}


def _find(rows: list[dict], iid: str, kind: str) -> dict:
    r = next((x for x in rows if x["id"] == iid), None)
    if not r:
        raise HTTPException(404, say("no_issue", kind))
    return r


def answer(user: dict, iid: str, body: dict, kind: str = "", ref: str = "") -> dict:
    """The answerer gives a status, a reply and the date it was acted on; the giver hears it the kind's way."""
    a, s, k = _about(user, kind, ref), settings(kind), _kind(kind)
    with store._LOCK:                                    # noqa: SLF001
        rows = _rows(kind, ref)
        r = _find(rows, iid, kind)
        if not _may("answer", user, kind, a, r):
            raise HTTPException(403, say("not_yours", kind))
        if "status" in body:
            if not limits.one_of(str(body["status"]), [st["id"] for st in s["statuses"]]):
                raise HTTPException(400, say("bad_status", kind))
            r["status"] = str(body["status"])
        if "reply" in body:
            r["reply"] = limits.clip(str(body["reply"] or "").strip(), s["text_max"])
        if "action_date" in body:
            r["action_date"] = limits.clip(body["action_date"], s["place_max"])
        r.update(s["answered_marks"], updated=store.now(), answered_by=next((user[f] for f in frame()["answered_by_fields"] if user.get(f)), ""))
        store.write(_name(kind, ref), rows)
    if r["by"] != user["id"]:
        if k["tell_giver"] == "bell":
            bell.push(r["by"], say("bell_reply", kind, title=a["title"] or r["title"]), (r.get("link") or a["link"]).lstrip("/"))
        elif k["tell_giver"] == "banner" and r["reply"]:
            _unseen(r["by"], {"id": r["id"], "kind": kind, "ref": ref, "title": r["title"], "reply": r["reply"], "by": r["answered_by"]})
    return _public(user, kind, ref, a, r) | {"message": say("saved", kind)}


def remove(user: dict, iid: str, kind: str = "", ref: str = "") -> dict:
    """Whoever the kind's remove chip allows; the screenshot is kept aside, not destroyed."""
    a = _about(user, kind, ref)
    with store._LOCK:                                    # noqa: SLF001
        rows = _rows(kind, ref)
        r = _find(rows, iid, kind)
        if not _may("remove", user, kind, a, r):
            raise HTTPException(403, say("not_yours", kind))
        if r.get("shot") and (_shots(kind, ref) / r["shot"]).is_file():
            store.keep_aside(_shots(kind, ref) / r["shot"])
        left = [x for x in rows if x["id"] != iid]
        store.write(_name(kind, ref), left)
    if not any(x["by"] == r["by"] for x in left):
        _index(r["by"], f"{kind}|{ref}", None)
    return {"message": say("removed", kind)}


def shot(user: dict, iid: str, kind: str = "", ref: str = ""):
    a = _about(user, kind, ref)
    r = _find(_rows(kind, ref), iid, kind)
    if not r.get("shot") or not _may("see", user, kind, a, r):
        raise HTTPException(404, say("no_issue", kind))
    return _shots(kind, ref) / r["shot"]


def counts(kind: str, ref: str) -> tuple[int, int]:
    """(notes, notes the answerer has not opened) on one thing - a balloon on the maker's row."""
    rows = _rows(kind, ref)
    return len(rows), sum(1 for r in rows if not r.get("seen_answerer"))


def open_count() -> int:
    q = frame()["queue_kind"]
    return sum(1 for r in _rows(q, "") if r["status"] == settings(q)["statuses"][0]["id"])


def _read(store_tpl: str, uid: str, default):
    return store.read(store_tpl.format(uid=uid), default)


def _write(store_tpl: str, uid: str, value) -> None:
    name = store_tpl.format(uid=uid)
    store.path_of(name).parent.mkdir(parents=True, exist_ok=True)
    store.write(name, value)


def _unseen(uid: str, note: dict) -> None:
    with store._LOCK:                                    # noqa: SLF001
        d = [x for x in _read(frame()["unseen_store"], uid, []) or [] if x["id"] != note["id"]]
        _write(frame()["unseen_store"], uid, [*d, note])


def seen(user: dict, iid: str) -> dict:
    with store._LOCK:                                    # noqa: SLF001
        d = _read(frame()["unseen_store"], user["id"], []) or []
        _write(frame()["unseen_store"], user["id"], [x for x in d if x["id"] != iid])
    return {"ok": True}


def bootstrap_extra(request: Request, u: dict | None) -> dict:
    """The balloon for whoever answers reported issues, and the banner replies waiting for this person."""
    if not u:
        return {}
    out = {}
    if access.may(u, _kind(frame()["queue_kind"])["screen"]):
        out["issues_open"] = open_count()
    mine = _read(frame()["unseen_store"], u["id"], []) or []
    if mine:
        out["issue_replies"] = mine
    return out


# --- lists (core/lists.py: searched, paged by the server) ---------------------------------------------------------------

def _queue_rows(user: dict, args: dict) -> list[dict]:
    """Reported issues: the answerer's queue (open / resolved / all)."""
    q = frame()["queue_kind"]
    a, scr = _about(user, q, ""), _kind(q)["screen"]
    if not access.may(user, scr):
        raise HTTPException(403, access.say("no_access", label=access.label_of(scr, "")))
    status = str(args.get("status") or "")
    return [_public(user, q, "", a, r) for r in _rows(q, "") if not status or r["status"] == status]


def _thread_rows(user: dict, args: dict) -> list[dict]:
    """The notes on one thing that this person may see (the answerer: all, a giver: their own) - opening them marks them seen."""
    kind, ref = str(args.get("kind") or frame()["default_kind"]), str(args.get("ref") or "")
    a = _about(user, kind, ref)
    answerer = _may("answer", user, kind, a)
    mark = "seen_answerer" if answerer else "seen_giver"
    with store._LOCK:                                    # noqa: SLF001
        rows = _rows(kind, ref)
        shown = [r for r in rows if _may("see", user, kind, a, r)]
        if any(not r.get(mark) for r in shown):
            for r in shown:
                r[mark] = True
            store.write(_name(kind, ref), rows)
    return [_public(user, kind, ref, a, r) for r in shown]


def _where_i_wrote(uid: str) -> dict:
    """issues_by/<uid>; notes written before the index existed (2026-10-03) are found ONCE by a walk of every kind's store,
    then the index is kept on every file / remove."""
    got = _read(frame()["index_store"], uid, None)
    if got is not None:
        return got
    found = {}
    for kind, k in kinds().items():
        refs = [p.stem for p in store.path_of(k["store"].format(ref="x")).parent.glob("*.json")] if k["per_ref"] else [""]
        for ref in refs:
            ats = [r["at"] for r in _rows(kind, ref) if r["by"] == uid]
            if ats:
                found[f"{kind}|{ref}"] = max(ats)
    with store._LOCK:                                    # noqa: SLF001
        _write(frame()["index_store"], uid, found)
    return found


def _my_rows(user: dict, args: dict) -> list[dict]:
    """My reports: every note this person sent, of every kind, with its status and answer (2026-10-03 owner: "Where I as
    reader can see all my feedbacks?"). Reads only the places they wrote (issues_by/<uid>)."""
    out = []
    for key in _where_i_wrote(user["id"]):
        kind, _, ref = key.partition("|")
        if kind not in kinds():
            continue
        try:
            a = _about(user, kind, ref)
        except HTTPException:
            continue                                     # the thing is gone or no longer theirs to see
        out += [_public(user, kind, ref, a, r) for r in _rows(kind, ref) if r["by"] == user["id"]]
    return out


lists.source("issues", _queue_rows)
lists.source("issue_thread", _thread_rows)
lists.source("my_reports", _my_rows)


# --- routes -------------------------------------------------------------------------------------------------------------

def _where(request: Request) -> tuple[str, str]:
    q = request.query_params
    return str(q.get("kind") or frame()["default_kind"]), str(q.get("ref") or "")


@router.post("/api/core/issues")
def api_file(body: dict = Body(...), u: dict = Depends(auth.signed_in)):
    r = file(u, body or {})
    return {"id": r["id"], "note": r, "message": r["message"]}


@router.post("/api/core/issues/{iid}")
def api_answer(request: Request, iid: str, body: dict = Body(...), u: dict = Depends(auth.signed_in)):
    kind, ref = _where(request)
    return answer(u, iid, body or {}, kind, ref)


@router.delete("/api/core/issues/{iid}")
def api_remove(request: Request, iid: str, u: dict = Depends(auth.signed_in)):
    kind, ref = _where(request)
    return remove(u, iid, kind, ref)


@router.get("/api/core/issues/{iid}/shot")
def api_shot(request: Request, iid: str, u: dict = Depends(auth.signed_in)):
    kind, ref = _where(request)
    return FileResponse(str(shot(u, iid, kind, ref)), headers={"Cache-Control": frame()["shot_cache"]})


@router.get("/api/core/issues/{iid}/files/{n}")
def api_file_part(request: Request, iid: str, n: int, u: dict = Depends(auth.signed_in)):
    """A picture or voice note of a note - to whoever may see the note."""
    return FileResponse(attachment(u, iid, n, *_where(request)), headers={"Cache-Control": frame()["shot_cache"]})


@router.post("/api/core/issues/{iid}/seen")
def api_seen(iid: str, u: dict = Depends(auth.signed_in)):
    return seen(u, iid)


# --- Push to (2026-10-24 owner): a reported issue becomes a request in another portal (core/push.py); Portal Admin only ----

@router.get("/api/core/issues/push")
def api_push_menu(u: dict = Depends(auth.owner)):
    from core import push  # noqa: PLC0415
    return push.menu()


@router.post("/api/core/issues/push/key")
def api_push_key(body: dict = Body(...), u: dict = Depends(auth.owner)):
    from core import push  # noqa: PLC0415
    return push.keep_key(str(body.get("target") or ""), str(body.get("key") or ""))


@router.post("/api/core/issues/push/connect")
def api_push_connect(request: Request, body: dict = Body(...), u: dict = Depends(auth.owner)):
    """Connect (no key to copy): the address of the target's Allow page; it answers on /push/back below."""
    from core import mcp_oauth, push  # noqa: PLC0415
    back = mcp_oauth.api_base(request) + request.scope.get("root_path", "") + push.K()["connect_back"]
    return push.connect_start(str(body.get("target") or ""), back)


@router.get("/api/core/issues/push/back")
def api_push_back(request: Request, state: str = "", code: str = "", error: str = ""):
    """The Allow page sends the Connect window here. Not signed in on purpose: the one-time state is the proof (OAuth).
    No inline script or style (the portal's script policy): words ride in data-*, core-static/push-back.js tells the
    Issues tab (same site, BroadcastChannel) and closes the window."""
    from core import push  # noqa: PLC0415
    ok, said = push.connect_back(state, code, error)
    root, say_ = request.scope.get("root_path", ""), html.escape(said)
    return HTMLResponse(f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer"><title>{say_}</title><link rel="stylesheet" href="{root}/core-static/portal.css">
<body class="push-back" data-ok="{int(ok)}" data-message="{say_}"><p>{say_}</p><script src="{root}/core-static/push-back.js"></script></body></html>""")


def push_issue(user: dict, iid: str, body: dict) -> dict:
    """Send the queue's issue; the row keeps what was pushed (target, ref, code, link, when) and says it in the reply line."""
    from core import push  # noqa: PLC0415
    q = frame()["queue_kind"]
    r = _find(_rows(q, ""), iid, q)
    p = push.send(str(body.get("target") or ""), r, body)
    with store._LOCK:                                    # noqa: SLF001
        rows = _rows(q, "")
        _find(rows, iid, q)["pushed"] = [*(_find(rows, iid, q).get("pushed") or []), p]
        store.write(_name(q, ""), rows)
    return {"pushed": p, "message": push._w("push_done", target=p["label"], ref=p["ref"])}  # noqa: SLF001


@router.post("/api/core/issues/{iid}/push")
def api_push(iid: str, body: dict = Body(...), u: dict = Depends(auth.owner)):
    return push_issue(u, iid, body or {})


@router.get("/api/core/issues/{iid}/push")
def api_push_follow(iid: str, u: dict = Depends(auth.owner)):
    """Each pushed request's stage now, read from where it lives."""
    from core import push  # noqa: PLC0415
    q = frame()["queue_kind"]
    return {"pushed": [p | push.follow(p) for p in _find(_rows(q, ""), iid, q).get("pushed") or []]}


if __name__ == "__main__":  # ponytail: one runnable self-check on throwaway data
    import tempfile
    from pathlib import Path

    from core import store as cstore
    cstore.DATA = Path(tempfile.mkdtemp())
    access.may = lambda u, s, f="": (u or {}).get("role") == "owner"   # the catalog is the portal's; here: owner = admin
    kid, boss = {"id": "k1", "email": "kid@x.org", "name": "Kid", "role": "member"}, {"id": "b1", "email": "b@x.org", "role": "owner"}
    try:
        file(kid, {"title": "", "body": "x"})
        raise AssertionError("a report without a header")
    except HTTPException as e:
        assert e.status_code == 400
    from PIL import Image as _Img
    _b = io.BytesIO()
    _Img.new("RGB", (4, 4)).save(_b, "PNG")
    png = "data:image/png;base64," + base64.b64encode(_b.getvalue()).decode()
    r = file(kid, {"title": "Copies my book", "body": "Chapter 2 is mine", "screenshot": png, "surface": "home", "context": "work w1"})
    raw_ = _rows("issue", "")[0]
    assert raw_["email"] == "kid@x.org" and raw_["shot"].endswith(".png") and (_shots("issue", "") / raw_["shot"]).exists(), "the account is the reporter"
    assert not r["email"], "the reporter's own copy shows no email (only the answerer sees it)"
    for bad_ in ("data:text/html;base64,PHNjcmlwdD4=", "data:image/png;base64," + base64.b64encode(b"<svg onload=x>").decode()):
        try:
            file(kid, {"title": "t", "body": "b", "screenshot": bad_})
            raise AssertionError("a non-picture attachment was taken")
        except HTTPException as e:
            assert e.status_code == 400
    assert open_count() == 1 and bootstrap_extra(None, boss)["issues_open"] == 1, "the admin's balloon counts it"
    assert "issues_open" not in bootstrap_extra(None, kid), "a member sees no queue"
    try:
        answer(kid, r["id"], {"status": "resolved"})
        raise AssertionError("the reporter answered their own report")
    except HTTPException as e:
        assert e.status_code == 403
    assert lists.page("issues", boss, {"status": "open"})["rows"][0]["email"] == "kid@x.org", "the answerer sees who"
    answer(boss, r["id"], {"status": "resolved", "reply": "Taken down - thank you."})
    got = bootstrap_extra(None, kid)["issue_replies"]
    assert got[0]["reply"] == "Taken down - thank you." and open_count() == 0, "the reporter is answered in the portal, not by email"
    seen(kid, r["id"])
    assert "issue_replies" not in bootstrap_extra(None, kid), "a banner read once is gone"
    cstore.path_of("issues_by/k1").unlink()           # as before the index existed
    mine_ = lists.page("my_reports", kid, {})["rows"]
    assert len(mine_) == 1, "a note written before the index still shows in My reports (found once by a walk)"
    assert _public(kid, "issue", "", {"owner_id": "", "title": "The work", "link": "#/w", "keeper": False, "open": True},
                   {"id": "z", "by": "k1", "text": "t", "status": "open"})["about"] == "The work", "an old note names what it is about"
    assert [m["status_label"] for m in mine_] and mine_[0]["reply"].startswith("Taken down"), "My reports shows it, answered"
    # a row written before the merge (user_id / body / created_at) still reads
    cstore.write("issues", [*cstore.read("issues", []), {"id": "old1", "user_id": "k1", "body": "old", "created_at": "2026-09-01T00:00:00+00:00",
                                                          "title": "Old", "status": "open", "shot": "", "reply": "", "email": "kid@x.org", "name": "Kid"}])
    assert any(x["text"] == "old" for x in lists.page("issues", boss, {})["rows"]), "an old report still shows in the queue"
    print("issues self-check OK")
