"""2026-10-24 Connect your AI (core/mcp.py + core/mcp_oauth.py, the SteadyMove / AstroStage door; chips mcp.server, mcp.tools,
ui.connect_ai, guide.connect_ai) - boilerplate, the same in every Fy portal: it reads the portal's OWN chip mcp.tools, so it
names no portal's tools. An AI app reaches the portal only at POST /mcp, signed in from the app (Allow) or with a key made on
the screen; only the Portal Admin's; only the tools; a person's step is said, never run; a tool that presses the portal's own
routes does so as the key's maker, so the guards and Portal Activity apply. Run by the portal's selfcheck.py:

    selfcheck_mcp.static_check(app); selfcheck_mcp.door_walk(app, owner, {"me": <a signed-in client who is not the Portal Admin>}, None)

(`member(app, owner)` makes such a client.) The bite test runs it on a copy of the portal folder."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _chip(rel: str) -> dict:
    return {p["name"]: p["default"] for p in json.loads((HERE / rel).read_text(encoding="utf-8"))["params"]}


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
    """Every tool row is complete, each call one of this portal's real routes, a person's step has no call, the screen is on
    the shell with its sign-in road, and Agent & MCP is gone for good."""
    from fastapi.routing import APIRoute
    from core import access, mcp
    routes = {(m, r.path) for r in app.app.routes if isinstance(r, APIRoute) for m in r.methods}
    for mod in list(sys.modules.values()):
        for x in getattr(getattr(mod, "router", None), "routes", []) or []:
            if isinstance(x, APIRoute):
                routes |= {(mm, x.path) for mm in x.methods}
    known = {(m, re.sub(r"\{[^}]+\}", "{}", p)) for m, p in routes} | {("GET", "/health")}
    rows = mcp.rows()
    assert len({r["name"] for r in rows}) == len(rows), "two tools of one name"
    k = mcp.cfg()
    check = next((r for r in rows if r["name"] == k["check"]["tool"]), None)
    assert check and check.get("kind", "read") == "read" and not (check.get("input_schema") or {}).get("required"), \
        f"chip mcp.tools needs the no-input read tool {k['check']['tool']!r} that Check runs (chip mcp.server check)"
    fns = {f["id"] for f in access._BY_ID["connect-ai"].get("functions", [])}  # noqa: SLF001
    for r in rows:
        assert r.get("kind", "read") in ("read", "change", "human") and r.get("title") and r.get("description"), r
        assert r.get("function") in fns, f"{r['name']}: its People & access function is not on the Connect your AI screen"
        if r.get("kind") == "human":
            assert not r.get("calls"), f"{r['name']}: a person's step must never be run"
            continue
        assert mcp.ready(r), f"{r['name']}: no calls and no module answer (core/mcp.tool)"
        for c in r.get("calls") or []:
            assert c["path"].startswith("/") and "://" not in c["path"], f"{r['name']}: {c['path']} is not one of this portal's own routes"
            here = re.sub(r"\{[^}]+\}", "x1", c["path"])        # a slot is one address part; a route's {slot} takes any part
            assert any(m == c["method"] and re.fullmatch(re.escape(p).replace(r"\{\}", "[^/]+"), here) for m, p in known), \
                f"{r['name']}: {c['method']} {c['path']} is not a route of this portal"
            if r.get("kind", "read") == "read":
                assert c["method"] == "GET", f"{r['name']} reads but calls {c['method']}"
    assert mcp._fill("/api/x/{a}", {"a": "../../api/smtp/log"}, path=True) == "/api/x/..%2F..%2Fapi%2Fsmtp%2Flog", \
        "a value walked out of its slot into another route"  # noqa: SLF001
    assert mcp._fill({"b": "<p>{t|html}</p>"}, {"t": "<b>hi</b> &"})["b"] == "<p>&lt;b&gt;hi&lt;/b&gt; &amp;</p>", "text for a page went in unescaped"  # noqa: SLF001
    # the door and the sign-in road are SERVED (asked live: a router that merely exists in a module is not served)
    from fastapi.testclient import TestClient
    live = TestClient(app.app)
    meta = live.get("/.well-known/oauth-protected-resource/mcp")
    assert meta.status_code == 200 and meta.json()["resource"].endswith("/mcp"), "Connect your AI lost its sign-in road (core/mcp_oauth.py)"
    srv = live.get("/.well-known/oauth-authorization-server")
    assert srv.status_code == 200 and {"authorization_endpoint", "token_endpoint", "registration_endpoint"} <= set(srv.json()), \
        "the AI app cannot find where to sign in (core/mcp_oauth.py)"
    assert live.post("/mcp", json={}).status_code == 401, "the door is not served at /mcp (core/mcp.py)"
    shell = (HERE / "core" / "static" / "shell.js").read_text(encoding="utf-8")
    assert "'connect-ai': () => import(" in shell, "the shell lost the Connect your AI screen"
    ca = (HERE / "core" / "static" / "page-connect-ai.js").read_text(encoding="utf-8")
    assert '<details class="card ca-dev">' in ca and ca.index('id="ca-status"') < ca.index('<details class="card ca-dev">'), \
        "Connect your AI: the live status comes first; keys and the command live only under the folded For developers"
    assert "list: 'mcp_tools'" in ca, "the tools list lost its forgiving search (list mcp_tools)"
    assert "pill solid" not in ca, "a pill outside a confirm dialog is white on white (--tone is set only in .modal.confirm)"
    g = _chip("chips/guide.connect_ai.json")
    tour = next(iter(sorted((HERE / "tours").glob("*-connect-ai.json"))), None)
    assert tour, "Connect your AI has no tour (tours/<prefix>-connect-ai.json, made from chip guide.connect_ai)"
    says = [x["say"] for x in json.loads(tour.read_text(encoding="utf-8"))["steps"]]
    assert says == [g["lede"]] + [x["say"] for x in g["steps"]], f"{tour.name} is not the Guide me walk of Connect your AI - rebuild it from chip guide.connect_ai"
    gone = [f for f in ("core/mcp_door.py", "tools/mcp/server.py", "static/page-mcp.js", "core/chips/ui.mcp.json") if (HERE / f).exists()]
    assert not gone and not any(s["id"] == "mcp" for s in access.CATALOG), f"Agent & MCP is back - one way everywhere is Connect your AI: {gone}"
    print(f"  connect your ai: {len(rows)} tools, each one of this portal's own routes or a person's step, sign-in road served OK")


def _rpc(client, key: str, method: str, params: dict | None = None, rid: int = 1):
    r = client.post("/mcp", headers={"Authorization": f"Bearer {key}"}, json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
    return r


def door_walk(app, c, co, other) -> None:  # noqa: ARG001 - the shared walk signature
    """The door on the real portal: the Portal Admin's key alone, only the tools, people's steps said, recorded as the owner."""
    from fastapi.testclient import TestClient
    from core import engine, mcp, store
    rows = mcp.rows()
    assert co["me"].get("/api/core/mcp").status_code == 403 and co["me"].post("/api/core/mcp/keys", json={}).status_code == 403, \
        "someone who is not the Portal Admin reached Connect your AI"
    made = c.post("/api/core/mcp/keys", json={"label": "selfcheck"})
    assert made.status_code == 200, made.text
    key = made.json()["key"]
    assert key not in json.dumps(store.read(mcp.KEYS, [])) and key not in c.get("/api/core/mcp").text, "the key itself was kept or shown again"
    bare = TestClient(app.app)
    bare.headers["X-Real-IP"] = "10.9.8.7"
    r = bare.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert r.status_code == 401 and "resource_metadata" in r.headers.get("www-authenticate", ""), "the door answers with no sign-in"
    assert _rpc(bare, key + "x", "ping").status_code == 401, "a wrong key works"
    init = _rpc(bare, key, "initialize", {"protocolVersion": "2025-06-18"}).json()["result"]
    assert init["serverInfo"]["title"] == engine.product_name() and init["instructions"], init
    listed = _rpc(bare, key, "tools/list").json()["result"]["tools"]
    assert [t["name"] for t in listed] == [r_["name"] for r_ in rows if r_.get("on")], "the tools offered are not the chip's"
    assert all(t["annotations"]["readOnlyHint"] == (r_.get("kind") != "change") for t, r_ in zip(listed, [x for x in rows if x.get("on")])), \
        "a change tool is offered as read-only (or a read as a change)"
    # every tool that needs no input answers through the door, as the owner, and the owner's call is in Portal Activity
    for r_ in [x for x in rows if x.get("kind", "read") == "read" and not (x.get("input_schema") or {}).get("required")]:
        got = _rpc(bare, key, "tools/call", {"name": r_["name"], "arguments": {}}).json()["result"]
        text = got["content"][0]["text"]
        # answered - or refused by the portal's OWN guard in plain words (CodyFy: a Portal Admin with no company); never a crash
        assert not got["isError"] or (text.startswith(mcp.say("failed", why="").rstrip()) and "Internal Server Error" not in text), \
            (f"tool {r_['name']} broke through the door", text[:200])
    last = next(c_["path"] for x in rows if x.get("kind", "read") == "read" and not (x.get("input_schema") or {}).get("required")
                for c_ in x.get("calls") or [] if not engine.run("ledger.skip_path", {"path": c_["path"]}))   # /health is never logged
    owner_email = c.get("/api/bootstrap").json()["user"]["email"]
    act = c.get("/api/core/activity", params={"q": last}).json()
    assert any(x.get("email") == owner_email and x.get("path") == last for x in act.get("rows") or []), (f"a tool's call ({last}) is not in Portal Activity as the owner", act.get("rows", [])[:3])
    # a person's step: said in its own words, never run
    for r_ in [x for x in rows if x.get("kind") == "human"]:
        got = _rpc(bare, key, "tools/call", {"name": r_["name"], "arguments": {}}).json()["result"]
        assert not got["isError"] and got["content"][0]["text"] == mcp.say("human_step", title=r_["title"], say=r_["description"]), got
    # only the tools: a name that is not a row, a missing input
    assert "error" in _rpc(bare, key, "tools/call", {"name": "smtp_log", "arguments": {}}).json(), "an unknown tool ran"
    need = next((x for x in rows if (x.get("input_schema") or {}).get("required") and x.get("kind") != "human"), None)
    if need:
        got = _rpc(bare, key, "tools/call", {"name": need["name"], "arguments": {}}).json()["result"]
        assert got["isError"], f"{need['name']} ran without its required input"
    # a key whose maker is NOT the Portal Admin (planted - or a Portal Admin since demoted) never works
    fake = mcp.cfg()["key"]["prefix"] + "planted-for-someone-else"
    who = co["me"].get("/api/bootstrap").json()["user"]["id"]
    store.write(mcp.KEYS, mcp.keys() + [{"id": "planted", "label": "x", "hash": mcp._hash(fake), "hint": "else", "made_by": who,  # noqa: SLF001
                                          "made_at": store.now(), "revoked_at": "", "last_used": ""}])
    assert _rpc(bare, fake, "tools/list").status_code == 401, "a key made for someone who is not the Portal Admin works"
    # Check: the real round trip, said step by step
    ck = c.post("/api/core/mcp/check").json()
    assert ck["ok"] and len(ck["steps"]) == 3, ("Check fails for the Portal Admin - the check tool must need no company (chip mcp.server check)", ck)
    # the screen's list forgives a typo
    t = next(x for x in rows if max(len(w) for w in re.findall(r"[A-Za-z]+", x["title"])) >= 6)
    word = max(re.findall(r"[A-Za-z]+", t["title"]), key=len).lower()
    lst = c.get("/api/lists/mcp_tools", params={"q": word[:2] + word[3:]}).json()
    assert any(x["name"] == t["name"] for x in lst["rows"]), (f"the tools list does not forgive a typo ({word[:2] + word[3:]})", lst)
    # revoked = stopped at once
    kid = made.json()["row"]["id"]
    assert c.delete(f"/api/core/mcp/keys/{kid}").status_code == 200 and _rpc(bare, key, "tools/list").status_code == 401, "a revoked key works"
    print("  connect your ai door: the Portal Admin's key alone, only the tools, people's steps said not run, in Portal Activity, Check OK")
