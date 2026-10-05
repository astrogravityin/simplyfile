"""Throw-away data for rehearsing the showcase tour: owner + an approved firm 'Demo CA Filing Firm' (fake details), no clients.
Data dir = argv[1]. Test logins are in TEST-LOGIN.txt next to this script."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import os
import sys
from pathlib import Path

DATA = sys.argv[1]
os.environ["TV_DATA"] = DATA
sys.path.insert(0, _R + r"")
os.chdir(_R + r"")
from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402

HERE = Path(__file__).parent
creds = dict(line.split("=", 1) for line in (HERE / "TEST-LOGIN.txt").read_text().split())
PACK = Path(_R + r"\Requirements\Showcase - Demo CA Filing Firm\A Firm papers - placeholders")
adm = TestClient(app.app)
assert adm.post("/api/auth/first-account", json={"email": creds["admin"], "password": creds["admin_pw"]}).status_code == 200
assert adm.post("/api/users", json={"email": creds["uncle"], "password": creds["uncle_pw"], "display_name": "Demo CA Filing Firm"}).status_code == 200
ca = TestClient(app.app)
assert ca.post("/api/auth/signin", json={"identity": creds["uncle"], "password": creds["uncle_pw"]}).status_code == 200
fid = ca.post("/api/firm/start", json={"kind": "ca_firm"}).json()["id"]
ca.put("/api/firm", json={"name": "Demo CA Filing Firm", "pan": "AAFFP1234C", "tan": "HYDP12345E", "gstin": "36AAFFP1234C1Z5", "frn": "012345S",
                          "membership_no": "212345", "owner_name": "Demo Partner", "aadhaar_last4": "4821", "phone": "9000000001",
                          "email": creds["uncle"], "address": "Somajiguda, Hyderabad 500082", "consent": True})
for k, f in [("owner_aadhaar", "1"), ("pan_card", "2"), ("tan_letter", "3"), ("gst_cert", "4"), ("icai_cert", "5")]:
    p = next(PACK.glob(f"{f} *.pdf"))
    assert ca.post(f"/api/firm/docs/{k}", files={"file": (p.name, p.read_bytes())}).status_code == 200
assert ca.post(f"/api/firm/{fid}/move", json={"action": "submit"}).status_code == 200
assert adm.post(f"/api/firm/{fid}/move", json={"action": "approve"}).json()["state"] == "approved"
print("seeded", DATA)
