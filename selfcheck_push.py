"""Push-stream guards (A20, owner 2026-11-08 "server tells, page never asks on a timer"; DomainTemplate W1.2).

1. no_polls()  - no page script asks the server on a timer. A `setInterval` is a poll unless its line says `ticks only`
                 (a clock / countdown that never calls the server) and its callback makes no call; a `setTimeout` that
                 redraws a whole page (`...Page(`) is a poll too. Files that still poll are listed in POLLING below: the
                 list may only SHRINK - a new poller fails, and a listed file that stopped polling must come off the list.
2. live()      - two people on a real server: the Portal Admin's page holds the stream, a member asks for access, and the
                 admin's bell count arrives in < 2 s with no reload (core/events.py + core/notify.py).

Called from selfcheck.py with one line each; `python selfcheck_push.py` runs both.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# ratchet: files that still poll (2026-11-11). Only shrinks. Each is a screen to move onto the stream (topic in chip events.settings).
POLLING: set[str] = set()   # 2026-11-20: static/dock.js left - the Connect badge hears the kit's push stream (ConnectPlus.onNews)
BUDGET_S = 2.0                           # the owner's bar for "rings the other in < 2 s" (gap plan W1.2)
_FETCH = re.compile(r"\bapi\(|\bfetch\(|\bPage\(|\bcountConnect\(|\.json\(\)")


def _call_text(src: str, start: int) -> str:
    """The text of the call opened at src[start] == '(' up to its matching ')'."""
    depth = 0
    for i in range(start, len(src)):
        depth += {"(": 1, ")": -1}.get(src[i], 0)
        if depth == 0:
            return src[start:i + 1]
    return src[start:]


def polls(src: str) -> list[str]:
    """Each timer in this script that asks the server - the line it starts on."""
    out = []
    for m in re.finditer(r"\bset(Interval|Timeout)\s*\(", src):
        body = _call_text(src, m.end() - 1)
        end = src.find("\n", m.start())
        line = src[src.rfind("\n", 0, m.start()) + 1: end if end >= 0 else len(src)]
        if m.group(1) == "Interval" and ("ticks only" not in line or _FETCH.search(body)):
            out.append(line.strip())
        elif m.group(1) == "Timeout" and re.search(r"\b\w+Page\(", body):
            out.append(line.strip())
    return out


def no_polls() -> None:
    # the guard bites: a planted poll is caught, a ticking clock is not
    assert polls("const t = setInterval(async () => { await api('/x'); }, 3000);"), "guard missed a setInterval fetch"
    assert polls("setInterval(() => fetch('/x'), 9e3); // ticks only"), "a `ticks only` line that fetches must still fail"
    assert polls("timer = setTimeout(() => { memoryPage(host); }, 5000);"), "guard missed a page that redraws itself on a timer"
    assert not polls("tick = setInterval(paint, 1000); // ticks only") and not polls("t = setTimeout(load, 250);")
    found = {}
    for f in sorted((HERE / "static").glob("*.js")) + sorted((HERE / "core" / "static").glob("*.js")):
        hits = polls(f.read_text(encoding="utf-8"))
        if hits:
            found[f.relative_to(HERE).as_posix()] = hits
    new = {k: v for k, v in found.items() if k not in POLLING}
    assert not new, f"a page asks the server on a timer - use the push stream (core/static/events.js onEvent): {new}"
    gone = POLLING - set(found)
    assert not gone, f"{sorted(gone)} no longer poll - take them off POLLING in selfcheck_push.py (the list only shrinks)"
    for name in ("core/static/shell.js", "core/static/ui.js", "static/page-tourvideo.js", "core/static/page-connect-ai.js"):
        assert name not in found, f"{name} polls again (bell / job progress / tour runs / MCP status come down the stream)"
    print(f"  no polls: {len(POLLING)} files still on the shrinking list, none new OK")


def _chip_defaults(name: str) -> dict:
    """A chip's defaults read from its file (the portal's own chips/ wins over core's) - never import core here: an import binds
    core.store to the real data folder before the api part sets its throw-away one (the starter's api check then saw accounts)."""
    chip = next((f for f in (HERE / "chips" / f"{name}.json", HERE / "core" / "chips" / f"{name}.json") if f.is_file()), None)
    if chip is None:                                   # a portal without that chip (no sso.settings: no outside sign-in page)
        return {}
    return {x["name"]: x.get("default") for x in json.loads(chip.read_text(encoding="utf-8"))["params"]}


def csp_enforced(pol: str) -> dict:
    """2026-11-18 gap audit C1-10 (N-23, class J) + week class 39: the ENFORCED policy (chip security.headers) has a host
    allow-list - an injected script may neither run from nor send data to another site. Returns the policy as directive -> sources."""
    parts = {p.split()[0]: p.split()[1:] for p in (pol or "").split(";") if p.strip()}
    for need in ("default-src", "script-src", "connect-src", "worker-src"):
        assert need in parts, f"the enforced CSP has no {need}: {pol!r}"
    for d, srcs in parts.items():
        bad = [s for s in srcs if s == "*" or s in ("'unsafe-eval'", "'strict-dynamic'")]
        assert not bad, f"the enforced CSP {d} allows {bad} - any site may run code or receive data: {pol!r}"
    for d in ("script-src", "connect-src"):
        named = [s for s in parts[d] if s.startswith("'") or re.fullmatch(r"(https|wss)://(\*\.)?[a-z0-9-]+(\.[a-z0-9-]+)+(:\d+)?", s)
                 or re.fullmatch(r"http://(127\.0\.0\.1|localhost)(:\d+)?", s)]   # the PC's own loopback (a local connector) is no other site
        assert named == parts[d] and "'unsafe-inline'" not in named, f"{d} must name its hosts (a *.domain is fine, * / https: is not): {parts[d]}"
    # 2026-11-20 prod: Connect Plus calls broke - LiveKit signals over wss://api.astrostage.in and Chromium 151 does NOT let
    # https://*.astrostage.in cover a wss:// subdomain (measured: BLOCKED by connect-src; same-origin wss stays 'self').
    # Every https host the page may call is listed again as wss, so a WebSocket to it (calls, live news) is never refused.
    no_ws = [s for s in parts["connect-src"] if s.startswith("https://") and "wss://" + s[8:] not in parts["connect-src"]]
    assert not no_ws, f"connect-src lists {no_ws} without its wss:// form - a WebSocket there (LiveKit calls) is blocked: {parts['connect-src']}"
    sso = re.sub(r"^(https?://[^/]+).*", r"\1", str(_chip_defaults("sso.settings").get("api") or ""))
    host = sso.split("://")[-1]
    ok = not sso or any(s == sso or (s.startswith("https://*.") and host.endswith(s[9:])) for s in parts["connect-src"])
    assert ok, f"the sign-in page calls {sso} (chip sso.settings api) but connect-src blocks it: {parts['connect-src']}"
    assert "'self'" in parts["worker-src"], f"worker-src must let the portal's own service worker start: {parts['worker-src']}"
    return parts


def csp_loopback_test() -> None:
    """2026-11-23 (lesson feedback_csp_connector_port_range): a local connector's loopback http address is named in connect-src;
    any other http host is still refused."""
    base = "default-src 'self'; script-src 'self'; worker-src 'self'; connect-src 'self' https://*.valuestream.in wss://*.valuestream.in {}"
    for ok in ("http://127.0.0.1:8898", "http://localhost:8907", "http://127.0.0.1"):
        csp_enforced(base.format(ok))
    for bad in ("http://evil.example.com", "http://127.0.0.1." + "evil" + ".test", "http://10.0.0.5:8898", "http://127.0.0.1:8898/x", "http:"):
        try:
            csp_enforced(base.format(bad))
        except AssertionError:
            continue
        raise AssertionError(f"csp_enforced let {bad} through")
    print("  CSP loopback: 127.0.0.1 / localhost named, remote http refused OK")


def csp_quiet() -> None:
    """2026-11-11 A20: the admin bell filled with 'Error Doctor needs you: CSP style-src-attr / style-src-elem at /start' -
    the shell draws with inline style attributes and <style> blocks on purpose. The policy must allow inline STYLES
    (chip security.headers) while scripts stay 'self', or every page view rings the owner (2026-11-18: the policy is enforced,
    report-only is gone - a forbidden inline style would now be a broken page, not just a note)."""
    pol = _chip_defaults("security.headers")["headers"]["Content-Security-Policy"]
    parts = csp_enforced(pol)
    inline = any('style="' in f.read_text(encoding="utf-8") for f in (HERE / "core" / "static").glob("*.js"))
    assert not inline or "'unsafe-inline'" in parts.get("style-src", []),         f"pages use inline styles but the CSP forbids them: {pol}"
    assert "'unsafe-inline'" not in parts.get("script-src", parts.get("default-src", [])), "inline scripts must stay blocked"
    print("  CSP (chip): enforced, hosts named for script/connect/worker, inline styles allowed, scripts 'self' OK")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def live() -> None:
    import httpx
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        data = str(Path(tmp) / "data")                    # both names: the api part leaves PORTAL_DATA set to ITS locked folder
        env = os.environ | {"TV_DATA": data, "PORTAL_DATA": data, "PYTHONIOENCODING": "utf-8"}
        env.pop("PORTAL_EDITION", None)
        log = open(Path(tmp) / "server.log", "w+b")          # a file, never a pipe: a full pipe stalls the server
        srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
                               cwd=HERE, env=env, stdout=log, stderr=log)
        try:
            for _ in range(300):
                try:
                    if httpx.get(f"{base}/health", timeout=1).status_code < 500:
                        break
                except httpx.HTTPError:
                    time.sleep(0.2)
            else:
                raise AssertionError("server never came up: " + (Path(tmp) / "server.log").read_text(errors="replace")[-2000:])
            owner, member = httpx.Client(base_url=base, timeout=10), httpx.Client(base_url=base, timeout=10)
            csp_enforced(owner.get("/").headers.get("content-security-policy", ""))   # C1-10: the policy a real answer carries
            print("  CSP read back from GET /: enforced, script-src + connect-src + worker-src, no * / unsafe-eval / strict-dynamic OK")
            owner.get("/api/bootstrap")                      # the empty portal makes its setup code (C1-9) in the data folder
            code = (Path(data) / "setup_code.txt").read_text(encoding="utf-8").strip()
            assert owner.post("/api/auth/first-account", json={"setup_code": code, "email": "owner@example.com", "password": "a-good-password"}).status_code == 200
            r = owner.post("/api/users", json={"email": "push-member@demo.example", "password": "a-good-password-p", "display_name": "Push Member"})
            assert r.status_code == 200, r.text
            assert member.post("/api/auth/signin", json={"identity": "push-member@demo.example", "password": "a-good-password-p"}).status_code == 200
            assert httpx.get(f"{base}/api/core/events", timeout=5).status_code == 401, "the stream is for a signed-in person only"
            topics = member.get("/api/bootstrap").json()["events"]["topics"]

            got: list = []
            hello = threading.Event()
            rang = threading.Event()

            def listen():                                      # client B: the Portal Admin's open page
                with owner.stream("GET", "/api/core/events", timeout=httpx.Timeout(10, read=30)) as s:
                    assert s.headers["content-type"].startswith("text/event-stream")
                    name = ""
                    for line in s.iter_lines():
                        if line.startswith("event: "):
                            name = line[7:]
                        elif line.startswith("data: ") and name == topics["bell"]:
                            got.append((time.monotonic(), json.loads(line[6:])))
                            (hello if len(got) == 1 else rang).set()
                            if rang.is_set():
                                return
            t = threading.Thread(target=listen, daemon=True)
            t.start()
            assert hello.wait(10) and got[0][1] == {"unread": 0}, f"the stream starts from the bell count now: {got}"
            screens = [s["id"] for s in member.get("/api/bootstrap").json().get("catalog", []) if not s.get("admin")]
            sent = None
            for sid in screens + ["approvals", "analytics", "server", "portalstats", "taxwatch"]:
                t0 = time.monotonic()
                r = member.post("/api/core/access/requests", json={"screen": sid, "reason": "push test"})
                if r.status_code == 200:
                    sent = t0
                    break
            assert sent, "no screen the member could ask for"
            assert rang.wait(BUDGET_S + 3), "the member's access request never reached the admin's open page"
            took = got[-1][0] - sent
            assert got[-1][1]["unread"] >= 1 and took < BUDGET_S, f"the bell took {took:.2f} s (bar {BUDGET_S} s): {got}"
            assert owner.get("/api/core/bell").json()["rows"][0]["href"], "the note links to the screen it is about"
            print(f"  push stream: member's access request rang the admin's open page in {took * 1000:.0f} ms, no reload OK")
        finally:
            srv.terminate()
            try:
                srv.wait(10)
            except subprocess.TimeoutExpired:
                srv.kill()
            log.close()


def memory_pushed() -> None:
    """A new Memory watch reading reaches a page that may open the screen (key s:memory), and only when one listens."""
    import asyncio
    sys.path.insert(0, str(HERE))
    import store  # noqa: F401 - registers the portal's chips
    from core import access, events, memwatch
    access.load(HERE / "catalog.json")                                   # who may open which screen

    async def _main():
        assert memwatch.SCREEN_KEY in events.keys_of({"id": "o", "role": "owner"}), "the owner's stream must carry Memory watch news"
        loop, q = asyncio.get_running_loop(), asyncio.Queue()
        memwatch.tell({"t": "nobody"})                                   # nobody listening: nothing made
        events._SUBS[memwatch.SCREEN_KEY].add((loop, q))  # noqa: SLF001
        try:
            memwatch.tell({"t": "x1"})
            _, name, data = await asyncio.wait_for(q.get(), 5)
            assert name == events.topic("memory") and data == {"t": "x1"} and q.empty(), (name, data)
        finally:
            events._SUBS[memwatch.SCREEN_KEY].discard((loop, q))  # noqa: SLF001
    asyncio.run(_main())
    print("  Memory watch pushed: each reading reaches open Memory watch pages OK")


def main() -> None:
    csp_loopback_test()
    no_polls()
    memory_pushed()
    csp_quiet()
    live()


if __name__ == "__main__":
    main()
    print("push checks passed.")
