"""The demo site on this machine, as visitors will see it: http://localhost:8835/tax/

    .venv/Scripts/python tools/showcase/demo_local.py          # fresh copy of tmp/demo/demo-tax-snapshot.tgz each start
    .venv/Scripts/python tools/showcase/demo_local.py --keep   # carry on with what you did last time

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


if __name__ == "__main__":
    main()
