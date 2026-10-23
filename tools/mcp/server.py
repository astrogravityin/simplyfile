"""Agent & MCP - the laptop side (2026-10-23 owner). Claude Code starts this as an MCP server over stdio:

    claude mcp add <portal> --scope user -e PORTAL_MCP_URL=https://<portal> -e PORTAL_MCP_KEY=<owner key> -- python "<folder>/tools/mcp/server.py"

(the exact line, key filled in once, is on Admin > Agent & MCP). Each tool is a row of the portal's chip mcp.tools - one of its own
routes, called with the owner key in a header (core/mcp_door.py checks it on every call). This file holds no business logic and no
word: knobs from core/chips/mcp.settings.json, words from core/chips/ui.mcp.json (both read from this folder, then the portal's own
answer wins), tools from the portal (GET /api/mcp/tools; this folder's chips/mcp.tools.json while it cannot be reached).
  - no address = no call: there is NO default portal, so nothing here can reach production by itself;
  - plain http carries the key only to this computer (chip local_hosts);
  - a person's step (kind human: sign-ins, permissions, merge, payments) is never called - its words say what the person does.
Standard library only (any Python 3.10+). Guard: selfcheck_mcp.py client_walk."""
from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]


def _chip(rel: str) -> dict:
    c = json.loads((HERE / rel).read_text(encoding="utf-8"))
    return {p["name"]: p["default"] for p in c["params"]}


def _product() -> str:
    e = _chip("chips/edition.settings.json")
    rows = e.get("rows") or [{}]
    want = os.environ.get("PORTAL_EDITION") or e.get("default_edition") or ""
    return next((r for r in rows if r.get("id") == want), rows[0]).get("product_name", "")


PRODUCT = _product()


def _named(v):
    if isinstance(v, str):
        return v.replace("{product}", PRODUCT)
    if isinstance(v, list):
        return [_named(x) for x in v]
    if isinstance(v, dict):
        return {k: _named(x) for k, x in v.items()}
    return v


K = _named(_chip("core/chips/mcp.settings.json"))
WORDS = _named({k: v for k, v in _chip("core/chips/ui.mcp.json").items() if k.startswith("c_")})
URL = (os.environ.get(K["env_url"]) or "").strip().rstrip("/")
KEY = (os.environ.get(K["env_key"]) or "").strip()


def W(key: str, **v) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(v.get(m.group(1), m.group(0))), WORDS[key])


def problem() -> str:
    """Why no call may go out ('' = it may): no address, no key, or plain http to another computer."""
    if not URL:
        return W("c_no_url", env_url=K["env_url"])
    u = urllib.parse.urlsplit(URL)
    if u.scheme not in ("https", "http") or not u.hostname or u.query or u.fragment or (u.scheme == "http" and u.hostname not in K["local_hosts"]):
        return W("c_bad_url", url=URL)
    return "" if KEY else W("c_no_key", env_key=K["env_key"])


class Refused(Exception):
    pass


def call(method: str, path: str, body=None, query: dict | None = None):
    """One route of the portal, with the owner key. Only ever URL + a path that starts with one '/'."""
    why = problem()
    if why:
        raise Refused(why)
    if not path.startswith("/") or path.startswith("//") or "://" in path:
        raise Refused(W("c_unknown", name=path))
    q = urllib.parse.urlencode({k: v for k, v in (query or {}).items() if v not in ("", None)})
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(URL + path + (f"?{q}" if q else ""), data=data, method=method,
                                 headers={K["header"]: KEY, "Accept": "application/json", "User-Agent": K["user_agent"],
                                          **({"Content-Type": "application/json"} if data is not None else {})})
    try:
        with urllib.request.urlopen(req, timeout=float(K["timeout_s"])) as r:   # noqa: S310 - the scheme is checked in problem()
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(raw).get("detail")
        except ValueError:
            detail = raw
        if isinstance(detail, dict):
            detail = detail.get("message") or json.dumps(detail)
        raise Refused(W("c_failed", status=e.code, detail=str(detail or e.reason)[:600])) from None
    except (urllib.error.URLError, OSError) as e:
        raise Refused(W("c_unreachable", why=str(getattr(e, "reason", e))[:200])) from None
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def _tools() -> list[dict]:
    try:
        got = call("GET", "/api/mcp/tools")
        WORDS.update(got.get("words") or {})
        return got["tools"]
    except (Refused, KeyError, AttributeError, TypeError):
        return _named(_chip("chips/mcp.tools.json"))["tools"]


TOOLS: list[dict] = []


def tools() -> list[dict]:
    if not TOOLS:
        TOOLS.extend(_tools())
    return TOOLS


def _fill(v, slots: dict, path: bool = False):
    """{slot} from the input / an earlier call; "{x}" alone keeps x's own type; {x|html} is escaped for a page."""
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
            return urllib.parse.quote(x, safe="")      # a slot is one address part - never a '/' or '..' into another route
        return html.escape(x) if m.group(2) == "html" else x
    return re.sub(r"\{(\w+)(?:\|(\w+))?\}", one, v)


def run(name: str, args: dict) -> tuple[str, bool]:
    t = next((x for x in tools() if x["name"] == name), None)
    if not t:
        return W("c_unknown", name=name), True
    if t["kind"] == "human":
        return W("c_human", title=t["title"], say=t["say"]), False
    slots = {**(t.get("defaults") or {}), **{k: v for k, v in (args or {}).items() if v not in ("", None)}}
    need = [r for r in (t.get("input") or {}).get("required", []) if r not in slots]
    if need:
        return W("c_need", name=name, what=", ".join(need)), True
    out = []
    try:
        for c in t.get("calls") or []:
            got = call(c["method"], _fill(c["path"], slots, path=True), _fill(c.get("body"), slots) if "body" in c else None,
                       _fill(c.get("query") or {}, slots))
            if isinstance(got, dict):
                slots |= {s: got.get(k) for s, k in (c.get("save") or {}).items()}
                if c.get("keep"):
                    got = {k: got.get(k) for k in c["keep"]}
            out.append({"call": f"{c['method']} {c['path']}", "answer": got})
    except Refused as e:
        return "\n".join([json.dumps(out, ensure_ascii=False, indent=1)] * bool(out) + [str(e)]), True
    text = json.dumps(out[0]["answer"] if len(out) == 1 else out, ensure_ascii=False, indent=1)
    if t.get("link"):
        text += "\n" + W("c_link", link=URL + _fill(t["link"], slots, path=True))
    most = int(K["max_chars"])
    return (text[:most] + "\n" + W("c_cut", n=most)) if len(text) > most else text, False


def answer(msg: dict) -> dict | None:
    m, mid = msg.get("method"), msg.get("id")
    if mid is None:                      # a notification (notifications/initialized ...): nothing to answer
        return None
    if m == "initialize":
        res = {"protocolVersion": (msg.get("params") or {}).get("protocolVersion") or K["protocol_version"],
               "capabilities": {"tools": {}}, "serverInfo": {"name": K["server_name"], "version": "1"},
               "instructions": WORDS["c_instructions"]}
    elif m == "ping":
        res = {}
    elif m == "tools/list":
        res = {"tools": [{"name": t["name"], "title": t["title"], "description": t["say"],
                          "inputSchema": t.get("input") or {"type": "object", "properties": {}},
                          "annotations": {"readOnlyHint": t["kind"] != "change"}} for t in tools()]}
    elif m == "tools/call":
        p = msg.get("params") or {}
        text, bad = run(str(p.get("name") or ""), p.get("arguments") or {})
        res = {"content": [{"type": "text", "text": text}], "isError": bad}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": W("c_unknown", name=m)}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}


def main() -> None:
    for f in (sys.stdin, sys.stdout):
        f.reconfigure(encoding="utf-8")      # Windows consoles default to a code page; MCP speaks UTF-8
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        out = answer(msg)
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
