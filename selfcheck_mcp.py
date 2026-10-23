"""2026-10-23 Agent & MCP (core/mcp_door.py, tools/mcp/server.py, chips mcp.settings / mcp.tools / ui.mcp) - boilerplate, the same in
every portal: it reads the portal's OWN chip mcp.tools, so it names no portal's tools. The owner key works only while its person is
the Portal Admin, reaches only the tools' own routes, never a person's step, and its calls land in Portal Activity; the laptop
client calls only the address it is given (no default portal: a check can never reach production), carries the key only over
https or to this computer, and never calls a person's step. Run by the portal's selfcheck.py:

    selfcheck_mcp.static_check(app); selfcheck_mcp.door_walk(app, owner, {"me": <a signed-in client who is not the Portal Admin>}, None)
    selfcheck_mcp.client_walk()

(`member(app, owner)` makes such a client.) The bite test runs it on a copy of the portal folder."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLIENT = HERE / "tools" / "mcp" / "server.py"


def _chip(rel: str) -> dict:
    return {p["name"]: p["default"] for p in json.loads((HERE / rel).read_text(encoding="utf-8"))["params"]}


def _tools() -> list[dict]:
    return _chip("chips/mcp.tools.json")["tools"]


def _sample(rx: str) -> str:
    """One address a person's-step pattern catches ('' when this simple reading cannot make one)."""
    s = rx.lstrip("^").rstrip("$").replace("(/|$)", "")
    s = re.sub(r"\[\^/\]\+", "x1", s)
    s = re.sub(r"\(([^|()]*)\|[^()]*\)", r"\1", s)
    return s if s.startswith("/") and re.search(rx, s) else ""


def _bare(tools: list[dict], kind: str) -> list[dict]:
    """The tools of a kind that need no input."""
    return [t for t in tools if t["kind"] == kind and not (t.get("input") or {}).get("required")]


def member(app, owner):
    """A signed-in person who is NOT the Portal Admin (made by the owner on People & access), with their own address."""
    from fastapi.testclient import TestClient
    r = owner.post("/api/users", json={"email": "mcp-member@demo.example", "password": "a-good-password-mcp", "display_name": "Demo Member"})
    assert r.status_code == 200, r.text
    m = TestClient(app.app)
    m.headers["X-Real-IP"] = "10.9.8.6"
    assert m.post("/api/auth/signin", json={"identity": "mcp-member@demo.example", "password": "a-good-password-mcp"}).status_code == 200
    return {"me": m}


def static_check(app) -> None:
    """Every tool row is one of the portal's real routes; a person's step has no call; the client names no portal of its own."""
    from fastapi.routing import APIRoute
    routes = {(m, r.path) for r in app.app.routes if isinstance(r, APIRoute) for m in r.methods}
    for m in list(sys.modules.values()):
        r = getattr(m, "router", None)
        for x in getattr(r, "routes", []) or []:
            if isinstance(x, APIRoute):
                routes |= {(mm, x.path) for mm in x.methods}
    norm = lambda p: re.sub(r"\{[^}]+\}", "{}", p)  # noqa: E731
    known = {(m, norm(p)) for m, p in routes} | {("GET", "/health")}
    tools = _tools()
    assert len({t["name"] for t in tools}) == len(tools), "two tools of one name"
    assert _bare(tools, "read"), "chip mcp.tools needs a read tool with no input (the status Claude checks first)"
    for t in tools:
        assert t["kind"] in ("read", "change", "human") and t.get("title") and t.get("say"), t
        if t["kind"] == "human":
            assert not t.get("calls"), f"{t['name']}: a person's step must never be called"
            continue
        assert t.get("calls"), f"{t['name']}: no call"
        for c in t["calls"]:
            assert c["path"].startswith("/") and "://" not in c["path"], f"{t['name']}: {c['path']} is not one of this portal's own routes"
            here = re.sub(r"\{[^}]+\}", "x1", c["path"])        # a slot is one address part; a route's {slot} takes any part
            assert any(m == c["method"] and re.fullmatch(re.escape(p).replace(r"\{\}", "[^/]+"), here) for m, p in known), \
                f"{t['name']}: {c['method']} {c['path']} is not a route of this portal"
            if t["kind"] == "read":
                assert c["method"] == "GET", f"{t['name']} reads but calls {c['method']}"
    src = CLIENT.read_text(encoding="utf-8")
    assert not re.search(r"https?://[\w.-]+\.", src.split('"""', 2)[2]), "the client names a portal of its own - there must be no default address"
    k = _chip("core/chips/mcp.settings.json")
    assert not any("://" in str(v) for v in k.values()), "mcp.settings holds an address - the client must never have a default portal"
    js = (HERE / "static" / "page-mcp.js").read_text(encoding="utf-8")
    assert 'id="mcp-make"' in js, "the screen lost Make my key"
    assert "pill solid" not in js, "a pill in the shown-once popup: its colour (--tone) is set only in a confirm dialog - white on white"
    print(f"  agent & mcp: {len(tools)} tools, each one of this portal's own routes, people's steps never called, no default portal OK")


def door_walk(app, c, co, other) -> None:  # noqa: ARG001 - the shared walk signature
    """The owner key on the real portal: the Portal Admin's alone, on every call; only the tools; never a person's step; recorded."""
    from fastapi.testclient import TestClient
    from core import engine, mcp_door, store
    k = engine.run("mcp.settings")
    H = k["header"]
    tools = engine.run("mcp.tools")["tools"]
    assert co["me"].get("/api/mcp").status_code == 403 and co["me"].post("/api/mcp/key", json={}).status_code == 403, \
        "someone who is not the Portal Admin reached Agent & MCP"
    made = c.post("/api/mcp/key", json={})
    assert made.status_code == 200, made.text
    once = made.json()["once"]
    key = re.search(rf"{k['env_key']}=(\S+)", once).group(1)
    assert key.startswith(k["key_prefix"]) and made.json()["key"]["hint"] == key[-int(k["hint_len"]):], made.json()
    seen = c.get("/api/mcp").json()
    assert key not in json.dumps(seen) and seen["key"]["hint"] and "once" not in seen, "the key came back after it was shown once"
    assert key not in json.dumps(store.read(mcp_door.FILE, {})), "the key itself was kept - only its fingerprint may be"
    bare = TestClient(app.app)
    bare.headers["X-Real-IP"] = "10.9.8.7"
    ok = bare.get("/api/mcp/tools", headers={H: key})
    assert ok.status_code == 200 and [t["name"] for t in ok.json()["tools"]] == [t["name"] for t in tools], ok.text[:300]
    assert bare.get("/api/mcp/about", headers={H: key}).json()["build"], "about has no build"
    assert bare.get("/api/mcp/tools").status_code == 401, "the tools answer with no key"
    assert bare.get("/api/mcp/tools", headers={H: key + "x"}).status_code == 401, "a wrong key works"
    # every tool that needs no input answers through the door, as the owner
    for t in _bare(tools, "read"):
        for call in t["calls"]:
            r = bare.get(call["path"], headers={H: key})
            assert r.status_code < 400, (f"tool {t['name']}: {call['path']} answered {r.status_code} through the door", r.text[:200])
    # a key whose person is NOT the Portal Admin (planted for someone else - or a Portal Admin since demoted) never works
    fake = k["key_prefix"] + "planted-for-someone-else"
    rows = store.read(mcp_door.FILE, {})
    rows[co["me"].get("/api/bootstrap").json()["user"]["id"]] = {"th": mcp_door._th(fake), "hint": "else"}  # noqa: SLF001
    store.write(mcp_door.FILE, rows)
    r = bare.get("/api/mcp/tools", headers={H: fake})
    assert r.status_code == 401 and r.json()["detail"] == mcp_door.W("e_key"), ("a non-owner key works", r.status_code, r.text[:200])
    r = bare.get(_bare(tools, "read")[0]["calls"][-1]["path"], headers={H: fake})
    assert r.status_code == 401, ("a non-owner key reached a tool", r.status_code)
    # only the tools' own routes: an owner route that is not a tool, the key screen itself
    assert not mcp_door.allowed("GET", "/api/smtp/log"), "Recent mail must not be a tool"
    assert bare.get("/api/smtp/log", headers={H: key}).status_code == 403, "the key reached an owner route that is not a tool"
    assert bare.post("/api/mcp/key", headers={H: key}, json={}).status_code == 403, "a key made a key"
    # a person's step: refused with its own words, never attempted
    tried = 0
    for t in tools:
        for rx in t.get("paths") or [] if t["kind"] == "human" else []:
            p = _sample(rx)
            if not p:
                continue
            h = mcp_door.human_hit(p)
            for m in ("GET", "POST"):
                r = bare.request(m, p, headers={H: key}, **({"json": {}} if m == "POST" else {}))
                assert r.status_code == 403 and r.json()["detail"] == mcp_door.W("e_human", title=h["title"], say=h["say"]), \
                    (f"a person's step was attempted: {m} {p}", r.status_code, r.text[:200])
            tried += 1
    assert tried, "no person's step could be tried - chip mcp.tools needs a human row with paths"
    # a browser signed in as someone else: the key's call is the owner's, the browser's cookie is dropped
    assert co["me"].get("/api/mcp/tools", headers={H: key}).status_code == 200, "the door kept the browser's own sign-in"
    assert co["me"].get("/api/mcp/about", headers={H: key}).status_code == 200
    who = {x.get("email") for x in c.get("/api/core/activity", params={"q": "/api/mcp/about"}).json().get("rows") or []}
    assert who == {c.get("/api/bootstrap").json()["user"]["email"]}, ("a key call from someone else's browser was recorded as them", who)
    # Portal Activity has the call, as the Portal Admin
    owner_email = c.get("/api/bootstrap").json()["user"]["email"]
    act = c.get("/api/core/activity", params={"q": "/api/mcp/tools"}).json()     # the Portal Activity screen's own read
    hits = [(x.get("email"), x.get("path"), x.get("status")) for x in act.get("rows") or []]
    assert any(h[0] == owner_email and h[1] == "/api/mcp/tools" and h[2] == 200 for h in hits), ("a key call is not in Portal Activity", hits)
    assert c.get("/api/mcp").json()["key"]["uses"] >= 3, "last used / calls not counted"
    # a new key stops the old at once; Delete stops it too
    again = c.post("/api/mcp/key", json={}).json()["once"]
    key2 = re.search(rf"{k['env_key']}=(\S+)", again).group(1)
    assert bare.get("/api/mcp/tools", headers={H: key}).status_code == 401, "the old key still works after a new one was made"
    assert bare.get("/api/mcp/tools", headers={H: key2}).status_code == 200
    assert c.delete("/api/mcp/key").status_code == 200 and bare.get("/api/mcp/tools", headers={H: key2}).status_code == 401, "a deleted key works"
    # the tools list forgives a typo: a word of a tool's title with one letter dropped
    t = next(x for x in tools if max(len(w) for w in re.findall(r"[A-Za-z]+", x["title"])) >= 6)
    word = max(re.findall(r"[A-Za-z]+", t["title"]), key=len).lower()
    lst = c.get("/api/lists/mcp_tools", params={"q": word[:2] + word[3:]}).json()
    assert any(x["name"] == t["name"] for x in lst["rows"]), (f"the tools list does not forgive a typo ({word[:2] + word[3:]})", lst)
    print("  agent & mcp door: the Portal Admin's key alone, checked every call, only the tools, people's steps refused, in Portal Activity OK")


class _Rec(BaseHTTPRequestHandler):
    """A fake portal on 127.0.0.1 - or, as a proxy, the trap that proves no call left for anywhere else."""
    hits: list = []

    def log_message(self, *a):  # noqa: D401, ANN002
        pass

    def _go(self):
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n).decode() if n else ""
        self.hits.append((self.command, self.path, dict(self.headers), body))
        if self.command == "CONNECT" or self.path.startswith("http"):
            self.send_response(502)
            self.end_headers()
            return
        out = {"tools": _tools()} if self.path == "/api/mcp/tools" else {"ok": True, "id": "7", "code": "X-0007", "path": self.path}
        raw = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    do_GET = do_POST = do_PUT = do_DELETE = do_CONNECT = _go


def _serve(cls):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), type("H", (cls,), {"hits": []}))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _client(env: dict, msgs: list[dict]) -> list[dict]:
    lines = "".join(json.dumps(m) + "\n" for m in msgs)
    e = {k_: v for k_, v in os.environ.items() if not k_.startswith("PORTAL_MCP_")} | env
    out = subprocess.run([sys.executable, str(CLIENT)], input=lines, capture_output=True, text=True, encoding="utf-8", timeout=60, env=e)
    assert out.returncode == 0, out.stderr[-800:]
    return [json.loads(x) for x in out.stdout.splitlines() if x.strip()]


def _call(i: int, name: str, args: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}


def client_walk() -> None:
    """The laptop client over stdio against a fake portal on 127.0.0.1, with a proxy trap for every other address."""
    k = _chip("core/chips/mcp.settings.json")
    words = _chip("core/chips/ui.mcp.json")
    tools = _tools()
    first = _bare(tools, "read")[0]
    humans = [t for t in tools if t["kind"] == "human"]
    slotted = next((t for t in tools if t["kind"] != "human" and any(re.search(r"\{\w+\}", c["path"]) for c in t["calls"])), None)
    chained = next((t for t in tools if t["kind"] != "human" and len(t["calls"]) > 1), None)
    fake, trap = _serve(_Rec), _serve(_Rec)
    base = f"http://127.0.0.1:{fake.server_address[1]}"
    proxy = f"http://127.0.0.1:{trap.server_address[1]}"
    net = {"HTTP_PROXY": proxy, "HTTPS_PROXY": proxy, "http_proxy": proxy, "https_proxy": proxy, "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}
    try:
        # 1) no address: nothing is called - no default portal (the trap would see a call to production)
        got = _client(net | {k["env_key"]: "pak_test"}, [_call(1, first["name"])])
        assert got[0]["result"]["isError"] and k["env_url"] in got[0]["result"]["content"][0]["text"], got
        # 2) plain http to another computer never carries the key
        got = _client(net | {k["env_url"]: "http://portal.example.test", k["env_key"]: "pak_test"}, [_call(1, first["name"])])
        assert got[0]["result"]["isError"], got
        assert not trap.RequestHandlerClass.hits, f"the client called outside the address it was given: {trap.RequestHandlerClass.hits[:2]}"
        # 3) against the fake portal: the handshake, the tools, a read, people's steps, a value that tries to leave its slot
        env = net | {k["env_url"]: base, k["env_key"]: "pak_test"}
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": k["protocol_version"]}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                _call(3, first["name"]),
                {"jsonrpc": "2.0", "id": 4, "method": "nope"}]
        msgs += [_call(100 + i, t["name"]) for i, t in enumerate(humans)]
        if slotted:
            need = (slotted.get("input") or {}).get("required") or []
            msgs += [_call(5, slotted["name"], {r: "../../api/smtp/log" for r in need})]
            if need:
                msgs += [_call(6, slotted["name"], {})]
        if chained:
            msgs += [_call(7, chained["name"], {r: "Say <b>hi</b> & smile" for r in (chained.get("input") or {}).get("required") or []})]
        got = _client(env, msgs)
        by = {m["id"]: m for m in got}
        assert by[1]["result"]["capabilities"] == {"tools": {}} and by[1]["result"]["instructions"], by[1]
        assert [t["name"] for t in by[2]["result"]["tools"]] == [t["name"] for t in tools], by[2]
        assert not by[3]["result"]["isError"], by[3]
        assert by[4]["error"]["code"] == -32601, by[4]
        hits = fake.RequestHandlerClass.hits
        assert all(h[2].get(k["header"]) == "pak_test" for h in hits), "a call went without the owner key"
        paths = [(h[0], h[1].split("?")[0]) for h in hits]
        assert all((c["method"], c["path"]) in paths for c in first["calls"]), (first["name"], paths)
        for i, t in enumerate(humans):
            r = by[100 + i]["result"]
            assert not r["isError"] and r["content"][0]["text"].startswith(words["c_human"].split("{")[0]), r
        assert not any(re.search(rx, h[1]) for t in humans for rx in t.get("paths") or [] for h in hits), f"a person's step was called: {paths}"
        if slotted:
            assert not any(h[1].startswith("/api/smtp") for h in hits) and any("..%2F..%2Fapi%2Fsmtp%2Flog" in h[1] for h in hits), \
                ("a value walked out of its slot into another route", paths)
            if (slotted.get("input") or {}).get("required"):
                assert by[6]["result"]["isError"], by[6]
        if chained:
            r = by[7]["result"]
            assert not r["isError"], r
            mine = [p for p in paths if any(re.fullmatch(re.sub(r"\\\{\w+\\\}", "[^/]+", re.escape(c["path"])), p[1]) for c in chained["calls"])]
            assert len(mine) >= len(chained["calls"]), (chained["name"], paths)
            for c in chained["calls"]:
                if "|html}" in json.dumps(c.get("body") or {}):
                    sent = next(h[3] for h in hits if h[0] == c["method"] and h[3])
                    assert "&lt;b&gt;hi&lt;/b&gt; &amp; smile" in sent and "<b>hi" not in sent, ("text for a page went in unescaped", sent)
        for t in tools:
            if t.get("link"):
                got = _client(env, [_call(1, t["name"], {r: "X-0007" for r in (t.get("input") or {}).get("required") or []})])
                assert base in got[0]["result"]["content"][0]["text"], got
        assert not trap.RequestHandlerClass.hits, "a call left for another address"
    finally:
        fake.shutdown()
        trap.shutdown()
    print("  agent & mcp client: no default portal (nothing reached outside 127.0.0.1), key only over https/this computer, "
          "people's steps never called, slots stay in their route OK")
