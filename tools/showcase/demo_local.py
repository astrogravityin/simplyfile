"""The demo site on this machine, as visitors will see it: http://localhost:8835/tax/

    .venv/Scripts/python tools/showcase/demo_local.py          # fresh copy of tmp/demo/demo-tax-snapshot.tgz each start
    .venv/Scripts/python tools/showcase/demo_local.py --keep   # carry on with what you did last time
    .venv/Scripts/python tools/showcase/demo_local.py --test   # 2026-10-11: unpack a throw-away copy, sign a visitor in with the
                                                               # emailed code, check the seat, the clients and New filing's worked
                                                               # examples (chip wizard.cases) are all there, stop (free ports)

Unpacks the snapshot into tmp/demo/local, points its mail at a sink inside this script, and runs the portal in demo mode
(PORTAL_DEMO=1, PORTAL_BASE=/tax). The emailed sign-in code is printed here instead of being sent. Ctrl+C stops it."""
from __future__ import annotations

import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tarfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "tmp" / "demo" / "demo-tax-snapshot.tgz"
DATA = ROOT / "tmp" / "demo" / "local"
PORT, SINK = 8835, 1025
MAILS: list[str] = []


class Mail(socketserver.StreamRequestHandler):
    """Just enough SMTP to take one message and print its subject (the code) - nothing is sent anywhere."""

    def handle(self):
        say = lambda s: self.wfile.write((s + "\r\n").encode())  # noqa: E731
        say("220 sink")
        while line := self.rfile.readline():
            cmd = line.decode("utf-8", "replace").strip().upper()
            if cmd.startswith("DATA"):
                say("354 go")
                body = b""
                while (row := self.rfile.readline()) not in (b".\r\n", b".\n", b""):
                    body += row
                text = body.decode("utf-8", "replace")
                to = re.search(r"^To: (.*)$", text, re.M)
                subj = re.search(r"^Subject: (.*)$", text, re.M)
                print(f"\n  >>> mail to {to.group(1) if to else '?'}: {subj.group(1) if subj else '(no subject)'}\n", flush=True)
                MAILS.append(text)
                say("250 ok")
            elif cmd.startswith("QUIT"):
                say("221 bye")
                return
            else:
                say("250 ok")


def main() -> None:
    if not SNAP.exists():
        sys.exit(f"no snapshot at {SNAP} - make it with tools/showcase/record_all.sh (or pack_demo.py)")
    if "--keep" not in sys.argv or not DATA.exists():
        shutil.rmtree(DATA, ignore_errors=True)
        DATA.mkdir(parents=True)
        with tarfile.open(SNAP) as t:
            t.extractall(DATA, filter="data")
    (DATA / "smtp.json").write_text(json.dumps({"host": "127.0.0.1", "port": str(SINK), "security": "none", "username": "",
                                                "password": "", "from_email": "demo@valuestream.in", "from_name": "SimplyFy demo"}))
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    sink = socketserver.ThreadingTCPServer(("127.0.0.1", SINK), Mail)
    threading.Thread(target=sink.serve_forever, daemon=True).start()
    env = os.environ | {"PORTAL_DEMO": "1", "PORTAL_BASE": "/tax", "PORTAL_DATA": str(DATA), "TV_DATA": str(DATA),
                        "PORTAL_COOKIE": "sfdemo_local", "PORTAL_TRUSTED_PROXY": "none"}
    print(f"demo: http://localhost:{PORT}/tax/  - Try the demo, any name and email; the code shows up here", flush=True)
    try:
        subprocess.run([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(PORT)], cwd=ROOT, env=env)
    except KeyboardInterrupt:
        pass


def test() -> None:
    """The snapshot as a visitor meets it: a fresh copy, the demo's sign-in by code, then what they land on."""
    import http.cookiejar
    import time
    import urllib.error
    import urllib.request
    sys.path.insert(0, str(ROOT))
    import socket
    free = []
    for _ in range(2):                                     # two free ports: the portal's and the mail sink's
        with socket.socket() as so:
            so.bind(("127.0.0.1", 0))
            free.append(so.getsockname()[1])
    data, (port, sink_port) = ROOT / "tmp" / "demo" / "test", free
    shutil.rmtree(data, ignore_errors=True)
    data.mkdir(parents=True)
    with tarfile.open(SNAP) as t:
        t.extractall(data, filter="data")
    (data / "smtp.json").write_text(json.dumps({"host": "127.0.0.1", "port": str(sink_port), "security": "none", "username": "", "password": "",
                                                "from_email": "demo@valuestream.in", "from_name": "SimplyFy demo"}))
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    sink = socketserver.ThreadingTCPServer(("127.0.0.1", sink_port), Mail)
    threading.Thread(target=sink.serve_forever, daemon=True).start()
    env = os.environ | {"PORTAL_DEMO": "1", "PORTAL_BASE": "/tax", "PORTAL_DATA": str(data), "TV_DATA": str(data),
                        "PORTAL_COOKIE": "sfdemo_test_session", "PORTAL_TRUSTED_PROXY": "none"}
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                           stdout=open(data.parent / "test.log", "w"), stderr=subprocess.STDOUT)
    web = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = f"http://127.0.0.1:{port}/tax"

    def call(path, body=None):
        req = urllib.request.Request(base + path, json.dumps(body).encode() if body is not None else None, {"Content-Type": "application/json"})
        try:
            raw = web.open(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            raise AssertionError(f"{path}: {e.code} {e.read()[:200]!r}") from None
        try:
            return json.loads(raw or b"{}")
        except ValueError:
            raise AssertionError(f"{path}: not JSON - {raw[:120]!r}") from None
    try:
        for _ in range(60):
            try:
                web.open(base + "/", timeout=5)
                break
            except Exception:  # noqa: BLE001 - still starting
                time.sleep(1)
        email = "visitor.test@demo.example"
        call("/api/demo/code/send", {"name": "Demo Visitor", "email": email})
        for _ in range(120):
            if MAILS:
                break
            time.sleep(0.5)
        assert MAILS, "no code reached the mail sink"
        code = re.search(r"^Subject: .*?(\d{6})", MAILS[-1], re.M).group(1)
        call("/api/demo/code/check", {"name": "Demo Visitor", "email": email, "code": code})
        boot = call("/api/bootstrap")
        assert boot.get("user"), "the visitor is not signed in"
        assert (boot.get("edition") or {}).get("landing") == "#/clients", boot.get("edition")
        summary = call("/api/clients/summary?ay=2026-27")
        h = call("/api/wizard")
        from core import engine  # noqa: PLC0415
        import store  # noqa: F401,PLC0415
        want = {c["id"] for c in engine.run("wizard.cases")["rows"]}
        have = [x for x in h["sessions"] if x["client"]]
        assert len(have) >= len(want), (len(have), len(want))
        assert [w["id"] for w in h["who"]][:5] == ["individual", "huf", "firm", "llp", "aop"], h["who"]
        print(f"demo test PASS - a visitor signed in by code; lands on {boot['edition']['landing']} (New filing's cards on top); "
              f"{summary.get('active', summary)} clients; {len(have)} worked examples waiting in New filing; who-cards {[w['id'] for w in h['who']]}"
              f" + not yet {[w['id'] for w in h['not_yet']]}")
    finally:
        srv.terminate()
        sink.shutdown()


if __name__ == "__main__":
    test() if "--test" in sys.argv else main()
