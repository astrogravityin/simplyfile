"""Before the My return tour: a self-filer (firm kind 'Individual / HUF') on the rehearsal server - the owner makes the account,
the person applies with their own (fake) details and papers, it is approved on submit, and their one client is themselves.
Optionally drops the demo documents in (tools/showcase/make_myreturn_demo.py writes them). Run from the repo root:

    python tools/showcase/pre_selfer.py [http://localhost:8832] [--docs]
"""
import http.cookiejar
import json
import sys
import urllib.request
import uuid
from pathlib import Path

BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "http://localhost:8832")
HERE = Path(__file__).parent
creds = dict(line.split("=", 1) for line in (HERE / "TEST-LOGIN.txt").read_text().split())
PACK = Path(r"Requirements/Showcase - Demo CA Filing Firm/A Firm papers - placeholders")
DOCS = Path("tools/tour_video/showcase/self")


def client():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def call(web, method, path, body=None, files=None):
    if files:
        b = uuid.uuid4().hex
        data = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{n}\"\r\n\r\n".encode() + v + b"\r\n" for k, (n, v) in files.items())
        data += f"--{b}--\r\n".encode()
        req = urllib.request.Request(BASE + path, data, {"Content-Type": f"multipart/form-data; boundary={b}"}, method=method)
    else:
        req = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None, {"Content-Type": "application/json"}, method=method)
    try:
        with web.open(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:300]}


adm, me = client(), client()
call(adm, "POST", "/api/auth/signin", {"identity": creds["admin"], "password": creds["admin_pw"]})
call(adm, "POST", "/api/users", {"email": creds["selfer"], "password": creds["selfer_pw"], "display_name": "Anil Kumar Demo"})
assert "error" not in call(me, "POST", "/api/auth/signin", {"identity": creds["selfer"], "password": creds["selfer_pw"]}), "sign-in"
f = call(me, "POST", "/api/firm/start", {"kind": "self"})
fid = f.get("id") or call(me, "GET", "/api/firm").get("id")
call(me, "PUT", "/api/firm", {"name": "Anil Kumar Demo", "pan": "ZZDPK0042Q", "owner_name": "Anil Kumar Demo", "aadhaar_last4": "0042",
                              "phone": "9000000042", "email": creds["selfer"], "address": "Flat 42, Demo Residency, Madhapur, Hyderabad 500081",
                              "consent": True})
print("submit (approved at once):", call(me, "POST", f"/api/firm/{fid}/move", {"action": "submit"}).get("state"))
home = call(me, "GET", "/api/myreturn")
print("my return:", home.get("self"), [c["name"] for c in home.get("clients", [])])
if "--docs" in sys.argv and home.get("clients"):
    cid, ay = home["clients"][0]["id"], home["current_ay"]
    for p in sorted(DOCS.iterdir()):
        d = call(me, "POST", f"/api/myreturn/{cid}/{ay}/docs", files={"file": (p.name, p.read_bytes())})
        print(" ", p.name, "->", (d.get("added") or {}).get("kind") or d)
