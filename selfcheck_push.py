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
POLLING = {
    "static/dock.js",                    # Connect Plus kit's own chat-list badge (k.list_poll_ms) - the kit's stream is next
    "core/static/page-connect-ai.js",    # Connect your AI: MCP status re-read while open - an `mcp` topic is next
    "core/static/page-memory.js",        # Memory watch Auto refresh - a `memory` topic is next
}
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
    for name in ("core/static/shell.js", "core/static/ui.js", "static/page-tourvideo.js"):
        assert name not in found, f"{name} polls again (bell / job progress / tour runs come down the stream)"
    print(f"  no polls: {len(POLLING)} files still on the shrinking list, none new OK")


def csp_quiet() -> None:
    """2026-11-11 A20: the admin bell filled with 'Error Doctor needs you: CSP style-src-attr / style-src-elem at /start' -
    the shell draws with inline style attributes and <style> blocks on purpose. The report-only policy must allow inline
    STYLES (chip security.headers) while scripts stay 'self', or every page view rings the owner again."""
    sys.path.insert(0, str(HERE))
    from core import engine
    pol = engine.run("security.headers")["headers"]["Content-Security-Policy-Report-Only"]
    parts = {p.split()[0]: p.split()[1:] for p in pol.split(";") if p.strip()}
    inline = any('style="' in f.read_text(encoding="utf-8") for f in (HERE / "core" / "static").glob("*.js"))
    assert not inline or "'unsafe-inline'" in parts.get("style-src", []),         f"pages use inline styles but the report-only CSP forbids them - the Doctor floods the owner's bell: {pol}"
    assert "'unsafe-inline'" not in parts.get("script-src", parts.get("default-src", [])), "inline scripts must stay reported"
    print("  CSP report-only: inline styles allowed, scripts 'self' (no Doctor flood) OK")


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
            assert owner.post("/api/auth/first-account", json={"email": "owner@example.com", "password": "a-good-password"}).status_code == 200
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


def main() -> None:
    no_polls()
    csp_quiet()
    live()


if __name__ == "__main__":
    main()
    print("push checks passed.")
