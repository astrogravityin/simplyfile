"""Connect your AI - the ONE generic MCP door for every portal on this framework (2026-10-23 owner: "go with your pick";
the AstroStage door backend/services/mcp_door.py, same protocol, same rules). No per-tool code lives here.

An AI app (Claude, Codex, Gemini...) speaks JSON-RPC 2.0 to POST /mcp with an MCP key (Authorization: Bearer <key>).
This module answers initialize, ping, tools/list and tools/call from two chips:
  - chip mcp.server: the key's shape, the server's name and instructions, limits, every word it sends;
  - chip mcp.tools:  one row per tool - name, words, input schema, Access Control function, on/off.
A module attaches each tool's answer once:   mcp.tool("voice_for_text", fn)    fn(args, ctx) -> dict   (READ-ONLY)
ctx = {"user": the key's maker, "base": "https://<this site>"}. A row with no attached answer is simply not offered.

2026-10-24 (the Fy portals, owner: "one way everywhere, keep changes allowed"): a row may also say
  - kind: read (default) / change / human - change tools may change things (readOnlyHint false); a human row is a person's
    step (sign-ins, payments, filing elsewhere): it is never run, its words tell the AI what the person does;
  - calls: [{method, path, body, query, save, keep}] - the tool presses the portal's OWN routes, in-process, as the key's
    maker (every route guard, firm wall and Portal Activity apply); {slot}s come from the input, `defaults` or an earlier
    call's `save`; a slot in a path is one address part (quoted), {x|html} is escaped for a page; `link` = an address to open.
  Such rows need no module code; a module's mcp.tool() answer still wins for its row.

Keys: an owner makes one on the Connect your AI screen (the secret is shown once; only its SHA-256 is kept), it acts as
that owner, and dies when revoked or when they stop being an owner. Nothing a caller sends is logged.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import secrets
import urllib.parse
import time
from collections import defaultdict, deque
from typing import Any, Callable

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from core import access, auth, engine, lists, store

router = APIRouter()
TOOLS: dict[str, Callable[[dict, dict], dict]] = {}
NAMING: dict = {}                                   # the portal names its own server (app.py: its edition's product name)
KEYS = "mcp_keys"
JSONRPC = "2.0"
PARSE, INVALID, NO_METHOD, BAD_PARAMS = -32700, -32600, -32601, -32602
_CALLS: dict[Any, deque] = defaultdict(deque)


class ToolError(Exception):
    """A refusal in chip mcp.server words: key + slots."""

    def __init__(self, key: str, **slots: Any):
        super().__init__(key)
        self.key, self.slots = key, slots


def cfg() -> dict:
    return engine.run("mcp.server")


def say(key: str, **slots: Any) -> str:
    return engine.say("mcp.server", key, **slots) if key in cfg() else key


def naming() -> dict:
    """The server's name: what the portal set (NAMING), else this site's product (chip edition.settings)."""
    title = engine.product_name() or ""
    return {"name": re.sub(r"[^a-z0-9-]", "", title.lower()) or "portal", "title": title or "portal"} | NAMING


def tool(name: str, fn: Callable[[dict, dict], dict]) -> None:
    """A module attaches one read-only answer. Its words, schema and gate are its row in chip mcp.tools."""
    TOOLS[name] = fn


def rows() -> list[dict]:
    return list(engine.run("mcp.tools")["tools"])


def ready(r: dict) -> bool:
    """A row is answered by a module (mcp.tool), by its own routes (calls) or, for a person's step, by its words."""
    return r["name"] in TOOLS or bool(r.get("calls")) or r.get("kind") == "human"


def offered(allowed) -> list[dict]:
    return [r for r in rows() if r.get("on") and ready(r) and allowed(r)]


# --- tools that press the portal's own routes (rows with `calls`) ---------------------------------------------------------

def _fill(v: Any, slots: dict, path: bool = False) -> Any:
    """{slot} from the input / defaults / an earlier call; "{x}" alone keeps x's own type; {x|html} escaped for a page."""
    if isinstance(v, dict):
        return {k: _fill(x, slots) for k, x in v.items()}
    if isinstance(v, list):
        return [_fill(x, slots) for x in v]
    if not isinstance(v, str):
        return v
    whole = re.fullmatch(r"\{(\w+)\}", v)
    if whole and not path:
        return slots.get(whole.group(1), "")

    def one(m):
        x = str(slots.get(m.group(1), ""))
        if path:
            return urllib.parse.quote(x, safe="")      # one address part - never a '/' or '..' into another route
        return html.escape(x) if m.group(2) == "html" else x
    return re.sub(r"\{(\w+)(?:\|(\w+))?\}", one, v)


def run_calls(row: dict, args: dict, ctx: dict) -> dict:
    """The row's calls against this portal's own routes, in-process, signed in as the key's maker for these calls only.
    ponytail: Starlette's TestClient is the sync bridge into the app (run in a worker thread by the door)."""
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from core import auth  # noqa: PLC0415
    slots = {**(row.get("defaults") or {}), **{k: v for k, v in args.items() if v not in ("", None)}}
    tok = store.start_session(ctx["user"], int(cfg()["limits"].get("session_seconds", 300)))
    out: list[dict] = []
    try:
        c = TestClient(ctx["app"], base_url=ctx["base"])
        c.cookies.set(auth.COOKIE, tok)
        for call in row["calls"]:
            q = {k: v for k, v in _fill(call.get("query") or {}, slots).items() if v not in ("", None)}
            r = c.request(call["method"], auth.BASE + _fill(call["path"], slots, path=True), params=q or None,
                          json=_fill(call["body"], slots) if "body" in call else None, headers={"X-Real-IP": ctx.get("ip") or ""})
            try:
                got = r.json()
            except ValueError:
                got = r.text
            if r.status_code >= 400:
                detail = got.get("detail") if isinstance(got, dict) else got
                raise ToolError("failed", why=str(detail if not isinstance(detail, dict) else detail.get("message") or detail)[:300])
            if isinstance(got, dict):
                slots |= {s: got.get(k) for s, k in (call.get("save") or {}).items()}
                if call.get("keep"):
                    got = {k: got.get(k) for k in call["keep"]}
            out.append({"call": f"{call['method']} {call['path']}", "answer": got})
    finally:
        store.end_session(tok)
    res = {"answer": out[0]["answer"]} if len(out) == 1 else {"steps": out}
    if row.get("link"):
        res["open"] = ctx["base"] + auth.BASE + _fill(row["link"], slots, path=True)
    return res


# --- input check (the subset the tool rows use) --------------------------------------------------------------------------

_TYPES = {"string": str, "object": dict, "array": list, "boolean": bool}


def problems(schema: dict, value: Any, at: str = "") -> list[str]:
    """What is wrong with `value` against a small JSON Schema: type, required, properties, additionalProperties false,
    minimum / maximum, maxLength. ponytail: the subset our rows use; a full validator if a row ever needs more."""
    kind, name = schema.get("type"), at or "input"
    if kind in ("integer", "number"):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or (kind == "integer" and int(value) != value):
            return [f"{name} ({kind})"]
        if "minimum" in schema and value < schema["minimum"] or "maximum" in schema and value > schema["maximum"]:
            return [f"{name} ({schema.get('minimum', '')}..{schema.get('maximum', '')})"]
        return []
    if kind in _TYPES and not isinstance(value, _TYPES[kind]):
        return [f"{name} ({kind})"]
    if kind == "string" and "maxLength" in schema and len(value) > schema["maxLength"]:
        return [f"{name} (at most {schema['maxLength']})"]
    out: list[str] = []
    if kind == "object":
        props = schema.get("properties") or {}
        out += [f"{at + '.' if at else ''}{k}" for k in schema.get("required") or [] if k not in value]
        if schema.get("additionalProperties") is False:
            out += [f"{at + '.' if at else ''}{k} (not known)" for k in value if k not in props]
        for k, sub in props.items():
            if k in value and isinstance(sub, dict):
                out += problems(sub, value[k], f"{at + '.' if at else ''}{k}")
    if kind == "string" and schema.get("enum") and value not in schema["enum"]:
        out.append(f"{name} ({', '.join(schema['enum'])})")
    return out


def over_rate(key_id: Any) -> bool:
    """ponytail: per-process window; a shared store if the door ever runs on several workers."""
    per_min = int(cfg()["limits"]["calls_per_minute"])
    now, q = time.monotonic(), _CALLS[key_id]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= per_min:
        return True
    q.append(now)
    return False


# --- JSON-RPC --------------------------------------------------------------------------------------------------------------

def _error(rid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": JSONRPC, "id": rid, "error": {"code": code, "message": message}}


def _content(text: str, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": error}


def answer(msg: Any, allowed, key_id: Any, ctx: dict) -> dict | None:
    """One JSON-RPC message -> its answer, or None for a notification. `allowed(row)` = may this caller use that tool."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != JSONRPC or not isinstance(msg.get("method"), str):
        return _error(msg.get("id") if isinstance(msg, dict) else None, INVALID, say("parse"))
    rid, method, params = msg.get("id"), msg["method"], msg.get("params") or {}
    if "id" not in msg:
        return None                                    # notifications/initialized and friends need no answer
    srv = cfg()["server"] | naming()
    if method == "initialize":
        offered_v = list(srv["protocol_versions"])
        asked = params.get("protocolVersion")
        return {"jsonrpc": JSONRPC, "id": rid, "result": {
            "protocolVersion": asked if asked in offered_v else offered_v[0], "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": srv["name"], "title": srv["title"], "version": str(srv["version"])}, "instructions": srv["instructions"]}}
    if method == "ping":
        return {"jsonrpc": JSONRPC, "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": JSONRPC, "id": rid, "result": {"tools": [
            {"name": r["name"], "title": r.get("title") or r["name"], "description": r.get("description") or "",
             "inputSchema": r.get("input_schema") or {"type": "object"}, "annotations": {"readOnlyHint": r.get("kind") != "change", "openWorldHint": False}}
            for r in offered(allowed)]}}
    if method != "tools/call":
        return _error(rid, NO_METHOD, say("unknown_method", method=method[:60]))
    name = str(params.get("name") or "")
    row = next((r for r in rows() if r["name"] == name), None)
    if not row or not ready(row):
        return _error(rid, BAD_PARAMS, say("unknown_tool", tool=name[:60]))
    if not row.get("on"):
        return _error(rid, BAD_PARAMS, say("tool_off", tool=name))
    if not allowed(row):
        return _error(rid, BAD_PARAMS, say("not_allowed", tool=name))
    if over_rate(key_id):
        return _error(rid, INVALID, say("rate"))
    args = params.get("arguments") or {}
    bad = problems(row.get("input_schema") or {"type": "object"}, args) if isinstance(args, dict) else ["arguments (object)"]
    if bad:
        return {"jsonrpc": JSONRPC, "id": rid, "result": _content(say("bad_input", tool=name, need=", ".join(bad[:8])), error=True)}
    if row.get("kind") == "human" and name not in TOOLS:     # a person's step: said, never run
        return {"jsonrpc": JSONRPC, "id": rid, "result": _content(say("human_step", title=row.get("title") or name, say=row.get("description") or ""))}
    try:
        out = TOOLS[name](args, ctx) if name in TOOLS else run_calls(row, args, ctx)
    except ToolError as e:
        return {"jsonrpc": JSONRPC, "id": rid, "result": _content(say(e.key, **e.slots), error=True)}
    except Exception as e:  # noqa: BLE001 - the AI hears the reason; the arguments are never logged
        return {"jsonrpc": JSONRPC, "id": rid, "result": _content(say("failed", why=str(getattr(e, "detail", "") or e)[:200]), error=True)}
    return {"jsonrpc": JSONRPC, "id": rid, "result": {**_content(json.dumps(out, ensure_ascii=False, default=str)), "structuredContent": out}}


# --- keys ------------------------------------------------------------------------------------------------------------------

def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def keys() -> list[dict]:
    return list(store.read(KEYS, []) or [])


def make_key(u: dict, label: str) -> dict:
    k = cfg()["key"]
    live = [x for x in keys() if not x.get("revoked_at")]
    if len(live) >= int(k["max_active"]):
        raise HTTPException(400, say("key_limit", max=k["max_active"]))
    raw = k["prefix"] + secrets.token_urlsafe(int(k["bytes"]))
    row = {"id": store.new_id(), "label": str(label or "").strip()[: int(k["label_chars"])] or say("key_default_label"),
           "hash": _hash(raw), "hint": raw[-4:], "made_by": u["id"], "made_at": store.now(), "revoked_at": "", "last_used": ""}
    store.write(KEYS, keys() + [row])
    return {"key": raw, "row": {x: row[x] for x in ("id", "label", "hint", "made_at")}, "message": say("key_made")}


def revoke_key(key_id: str) -> dict:
    all_ = keys()
    row = next((x for x in all_ if x["id"] == key_id and not x.get("revoked_at")), None)
    if not row:
        raise HTTPException(404, say("key_missing"))
    row["revoked_at"] = store.now()
    store.write(KEYS, all_)
    return {"message": say("key_revoked")}


def key_user(raw: str) -> tuple[dict | None, dict | None]:
    """The live key's row and its maker - only while the maker is still an owner."""
    h = _hash(raw or "")
    row = next((x for x in keys() if secrets.compare_digest(x["hash"], h) and not x.get("revoked_at")), None)
    u = store.user_by_id(row["made_by"]) if row else None
    if not u or engine.run("people.is_owner", {"role": u.get("role") or ""}) is not True:
        return None, None
    return u, row


def _base(request: Request) -> str:
    from core import mcp_oauth as oa  # noqa: PLC0415 - one reading of this site's public origin (https unless this computer)
    return oa.api_base(request)


def _refuse(request: Request, key: str) -> JSONResponse:
    """401 in words, pointing the AI app at Sign in (RFC 9728 resource_metadata) - the no-terminal road."""
    from core import mcp_oauth as oa  # noqa: PLC0415
    meta = f"{oa.api_base(request)}/.well-known/oauth-protected-resource/mcp"
    return JSONResponse(_error(None, INVALID, say(key)), status_code=401,
                        headers={"WWW-Authenticate": f'Bearer realm="mcp", resource_metadata="{meta}"'})


def caller(raw: str) -> tuple[dict | None, str, str]:
    """(user, rate id, refusal word) for a bearer: a sign-in token from an AI app, else an MCP key (For developers)."""
    from core import mcp_oauth as oa  # noqa: PLC0415
    if not raw:
        return None, "", "sign_in_needed"
    if raw.startswith(oa.cfg()["access_prefix"]):
        u, gid = oa.bearer_grant(raw)
        return u, f"grant:{gid}", "" if u else "token_bad"
    u, row = key_user(raw)
    if u:
        all_ = keys()
        for x in all_:
            if x["id"] == row["id"]:
                x["last_used"] = store.now()
        store.write(KEYS, all_)
    return u, (row or {}).get("id", ""), "" if u else "bad_key"


@router.post("/mcp")
async def mcp_door(request: Request):
    auth_ = request.headers.get("authorization") or ""
    u, rate_id, why = caller(auth_[7:].strip() if auth_.lower().startswith("bearer ") else "")
    if not u:
        return _refuse(request, why)
    try:
        body = json.loads(await request.body() or b"null")
    except ValueError:
        return JSONResponse(_error(None, PARSE, say("parse")), status_code=400)
    allowed = lambda r: access.may(u, "connect-ai", str(r.get("function") or ""))   # noqa: E731
    ctx = {"user": u, "base": _base(request), "app": request.app, "ip": auth.client_ip(request)}
    from starlette.concurrency import run_in_threadpool  # noqa: PLC0415 - a tool may call this same app (run_calls)
    got = await run_in_threadpool(lambda: [a for m in (body if isinstance(body, list) else [body])
                                           if (a := answer(m, allowed, rate_id, ctx)) is not None])
    if not got:
        return Response(status_code=202)
    return JSONResponse(got if isinstance(body, list) else got[0])


@router.get("/mcp")
@router.delete("/mcp")
def mcp_no_stream():
    return Response(status_code=405, headers={"Allow": "POST"})


def status(u: dict) -> dict:
    """The live line on the screen: the apps connected and the latest call by any of them or any key."""
    from core import mcp_oauth as oa  # noqa: PLC0415
    conns = oa.connections(u)
    used = [(c["last_used"], c["client"]) for c in conns if c["last_used"]]
    used += [(time.time() - store.seconds_since(k["last_used"]), k["label"])
             for k in keys() if k.get("last_used") and not k.get("revoked_at")]
    best = max(used, default=None)
    recent = bool(best) and time.time() - best[0] < float(cfg()["check"]["connected_days"]) * 86400
    return {"connections": conns, "last": {"at": best[0], "who": best[1]} if best else None, "connected": recent}


def check(u: dict, request: Request) -> dict:
    """Check: the real round trip through the door as this person - initialize, tools/list, one tool call (chip
    mcp.server check) - each step said in plain words; the first that fails says why."""
    ck = cfg()["check"]
    ctx = {"user": u, "base": _base(request), "app": request.app, "ip": auth.client_ip(request)}
    yes = lambda r: access.may(u, "connect-ai", str(r.get("function") or ""))   # noqa: E731
    steps = []
    init = answer({"jsonrpc": JSONRPC, "id": 1, "method": "initialize", "params": {}}, yes, f"check:{u['id']}", ctx)
    steps.append({"say": say("check_init"), "ok": "result" in init})
    listed = answer({"jsonrpc": JSONRPC, "id": 2, "method": "tools/list"}, yes, f"check:{u['id']}", ctx)
    n = len((listed.get("result") or {}).get("tools") or [])
    steps.append({"say": say("check_list", n=n), "ok": n > 0})
    got = answer({"jsonrpc": JSONRPC, "id": 3, "method": "tools/call", "params": {"name": ck["tool"], "arguments": ck["arguments"]}}, yes, f"check:{u['id']}", ctx)
    res = got.get("result") or {}
    ok = bool(res) and not res.get("isError")
    steps.append({"say": say("check_call", tool=ck["tool"]) if ok else say("check_failed", why=(res.get("content") or [{}])[0].get("text") or (got.get("error") or {}).get("message", "")), "ok": ok})
    return {"steps": steps, "ok": all(x["ok"] for x in steps), "message": say("check_ok") if all(x["ok"] for x in steps) else ""}


def _tool_rows(u: dict, a: dict) -> list[dict]:  # noqa: ARG001 - the screen's list (list mcp_tools: forgiving search)
    words = engine.run("ui.connect_ai")
    return [{"n": i, "name": r["name"], "title": r.get("title") or r["name"], "description": r.get("description") or "",
             "on": bool(r.get("on")), "ready": ready(r), "kind": r.get("kind") or "read",
             "kind_word": words.get(f"kind_{r.get('kind') or 'read'}", "")} for i, r in enumerate(rows())]


lists.source("mcp_tools", _tool_rows, screen="connect-ai")


@router.get("/api/core/mcp/status")
def api_mcp_status(u: dict = Depends(access.screen("connect-ai"))):
    return status(u)


@router.post("/api/core/mcp/check")
def api_mcp_check(request: Request, u: dict = Depends(access.screen("connect-ai"))):
    return check(u, request)


@router.get("/api/core/mcp")
def api_mcp(request: Request, u: dict = Depends(access.screen("connect-ai"))):
    srv = cfg()["server"] | naming()
    return {"url": f"{_base(request)}/mcp", "name": srv["name"], "title": srv["title"], "status": status(u), "poll_seconds": cfg()["poll_seconds"],
            "tools": [{"name": r["name"], "title": r.get("title") or r["name"], "description": r.get("description") or "",
                       "on": bool(r.get("on")), "ready": ready(r), "kind": r.get("kind") or "read"} for r in rows()],
            "keys": [{x: k[x] for x in ("id", "label", "hint", "made_at", "last_used")} for k in keys() if not k.get("revoked_at")],
            "max_keys": cfg()["key"]["max_active"]}


@router.post("/api/core/mcp/keys")
def api_mcp_key(body: dict = Body(default={}), u: dict = Depends(access.screen("connect-ai"))):
    return make_key(u, str((body or {}).get("label") or ""))


@router.delete("/api/core/mcp/keys/{key_id}")
def api_mcp_revoke(key_id: str, _: dict = Depends(access.screen("connect-ai"))):
    return revoke_key(key_id)


if __name__ == "__main__":  # ponytail: one runnable self-check - keys, the protocol, gates, input check, rate
    import tempfile
    from pathlib import Path
    store.DATA = Path(tempfile.mkdtemp())
    o = store.add_user("o@x.io", "password-o", role="owner")
    m = store.add_user("m@x.io", "password-m")
    tool("echo", lambda a, ctx: {"said": a["text"], "by": ctx["user"]["id"]})
    real = engine.run
    engine.run = lambda cid, args=None, *x: ({"tools": [{"name": "echo", "on": True, "function": "", "input_schema": {
        "type": "object", "properties": {"text": {"type": "string", "maxLength": 5}}, "required": ["text"], "additionalProperties": False}},
        {"name": "ghost", "on": True}]} if cid == "mcp.tools" else real(cid, args, *x))
    made = make_key(o, "Claude")
    assert made["key"].startswith(cfg()["key"]["prefix"]) and made["key"] not in json.dumps(keys()), "only the hash is kept"
    assert key_user(made["key"])[0]["id"] == o["id"] and key_user("nope") == (None, None)
    ctx, yes = {"user": o, "base": "http://x"}, (lambda r: True)
    init = answer({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}, yes, "k", ctx)
    assert init["result"]["protocolVersion"] == "2025-06-18" and init["result"]["serverInfo"]["name"]
    listed = answer({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, yes, "k", ctx)["result"]["tools"]
    assert [t["name"] for t in listed] == ["echo"], "a row with no attached answer is not offered"
    got = answer({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "echo", "arguments": {"text": "hi"}}}, yes, "k", ctx)
    assert got["result"]["structuredContent"] == {"said": "hi", "by": o["id"]}
    bad = answer({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "echo", "arguments": {"text": "too long", "x": 1}}}, yes, "k", ctx)
    assert bad["result"]["isError"] and "x (not known)" in bad["result"]["content"][0]["text"]
    assert answer({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "echo", "arguments": {"text": "a"}}}, lambda r: False, "k", ctx)["error"]
    assert answer({"jsonrpc": "2.0", "method": "notifications/initialized"}, yes, "k", ctx) is None
    assert answer({"jsonrpc": "2.0", "id": 6, "method": "resources/list"}, yes, "k", ctx)["error"]["code"] == NO_METHOD
    store.write("users", [x | ({"role": "member"} if x["id"] == o["id"] else {}) for x in store.read("users", [])])
    assert key_user(made["key"]) == (None, None), "a key dies with its maker's owner role"
    revoke_key(made["row"]["id"])
    assert not [k for k in keys() if not k["revoked_at"]], "revoked"
    for _ in range(int(cfg()["limits"]["calls_per_minute"])):
        over_rate("r")
    assert over_rate("r"), "too many calls in a minute are refused"
    engine.run = real
    print("mcp self-check OK")
