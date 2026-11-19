"""Egress - the one door every outbound fetch goes through (2026-11-18, gap audit C1-17: webhooks, providers, recite, push,
SSO, geo and the funds feed each opened their own URL, so a chip or credential row pointing at 127.0.0.1, 10.x or the cloud
metadata address 169.254.169.254 was fetched from inside the server - server-side request forgery).

    with egress.fetch(url_or_request, timeout=10, purpose="webhook") as r: ...

Refused (a urllib URLError, so callers' existing `except URLError` still catches it):
  * a scheme other than https (http only for a purpose the chip names in `exceptions`),
  * any address that is not public - private, loopback, link-local / metadata, CGNAT, multicast, reserved - unless the
    purpose's exception lists that network in `nets` (link-local and metadata never, whatever the chip says),
  * a host outside `hosts=` when the caller declares an allow-list.
The check is made on the IP the socket connects to (DNS resolved once, the vetted address is the one dialled, so a name that
re-resolves to 10.x between check and connect gets nowhere), and again on every redirect hop; a redirect to another host drops
the Authorization / key headers. Proxies from the environment are ignored (a proxy would hide the real target).

Every value - the exceptions, the words, the dropped headers, the files allowed to open a URL themselves and their ceiling -
is chip security.egress. Guard: python -m core.egress (refusals, a redirect into 10.x, the grep ratchet).
"""
from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from core import engine, ops

ROOT = Path(__file__).resolve().parent.parent
_resolve = socket.getaddrinfo        # one name, so the self-test can stand in for DNS


class Refused(urllib.error.URLError):
    """An outbound address this portal will not open."""


def K() -> dict:
    return engine.run("security.egress")


def _say(key: str, **values) -> str:
    return ops.template(K()["words"][key], values)


def rules(purpose: str = "", hosts: list | None = None) -> dict:
    ex = (K()["exceptions"] or {}).get(purpose) or {}
    return {"http": bool(ex.get("http")), "nets": [ipaddress.ip_network(n, strict=False) for n in ex.get("nets") or []],
            "hosts": [str(h).lower() for h in hosts] if hosts else None}


def check_url(url: str, r: dict) -> None:
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ("https", "http") or (u.scheme == "http" and not r["http"]):
        raise Refused(_say("scheme", scheme=u.scheme or "-", url=url[:80]))
    host = (u.hostname or "").lower()
    if not host or (r["hosts"] is not None and host not in r["hosts"]):
        raise Refused(_say("host", host=host or "-"))


def check_ip(ip: str, r: dict) -> None:
    a = ipaddress.ip_address(ip.split("%")[0])
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    if a.is_link_local or a.is_multicast or a.is_unspecified:
        raise Refused(_say("address", ip=str(a)))             # metadata 169.254.169.254 lives here: never, whatever the chip says
    if not a.is_global and not any(a in n for n in r["nets"]):
        raise Refused(_say("address", ip=str(a)))


def _connector(r: dict):
    def connect(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):  # type: ignore[attr-defined]  # noqa: SLF001
        host, port = address
        infos = _resolve(host, port, type=socket.SOCK_STREAM)
        for info in infos:                                    # every address the name gives must pass, not just the first
            check_ip(str(info[4][0]), r)
        last: OSError | None = None
        for fam, kind, proto, _, sa in infos:
            s = socket.socket(fam, kind, proto)
            try:
                if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:  # type: ignore[attr-defined]  # noqa: SLF001
                    s.settimeout(timeout)
                if source_address:
                    s.bind(source_address)
                s.connect(sa)                                 # the vetted address is the one dialled
                return s
            except OSError as e:
                s.close()
                last = e
        raise last or OSError(_say("address", ip=host))
    return connect


def _pinned(base):
    class Conn(base):
        def __init__(self, *a, rules: dict, **k):
            super().__init__(*a, **k)
            self._create_connection = _connector(rules)
    return Conn


_HTTP, _HTTPS = _pinned(http.client.HTTPConnection), _pinned(http.client.HTTPSConnection)


class _HttpH(urllib.request.HTTPHandler):
    def __init__(self, r: dict):
        super().__init__()
        self.r = r

    def http_open(self, req):
        return self.do_open(_HTTP, req, rules=self.r)


class _HttpsH(urllib.request.HTTPSHandler):
    def __init__(self, r: dict):
        super().__init__()
        self.r = r

    def https_open(self, req):
        return self.do_open(_HTTPS, req, context=self._context, rules=self.r)  # type: ignore[attr-defined]


class _Redirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, r: dict):
        super().__init__()
        self.r = r

    def http_error_302(self, req, fp, code, msg, headers):
        loc = headers.get("location") or headers.get("uri")
        if loc:                                               # each hop's scheme and host; its IP is checked when it connects
            check_url(urllib.parse.urljoin(req.full_url, loc), self.r)
        return super().http_error_302(req, fp, code, msg, headers)

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlsplit(newurl).hostname != urllib.parse.urlsplit(req.full_url).hostname:
            for h in K()["drop_on_host_change"]:
                new.remove_header(h.capitalize())
        return new


def opener(r: dict) -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _HttpH(r), _HttpsH(r), _Redirect(r))


def open_with(r: dict, req: str | urllib.request.Request, timeout: float):
    rq = req if isinstance(req, urllib.request.Request) else urllib.request.Request(req)
    check_url(rq.full_url, r)
    try:
        return opener(r).open(rq, timeout=timeout)
    except urllib.error.URLError as e:
        if isinstance(e.reason, Refused):                     # urllib wraps a refusal made while connecting; hand it back bare
            raise e.reason from None
        raise


def fetch(req: str | urllib.request.Request, *, timeout: float, purpose: str = "", hosts: list | None = None):
    """Open one outbound URL through the checks above; the response is used exactly like urlopen's."""
    return open_with(rules(purpose, hosts), req, timeout)


# --- the ratchet: no file opens a URL itself ---------------------------------------------------------------------------

def direct_fetches(root: Path = ROOT) -> dict[str, int]:
    """'relative/path.py' -> lines that open a URL without this door (chip security.egress direct_pattern)."""
    pat, out = re.compile(K()["direct_pattern"]), {}
    for f in sorted(root.rglob("*.py")):
        rel = f.relative_to(root).as_posix()
        if rel == "core/egress.py" or any(p.startswith(".") or p in {"node_modules", "__pycache__"} for p in f.relative_to(root).parts):
            continue
        n = sum(1 for line in f.read_text(encoding="utf-8", errors="replace").splitlines() if pat.search(line))
        if n:
            out[rel] = n
    return out


def ratchet_problems(root: Path = ROOT) -> list[str]:
    k, hits = K(), direct_fetches(root)
    bad = [_say("ratchet_file", file=f, n=n) for f, n in hits.items() if f not in k["direct_files"]]
    total = sum(n for f, n in hits.items() if f in k["direct_files"])
    if total > int(k["direct_ceiling"]):
        bad.append(_say("ratchet_ceiling", n=total, ceiling=k["direct_ceiling"]))
    return bad


def _self_test() -> None:
    import threading  # noqa: PLC0415
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: PLC0415

    def refused(url: str, purpose: str = "", hosts: list | None = None, r: dict | None = None) -> bool:
        try:
            open_with(rules(purpose, hosts) if r is None else r, url, 3).close()
        except Refused:
            return True
        except OSError:             # it dialled out (refused, timed out): the address was let through
            return False
        return False

    for ip in ("127.0.0.1", "169.254.169.254", "10.0.0.1", "192.168.1.1", "[::1]", "[::ffff:10.0.0.1]", "100.64.0.1", "0.0.0.0"):
        assert refused(f"https://{ip}/"), f"egress let https://{ip}/ through"
    assert refused("http://example.com/"), "egress let a plain-http address through for a purpose with no exception"
    assert refused("file:///etc/passwd"), "egress opened a file: address"
    assert refused("https://example.com/", hosts=["api.example.org"]), "egress ignored the caller's host allow-list"
    real = globals()["_resolve"]
    globals()["_resolve"] = lambda host, port, **_k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.2.3", port))]
    try:
        assert refused("https://looks-public.example/"), "egress trusted the NAME - a public-looking name resolving to 10.x went through"
    finally:
        globals()["_resolve"] = real
    loop: dict = {"http": True, "nets": [ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("169.254.0.0/16")], "hosts": None}
    assert refused("http://169.254.169.254/latest/meta-data/", r=loop), "the metadata address opened because a chip listed its net"

    seen: dict = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path.startswith("/to/"):
                self.send_response(302)
                self.send_header("Location", self.path[len("/to/"):].replace("_", "/").replace("~", ":"))
                self.end_headers()
                return
            seen["auth"] = self.headers.get("Authorization")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with open_with(loop, f"{base}/to/{base.replace(':', '~').replace('/', '_')}_ok", 5) as resp:
            assert resp.read() == b"ok", "a redirect inside the allowed net should still work (control)"
        assert refused(f"{base}/to/http~__10.0.0.1~{srv.server_address[1]}_x", r=loop), "a redirect into 10.x was followed"
        assert refused(f"{base}/to/http~__169.254.169.254_latest", r=loop), "a redirect to the metadata address was followed"
        assert refused(f"{base}/to/file~___etc_passwd", r=loop), "a redirect to file: was followed"
        tight = dict(loop, http=False)
        assert refused(f"{base}/", r=tight), "plain http opened though the purpose has no http exception"
        rq = urllib.request.Request(f"{base}/to/http~__localhost~{srv.server_address[1]}_ok", headers={"Authorization": "Bearer t"})
        loop6 = dict(loop, nets=[*loop["nets"], ipaddress.ip_network("::1/128")])
        with open_with(loop6, rq, 5) as resp:
            resp.read()
        assert seen.get("auth") is None, "a redirect to another host carried the Authorization header"
    finally:
        srv.shutdown()
    bad = ratchet_problems()
    assert not bad, "outbound fetch outside core/egress.py:\n  " + "\n  ".join(bad)
    print("egress ok:", sum(direct_fetches().values()), "direct lines in listed files, ceiling", K()["direct_ceiling"])


if __name__ == "__main__":
    _self_test()
