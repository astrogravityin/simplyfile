"""Two demo companies in the showcase data (2026-10-11 owner: ITR-6 "added to the showcase seed so the nightly demo reset includes
them"): Zenith Demo Traders (trading, 115BAA) and Kaveri Demo Fabricators (manufacturing, normal provisions, MAT, losses brought
forward) - their client masters (CIN, option, directors, shareholders), their documents uploaded and mapped (tools/showcase/
company_demo.py, invented), 26AS read, the red findings explained, and the company's year typed. Both end at a schema-valid ITR-6.
Run on a data dir after the showcase parts (record_all.sh does): python pre_companies.py <data dir>. Demo figures, not a real company's."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import os
import sys

os.environ["TV_DATA"] = os.environ["PORTAL_DATA"] = sys.argv[1]
sys.path.insert(0, _R)
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
os.chdir(_R)
import app  # noqa: E402,F401 - registers chips and the catalog
import clients  # noqa: E402
import compute  # noqa: E402
import intake  # noqa: E402
import itr_json  # noqa: E402
import recon  # noqa: E402
from core import store  # noqa: E402
import company_demo as demo  # noqa: E402

AY = demo.AY
import firms  # noqa: E402
ca = sorted((f for f in firms._all() if f.get("kind") == "ca_firm"), key=lambda f: f.get("name") != "Demo CA Filing Firm")  # noqa: SLF001
firm_user = next((u for f in ca for u in store.users() if u.get("firm_id") == f["id"] and u.get("firm_role") == "firm_admin"), None)
if not firm_user:
    sys.exit("pre_companies: no approved CA firm in this data (run the seed first)")
said = []
for key, x in demo.COMPANIES.items():
    mine = [c for c in clients._all() if c.get("firm_id") == firm_user["firm_id"]]  # noqa: SLF001
    if any(c["pan"] == x["client"]["pan"] for c in mine):
        said.append(f"{x['client']['name']} is there already")
        continue
    c = clients.save(firm_user, x["client"] | {"ay": AY})
    cid = c["id"]
    for name, data in demo.documents(key):
        if name.endswith(".txt"):
            recon.add(firm_user, cid, AY, name, data)
        else:
            intake.add(firm_user, cid, AY, name, data)
    for f in recon.findings(cid, AY)["findings"]:
        if f["severity"] == "red":
            recon.explain(firm_user, cid, AY, f["id"], "TDS u/s 194Q by buyers on our sales; the sales are in the books as revenue from operations.")
    compute.set_state(firm_user, cid, AY, {"company": x["year"]})
    rep = itr_json.report(cid, AY)
    d = compute.compute(cid, AY)
    assert rep["valid"], (key, rep["errors"][:5])
    said.append(f"{x['client']['name']}: income {d['income']:,.0f}, tax {d['tax']['total']:,.0f} ({d['tax']['basis']}), ITR-6 valid ({rep['filled']} values)")
print("pre_companies: " + "; ".join(said))
