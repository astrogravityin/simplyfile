"""Pick the local port this portal runs on - start.cmd / start.sh call it (owner 2026-11-22, lesson feedback_port_identify_then_next_free).

2026-11-22: a test server from another session took 127.0.0.1:8898, the YCS connector's port. The YCS page saw "something answers"
and said "Not running"; start.cmd here did worse - any 200 on 8850 meant "Starter is already running" and it opened the WRONG portal.
Rule: a port that answers is not proof it is us. Ask /health/run (local only) for "root"; reuse the port only when it is this folder,
else take the next free port from the preferred one and print it.

  python tools/pick_port.py 8850          -> "running 8850" (this portal already answers there) or "free 8851"
  python tools/pick_port.py --selfcheck   -> proves both answers on throwaway ports
Stdlib only: it runs before the .venv has its packages.
"""
from __future__ import annotations

import json
import socket
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPAN = 20  # ponytail: preferred..preferred+19; widen if more than 20 servers ever sit on one range


def ours(port: int, root: Path = ROOT, timeout: float = 1.5) -> bool:
    """True only when the server on this port says it runs from this folder."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health/run", timeout=timeout) as r:
            said = str(json.loads(r.read()).get("root") or "")
        return bool(said) and Path(said).resolve() == root.resolve()   # no "root" = an older portal or another app: not us
    except (OSError, ValueError, AttributeError):
        return False


def free(port: int) -> bool:
    """Nothing answers on 127.0.0.1 AND the port binds on every interface (Windows lets 0.0.0.0 bind over a 127.0.0.1 listener)."""
    with socket.socket() as c:
        c.settimeout(0.5)
        if c.connect_ex(("127.0.0.1", port)) == 0:
            return False
    with socket.socket() as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def pick(preferred: int, root: Path = ROOT) -> tuple[str, int]:
    span = range(preferred, min(preferred + SPAN, 65536))   # 2026-11-22: an OS-given port near 65535 ran past the top (OverflowError)
    for p in span:
        if not free(p) and ours(p, root):
            return "running", p
    for p in span:
        if free(p):
            return "free", p
    raise SystemExit(f"No free port between {preferred} and {span[-1]} - close a server you no longer need, then start again.")


def selfcheck() -> None:
    import http.server
    import tempfile
    import threading

    def serve(root: str) -> http.server.HTTPServer:
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                body = json.dumps({"status": "healthy", "root": root}).encode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv

    for other in (serve(tempfile.gettempdir()), serve("")):   # another app; an older portal with no "root" (2026-11-22 bug)
        p = other.server_address[1]
        got = pick(p)
        assert got[0] == "free" and got[1] != p, f"another app's port must be skipped, got {got}"
        other.shutdown()
    me = serve(str(ROOT))                           # this portal already running
    assert pick(me.server_address[1]) == ("running", me.server_address[1]), "this portal's own port must be reused"
    me.shutdown()
    assert pick(65530)[1] <= 65535, "the span must stop at 65535"   # raised OverflowError before the cap
    print("  ports: another app's port skipped, own running copy reused OK")


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        selfcheck()
    else:
        print(*pick(int(sys.argv[1]) if sys.argv[1:] else 8850))
