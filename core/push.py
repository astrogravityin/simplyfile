"""Issue > Push to (2026-10-24 owner): the Portal Admin sends a reported issue to another portal of the family as a request -
CodyFy first, into the company named on the target (ValueStream for every FY portal) - and the issue row then follows its stage.

Generic: the targets, their MCP tools (send, follow), the key form, company, project and the link are chip issues.push; every
word is chip ui.issues push_*. Calls go through the target's own MCP door (JSON-RPC tools/call); nothing here names a portal.
The key is pasted once by the Portal Admin, checked by a round trip, and kept in an owner-only store file.
"""
from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from typing import Any

from fastapi import HTTPException

from core import engine, store

_SLOT = re.compile(r"\{(\w+)(\|html)?\}")


def K() -> dict:
    return engine.run("issues.push")


def targets() -> list[dict]:
    return [t for t in K()["targets"] if t.get("on", True)]


def target(tid: str) -> dict:
    t = next((x for x in targets() if x["id"] == str(tid or "").strip()), None)
    if not t:
        raise HTTPException(400, _w("push_unknown"))
    return t


def _w(word: str, **v) -> str:
    s = str(engine.run("ui.issues").get(word, word))
    return s.format(**v) if v else s


def fill(x: Any, vals: dict) -> Any:
    """{slot} (or {slot|html}, escaped) from vals through dicts and lists; a string that is one slot keeps the value's type."""
    if isinstance(x, dict):
        return {k: fill(v, vals) for k, v in x.items()}
    if isinstance(x, list):
        return [fill(v, vals) for v in x]
    if not isinstance(x, str):
        return x
    m = _SLOT.fullmatch(x)
    if m and not m.group(2):
        return vals.get(m.group(1), "")
    return _SLOT.sub(lambda g: html.escape(str(vals.get(g.group(1), ""))) if g.group(2) else str(vals.get(g.group(1), "")), x)


def dig(got: Any, path: str) -> Any:
    """A field of an answer by its dotted path (steps.0.answer.code)."""
    for p in str(path).split("."):
        if isinstance(got, list) and p.isdigit() and int(p) < len(got):
            got = got[int(p)]
        elif isinstance(got, dict):
            got = got.get(p)
        else:
            return ""
    return "" if got is None else got


def key_of(tid: str) -> str:
    return str((store.read(K()["key_store"], {}) or {}).get(tid, ""))


def _rpc(t: dict, key: str, method: str, params: dict | None = None) -> dict:
    """One JSON-RPC call to the target's MCP door; a tool's own error (isError) is raised with its words."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    req = urllib.request.Request(str(t["base"]).rstrip("/") + str(t.get("mcp_path") or "/mcp"), data=body, method="POST",
                                 headers={"Authorization": fill(t["key_format"], {"key": key}), "Content-Type": "application/json",
                                          "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(req, timeout=float(K()["timeout_s"])) as r:   # noqa: S310 - the address is the chip's
            got = json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raise PushFailed(f"{e.code} {e.read().decode('utf-8', 'replace')[:200]}") from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise PushFailed(f"{type(e).__name__}: {e}") from e
    res = got.get("result") or {}
    if got.get("error") or res.get("isError"):
        raise PushFailed(str((got.get("error") or {}).get("message") or "".join(x.get("text", "") for x in res.get("content") or []))[:300])
    return res


class PushFailed(Exception):
    """The target answered with an error: its own words."""


def _tool(t: dict, key: str, c: dict, vals: dict) -> dict:
    return _rpc(t, key, "tools/call", {"name": c["tool"], "arguments": fill(c.get("arguments") or {}, vals)}).get("structuredContent") or {}


def keep_key(tid: str, key: str) -> dict:
    """Checked by a round trip before it is kept - a key the target refuses is never stored."""
    t, key = target(tid), str(key or "").strip()
    try:
        _rpc(t, key, t["check"]["method"])
    except PushFailed as e:
        raise HTTPException(400, _w("push_key_bad", target=t["label"], why=str(e))) from e
    with store._LOCK:                                    # noqa: SLF001
        keys = store.read(K()["key_store"], {}) or {}
        store.write(K()["key_store"], keys | {tid: key})
    return {"message": _w("push_key_ok", target=t["label"])}


def menu() -> dict:
    """The dialog's targets: words, company, project, kinds, and whether a key is kept (never the key)."""
    names = {"product": engine.product_name()}
    return {"targets": [{"id": t["id"], "label": t["label"], "hint": t["hint"], "company": t.get("company", ""),
                         "project": fill(t.get("project", ""), names), "types": t["types"], "type": t["type"],
                         "ready": bool(key_of(t["id"]))} for t in targets()]}


def _vals(t: dict, row: dict, body: dict) -> dict:
    v = {"product": engine.product_name(), "title": str(body.get("title") or row.get("title") or "").strip(),
         "context": row.get("context", ""), "name": row.get("name", ""), "company": t.get("company", ""), "base": str(t["base"]).rstrip("/")}
    v["project"] = fill(t.get("project", ""), v)
    v["type"] = body.get("type") if body.get("type") in t["types"] else t["type"]
    v["text"] = fill(t["text"], v | {"text": str(body.get("text") or row.get("text") or "").strip()})
    return v


def send(tid: str, row: dict, body: dict) -> dict:
    """Run the target's send tools in order (each keeps what its `save` names), then read its stage once."""
    t = target(tid)
    key = key_of(tid)
    if not key:
        raise HTTPException(400, _w("push_no_key", target=t["label"]))
    v = _vals(t, row, body)
    try:
        for c in t["send"]:
            got = _tool(t, key, c, v)
            v |= {slot: dig(got, path) for slot, path in (c.get("save") or {}).items()}
        st = status(t, key, v)
    except PushFailed as e:
        raise HTTPException(502, _w("push_failed", target=t["label"], why=str(e))) from e
    return {"target": tid, "label": t["label"], "code": v.get("code", ""), "ref": st.get("ref") or v.get("code", ""),
            "stage": st.get("stage", ""), "link": fill(t["link"], v), "company": v["company"], "at": store.now()}


def status(t: dict, key: str, v: dict) -> dict:
    s = t.get("status") or {}
    if not s:
        return {}
    got = _tool(t, key, s, v)
    return {name: dig(got, path) for name, path in (s.get("pick") or {}).items()}


def follow(p: dict) -> dict:
    """One pushed request's stage now (a failed read says why, never a silent blank)."""
    try:
        t = target(p["target"])
        return status(t, key_of(t["id"]), {"code": p.get("code", ""), "company": p.get("company", "")})
    except (PushFailed, HTTPException) as e:
        return {"why": str(getattr(e, "detail", "") or e)[:200]}


if __name__ == "__main__":  # ponytail: one runnable self-check - a stand-in MCP door on this machine, throwaway data
    import tempfile
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path

    from core import issues
    from core import push as me   # the module issues calls - patched there, never this __main__ copy

    assert fill("<p>{t|html}</p>", {"t": "<b>"}) == "<p>&lt;b&gt;</p>" and fill({"n": "{n}"}, {"n": 4}) == {"n": 4}
    assert dig({"steps": [{"answer": {"code": "c1"}}]}, "steps.0.answer.code") == "c1" and dig({}, "a.b") == ""
    seen: list = []

    class Door(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append((self.headers["Authorization"], msg))
            if self.headers["Authorization"] != "Bearer good":
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"error":"bad key"}')
                return
            a = (msg.get("params") or {}).get("arguments") or {}
            out = {"steps": [{"answer": {"id": "r9", "code": "c0de"}}]} if (msg.get("params") or {}).get("name") == "request_send" \
                else {"answer": {"ref": "REQ-0009", "stage_label": "With Claude"}}
            res = {"tools": []} if msg["method"] == "tools/list" else {"structuredContent": out | {"company": a.get("company")}}
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": res}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Door)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    store.DATA = Path(tempfile.mkdtemp())
    real = me.K()
    me.K = lambda: real | {"targets": [real["targets"][0] | {"base": f"http://127.0.0.1:{srv.server_port}"}]}  # noqa: E731
    store.write("issues", [{"id": "i1", "by": "k1", "name": "Kid", "title": "Download to Excel", "text": "Please add Excel.",
                            "status": "open", "context": "Results"}])
    t0 = me.targets()[0]
    assert t0["company"] == real["targets"][0]["company"] and me.menu()["targets"][0]["ready"] is False
    try:
        issues.push_issue({"id": "o1", "role": "owner"}, "i1", {"target": t0["id"]})
        raise AssertionError("pushed with no key")
    except HTTPException as e:
        assert e.status_code == 400 and not seen, "no key: said, nothing sent"
    try:
        me.keep_key(t0["id"], "wrong")
        raise AssertionError("a refused key was kept")
    except HTTPException as e:
        assert e.status_code == 400 and not me.key_of(t0["id"])
    assert me.keep_key(t0["id"], "good")["message"] and me.menu()["targets"][0]["ready"] is True
    assert me.K()["key_store"] in store.SECRET_FILES, "the key file is not owner-only"
    got = issues.push_issue({"id": "o1", "role": "owner"}, "i1", {"target": t0["id"], "type": "fix"})
    sent = next(m for _a, m in seen if (m.get("params") or {}).get("name") == "request_send")["params"]["arguments"]
    assert sent["company"] == t0["company"] and sent["new_project"] == engine.product_name() and sent["type"] == "fix", sent
    assert "Please add Excel." in sent["text"] and got["pushed"]["ref"] == "REQ-0009" and got["pushed"]["link"].endswith("r=c0de")
    row = store.read("issues", [])[0]
    assert row["pushed"][0]["code"] == "c0de" and "pushed" in issues.frame()["public_fields"], "the row does not keep what was pushed"
    assert me.follow(row["pushed"][0])["stage"] == "With Claude"
    owner_only = {r.path for r in issues.router.routes if "push" in r.path
                  and any(d.call is __import__("core.auth", fromlist=["owner"]).owner for d in r.dependant.dependencies)}
    assert owner_only == {"/api/core/issues/push", "/api/core/issues/push/key", "/api/core/issues/{iid}/push"}, owner_only
    js = (Path(__file__).parent / "static" / "page-issues.js").read_text(encoding="utf-8")
    assert "admin() && r.status === 'open'" in js and "data-push-open" in js, "the Push to button is not Portal Admin only"
    srv.shutdown()
    print("push self-check OK")
