"""Issue > Push to (2026-10-24 owner): the Portal Admin sends a reported issue to another portal of the family as a request -
CodyFy first, into the company named on the target (ValueStream for every FY portal) - and the issue row then follows its stage.

Generic: the targets, their MCP tools (send, follow), the key form, company, project and the link are chip issues.push; every
word is chip ui.issues push_*. Calls go through the target's own MCP door (JSON-RPC tools/call); nothing here names a portal.
The key is pasted once by the Portal Admin, checked by a round trip, and kept in an owner-only store file.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import re
import secrets
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException

from core import egress, engine, store

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


def _keys() -> dict:
    return store.read(K()["key_store"], {}) or {}


def _keep(**kv: Any) -> None:
    with store._LOCK:                                    # noqa: SLF001
        store.write(K()["key_store"], _keys() | kv)


def key_of(tid: str) -> str:
    """A pasted key as kept, or a Connect grant's access token - refreshed shortly before it runs out. A refused refresh
    = '' (not connected), so the dialog offers Connect again instead of failing a push later."""
    k = _keys().get(tid, "")
    if not isinstance(k, dict):
        return str(k)
    c = target(tid)["connect"]
    if float(k.get("exp", 0)) - time.time() > float(c["refresh_early_s"]):
        return str(k["access"])
    try:
        got = _form(target(tid), c["token"], {"grant_type": "refresh_token", "refresh_token": k["refresh"], "client_id": k["client_id"]})
    except PushFailed:
        return ""
    _keep(**{tid: _grant(k["client_id"], got)})
    return str(got["access_token"])


def _grant(client_id: str, got: dict) -> dict:
    return {"access": got["access_token"], "refresh": got.get("refresh_token", ""), "client_id": client_id,
            "exp": time.time() + float(got.get("expires_in") or 0)}


def _http(t: dict, path: str, data: bytes, ctype: str) -> dict:
    req = urllib.request.Request(str(t["base"]).rstrip("/") + path, data=data, method="POST", headers={"Content-Type": ctype, "Accept": "application/json"})
    try:
        with egress.fetch(req, timeout=float(K()["timeout_s"]), purpose="push") as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raise PushFailed(f"{e.code} {e.read().decode('utf-8', 'replace')[:200]}") from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise PushFailed(f"{type(e).__name__}: {e}") from e


def _form(t: dict, path: str, form: dict) -> dict:
    return _http(t, path, urlencode(form).encode(), "application/x-www-form-urlencoded")


# --- Connect (2026-10-25 owner: no key to copy): the target's own OAuth door - sign in there, press Allow, done ----------

def _s256(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def connect_start(tid: str, back: str) -> dict:
    """Where the Connect window goes: the target's Allow page for this portal (registered once per return address)."""
    t = target(tid)
    c, keys = t["connect"], _keys()
    clients = keys.get("_clients") or {}
    cid = clients.get(f"{tid} {back}")
    try:
        if not cid:
            cid = _http(t, c["register"], json.dumps({"client_name": fill(c["client_name"], {"product": engine.product_name()}),
                                                     "redirect_uris": [back]}).encode(), "application/json")["client_id"]
    except (PushFailed, KeyError) as e:
        raise HTTPException(502, _w("push_failed", target=t["label"], why=str(e))) from e
    verifier, state, now = secrets.token_urlsafe(48), secrets.token_urlsafe(24), time.time()
    pending = {s: p for s, p in (keys.get("_pending") or {}).items() if p["exp"] > now}
    pending[state] = {"target": tid, "verifier": verifier, "back": back, "client_id": cid, "exp": now + float(c["minutes"]) * 60}
    _keep(_clients=clients | {f"{tid} {back}": cid}, _pending=pending)
    return {"url": str(t["base"]).rstrip("/") + c["authorize"] + "?" + urlencode({
        "response_type": "code", "client_id": cid, "redirect_uri": back, "code_challenge": _s256(verifier),
        "code_challenge_method": "S256", "state": state, "scope": c["scope"]})}


def connect_back(state: str, code: str, error: str) -> tuple[bool, str]:
    """The Allow page's answer: the one-time state (unguessable, minutes-long) is the proof; code -> tokens, checked, kept."""
    pending = _keys().get("_pending") or {}
    p = pending.pop(str(state or ""), None)
    _keep(_pending=pending)
    if not p or p["exp"] < time.time():
        return False, _w("push_connect_stale")
    t = target(p["target"])
    if error or not code:
        return False, _w("push_connect_no", target=t["label"])
    try:
        got = _form(t, t["connect"]["token"], {"grant_type": "authorization_code", "code": code, "client_id": p["client_id"],
                                               "redirect_uri": p["back"], "code_verifier": p["verifier"]})
        _rpc(t, got["access_token"], t["check"]["method"])
    except (PushFailed, KeyError) as e:
        return False, _w("push_key_bad", target=t["label"], why=str(e))
    _keep(**{p["target"]: _grant(p["client_id"], got)})
    return True, _w("push_connected", target=t["label"])


def _rpc(t: dict, key: str, method: str, params: dict | None = None) -> dict:
    """One JSON-RPC call to the target's MCP door; a tool's own error (isError) is raised with its words."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    req = urllib.request.Request(str(t["base"]).rstrip("/") + str(t.get("mcp_path") or "/mcp"), data=body, method="POST",
                                 headers={"Authorization": fill(t["key_format"], {"key": key}), "Content-Type": "application/json",
                                          "Accept": "application/json, text/event-stream"})
    try:
        with egress.fetch(req, timeout=float(K()["timeout_s"]), purpose="push") as r:
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
    _keep(**{tid: key})
    return {"message": _w("push_key_ok", target=t["label"])}


def menu() -> dict:
    """The dialog's targets: words, company, project, kinds, and whether a key is kept (never the key)."""
    names = {"product": engine.product_name()}
    return {"targets": [{"id": t["id"], "label": t["label"], "hint": t["hint"], "company": t.get("company", ""),
                         "project": fill(t.get("project", ""), names), "types": t["types"], "type": t["type"],
                         "ready": bool(key_of(t["id"])), "connect": bool(t.get("connect"))} for t in targets()]}


def _vals(t: dict, row: dict, body: dict) -> dict:
    v = {"product": engine.product_name(), "title": str(body.get("title") or row.get("title") or "").strip(),
         "context": row.get("context", ""), "name": row.get("name", ""), "company": t.get("company", ""), "base": str(t["base"]).rstrip("/")}
    v["project"] = fill(t.get("project", ""), v)
    v["type"] = body.get("type") if body.get("type") in t["types"] else t["type"]
    v["part"] = str(body.get("part") or row.get("context") or v["product"]).strip()   # CodyFy needs the module: the page it came from
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
            raw = self.rfile.read(int(self.headers["Content-Length"])).decode()
            if self.path.startswith("/oauth/"):              # the target's OAuth door (Connect)
                self._oauth(raw)
                return
            msg = json.loads(raw)
            seen.append((self.headers["Authorization"], msg))
            if self.headers["Authorization"] not in {"Bearer good", "Bearer acc1", "Bearer acc2"}:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"error":"bad key"}')
                return
            a = (msg.get("params") or {}).get("arguments") or {}
            out = {"steps": [{"answer": {"id": "r9", "code": "c0de"}}]} if (msg.get("params") or {}).get("name") == "request_send" \
                else {"steps": [{"answer": {"id": "r9"}}, {"answer": {"ref": "REQ-0009", "stage_label": "With Claude"}}]}
            res = {"tools": []} if msg["method"] == "tools/list" else {"structuredContent": out | {"company": a.get("company")}}
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": res}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def _oauth(self, raw):
            from urllib.parse import parse_qs
            f = {k: v[0] for k, v in parse_qs(raw).items()}
            if self.path == "/oauth/register":
                out = {"client_id": "cl1"} if json.loads(raw)["redirect_uris"] else {}
            elif f.get("grant_type") == "authorization_code" and f.get("code") == "code1" and _s256(f.get("code_verifier", "")) == grants["challenge"]:
                out = {"access_token": "acc1", "refresh_token": "ref1", "expires_in": 3600}
            elif f.get("grant_type") == "refresh_token" and f.get("refresh_token") == "ref1":
                out = {"access_token": "acc2", "refresh_token": "ref2", "expires_in": 3600}
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"error":"invalid_grant"}')
                return
            body = json.dumps(out).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    grants: dict = {}
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Door)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    store.DATA = Path(tempfile.mkdtemp())
    real = me.K()
    me.K = lambda: real | {"targets": [real["targets"][0] | {"base": f"http://127.0.0.1:{srv.server_port}"}]}  # noqa: E731
    eg = egress.K()   # the stand-in door is on this machine: a test-only http + loopback exception (core/egress.py refuses it otherwise)
    egress.K = lambda: eg | {"exceptions": eg["exceptions"] | {"push": {"http": True, "nets": ["127.0.0.0/8"]}}}  # noqa: E731
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
    assert sent["part"], "CodyFy refuses a request with no module (2026-10-24)"
    assert sent["company"] == t0["company"] and sent["new_project"] == engine.product_name() and sent["type"] == "fix", sent
    assert "Please add Excel." in sent["text"] and got["pushed"]["ref"] == "REQ-0009" and got["pushed"]["link"].endswith("r=c0de")
    row = store.read("issues", [])[0]
    assert row["pushed"][0]["code"] == "c0de" and "pushed" in issues.frame()["public_fields"], "the row does not keep what was pushed"
    assert me.follow(row["pushed"][0])["stage"] == "With Claude"
    owner_only = {r.path for r in issues.router.routes if "push" in r.path
                  and any(d.call is __import__("core.auth", fromlist=["owner"]).owner for d in r.dependant.dependencies)}
    assert owner_only == {"/api/core/issues/push", "/api/core/issues/push/key", "/api/core/issues/push/connect", "/api/core/issues/{iid}/push"}, owner_only
    # Connect (2026-10-25 owner: no key to copy): Allow on the target -> tokens kept; refreshed before they run out; one-time state
    from urllib.parse import parse_qs, urlparse
    back = "http://127.0.0.1/api/core/issues/push/back"
    q = {k: v[0] for k, v in parse_qs(urlparse(me.connect_start(t0["id"], back)["url"]).query).items()}
    assert q["client_id"] == "cl1" and q["redirect_uri"] == back and q["code_challenge_method"] == "S256", q
    grants["challenge"] = q["code_challenge"]
    assert me.connect_back(q["state"], "", "access_denied")[0] is False, "Deny must not connect"
    assert me.connect_back(q["state"], "code1", "")[0] is False, "a state is one use only"
    q = {k: v[0] for k, v in parse_qs(urlparse(me.connect_start(t0["id"], back)["url"]).query).items()}
    grants["challenge"] = q["code_challenge"]
    ok, said = me.connect_back(q["state"], "code1", "")
    assert ok and said and me.key_of(t0["id"]) == "acc1" and me.menu()["targets"][0]["ready"] is True, said
    me._keep(**{t0["id"]: me._keys()[t0["id"]] | {"exp": 0}})            # ran out -> refreshed on the next use
    assert me.key_of(t0["id"]) == "acc2" and me._keys()[t0["id"]]["refresh"] == "ref2"
    me._keep(**{t0["id"]: me._keys()[t0["id"]] | {"exp": 0}})            # refresh refused -> not connected, Connect offered again
    assert me.key_of(t0["id"]) == "" and me.menu()["targets"][0]["ready"] is False
    fake = type("R", (), {"scope": {"root_path": ""}})()
    page = issues.api_push_back(fake, state="nope").body.decode()
    assert 'data-ok="0"' in page and "<script>" not in page and "style=" not in page,         "the Connect back page must carry no inline script/style (script policy) and a stale state must not say ok"
    assert "window.close" in (Path(__file__).parent / "static" / "push-back.js").read_text(encoding="utf-8")
    js = (Path(__file__).parent / "static" / "page-issues.js").read_text(encoding="utf-8")
    assert "admin() && r.status === 'open'" in js and "data-push-open" in js, "the Push to button is not Portal Admin only"
    pushjs = js.split("// The road an issue takes")[1].split("function answer")[0]
    assert "data-push-connect-go" in pushjs and "BroadcastChannel" in pushjs and not any(t in pushjs for t in ("<select", "style=")), \
        "the Push dialog lost its Connect step, went back to a plain select, or took an inline style (script policy)"
    srv.shutdown()
    print("push self-check OK")
