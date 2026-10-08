"""Notes - the bottom bar's notebook, as the studio has it (2026-10-04 owner: "bring the entire thing from the studio").

A person's own notes: a name, rich text (bold, italic, underline, lists, highlight and text colours, pasted pictures)
and voice notes - the recording, with the words the browser wrote down while it was spoken. Private to each person.
Storage only: what a note may keep is chip notes.settings (tags, styles), the search is chip notes.list_view, limits are
chip page.dock, words chip ui.dock. A note is cleaned on save: only the allowed tags and styles survive.
"""
from __future__ import annotations

import html
import re
import threading
from html.parser import HTMLParser

from fastapi import HTTPException

from core import engine, store

FILE = "sf_notes"
_LOCK = threading.Lock()


def _k() -> dict:
    return engine.run("page.dock", {}) | engine.run("notes.settings", {})


def _say(key: str) -> str:
    return str(engine.run("ui.dock", {}).get(key.replace(".", "_"), key))


class _Clean(HTMLParser):
    """Keeps only the tags and inline styles chip notes.settings allows; pictures only as data:image."""

    def __init__(self, tags: set, styles: set):
        super().__init__(convert_charrefs=True)
        self.tags, self.styles, self.out, self.text = tags, styles, [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.tags:
            return
        keep = []
        for k, v in attrs:
            v = v or ""
            if k == "src" and tag == "img" and v.startswith("data:image/"):
                keep.append(f'src="{html.escape(v, quote=True)}"')
            elif k == "style":
                parts = [p.strip() for p in v.split(";") if ":" in p and p.split(":")[0].strip().lower() in self.styles
                         and not re.search(r"url\(|expression", p, re.I)]
                if parts:
                    keep.append(f'style="{html.escape("; ".join(parts), quote=True)}"')
            elif k == "color" and tag == "font" and re.fullmatch(r"#?\w+", v):
                keep.append(f'color="{v}"')
        if tag == "img" and not any(a.startswith("src=") for a in keep):
            return
        self.out.append(f"<{tag}{' ' if keep else ''}{' '.join(keep)}>")

    def handle_endtag(self, tag):
        if tag in self.tags and tag not in ("br", "img"):
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        self.out.append(html.escape(data, quote=False))
        self.text.append(data)


def clean(content: str) -> tuple[str, str]:
    """(safe html, its plain text)."""
    k = _k()
    p = _Clean(set(k["tags"]), set(k["styles"]))
    p.feed(content or "")
    p.close()
    return "".join(p.out), re.sub(r"\s+", " ", " ".join(p.text)).strip()


def _all() -> list[dict]:
    rows = store.read(FILE, [])
    for n in rows:                      # notes written before the studio's port: title / text / pictures / voices
        if "content" not in n:
            body = html.escape(n.pop("text", "") or "", quote=False)
            n["name"] = n.pop("title", "") or body[:40]
            n["content"] = body.replace("\n", "<br>") + "".join(f'<br><img src="{p}">' for p in n.pop("pictures", []) or [])
            n["text"] = body
            n["attachments"] = [{"id": i + 1, "kind": "audio", "data": v, "transcript": "", "transcript_status": "unavailable"}
                                for i, v in enumerate(n.pop("voices", []) or [])]
    return rows


def _mine(u: dict, nid: str) -> tuple[list[dict], dict]:
    rows = _all()
    n = next((x for x in rows if x["id"] == nid and x["user_id"] == u["id"]), None)
    if not n:
        raise HTTPException(404, _say("notes.open_failed"))
    return rows, n


def listed(u: dict, q: str = "") -> list[dict]:
    k = _k()
    mine = [{"id": n["id"], "name": n.get("name", ""), "text": n.get("text", ""), "updated_at": n["updated_at"]} for n in _all() if n["user_id"] == u["id"]]
    rows = engine.run("notes.list_view", {"rows": mine, "query": q})["rows"]
    return [r | {"preview": r["text"][: int(k["preview_chars"])]} for r in rows]


def one(u: dict, nid: str) -> dict:
    return _mine(u, nid)[1]


def save(u: dict, body: dict, nid: str = "") -> dict:
    k = _k()
    content, text = clean(str(body.get("content") or ""))
    if len(content.encode()) > int(k["note_max_kb"]) * 1024:
        raise HTTPException(400, _say("notes.save_failed"))
    name = str(body.get("name") or "").strip()[: int(k["name_chars"])] or text[:40] or _say("notes.paper")
    with _LOCK:
        if nid:
            rows, n = _mine(u, nid)
        else:
            rows = _all()
            if sum(1 for x in rows if x["user_id"] == u["id"]) >= int(k["notes_max"]):
                raise HTTPException(400, _say("notes.save_failed"))
            n = {"id": store.new_id(), "user_id": u["id"], "created_at": store.now(), "attachments": []}
            rows.append(n)
        n.update(name=name, content=content, text=text, updated_at=store.now())
        store.write(FILE, rows)
    return n


def add_voice(u: dict, nid: str, body: dict) -> dict:
    """A voice note on a saved note: the recording, and the words the browser wrote down while it was spoken."""
    k = _k()
    data = str(body.get("data") or "")
    if not data.startswith("data:audio/") or len(data) * 3 // 4 > int(k["voice_max_kb"]) * 1024:
        raise HTTPException(400, _say("notes.voice_failed"))
    words = str(body.get("transcript") or "").strip()[:20000]
    with _LOCK:
        rows, n = _mine(u, nid)
        files = n.setdefault("attachments", [])
        if len(files) >= int(k["voices_per_note"]):
            raise HTTPException(400, _say("notes.voice_failed"))
        files.append({"id": max([f["id"] for f in files] or [0]) + 1, "kind": "audio", "name": "voice note", "data": data,
                      "transcript": words, "transcript_status": "done" if words else "unavailable", "at": store.now()})
        n["updated_at"] = store.now()
        store.write(FILE, rows)
    return n


def drop_file(u: dict, nid: str, fid: int) -> dict:
    with _LOCK:
        rows, n = _mine(u, nid)
        n["attachments"] = [f for f in n.get("attachments", []) if f["id"] != fid]
        store.write(FILE, rows)
    return n


def delete(u: dict, nid: str) -> dict:
    with _LOCK:
        rows, n = _mine(u, nid)
        store.write(FILE, [x for x in rows if x is not n])
    return {"ok": True}


if __name__ == "__main__":  # ponytail: a note keeps its formatting and loses anything that could run
    import store as _s  # noqa: F401 - registers this portal's chips
    h, t = clean('<b>FD</b> <span style="background-color:#fef08a;position:fixed">rent</span><script>x()</script>'
                 '<img src="javascript:x"><img src="data:image/png;base64,AA"><a href="x" onclick="y">link</a>')
    assert h == '<b>FD</b> <span style="background-color:#fef08a">rent</span>x()<img src="data:image/png;base64,AA">link', h
    assert t == "FD rent x() link", t
    print("notes OK")
