"""python tools/e2e_bankonly.py

"Small business - only a bank statement" end to end through the API, on a throw-away data folder (2026-10-13). A made-up statement
with the layout of a Kotak-style savings statement (tools/showcase/make_bankonly_demo.py: serial numbers, wrapped narration, page
head / footer on every page, members' UPI credits, own transfers, a lender's credit, a PhonePe credit, interest):
  A  the path is offered; the statement alone is the document needed (AIS / 26AS optional); the form says ITR-4
  B  upload: rows read, the statement adds up, the holder / address / refund account come from it; the popup asks only PAN, date of
     birth, mobile, e-mail and father's name; the client is made; Review opens Classify
  C  classification: customer receipts are the turnover - own money, the lender's credit, the refund and interest are not; the
     PhonePe credit is "Not sure" and left out until tapped; the taps change the turnover at once and survive a reload
  D  the return: ITR-4, 44AD profit = 6% of the digital turnover, savings interest added, no late fee while filing is voluntary (s.139(1) 7th proviso); 234F once a condition applies
  E  the ITR-4 JSON is valid against the department's schema (schemas/itr/ITR-4_2026_Main_V1.1.json) and carries the figures
  F  a statement that does not add up (one entry left out) is said so in plain words and is not used - no turnover, a red check
  G  GST: a turnover over the services limit warns, in the return and in the chip
Prints PASS / FAIL per step; exits 1 on any FAIL."""
import os
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tools" / "showcase"))
os.chdir(HERE)
os.environ["TV_DATA"] = tempfile.mkdtemp(prefix="sf-bankonly-")
sys.stdout.reconfigure(encoding="utf-8")
from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402
import make_bankonly_demo as demo  # noqa: E402

AY = "2026-27"
results, S = [], {}


def step(name):
    def wrap(fn):
        try:
            got = fn()
            results.append(("PASS", name, got or ""))
        except Exception as e:  # noqa: BLE001
            results.append(("FAIL", name, f"{type(e).__name__}: {e}"))
            traceback.print_exc()
        return fn
    return wrap


def session(email, pw):
    s = TestClient(app.app)
    r = s.post("/api/auth/signin", json={"identity": email, "password": pw})
    assert r.status_code == 200, r.text
    return s


admin = TestClient(app.app)
assert admin.post("/api/auth/first-account", json={"setup_code": app.auth.setup_code(), "email": "admin@valuestream.test", "password": "Admin-pass-123"}).status_code == 200
admin.post("/api/users", json={"email": "ca@demo.example", "password": "Demo-pass-1234", "display_name": "Demo Partner"})
ca = session("ca@demo.example", "Demo-pass-1234")
fid = ca.post("/api/firm/start", json={"kind": "ca_firm"}).json()["id"]
ca.put("/api/firm", json={"name": "Demo Bank Only CA Firm", "pan": "AAFFZ1234C", "tan": "HYDZ12345E", "gstin": "36AAFFZ1234C1Z5", "frn": "012399S",
                          "membership_no": "212399", "owner_name": "Demo Partner", "aadhaar_last4": "4821", "phone": "+91 90000 00009",
                          "email": "ca@demo.example", "address": "Demo Road, Hyderabad", "consent": True})
for k in ("owner_aadhaar", "pan_card", "tan_letter", "gst_cert"):
    ca.post(f"/api/firm/docs/{k}", files={"file": (f"{k}.pdf", b"%PDF-1.4 demo")})
ca.post(f"/api/firm/{fid}/move", json={"action": "submit"})
admin.post(f"/api/firm/{fid}/move", json={"action": "approve"})
PDF, TRUTH = demo.build_with_truth()


def upload(wid, data, name="Bank statement.pdf"):
    r = ca.post(f"/api/wizard/{wid}/files", files={"file": (name, data)}, data={"password": "", "on_same": ""})
    assert r.status_code == 200, r.text
    return r.json()


def groups(cid):
    w = ca.get(f"/api/myreturn/{cid}/{AY}").json()
    return w, {g["name"]: g for g in w["bank"]["classify"]["groups"] if g["dir"] == "cr"}


@step("A The path is offered; the bank statement is the one document needed; ITR-4")
def _():
    h = ca.get("/api/wizard").json()
    assert "bankonly" in h["offered"]["individual"]
    row = next(r for r in h["scenarios"] if r["id"] == "bankonly")
    assert row["group"] == "income" and set(row["implies"]) == {"business", "services", "presumptive"}, row
    v = ca.post("/api/wizard", json={"who": "individual", "picked": ["bankonly"]}).json()
    S["wid"] = v["id"]
    need = {d["id"]: d["need"] for d in v["docs"] if d["need"]}
    assert need["bank"] == "required" and need["ais"] == "optional" and need["26as"] == "optional", need
    assert v["form"]["form"] == "ITR-4", v["form"]
    return f"docs {need}; {v['form']['form']}"


@step("B Upload: rows read, adds up, holder + address + refund account from the statement; popup asks only what is missing")
def _():
    v = upload(S["wid"], PDF)
    c = v["cards"][0]
    assert c["kind"] == "bank" and c["state"] == "held" and not c["problems"], c
    labels = {f["label"]: f["value"] for f in c["found"]}
    assert labels["Entries read"] == str(TRUTH["rows"]) and labels["Adds up"].startswith("Yes"), labels
    assert [a["id"] for a in v["asks"]] == ["pan", "dob", "mobile", "email", "father"], [a["id"] for a in v["asks"]]
    v = ca.put(f"/api/wizard/{S['wid']}", json={"answers": {"pan": "ZZDPK0099K", "dob": "1990-01-01", "mobile": "9000000099",
                                                              "email": "anil.trainer@demo.example", "father": "Demo Father"}}).json()
    assert v["client"] and v["client"]["name"] == demo.HOLDER and v["client"]["pan"] == "ZZDPK0099K", v["client"]
    assert v["asks"] == [] and v["next"] == "classify" and v["link"].endswith("step=classify"), (v["asks"], v.get("next"))
    S["cid"] = v["client"]["id"]
    return f"client {v['client']['name']}; next {v['next']}"


@step("C Classification: receipts are turnover; own money, the loan, refund and interest are not; the PhonePe credit is Not sure")
def _():
    w, g = groups(S["cid"])
    cl = w["bank"]["classify"]
    assert w["bank"]["ok"] and w["bank"]["docs"][0]["rows"] == TRUTH["rows"]
    assert abs(w["bank"]["digital"] - TRUTH["receipt"]) < 0.01, (w["bank"]["digital"], TRUTH["receipt"])
    assert cl["totals"]["cr"]["own"] == TRUTH["own"] and cl["totals"]["cr"]["loan"] == TRUTH["loan"], cl["totals"]
    assert cl["totals"]["cr"]["ask"] == TRUTH["ask"] and cl["undecided"] == 1, cl["totals"]
    assert g["zz kreditbee demo finance"]["class"] == "loan" and g["phonepe"]["class"] == "ask" and g["zz anil kumar demo"]["class"] == "own", list(g)
    assert cl["interest"] == TRUTH["interest"]
    assert [c["what"] for c in w["checks"] if c["level"] != "ok"] == ["bank_undecided"], w["checks"]
    # the taps: PhonePe as a customer -> turnover up at once; back to a loan -> down again; both persisted by the server
    key = g["phonepe"]["key"]
    r = ca.put(f"/api/myreturn/{S['cid']}/{AY}", json={"bank_class": {key: "receipt"}}).json()
    assert abs(r["bank"]["digital"] - (TRUTH["receipt"] + TRUTH["ask"])) < 0.01 and r["bank"]["classify"]["undecided"] == 0
    assert ca.put(f"/api/myreturn/{S['cid']}/{AY}", json={"bank_class": {key: "loan"}}).json()["bank"]["digital"] == r["bank"]["digital"] - TRUTH["ask"]
    assert ca.put(f"/api/myreturn/{S['cid']}/{AY}", json={"bank_class": {key: "nonsense"}}).status_code == 400
    again = ca.get(f"/api/myreturn/{S['cid']}/{AY}").json()
    assert again["bank"]["digital"] == TRUTH["receipt"] and again["return"]["business"]["digital"] == TRUTH["receipt"]
    return f"turnover {again['bank']['digital']}; loan {cl['totals']['cr']['loan']}; own {cl['totals']['cr']['own']}; not sure {cl['totals']['cr']['ask']}"


@step("D The return: ITR-4, 44AD at 6% of the digital turnover, savings interest, late fee 234F (belated)")
def _():
    ca.put(f"/api/myreturn/{S['cid']}/{AY}", json={"business": {"kind": "44AD", "code": "20023", "name": "Fitness training"}})
    w = ca.put(f"/api/myreturn/{S['cid']}/{AY}", json={"bank_confirmed": True, "regime_seen": True, "reviewed": True}).json()
    g = w["regimes"][w["regime"]]
    assert w["form"]["form"] == "ITR-4" and w["steps"]["done"]["classify"] is True
    assert g["business"]["income"] == round(TRUTH["receipt"] * 6 / 100), g["business"]
    assert w["return"]["other"]["savings"] == TRUTH["interest"], w["return"]["other"]
    assert w["late"] is True and g["fee_234f"] == 0 and w["must_file"]["required"] is False, (g["fee_234f"], w["must_file"])   # income below the exemption: voluntary
    w2 = ca.put(f"/api/myreturn/{S['cid']}/{AY}", json={"answers": {"foreign_travel": True}}).json()
    assert w2["must_file"]["required"] is True and w2["must_file"]["why"] == "travel" and w2["regimes"][w2["regime"]]["fee_234f"] == 1000, w2["must_file"]
    ca.put(f"/api/myreturn/{S['cid']}/{AY}", json={"answers": {"foreign_travel": False}})
    assert w["bank"]["need"] == [], w["bank"]["need"]
    return f"profit {g['business']['income']}; total income {g['tax']['total']}; tax {g['net_tax']}; 234F {g['fee_234f']} (voluntary); to pay {g['balance']}"


@step("E The ITR-4 JSON is valid against the department's schema and carries the figures")
def _():
    rep = ca.get(f"/api/myreturn/{S['cid']}/{AY}/itr-check").json()
    assert rep["valid"] is True and rep["form"] == "ITR-4" and rep["schema"].startswith("ITR-4_2026"), rep
    js = ca.get(f"/api/myreturn/{S['cid']}/{AY}/itr.json").json()["ITR"]["ITR4"]
    p = js["ScheduleBP"]["PersumptiveInc44AD"]
    assert p["GrsTrnOverBank"] == round(TRUTH["receipt"]) and p["PersumptiveInc44AD6Per"] == round(TRUTH["receipt"] * 6 / 100), p
    ba = js["Refund"]["BankAccountDtls"]["AddtnlBankDetails"][0]
    assert ba["BankAccountNo"] == demo.ACCOUNT and ba["IFSCCode"] == demo.IFSC, ba
    return f"{rep['schema']}: valid, {rep['filled']} fields; 44AD 6% = {p['PersumptiveInc44AD6Per']}"


@step("F A statement that does not add up is refused in plain words and its figures are not used")
def _():
    bad, _t = demo.build_with_truth(drop=40)
    v = ca.post("/api/wizard", json={"who": "individual", "picked": ["bankonly"]}).json()
    v = upload(v["id"], bad)
    c = v["cards"][0]
    assert c["kind"] == "bank" and c["problems"] and "does not add up" in c["problems"][0], c
    labels = {f["label"]: f["value"] for f in c["found"]}
    assert labels["Adds up"].startswith("No"), labels
    v = ca.put(f"/api/wizard/{v['id']}", json={"answers": {"pan": "ZZDPK0098J", "dob": "1990-01-01", "mobile": "9000000098",
                                                             "email": "b@demo.example", "father": "Demo Father"}}).json()
    cid = v["client"]["id"]
    w = ca.get(f"/api/myreturn/{cid}/{AY}").json()
    assert w["bank"]["ok"] is False and w["bank"]["classify"] is None and w["return"]["business"]["digital"] == 0, w["bank"]
    assert any(x["what"] == "bank_recon" and x["level"] == "bad" for x in w["checks"]), w["checks"]
    return c["problems"][0][:110]


@step("G GST: turnover over the services limit warns; below it does not")
def _():
    w = ca.get(f"/api/myreturn/{S['cid']}/{AY}").json()
    assert w["bank"]["gst"]["over"] is False and w["bank"]["gst"]["limit"] == 2000000
    w = ca.put(f"/api/myreturn/{S['cid']}/{AY}", json={"business": {"kind": "44AD", "digital": "2500000"}}).json()
    assert w["bank"]["gst"]["over"] is True, w["bank"]["gst"]
    return "over at 25 lakh, limit 20 lakh"


for st, name, got in results:
    print(f"{st}  {name}  {got}")
sys.exit(1 if any(r[0] == "FAIL" for r in results) else 0)
