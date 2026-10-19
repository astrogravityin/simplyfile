"""My return end to end, in a scratch data folder (2026-10-06): a self-filer's client, the four demo documents read, the checks,
both regimes, the form, and the ITR JSON checked against the department's schema. Run from the repo root after
tools/showcase/make_myreturn_demo.py:

    python tools/e2e_myreturn.py
"""
import os
import sys
sys.stdout.reconfigure(encoding="utf-8")   # rupee signs in the report, even when piped (Windows cp1252)
import tempfile
from pathlib import Path

os.environ["PORTAL_DATA"] = tempfile.mkdtemp(prefix="mr-e2e-")
os.environ["TV_DATA"] = os.environ["PORTAL_DATA"]
sys.path.insert(0, ".")
import store  # noqa: E402,F401 - maps the portal's settings and registers its chips, as the app does
import clients  # noqa: E402
import myreturn  # noqa: E402
import itr_json  # noqa: E402
import myreturn_read  # noqa: E402

DOCS = Path("tools/tour_video/showcase/self")
u = {"id": "u-demo", "firm_id": "", "role": "owner"}
c = clients.save(u, {"name": "Anil Kumar Demo", "pan": "ZZDPK0042Q", "status": "individual", "email": "anil.demo@demo.example",
                     "phone": "9000000042", "address": "Flat 42, Demo Residency, Madhapur, Hyderabad 500081"})
cid, ay = c["id"], clients.settings()["current_ay"]
fails = []


def ok(cond, what):
    print(("PASS " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


# 2026-10-19 owner (rules and assumptions beside the JSON): every return built here also says its rules, and none reads a fact
# that is not there (a blank in the sentence) - chip itr.assumptions, itr_json.assumptions
_assemble = itr_json.assemble


def _assemble_with_rules(f, form):
    d_, r_ = _assemble(f, form)
    ok(r_["rules"]["count"] > 0 and not r_["rules"]["missing"], f"{form}: the rules beside the JSON read real facts (missing {r_['rules']['missing']})")
    return d_, r_


itr_json.assemble = _assemble_with_rules


for f in sorted(DOCS.iterdir()):
    d = myreturn.add_doc(u, cid, ay, f.name, f.read_bytes())
    a = d["added"]
    print(f"  {f.name}: {a['kind']} via {a['method']} - " + "; ".join(f"{x['label']} {x['value']}" for x in a["found"]) + (f" | {a['problems']}" if a["problems"] else ""))
    ok(a["kind"] in ("prefill", "form16", "ais", "26as"), f"{f.name} recognised")
w = myreturn.answer(u, cid, ay, {"answers": {"father": "Demo Father", "metro": False}, "regime_seen": True, "reviewed": True})
r = w["return"]
e = r["employers"][0] if r["employers"] else {}
ok(e.get("gross_17_1") == 1440000 and e.get("tan") == "HYDD00042E", f"salary from Form 16: {e.get('gross_17_1')} {e.get('tan')}")
ok(r["via"]["c80c"] == 150000 and r["via"]["c80ccd2"] == 72000, f"deductions from Form 16: {r['via']}")
ok(r["other"]["savings"] == 18400 and r["other"]["deposits"] == 62000 and r["other"]["dividend"] == 9500, f"interest and dividend from AIS: {r['other']}")
ok(sum(t["tds"] for t in r["tds"]) == 138200, f"TDS from 26AS: {[(t['tan'], t['tds']) for t in r['tds']]}")
ok(r["banks"] and r["banks"][0]["ifsc"] == "DEMO0000042", "refund bank from the pre-filled JSON")
for g in ("new", "old"):
    x = w["regimes"][g]
    print(f"  {g}: income {x['tax']['total']} tax {x['tax']['tax']} fee {x['fee_234f']} interest {x['interest']['total']} balance {x['balance']}")
ok(w["better"]["better"] in ("new", "old"), f"cheaper regime: {w['better']}")
ok(w["form"]["form"] == "ITR-1", f"form: {w['form']}")
ok(all(x["level"] == "ok" for x in w["checks"]), f"checks agree: {[(x['what'], x['level'], x.get('gap')) for x in w['checks']]}")
name, data, rep = myreturn.export(cid, ay)
print("  JSON", name, len(data), "bytes;", rep["filled"], "values;", rep["error_count"], "schema problems")
for x in rep["errors"][:30]:
    print("   -", x["path"], "|", x["message"][:110])
ok(rep["valid"], "ITR-1 JSON fits the department's schema")
# filed on time: the dates, fee and regime as of that day; the filed JSON compared figure by figure
w = myreturn.answer(u, cid, ay, {"answers": {"filed_on": "2026-07-20"}})
ok(w["dates"]["kind"] == "original" and w["dates"]["due"] == 20260731, f"filed 20 July is an original return: {w['dates']['kind']} due {w['dates']['due']}")
ok(w["regimes"]["new"]["fee_234f"] == 0 and w["old_ok"], f"no late fee, old regime open: fee {w['regimes']['new']['fee_234f']} old_ok {w['old_ok']}")
name, data, rep = myreturn.export(cid, ay)
myreturn.add_doc(u, cid, ay, "filed " + name, data)
cmp = myreturn.compare(cid, ay)
print("  compare:", [(x["key"], x["ours"], x["theirs"], x["level"]) for x in cmp["rows"]])
ok(cmp["same"] and len(cmp["rows"]) >= 10, f"the filed JSON agrees figure by figure ({len(cmp['rows'])} figures)")
w = myreturn.answer(u, cid, ay, {"answers": {"filed_on": ""}})
# capital gains beyond the ITR-1 limit -> ITR-2
w = myreturn.answer(u, cid, ay, {"edits": {"cg": {"stcg_111a": 40000, "ltcg_112a": 210000}}})
ok(w["form"]["form"] == "ITR-2" and w["form"]["why"] == "why_cg", f"gains make it ITR-2: {w['form']}")
t = w["regimes"]["new"]["tax"]
ok(t["on_special"] == 18625, f"special-rate tax 20% of 40,000 + 12.5% of 85,000 = 18,625: {t['on_special']}")
name, data, rep = myreturn.export(cid, ay)
print("  JSON", name, len(data), "bytes;", rep["filled"], "values;", rep["error_count"], "schema problems")
for x in rep["errors"][:40]:
    print("   -", x["path"], "|", x["message"][:110])
ok(rep["valid"], "ITR-2 JSON fits the department's schema")
# a let-out house at a loss, health cover for self and senior parents, old regime (filed by the due date)
myreturn.answer(u, cid, ay, {"answers": {"filed_on": "2026-07-20", "parents_senior": True}})
w = myreturn.answer(u, cid, ay, {"houses": [{"kind": "let", "rent": 120000, "municipal_tax": 10000, "interest": 350000, "address": "Flat 1, Demo Towers"}],
                                 "edits": {"via": {"c80d_self": 20000, "c80d_parents": 30000}}, "regime": "old"})
doc, rep = itr_json.assemble(myreturn.facts(cid, ay), "ITR-2")
for x in rep["errors"][:40]:
    print("   -", x["path"], "|", x["message"][:110])
it2 = doc["ITR"]["ITR2"]
ok(rep["valid"], "ITR-2 with a house loss and 80D fits the schema")
ok(it2["ScheduleHP"]["TotalIncomeChargeableUnHP"] < 0 and it2["ScheduleCYLA"]["Salary"]["IncCYLA"]["HPlossCurYrSetoff"] > 0,
   f"house loss shown and set off against salary: {it2['ScheduleHP']['TotalIncomeChargeableUnHP']}")
d80 = it2["Schedule80D"]["Sec80DSelfFamSrCtznHealth"]
ok(d80["SelfAndFamily"] == 20000 and d80["ParentsSeniorCitizen"] == 30000 and d80["EligibleAmountOfDedn"] == 50000, f"80D split: {d80}")
ok(it2["ScheduleCGFor23"]["LongTermCapGain23"]["SaleOfEquityShareUs112A"]["BalanceCG"] == 210000, "112A gain in Schedule CG")
# 2026-10-07: the employer's address from Form 16 Part A (the demo's "Hyderabad 500081" names no state: the PIN says Telangana)
sal0 = it2["ScheduleS"]["Salaries"][0]["AddressDetail"]
ok(sal0["StateCode"] == "36" and sal0.get("PinCode") == 500081 and sal0["CityOrTownOrDistrict"] == "Hyderabad", f"employer's state, PIN and city from Form 16: {sal0}")
ok({x["SecCode"] for x in it2["ScheduleSI"]["SplCodeRateTax"]} == {"1A", "2A"} and it2["ScheduleSI"]["TotSplRateInc"] == 40000 + 85000,
   f"Schedule SI lists 111A and 112A: {it2['ScheduleSI']}")
blk = myreturn_read.employer_block("\n".join([
    "   Name and address of the Employer/Specified Bank                 Name and address of the Employee/Specified senior citizen",
    "   ACME DEMO PRIVATE LIMITED                                       DEMO PERSON",
    "   4TH FLOOR, DEMO TOWER, OUTER RING ROAD, BENGALURU -             FLAT 9, DEMO NAGAR, MYSURU - 570001",
    "   560103 Karnataka                                                 Karnataka",
    "   +(91)80-40000000", "   payroll@demo.example", "   PAN of the Deductor          TAN of the Deductor"]))
ok(blk.get("state") == "15" and blk.get("pin") == "560103" and blk.get("city") == "BENGALURU" and blk.get("email") == "payroll@demo.example",
   f"a two-column Form 16 Part A: the employer's column only: {blk}")
w = myreturn.answer(u, cid, ay, {"answers": {"filed_on": ""}, "houses": [], "regime": ""})
# start from documents (no client added first): a filed return names a new person; the pre-filled JSON finds the old one
import json  # noqa: E402
filed = json.loads(json.dumps(doc).replace("ZZDPK0042Q", "ZZDPK0043R"))
s1 = myreturn.start(u, ay, "filed.json", json.dumps(filed).encode())
ok(s1["cid"] != cid and clients.get(s1["cid"])["pan"] == "ZZDPK0043R" and clients.get(s1["cid"])["status"] == "individual"
   and s1["added"]["kind"] == "filed" and s1["step"] == "gather", f"filed return starts a new client, open on Gather: {s1['said']}")
pre = sorted(DOCS.iterdir())[0]
q = myreturn.start(u, ay, pre.name, pre.read_bytes())
ok(q.get("ask", {}).get("why") == "start" and q["ask"]["cid"] == cid and q["ask"]["have"], "a return already there: asked first, nothing touched")
ok(myreturn.start(u, ay, pre.name, pre.read_bytes(), on_old="continue")["cid"] == cid, "carry on: the pre-filled JSON goes into the return already there")
ais = next(f for f in sorted(DOCS.iterdir()) if "AIS" in f.name)
n_ais = lambda: len([x for x in myreturn.state(cid, ay)["docs"] if x["kind"] == "ais"])  # noqa: E731
q = myreturn.add_doc(u, cid, ay, "another AIS.pdf", ais.read_bytes())
ok(q.get("ask", {}).get("why") == "same" and n_ais() == 1, "a second AIS (another name) asks first: replace or keep both")
myreturn.add_doc(u, cid, ay, "another AIS.pdf", ais.read_bytes(), on_same="replace")
ok(n_ais() == 1 and next(x for x in myreturn.state(cid, ay)["docs"] if x["kind"] == "ais")["name"] == "another AIS.pdf"
   and any(myreturn.folder(cid, ay).glob("*.v1.pdf")), "replace: the new AIS in, the old one kept for History")

try:
    myreturn.start(u, ay, "x.json", b"{}")
    ok(False, "a file naming nobody is refused")
except Exception as e:  # noqa: BLE001
    ok(getattr(e, "status_code", 0) == 400, f"a file naming nobody is refused: {getattr(e, 'detail', e)}")
before = myreturn.work(cid, ay)["return"]["paid"]
w = myreturn.answer(u, cid, ay, {"paid": [{"kind": "self", "date": "2026-07-20", "amount": "12345"}]})
ok(len(w["return"]["paid"]) == len(before) + 1 and w["return"]["paid"][-1]["minor"] == "300", "tax paid with the return, typed on Check, counts as self-assessment")
myreturn.answer(u, cid, ay, {"paid": []})
f0 = sorted(DOCS.iterdir())[0]
again = myreturn.add_doc(u, cid, ay, f0.name, f0.read_bytes())
same = [x for x in myreturn.state(cid, ay)["docs"] if x["name"] == f0.name]
vs = myreturn.state(cid, ay)["docs"][-1]["version"]
ok(len(same) == 1 and vs >= 2 and (myreturn.folder(cid, ay) / f"{same[0]['id']}.v{vs - 1}{same[0]['ext']}").exists(),
   f"the same file again replaces it (v{vs}), the old one kept")
gone = myreturn.state(cid, ay)["docs"][0]
myreturn.remove_doc(u, cid, ay, gone["id"])
ok((myreturn.folder(cid, ay) / f"{gone['id']}.v1{gone['ext']}").exists(), "a removed document is kept for History (.v1)")
n_before = len(myreturn.state(cid, ay)["docs"])
st = myreturn.start(u, ay, pre.name, pre.read_bytes(), on_old="fresh")
docs_now = myreturn.state(cid, ay)["docs"]
ok(n_before > 1 and len(docs_now) == 1 and st["step"] == "gather" and any(myreturn.folder(cid, ay).glob("before-*.json")),
   "start again: one document (this one), the rest kept for History, the old return saved beside it")
# a consultant with no Form 16 (2026-10-06): 44ADA receipts from the bank, advance tax paid once in March -> ITR-4
k = clients.save(u, {"name": "Kavya Demo Consultant", "pan": "ZZDPC0044K", "status": "individual", "dob": "1985-05-05",
                     "email": "kavya.demo@demo.example", "phone": "9000000044", "address": "Flat 44, Demo Residency, Madhapur, Hyderabad 500081"})
kid = k["id"]
w = myreturn.answer(u, kid, ay, {"business": {"kind": "44ADA", "code": "14001", "name": "Kavya Demo Consulting", "digital": 1800000,
                                              "gstin": "36ZZDPC0044K1Z5", "gst_turnover": 1800000},
                                 "paid": [{"kind": "advance", "date": "2026-03-14", "amount": 60000, "bsr": "0510002", "challan": "12345"}],
                                 "answers": {"father": "Demo Father", "filed_on": "2026-08-20"}, "regime_seen": True, "reviewed": True})
bz = w["regimes"][w["regime"]]["business"]
ok(w["form"]["form"] == "ITR-4" and bz["income"] == 900000 and bz["receipts"] == 1800000, f"44ADA 18 lakh receipts -> 9 lakh income, ITR-4: {w['form']}")
ok(w["regimes"][w["regime"]]["interest"]["c"] == 0, f"one advance-tax instalment by 15 March is enough for 44ADA (234C): {w['regimes'][w['regime']]['interest']}")
ok(any(c2[0] == "14001" for c2 in w["biz_codes"]["44ADA"]), "the nature-of-work codes come from the department's ITR-4 schema")
doc4, rep4 = itr_json.assemble(myreturn.facts(kid, ay), "ITR-4")
for x in rep4["errors"][:30]:
    print("   -", x["path"], "|", x["message"][:110])
ok(rep4["valid"], "ITR-4 with 44ADA, GSTIN and advance tax fits the department's schema")
bp = doc4["ITR"]["ITR4"]["ScheduleBP"]
ok(bp["PersumptiveInc44ADA"]["TotPersumptiveInc44ADA"] == 900000 and bp["NatOfBus44ADA"][0]["CodeADA"] == "14001", "Schedule BP: 44ADA receipts, income and nature of work")
# her bank statement, as CSV, Excel and PDF: the year's receipts sorted from interest, cash and her own transfers
import io  # noqa: E402
ROWS = [["Date", "Narration", "Chq/Ref No", "Withdrawal Amt", "Deposit Amt", "Closing Balance"],
        ["01/04/2025", "NEFT CR-DEMO CLIENT ONE-INV 101", "N1", "", "1,50,000.00", "1,50,000.00"],
        ["15/04/2025", "UPI-DEMO GROCER", "U1", "2,000.00", "", "1,48,000.00"],
        ["30/06/2025", "INT.PD:0000000000:01-04-2025 TO 30-06-2025", "", "", "812.00", "1,48,812.00"],
        ["05/07/2025", "BY CASH DEPOSIT CDM", "", "", "20,000.00", "1,68,812.00"],
        ["10/07/2025", "TRF FROM SELF A/C DEMO", "", "", "50,000.00", "2,18,812.00"],
        ["12/08/2025", "IMPS-DEMO CLIENT TWO-FEES", "I2", "", "3,00,000.00", "5,18,812.00"]]
csv_bytes = ("\n".join(",".join(f'"{c}"' for c in r) for r in ROWS) + "\n").encode()
import openpyxl  # noqa: E402
wb = openpyxl.Workbook()
for r in ROWS:
    wb.active.append(r)
xb = io.BytesIO()
wb.save(xb)
from reportlab.lib.pagesizes import A4, landscape  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402
pb = io.BytesIO()
cv = canvas.Canvas(pb, pagesize=landscape(A4))
cv.setFont("Helvetica", 9)
cv.drawString(30, 560, "Statement of Account - Demo Bank - Kavya Demo Consultant")
for j, r in enumerate(ROWS):
    for x, cell_ in zip((30, 110, 380, 470, 580, 690), r):
        cv.drawString(x, 530 - 18 * j, cell_)
cv.save()
for nm, data in (("Demo Bank statement.csv", csv_bytes), ("Demo Bank statement.xlsx", xb.getvalue()), ("Demo Bank statement.pdf", pb.getvalue())):
    got = myreturn_read.read(nm, data)
    bk = (got["facts"] or {}).get("bank") or {}
    ok(got["kind"] == "bank" and bk.get("receipts") == 450000 and bk.get("cash") == 20000 and bk.get("interest") == 812,
       f"{nm[-4:]} bank statement read: receipts {bk.get('receipts')}, cash {bk.get('cash')}, interest {bk.get('interest')} {got['problems']}")
myreturn.add_doc(u, kid, ay, "Demo Bank statement.csv", csv_bytes)
w = myreturn.work(kid, ay)
ok(w["return"]["bank"]["receipts"] == 450000 and w["return"]["bank"]["statements"] == 1, "the statement's receipts are offered to the business card")
w = myreturn.answer(u, kid, ay, {"business": {"kind": "44ADA", "digital": 6000000, "cash": 1000000}})
ok(w["form"]["form"] == "ITR-3" and w["form"]["why"] == "why_biz_limit", "receipts over the 44ADA limit: ITR-3 with books")
ok((w["ca_needed"] or {}).get("why") == "ca_audit_turnover", f"70 lakh of professional receipts, 14% in cash: over the 50 lakh audit limit (s.44AB(b)) - a CA: {w['ca_needed']}")
# an HUF (2026-10-06): interest income of 12 lakh, 80C and an 80E claimed - no 87A rebate, no 80E, never ITR-1, status H
h = clients.save(u, {"name": "Demo Family HUF", "pan": "ZZDHF0045L", "status": "huf", "email": "demo.huf@demo.example",
                     "phone": "9000000045", "address": "Flat 45, Demo Residency, Madhapur, Hyderabad 500081"})
hid = h["id"]
w = myreturn.answer(u, hid, ay, {"edits": {"other": {"deposits": 1200000}, "via": {"c80c": 150000, "c80e": 40000}},
                                 "answers": {"father": "Demo Grandfather", "karta_name": "Demo Karta", "karta_pan": "ZZDPK0046M", "formed_on": "1990-04-01", "filed_on": "2026-07-20"}, "regime": "new", "regime_seen": True, "reviewed": True})
g = w["regimes"]["new"]
ok(w["form"]["form"] == "ITR-2" and w["form"]["why"] == "why_huf", f"an HUF never files ITR-1: {w['form']}")
ok(g["tax"]["rebate"] == 0 and g["tax"]["tax"] == 62400, f"no 87A rebate for an HUF: tax {g['tax']['tax']} on 12 lakh")
go = w["regimes"]["old"]
ok(go["via"]["d80C"] == 150000 and go["via"]["d80E"] == 0, f"an HUF keeps 80C, not 80E: {go['via']['d80C']}, {go['via']['d80E']}")
doc_h, rep_h = itr_json.assemble(myreturn.facts(hid, ay), "ITR-2")
for x in rep_h["errors"][:20]:
    print("   -", x["path"], "|", x["message"][:110])
ok(rep_h["valid"] and doc_h["ITR"]["ITR2"]["PartA_GEN1"]["PersonalInfo"]["Status"] == "H", "the HUF's ITR-2 says status H and fits the schema")
# the rest of Chapter VI-A (2026-10-06, wave 1): 80DD, 80DDB, 80EEA, 80EEB, 80GG, 80GGC in the old regime, with their schedules
v8 = clients.save(u, {"name": "Meera Demo Saver", "pan": "ZZDPM0047N", "status": "individual", "dob": "1970-02-02", "email": "meera.demo@demo.example",
                      "phone": "9000000047", "address": "Flat 47, Demo Residency, Madhapur, Hyderabad 500081"})
vid = v8["id"]
w = myreturn.answer(u, vid, ay, {"edits": {"other": {"deposits": 1800000}, "via": {"c80ddb": 80000, "c80eea": 200000, "c80eeb": 90000, "c80ggc": 25000, "c80gg": 240000}},
                                 "via_more": {"dd_nature": "2", "dd_type": "1", "dd_dependent": "2", "ddb_senior": True, "stamp": 4000000, "vehicle": "TS09ZZ0047",
                                              "ggc_party": "Demo Party", "ggc_date": "2025-11-11", "ggc_ref": "UTR0000047", "ggc_ifsc": "DEMO0000047",
                                              "loan_80eea": {"from": "B", "bank": "Demo Bank", "acc": "HL0047", "date": "2021-06-01", "amount": 3000000, "left": 2400000},
                                              "loan_80eeb": {"from": "B", "bank": "Demo Bank", "acc": "EV0047", "date": "2022-05-01", "amount": 900000, "left": 500000}},
                                 "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20"}, "regime_seen": True, "reviewed": True})
w = myreturn.answer(u, vid, ay, {"regime": "old"})
gv = w["regimes"]["old"]["via"]
ok((gv["d80DD"], gv["d80DDB"], gv["d80EEA"], gv["d80EEB"], gv["d80GGC"]) == (125000, 80000, 150000, 90000, 25000), f"80DD / 80DDB / 80EEA / 80EEB / 80GGC: {gv}")
ok(gv["d80GG"] == 60000, f"80GG: the least of 60,000, 25% and rent less 10% of the income left: {gv['d80GG']}")
ok(w["regimes"]["new"]["via"]["total"] == 0, "none of them in the new regime")
doc8, rep8 = itr_json.assemble(myreturn.facts(vid, ay), w["form"]["form"])
for x in rep8["errors"][:20]:
    print("   -", x["path"], "|", x["message"][:110])
it8 = next(iter(doc8["ITR"].values()))
ok(rep8["valid"] and it8["Schedule80DD"]["DeductionAmount"] == 125000 and it8["Schedule80EEA"]["TotalInterest80EEA"] == 150000
   and it8["Schedule80GGC"]["TotalEligibleDonationAmt80GGC"] == 25000, f"{w['form']['form']} with the deduction schedules fits the schema")
# --- wave 2 (2026-10-07) -------------------------------------------------------------------------------------------------
# 80EE and 80EEA both claimed: a red check, and 80EEA goes (s.80EEA(4)(b))
w = myreturn.answer(u, vid, ay, {"edits": {"via": {"c80ee": 40000}}})
ee = next((x for x in w["checks"] if x["what"] == "ee_both"), None)
ok(ee and ee["level"] == "red" and w["regimes"]["old"]["via"]["d80EEA"] == 0 and w["regimes"]["old"]["via"]["d80EE"] == 40000,
   f"80EE with 80EEA: red check, 80EEA dropped: {ee}")
w = myreturn.answer(u, vid, ay, {"edits": {"via": {"c80ee": ""}}})
ok(not any(x["what"] == "ee_both" for x in w["checks"]) and w["regimes"]["old"]["via"]["d80EEA"] == 150000, "80EE taken out: 80EEA back, no check")

# a co-owned house (s.26): a 50% share of a let-out flat, the co-owner named, in ITR-1 and ITR-2
w = myreturn.answer(u, cid, ay, {"answers": {"father": "Demo Father"}, "houses": [{"kind": "let", "rent": 300000, "municipal_tax": 20000, "interest": 100000, "share": 50,
                                             "co_name": "Demo Spouse", "co_pan": "ZZDPS0050A", "address": "Flat 50, Demo Towers"}]})
hx = w["regimes"]["new"]["houses"][0]
ok((hx["balance"], hx["nav"], hx["std"], hx["interest"], hx["net"]) == (280000, 140000, 42000, 50000, 48000), f"50% of a let house: {hx}")
w = myreturn.answer(u, cid, ay, {"houses": [{"kind": "self", "interest": 500000, "share": 50, "co_name": "Demo Spouse"}]})
ok(w["regimes"]["old"]["houses"][0]["interest"] == 200000, "self-occupied, 50% of 5 lakh interest: the 2 lakh cap on the share")
w = myreturn.answer(u, cid, ay, {"houses": [{"kind": "let", "rent": 300000, "municipal_tax": 20000, "interest": 100000, "share": 50,
                                             "co_name": "Demo Spouse", "co_pan": "ZZDPS0050A", "address": "Flat 50, Demo Towers"}]})
for form, root, where in (("ITR-1", "ITR1", lambda x: x["ITR1_IncomeDeductions"]), ("ITR-2", "ITR2", lambda x: x["ScheduleHP"])):
    dch, rch = itr_json.assemble(myreturn.facts(cid, ay), form)
    for x in rch["errors"][:10]:
        print("   -", x["path"], "|", x["message"][:110])
    pd = where(dch["ITR"][root])["PropertyDetails"][0]
    ok(rch["valid"] and pd["PropCoOwnedFlg"] == "YES" and pd["AsseseeShareProperty"] == 50 and pd["CoOwners"][0]["NameCoOwner"] == "Demo Spouse"
       and pd["Rentdetails"]["BalanceALV"] == 280000 and pd["Rentdetails"]["AnnualOfPropOwned"] == 140000 and pd["Rentdetails"]["IncomeOfHP"] == 48000,
       f"{form}: co-owned house - share, co-owner, the whole annual value and the share's: {pd.get('Rentdetails')}")
myreturn.answer(u, cid, ay, {"houses": []})

# winnings and crypto (115BB / 115BBJ / 115BBH) read from an AIS whose header has the address, e-mail and mobile
AIS2 = ["ANNUAL INFORMATION STATEMENT (AIS)", "PART A - GENERAL INFORMATION",
        "PAN ZZDPW0051B Name RAVI DEMO WINNER Date of Birth 01/01/1980",
        "Mobile Number 9000000051 E-mail Address ravi.demo@demo.example",
        "Address Flat 51, Demo Enclave, Banjara Hills, Hyderabad, Telangana 500034",
        "PART B1 - INFORMATION RELATING TO TAX DEDUCTED OR COLLECTED AT SOURCE",
        "SR. NO. INFORMATION CODE INFORMATION DESCRIPTION INFORMATION SOURCE COUNT AMOUNT",
        "1 TDS-194B Winnings from lottery or crossword puzzle DEMO LOTTERIES (HYDD00051A) 1 1,00,000",
        "2 TDS-194BA Net winnings from online games DEMO GAMES (HYDD00051B) 1 50,000",
        "3 TDS-194S Payment on transfer of virtual digital asset DEMO EXCHANGE (HYDD00051C) 2 3,00,000",
        "PART B2 - INFORMATION RELATING TO SPECIFIED FINANCIAL TRANSACTION (SFT)",
        "1 SFT-016(TD) Interest income Time deposit DEMO BANK LIMITED 1 6,00,000"]
pb2 = io.BytesIO()
cv = canvas.Canvas(pb2, pagesize=landscape(A4))
cv.setFont("Helvetica", 9)
for j, ln in enumerate(AIS2):
    cv.drawString(30, 560 - 16 * j, ln)
cv.save()
got = myreturn_read.read("AIS Ravi.pdf", pb2.getvalue())
gp, go = (got["facts"] or {}).get("person") or {}, (got["facts"] or {}).get("other") or {}
ok(got["kind"] == "ais" and go.get("lottery") == 100000 and go.get("online_games") == 50000 and got["facts"].get("vda_seen") == 300000
   and gp.get("email") == "ravi.demo@demo.example" and gp.get("mobile") == "9000000051" and gp.get("pin") == "500034" and gp.get("state") == "36",
   f"AIS: 194B winnings, 194BA online games, 194S VDA, and the header's address, e-mail, mobile: {gp} {go} {got['problems']}")
rv = clients.save(u, {"name": "Ravi Demo Winner", "pan": "ZZDPW0051B", "status": "individual", "dob": "1980-01-01"})
rid = rv["id"]
myreturn.add_doc(u, rid, ay, "AIS Ravi.pdf", pb2.getvalue())
w = myreturn.answer(u, rid, ay, {"vda": [{"name": "Demo Coin", "acquired": "2024-05-01", "transferred": "2025-11-20", "cost": 100000, "sale": 250000},
                                         {"name": "Demo Token", "acquired": "2025-04-10", "transferred": "2025-12-20", "cost": 80000, "sale": 50000}],
                                 "answers": {"father": "Demo Father", "lottery_on": "2025-08-10", "filed_on": "2026-07-20"}, "regime": "new", "regime_seen": True, "reviewed": True})
gn = w["regimes"]["new"]
ok(w["form"]["form"] == "ITR-2" and w["form"]["why"] == "why_special", f"winnings / VDA are never ITR-1: {w['form']}")
ok(gn["vda"]["income"] == 150000 and gn["vda"]["loss_ignored"] == 30000, f"VDA: 1.5 lakh gain, the 30,000 loss counts for nothing: {gn['vda']}")
ok(gn["tax"]["rebate"] == 10000 and gn["tax"]["on_special"] == 90000 and gn["tax"]["tax"] == 93600 and gn["via"]["total"] == 0,
   f"30% on 3 lakh of winnings and VDA, 87A only against the slab tax: {gn['tax']['rebate']} {gn['tax']['on_special']} {gn['tax']['tax']}")
go2 = w["regimes"]["old"]
ok(go2["tax"]["on_special"] == 90000 and go2["tax"]["rebate"] == 0, f"old regime: the same 30%, no rebate (total income 9 lakh > 5 lakh): {go2['tax']['rebate']}")
dr, rr = itr_json.assemble(myreturn.facts(rid, ay), "ITR-2")
for x in rr["errors"][:20]:
    print("   -", x["path"], "|", x["message"][:110])
i2 = dr["ITR"]["ITR2"]
osr = i2["ScheduleOS"]
ok(rr["valid"] and osr["IncOthThanOwnRaceHorse"]["LtryPzzlChrgblUs115BB"] == 100000 and osr["IncOthThanOwnRaceHorse"]["IncChrgblUs115BBJ"] == 50000
   and osr["IncFrmLottery"]["DateRange"]["Upto15Of9"] == 100000 and osr["IncChargeable"] == 750000,
   f"ITR-2 Schedule OS: winnings at their own rows and date range: {osr['IncOthThanOwnRaceHorse'].get('IncChargeableSpecialRates')}")
ok(i2["ScheduleVDA"]["TotIncCapGain"] == 150000 and len(i2["ScheduleVDA"]["ScheduleVDADtls"]) == 2 and i2["PartB-TI"]["CapGain"]["CapGains30Per115BBH"] == 150000
   and i2["ScheduleCGFor23"]["AccruOrRecOfCG"]["VDATrnsfGainsUnder30Per"]["DateRange"]["Up16Of9To15Of12"] == 150000,
   "Schedule VDA, the 115BBH gain in Part B-TI and Schedule CG's date range")
ok({x["SecCode"]: x["SplRateIncTax"] for x in i2["ScheduleSI"]["SplCodeRateTax"]} == {"5BB": 30000, "5BBJ": 15000, "5BBH": 45000}
   and i2["PartB-TI"]["TotalIncome"] == 900000 and i2["PartB-TI"]["IncChargeableTaxSplRates"] == 300000, f"Schedule SI and Part B-TI: {i2['ScheduleSI']}")
pa = i2["PartA_GEN1"]["PersonalInfo"]["Address"]
ok(pa["EmailAddress"] == "ravi.demo@demo.example" and pa["MobileNo"] == 9000000051 and pa["PinCode"] == 500034 and pa["StateCode"] == "36"
   and pa["CityOrTownOrDistrict"] == "Hyderabad", f"the person's address, e-mail and mobile from the AIS header: {pa}")
w = myreturn.answer(u, rid, ay, {"answers": {"address": "House 9, Demo Lane, Gachibowli", "city": "Hyderabad", "pin": "500032", "email": "ravi.new@demo.example"}})
pa = itr_json.assemble(myreturn.facts(rid, ay), "ITR-2")[0]["ITR"]["ITR2"]["PartA_GEN1"]["PersonalInfo"]["Address"]
ok(pa["ResidenceNo"] == "House 9" and pa["PinCode"] == 500032 and pa["EmailAddress"] == "ravi.new@demo.example" and pa["MobileNo"] == 9000000051,
   f"typed on Review: the address and e-mail win, the AIS mobile stays: {pa}")

# agricultural income: above 5,000 - partial integration (both regimes) and ITR-2; up to 5,000 - exempt, ITR-1
fm = clients.save(u, {"name": "Suresh Demo Farmer", "pan": "ZZDPF0052C", "status": "individual", "dob": "1975-06-06", "email": "suresh.demo@demo.example",
                      "phone": "9000000052", "address": "Plot 52, Demo Village, Medak, Telangana 502110"})
fid = fm["id"]
w = myreturn.answer(u, fid, ay, {"edits": {"other": {"deposits": 1000000}}, "answers": {"agri": 300000, "father": "Demo Father", "filed_on": "2026-07-20"},
                                 "regime_seen": True, "reviewed": True})
an, ao = w["regimes"]["new"]["tax"], w["regimes"]["old"]["tax"]
ok(w["form"]["form"] == "ITR-2" and w["form"]["why"] == "why_agri", f"3 lakh of farm income: ITR-2: {w['form']}")
ok((an["on_aggregate"], an["agri_rebate"], an["on_normal"], an["rebate"], an["tax"]) == (75000, 15000, 60000, 60000, 0),
   f"new regime: tax on 13 lakh less tax on 7 lakh = 60,000, then 87A (total income 10 lakh): {an['on_normal']} {an['tax']}")
ok((ao["on_normal"], ao["tax"]) == (180000, 187200), f"old regime: tax on 13 lakh less tax on 5.5 lakh = 1,80,000: {ao['on_normal']} {ao['tax']}")
da, ra = itr_json.assemble(myreturn.facts(fid, ay), "ITR-2")
for x in ra["errors"][:20]:
    print("   -", x["path"], "|", x["message"][:110])
ia = da["ITR"]["ITR2"]
tt = ia["PartB_TTI"]["ComputationOfTaxLiability"]["TaxPayableOnTI"]
ok(ra["valid"] and ia["ScheduleEI"]["NetAgriIncOrOthrIncRule7"] == 300000 and ia["PartB-TI"]["NetAgricultureIncomeOrOtherIncomeForRate"] == 300000
   and tt["TaxAtNormalRatesOnAggrInc"] == 75000 and tt["RebateOnAgriInc"] == 15000 and tt["TaxPayableOnTotInc"] == 60000,
   f"ITR-2 Schedule EI and Part B-TTI (tax on the aggregate, rebate on agricultural income): {tt}")
w = myreturn.answer(u, fid, ay, {"answers": {"agri": 4000}})
ok(w["form"]["form"] == "ITR-1" and w["regimes"]["new"]["tax"]["agri_rebate"] == 0, f"4,000 of farm income: exempt, ITR-1: {w['form']}")
d1, r1 = itr_json.assemble(myreturn.facts(fid, ay), "ITR-1")
ok(r1["valid"] and d1["ITR"]["ITR1"]["ITR1_IncomeDeductions"]["ExemptIncAgriOthUs10"]["ExemptIncAgriOthUs10Total"] == 4000, "ITR-1 shows the 4,000 as exempt agricultural income")

# 44AE: a heavy truck (16 t) for the year and a light one for 10 months -> ITR-4; more than 10 vehicles -> ITR-3
tr = clients.save(u, {"name": "Gopal Demo Transport", "pan": "ZZDPT0053D", "status": "individual", "dob": "1982-03-03", "email": "gopal.demo@demo.example",
                      "phone": "9000000053", "address": "Shed 53, Demo Auto Nagar, Vijayawada, Andhra Pradesh 520007"})
tid = tr["id"]
w = myreturn.answer(u, tid, ay, {"business": {"kind": "44AE", "code": "11008", "name": "Gopal Demo Transport",
                                              "vehicles": [{"reg": "AP16ZZ0001", "weight_kg": 16000, "months": 12, "own": "own"},
                                                           {"reg": "AP16ZZ0002", "weight_kg": 7500, "months": 10, "own": "hired"}]},
                                 "answers": {"father": "Demo Father", "filed_on": "2026-08-20"}, "regime_seen": True, "reviewed": True})
bz = w["regimes"][w["regime"]]["business"]
ok(w["form"]["form"] == "ITR-4" and bz["income"] == 267000 and [v["income"] for v in bz["vehicles"]] == [192000, 75000],
   f"44AE: 1,000 x 16 t x 12 + 7,500 x 10 = 2,67,000, ITR-4: {w['form']} {bz['income']}")
d4, r4 = itr_json.assemble(myreturn.facts(tid, ay), "ITR-4")
for x in r4["errors"][:20]:
    print("   -", x["path"], "|", x["message"][:110])
b4 = d4["ITR"]["ITR4"]["ScheduleBP"]
ok(r4["valid"] and b4["PersumptiveInc44AE"]["TotPersumInc44AE"] == 267000 and [g["TonnageCapacity"] for g in b4["GoodsDtlsUs44AE"]] == [16, 8]
   and b4["GoodsDtlsUs44AE"][1]["OwnedLeasedHiredFlag"] == "HIRED" and b4["NatOfBus44AE"][0]["CodeAE"] == "11008",
   f"ITR-4 Schedule BP 44AE fits the schema: {b4.get('PersumptiveInc44AE')}")
w = myreturn.answer(u, tid, ay, {"business": {"kind": "44AE", "code": "11008", "vehicles": [{"reg": f"AP16ZZ{n:04d}", "weight_kg": 7500, "months": 12} for n in range(11)]}})
ok(w["form"]["form"] == "ITR-3" and w["form"]["why"] == "why_biz_limit", f"11 goods carriages: 44AE closed, ITR-3: {w['form']}")


# --- wave 3 (2026-10-07): capital gains in full ---------------------------------------------------------------------------------
def itr2(cid_, what):
    """The return as ITR-2 JSON, checked against the department's schema (problems printed)."""
    d_, r_ = itr_json.assemble(myreturn.facts(cid_, ay), "ITR-2")
    for x_ in r_["errors"][:25]:
        print("   -", x_["path"], "|", x_["message"][:140])
    ok(r_["valid"], f"{what}: ITR-2 JSON fits the department's schema ({r_['error_count']} problems)")
    return d_["ITR"]["ITR2"]


def person(name, pan, n):
    return clients.save(u, {"name": name, "pan": pan, "status": "individual", "dob": "1978-04-04", "email": f"demo{n}@demo.example",
                            "phone": f"90000000{n}", "address": f"Flat {n}, Demo Residency, Madhapur, Hyderabad 500081"})["id"]


# 1 a CAMS-style CSV and a broker's Excel tax P&L: grandfathering, 111A, s.50AA debt fund, an old debt fund (112), a loss
iv = person("Priya Demo Investor", "ZZDPI0060A", 60)
CAMS = [["Consolidated Capital Gains Statement - Demo Registrar - FY 2025-26"], [],
        ["Scheme Name", "ISIN", "Category", "Units", "Purchase Date", "Purchase Value", "NAV as on 31/01/2018", "Redemption Date", "Redemption Amount", "STT"],
        ["Demo Bluechip Fund - Growth", "INF000Z01011", "Equity", "1000", "15/06/2017", "1,00,000.00", "250.00", "10/09/2025", "3,00,000.00", "3"],
        ["Demo Flexicap Fund - Growth", "INF000Z01029", "Equity", "500", "12/03/2020", "50,000.00", "", "10/09/2025", "1,30,000.00", "1"],
        ["Demo Midcap Fund - Growth", "INF000Z01037", "Equity", "200", "10/01/2025", "40,000.00", "", "10/08/2025", "52,000.00", "1"],
        ["Demo Liquid Fund - Growth", "INF000Z01045", "Debt", "100", "01/06/2023", "5,00,000.00", "", "01/12/2025", "5,50,000.00", "0"],
        ["Demo Gilt Fund - Growth", "INF000Z01052", "Debt", "100", "10/01/2021", "2,00,000.00", "", "01/12/2025", "2,60,000.00", "0"],
        ["Grand Total", "", "", "", "", "8,90,000.00", "", "", "12,92,000.00", ""]]
cams = ("\n".join(",".join(f'"{c}"' for c in r) for r in CAMS) + "\n").encode()
got = myreturn_read.read("CAMS CG statement.csv", cams)
cr = (got["facts"] or {}).get("cg_rows") or []
ok(got["kind"] == "cg" and len(cr) == 5 and cr[0]["fmv"] == 250000 and cr[0]["acquired"] == "2017-06-15" and cr[3]["asset"] == "debt_mf" and cr[0]["isin"] == "INF000Z01011",
   f"CAMS statement read: {len(cr)} sales, FMV per unit made the total, the debt funds known: {[(x['name'][:12], x['asset'], x['fmv']) for x in cr]}")
wb = openpyxl.Workbook()
for r_ in [["Tax P&L - Demo Broker"], ["Symbol", "ISIN", "Quantity", "Buy Date", "Buy Value", "Sell Date", "Sell Value", "Brokerage"],
           ["DEMOSTEEL", "INE000Z01010", 100, "05-01-2025", 90000, "20-06-2025", 60000, 100]]:
    wb.active.append(r_)
xb2 = io.BytesIO()
wb.save(xb2)
got = myreturn_read.read("Broker tax P&L.xlsx", xb2.getvalue())
br = (got["facts"] or {}).get("cg_rows") or []
ok(got["kind"] == "cg" and len(br) == 1 and br[0]["isin"] == "INE000Z01010" and br[0]["acquired"] == "2025-01-05" and br[0]["expenses"] == 100,
   f"a broker's Excel tax P&L read: {br}")
myreturn.add_doc(u, iv, ay, "CAMS CG statement.csv", cams)
myreturn.add_doc(u, iv, ay, "Broker tax P&L.xlsx", xb2.getvalue())
w = myreturn.answer(u, iv, ay, {"edits": {"other": {"deposits": 800000}}, "answers": {"father": "Demo Father", "filed_on": "2026-07-20"},
                                "regime": "new", "regime_seen": True, "reviewed": True})
cw = w["return"]["cgw"]
byname = {x["name"][:10]: x for x in cw["rows"]}
ok(byname["Demo Bluec"]["grandfathered"] and byname["Demo Bluec"]["final"] == 50000 and byname["Demo Flexi"]["final"] == 80000
   and byname["Demo Midca"]["bucket"] == "stcg_111a" and byname["Demo Liqui"]["deemed_50aa"] and byname["Demo Liqui"]["bucket"] == "stcg_app"
   and byname["Demo Gilt "]["bucket"] == "ltcg_112" and byname["DEMOSTEEL"]["final"] == -30100,
   f"each sale: grandfathered 50,000, 80,000 (112A), 12,000 (111A), 50,000 deemed short (50AA), 60,000 old debt fund (112), a 30,100 loss: "
   f"{[(k2, x['bucket'], x['final']) for k2, x in byname.items()]}")
# 111A: 12,000 gain less the 30,100 111A loss -> 18,100 short-term loss at 20%, set off against the slab-rate gain first (s.70(2))
ok(cw["final"] == {"stcg_111a": 0, "stcg_app": 31900, "ltcg_112": 60000, "ltcg_112a": 130000} and cw["cf"] == {"stcl": 0, "ltcl": 0},
   f"the loss set off across rates: {cw['final']}")
t = w["regimes"]["new"]["tax"]
ok(t["on_112a"] == 625 and t["on_112"] == 7500, f"112A 12.5% of (1,30,000 - 1,25,000) = 625, 112 12.5% of 60,000 = 7,500: {t['on_112a']} {t['on_112']}")
ok(w["form"]["form"] == "ITR-2" and w["form"]["why"] == "why_cg", f"capital gains with a loss: ITR-2: {w['form']}")
ok(any(x["what"] == "cg_sales" for x in w["checks"]) is False, "no AIS here: no sales check")
i2 = itr2(iv, "CAMS + broker statements")
s112 = i2["Schedule112A"]
ok(len(s112["Schedule112ADtls"]) == 2 and {x["ShareOnOrBefore"] for x in s112["Schedule112ADtls"]} == {"BE", "AE"} and s112["TotalBalance112A"] == 130000
   and next(x for x in s112["Schedule112ADtls"] if x["ShareOnOrBefore"] == "BE")["CostAcqWithoutIndx"] == 250000,
   f"Schedule 112A per scrip, grandfathered (BE) and not (AE): {[(x['ISINCode'], x['ShareOnOrBefore'], x['Balance']) for x in s112['Schedule112ADtls']]}")
te = i2["ScheduleCGFor23"]["CurrYrLosses"]
ok(te["InLossSetOff"]["StclSetoff20Per"] == 18100 and te["InStcgAppRate"]["StclSetoff20Per"] == 18100 and te["InStcgAppRate"]["CurrYrCapGain"] == 31900,
   f"Table E: the 111A loss against the slab-rate gain: {te['InStcgAppRate']}")
ok(i2["PartB-TI"]["CapGain"]["ShortTerm"]["ShortTermAppRate"] == 31900 and i2["PartB-TI"]["CapGain"]["LongTerm"]["LongTerm12_5Per"] == 190000
   and sum(i2["ScheduleCGFor23"]["AccruOrRecOfCG"]["LongTermUnder12_5Per"]["DateRange"].values()) == 190000,
   "Part B-TI and Table F carry the gains after set-off")

# 2 a house sold (s.50C, indexation choice), 54EC bonds, the buyer's TDS (AIS 194IA) -> ITR-2 Schedule CG B1, TDS3
sl = person("Ramesh Demo Seller", "ZZDPR0061B", 61)
AIS3 = ["ANNUAL INFORMATION STATEMENT (AIS)", "PART A - GENERAL INFORMATION", "PAN ZZDPR0061B Name RAMESH DEMO SELLER",
        "PART B1 - INFORMATION RELATING TO TAX DEDUCTED OR COLLECTED AT SOURCE",
        "1 TDS-194IA Payment on transfer of certain immovable property other than agricultural land DEMO BUYER (ZZDPB0061C) 1 90,00,000 90,000",
        "PART B2 - INFORMATION RELATING TO SPECIFIED FINANCIAL TRANSACTION (SFT)",
        "1 SFT-012 Sale of immovable property DEMO SUB-REGISTRAR 1 90,00,000"]
pb3 = io.BytesIO()
cv = canvas.Canvas(pb3, pagesize=landscape(A4))
cv.setFont("Helvetica", 8)
for j, ln in enumerate(AIS3):
    cv.drawString(20, 560 - 16 * j, ln)
cv.save()
got = myreturn_read.read("AIS Ramesh.pdf", pb3.getvalue())
t194 = (got["facts"] or {}).get("tds_194ia") or []
ok(got["kind"] == "ais" and t194 and t194[0]["pan"] == "ZZDPB0061C" and t194[0]["tds"] == 90000 and got["facts"].get("property_sft") == 9000000,
   f"AIS 194IA: the sale, the buyer's TDS and PAN; SFT-012: {t194} {got['problems']}")
myreturn.add_doc(u, sl, ay, "AIS Ramesh.pdf", pb3.getvalue())
house = {"asset": "house", "name": "Flat 61, Demo Towers", "acquired": "2010-06-15", "sold": "2025-11-20", "sale": 9000000, "stamp": 10500000, "cost": 3000000,
         "improve": 500000, "improve_on": "2015-08-01", "expenses": 100000, "buyer": "Demo Buyer", "buyer_pan": "ZZDPB0061C", "address": "Flat 61, Demo Towers, Hyderabad",
         "pin": "500081", "state": "36", "ex_kind": "54EC", "ex_amount": 5000000, "ex_on": "2026-03-01"}
w = myreturn.answer(u, sl, ay, {"cg_rows": [house], "edits": {"other": {"deposits": 1500000}},
                                "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20"}, "regime": "new", "regime_seen": True, "reviewed": True})
hx = w["return"]["cgw"]["rows"][0]
ok(hx["s50c"] and hx["consideration"] == 10500000 and hx["gain"] == 6900000 and hx["gain_indexed"] == 2905352 and hx["exempt"] == 5000000
   and hx["exempt_indexed"] == 2905352 and hx["final"] == 1900000 and hx["tax_plain"] == 237500 and hx["tax_indexed"] == 0 and hx["chosen"] == "indexed",
   f"s.50C value, 69 lakh gain (29,05,352 indexed), 54EC 50 lakh: 12.5% of 19 lakh = 2,37,500 vs nil with indexation: {hx['tax_plain']} {hx['tax_indexed']} {hx['chosen']}")
tn = w["regimes"]["new"]["tax"]
ok(tn["on_112"] == 0 and w["regimes"]["new"]["tds"] == 90000, f"the 112 tax is the lower (nil), the buyer's TDS counts: {tn['on_112']} {w['regimes']['new']['tds']}")
ok(any(x["what"] == "property" and x["level"] == "ok" for x in w["checks"]), "AIS says 90 lakh and the row's price is 90 lakh (1.05 crore taken, s.50C) - compared on the price: "
   + str([(x["what"], x["level"], x["a"], x["b"]) for x in w["checks"] if x["what"] == "property"]))
i2 = itr2(sl, "a house sold with 54EC")
lb = i2["ScheduleCGFor23"]["LongTermCapGain23"]["SaleofLandBuild"]
d0 = lb["SaleofLandBuildDtls"][0]
ok(d0["FullConsideration50C"] == 10500000 and d0["AquisitCostIndex"] == 6754491 and d0["LTCGonImmvblPrprty"] == 1900000 and d0["ExcessAmtSec1121a"] == 237500
   and lb["TotalExcessTax"] == 237500 and d0["ExemptionOrDednUs54"]["ExemptionGrandTotal"] == 5000000 and d0["TrnsfImmblPrprty"]["TrnsfImmblPrprtyDtls"][0]["PANofBuyer"] == "ZZDPB0061C",
   f"Schedule CG B1: both computations, the exemption, the excess tax, the buyer: {d0.get('TaxSec1121a')} {d0.get('TaxSec1121aiiB')} {d0.get('ExcessAmtSec1121a')}")
ok(i2["ScheduleCGFor23"]["DeducClaimInfo"]["DeducClaimDtlsUs54EC"][0]["AmtDeducted"] == 5000000 and i2["ScheduleTDS3"]["TDS3onOthThanSalDtls"][0]["PANOfBuyerTenant"] == "ZZDPB0061C"
   and i2["ScheduleTDS3"]["TotalTDS3OnOthThanSal"] == 90000, "Table D 54EC and Schedule TDS3 (194IA)")
# 54 with a Capital Gains Account Scheme deposit; a later house where 12.5% without indexation is lower
w = myreturn.answer(u, sl, ay, {"cg_rows": [house | {"ex_kind": "54", "ex_amount": 4000000, "ex_on": "2026-02-01", "cgas": 2000000, "cgas_on": "2026-07-25",
                                                     "cgas_acc": "CGAS0061", "cgas_ifsc": "DEMO0000061"},
                                            {"asset": "land", "name": "Plot 62, Demo Layout", "acquired": "2022-04-10", "sold": "2025-12-15", "sale": 6000000, "cost": 4000000}]})
r0, r1 = w["return"]["cgw"]["rows"]
ok(r0["exempt"] == 6000000 and r0["final"] == 900000 and r1["index_ok"] and r1["chosen"] == "plain" and r1["excess"] == 0,
   f"54: 40 lakh house + 20 lakh CGAS deposit; the plot bought 2022: 12.5% without indexation is lower: {r0['final']} {r1['tax_plain']} {r1['tax_indexed']}")
i2 = itr2(sl, "54 with CGAS, two properties")
c54 = i2["ScheduleCGFor23"]["DeducClaimInfo"]["DeducClaimDtlsUs54"][0]
ok(c54["AmtDeposited"] == 2000000 and c54["IFSC"] == "DEMO0000061" and c54["AmtDeducted"] == 6000000, f"Table D 54 with the CGAS deposit: {c54}")

# 3 losses: brought forward (one too old), set off in order; a house loss brought forward against house income; 54F on shares
ls_ = person("Sunita Demo Loss", "ZZDPL0062C", 62)
w = myreturn.answer(u, ls_, ay, {
    "losses_bf": [{"ay": "2023-24", "kind": "stcl", "amount": 50000, "filed_on": "2023-07-25"}, {"ay": "2020-21", "kind": "ltcl", "amount": 80000},
                  {"ay": "2016-17", "kind": "ltcl", "amount": 10000}, {"ay": "2024-25", "kind": "hp", "amount": 40000, "filed_on": "2024-07-20"}],
    "cg_rows": [{"asset": "equity", "name": "Demo Steel", "isin": "INE000Z01028", "acquired": "2025-01-05", "sold": "2025-06-05", "sale": 70000, "cost": 100000},
                {"asset": "equity", "name": "Demo Power", "isin": "INE000Z01036", "acquired": "2019-01-05", "sold": "2025-06-05", "sale": 500000, "cost": 200000},
                {"asset": "other", "name": "Gold coins", "acquired": "2019-03-01", "sold": "2025-07-01", "sale": 300000, "cost": 200000},
                {"asset": "debt_mf", "name": "Demo Short Debt", "acquired": "2024-02-01", "sold": "2025-08-01", "sale": 120000, "cost": 100000}],
    "houses": [{"kind": "let", "rent": 120000, "municipal_tax": 0, "interest": 24000, "address": "Flat 62, Demo Towers"}],
    "edits": {"other": {"deposits": 1000000}}, "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20"}, "regime": "new", "regime_seen": True, "reviewed": True})
cw = w["return"]["cgw"]
ok([x["usable"] for x in cw["life"]] == [True, True, False, True] and cw["bf_used"] == {"stcg_111a": 0, "stcg_app": 0, "ltcg_112": 90000, "ltcg_112a": 40000}
   and cw["final"] == {"stcg_111a": 0, "stcg_app": 0, "ltcg_112": 0, "ltcg_112a": 260000},
   f"30,000 111A loss -> 20,000 slab gain, 10,000 of the 112 gain; 50,000 short-term b/f -> 112; 80,000 long-term b/f -> 112 then 112A; AY 2016-17 too old: {cw['final']} {cw['bf_used']}")
gh = w["regimes"]["new"]
ok(gh["hp"]["bf"] == 40000 and gh["hp"]["after_bf"] == 20000 and gh["tax"]["on_112a"] == 16875,
   f"the house loss b/f against house income (60,000 -> 20,000); 112A 12.5% of 1,35,000 = 16,875: {gh['hp']} {gh['tax']['on_112a']}")
ok(w["form"]["form"] == "ITR-2", f"losses brought forward: ITR-2: {w['form']}")
i2 = itr2(ls_, "losses brought forward")
cfl = i2["ScheduleCFL"]
ok(cfl["LossCFFromPrev3rdYearFromAY"]["CarryFwdLossDetail"]["TotalSTCGPTILossCF"] == 50000 and cfl["LossCFFromPrev6thYearFromAY"]["CarryFwdLossDetail"]["TotalLTCGPTILossCF"] == 80000
   and cfl["AdjTotBFLossInBFLA"]["LossSummaryDetail"] == {"TotalHPPTILossCF": 40000, "TotalSTCGPTILossCF": 50000, "TotalLTCGPTILossCF": 80000}
   and "LossCFFromPrev10thYearFromAY" not in cfl, f"Schedule CFL by year, what was set off: {cfl.get('AdjTotBFLossInBFLA')}")
bf = i2["ScheduleBFLA"]
ok(bf["LTCG12_5Per"]["IncBFLA"]["BFlossPrevYrUndSameHeadSetoff"] == 130000 and bf["HP"]["IncBFLA"]["BFlossPrevYrUndSameHeadSetoff"] == 40000
   and bf["TotalBFLossSetOff"]["TotBFLossSetoff"] == 170000 and i2["PartB-TI"]["BroughtFwdLossesSetoff"] == 170000
   and i2["PartB-TI"]["GrossTotalIncome"] == i2["PartB-TI"]["BalanceAfterSetoffLosses"] - 170000, f"Schedule BFLA and Part B-TI: {bf['TotalBFLossSetOff']}")
# a long-term loss with no long-term gain is carried forward - but not from a belated return (s.80)
w = myreturn.answer(u, ls_, ay, {"losses_bf": [], "cg_rows": [{"asset": "other", "name": "Unlisted Demo Pvt Ltd", "acquired": "2018-01-01", "sold": "2025-09-01",
                                                               "sale": 100000, "cost": 250000}]})
ok(w["return"]["cgw"]["cf"] == {"stcl": 0, "ltcl": 150000} and w["return"]["cgw"]["cf_ok"], f"a long-term loss of 1.5 lakh goes forward: {w['return']['cgw']['cf']}")
i2 = itr2(ls_, "a long-term loss carried forward")
ok(i2["ScheduleCFL"]["CurrentAYloss"]["LossSummaryDetail"]["TotalLTCGPTILossCF"] == 150000 and i2["PartB-TI"]["LossesOfCurrentYearCarriedFwd"] == 150000,
   "Schedule CFL: this year's long-term loss goes forward")
w = myreturn.answer(u, ls_, ay, {"answers": {"filed_on": "2026-09-15"}})
ok(w["dates"]["kind"] == "belated" and w["return"]["cgw"]["cf_ok"] is False, f"filed 15 September: belated, the loss is lost (s.80): {w['dates']['kind']}")
i2 = itr2(ls_, "belated, the loss not carried forward")
ok("ScheduleCFL" not in i2 or i2["ScheduleCFL"]["CurrentAYloss"]["LossSummaryDetail"]["TotalLTCGPTILossCF"] == 0, "belated: Schedule CFL carries no capital loss of this year")
# 54F: shares sold, a house bought for part of the net consideration (one other house owned)
w = myreturn.answer(u, ls_, ay, {"answers": {"filed_on": "2026-07-20"}, "houses": [], "cg_rows": [
    {"asset": "equity", "name": "Demo Power", "isin": "INE000Z01036", "acquired": "2019-01-05", "sold": "2025-06-05", "sale": 3000000, "cost": 2000000,
     "ex_kind": "54F", "ex_amount": 1500000, "ex_on": "2025-12-01", "other_houses": 1}]})
f0 = w["return"]["cgw"]["rows"][0]
ok(f0["exempt"] == 500000 and f0["final"] == 500000, f"54F: 10 lakh gain x 15 lakh / 30 lakh = 5 lakh exempt: {f0['exempt']}")
i2 = itr2(ls_, "54F on shares")
ok(i2["ScheduleCGFor23"]["LongTermCapGain23"]["SaleOfEquityShareUs112A"]["DeductionUs54F"] == 500000
   and i2["ScheduleCGFor23"]["DeducClaimInfo"]["DeducClaimDtlsUs54F"][0]["AmtDeducted"] == 500000, "54F against the 112A gain, Table D")

# 4 last year's filed return: its Schedule CFL brings the losses forward a year (the 8th year's loss is gone)
prev = {"ITR": {"ITR2": {"Form_ITR2": {"FormName": "ITR-2", "AssessmentYear": "2025"}, "PartA_GEN1": {"PersonalInfo": {"PAN": "ZZDPL0062C",
        "AssesseeName": {"FirstName": "Sunita", "SurNameOrOrgName": "Demo Loss"}, "DOB": "1978-04-04"}}, "Verification": {"Date": "2025-07-28"},
        "ScheduleCFL": {"LossCFFromPrevYrToAY": {"CarryFwdLossDetail": {"DateOfFiling": "2024-07-30", "TotalSTCGPTILossCF": 20000, "TotalLTCGPTILossCF": 0, "TotalHPPTILossCF": 0}},
                        "LossCFFromPrev8thYearFromAY": {"CarryFwdLossDetail": {"DateOfFiling": "2017-07-30", "TotalSTCGPTILossCF": 0, "TotalLTCGPTILossCF": 5000, "TotalHPPTILossCF": 0}},
                        "AdjTotBFLossInBFLA": {"LossSummaryDetail": {"TotalSTCGPTILossCF": 5000, "TotalLTCGPTILossCF": 0, "TotalHPPTILossCF": 0}},
                        "CurrentAYloss": {"LossSummaryDetail": {"TotalSTCGPTILossCF": 0, "TotalLTCGPTILossCF": 70000, "TotalHPPTILossCF": 30000}}}}}}
d = myreturn.add_doc(u, ls_, ay, "ITR-2 AY 2025-26 filed.json", json.dumps(prev).encode())
ok(d["added"]["kind"] == "filed_prev" and not d["added"]["problems"], f"last year's return is known for what it is: {d['added']['kind']} {d['added']['problems']}")
w = myreturn.answer(u, ls_, ay, {"losses_from_prev": True})
ok(w["return"]["losses_bf"] == [{"ay": "2024-25", "kind": "stcl", "amount": 15000.0, "filed_on": "2024-07-30"},
                                {"ay": "2025-26", "kind": "hp", "amount": 30000.0, "filed_on": "2025-07-28"},
                                {"ay": "2025-26", "kind": "ltcl", "amount": 70000.0, "filed_on": "2025-07-28"}],
   f"from last year's Schedule CFL: 20,000 less 5,000 set off; last year's own losses; the 8th year's gone: {w['return']['losses_bf']}")
itr2(ls_, "losses from last year's return")

# 5 gifts (s.56(2)(x)) and pre-construction interest (s.24(b))
gf = person("Kiran Demo Gifts", "ZZDPG0063D", 63)
w = myreturn.answer(u, gf, ay, {"gifts": [{"from": "Demo Friend", "kind": "money", "value": 40000}, {"from": "Demo Neighbour", "kind": "money", "value": 30000},
                                          {"from": "Demo Brother", "relation": "brother", "kind": "money", "value": 500000},
                                          {"from": "Demo Guest", "occasion": "marriage", "kind": "money", "value": 200000},
                                          {"from": "Demo Uncle-in-law", "kind": "property", "value": 3000000},
                                          {"from": "Demo Friend", "kind": "movable", "value": 60000}],
                                "houses": [{"kind": "self", "interest": 180000, "pre_total": 250000, "completed": "2023-09-01", "address": "Flat 63, Demo Towers"}],
                                "edits": {"other": {"deposits": 300000}}, "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20"},
                                "regime_seen": True, "reviewed": True})
gg = w["regimes"]["old"]["gifts"]
ok(gg["money"] == 70000 and gg["property_free"] == 3000000 and gg["movable_free"] == 60000 and gg["total"] == 3130000,
   f"gifts: 70,000 from friends (over 50,000 together), a plot, shares; the brother's and the wedding's are not taxed: {gg['total']}")
ok(w["regimes"]["old"]["houses"][0]["interest"] == 200000 and w["regimes"]["new"]["houses"][0]["interest"] == 0,
   f"pre-construction: 1,80,000 + 50,000 (a fifth) capped at 2 lakh, self-occupied, old regime: {w['regimes']['old']['houses'][0]['interest']}")
i2 = itr2(gf, "gifts and pre-construction interest")
o2 = i2["ScheduleOS"]["IncOthThanOwnRaceHorse"]
ok(o2["Tot562x"] == 3130000 and o2["Aggrtvaluewithoutcons562x"] == 70000 and o2["Immovpropwithoutcons562x"] == 3000000 and o2["Anyotherpropwithoutcons562x"] == 60000,
   f"Schedule OS 1d: {o2['Tot562x']}")
w = myreturn.answer(u, gf, ay, {"gifts": [{"from": "Demo Friend", "kind": "money", "value": 70000}], "houses": []})
ok(w["form"]["form"] == "ITR-1", f"a gift alone stays in ITR-1: {w['form']}")
d1, r1 = itr_json.assemble(myreturn.facts(gf, ay), "ITR-1")
for x in r1["errors"][:10]:
    print("   -", x["path"], "|", x["message"][:110])
ok(r1["valid"] and any(x["OthSrcNatureDesc"] == "OTH" and x["OthSrcOthAmount"] == 70000 for x in d1["ITR"]["ITR1"]["ITR1_IncomeDeductions"]["OthersInc"]["OthersIncDtlsOthSrc"]),
   "ITR-1: the gift as other income")

# 6 which form: 112A up to 1.25 lakh with no loss stays ITR-1; a loss on a sale makes it ITR-2; with a business it is ITR-3
sm = person("Arjun Demo Small", "ZZDPS0064E", 64)
w = myreturn.answer(u, sm, ay, {"cg_rows": [{"asset": "equity", "name": "Demo Bank", "isin": "INE000Z01044", "acquired": "2020-01-01", "sold": "2025-10-01", "sale": 200000, "cost": 100000}],
                                "edits": {"other": {"deposits": 500000}}, "answers": {"father": "Demo Father", "state": "36"}, "regime_seen": True, "reviewed": True})
ok(w["form"]["form"] == "ITR-1", f"1 lakh of 112A gain, no loss: ITR-1: {w['form']}")
d1, r1 = itr_json.assemble(myreturn.facts(sm, ay), "ITR-1")
ok(r1["valid"] and d1["ITR"]["ITR1"]["LTCG112A"]["LongCap112A"] == 100000, "ITR-1 shows the 112A gain")
w = myreturn.answer(u, sm, ay, {"cg_rows": [{"asset": "equity", "name": "Demo Bank", "isin": "INE000Z01044", "acquired": "2020-01-01", "sold": "2025-10-01", "sale": 200000, "cost": 100000},
                                            {"asset": "equity", "name": "Demo Auto", "isin": "INE000Z01051", "acquired": "2020-01-01", "sold": "2025-10-01", "sale": 50000, "cost": 60000}]})
ok(w["form"]["form"] == "ITR-2", f"a loss on a sale: ITR-2: {w['form']}")
itr2(sm, "112A gain with a loss")
w = myreturn.answer(u, sm, ay, {"business": {"kind": "44ADA", "code": "14001", "name": "Arjun Demo Consulting", "digital": 1200000}})
ok(w["form"]["form"] == "ITR-3", f"a business and capital gains with a loss: ITR-3: {w['form']}")


# --- ITR-3 from My return (2026-10-07): presumptive with what ITR-4 cannot hold, and a business on its own figures --------------
def itr3(cid_, what):
    """The return as ITR-3 JSON (My return's own rows, chip itr.map "ITR-3 myreturn"), checked against the department's schema."""
    name_, data_, r_ = myreturn.export(cid_, ay)
    for x_ in r_["errors"][:25]:
        print("   -", x_["path"], "|", x_["message"][:140])
    ok(r_["valid"] and name_.startswith("ITR-3 ") and r_["form"] == "ITR-3", f"{what}: ITR-3 JSON fits the department's schema ({r_['error_count']} problems)")
    return json.loads(data_)["ITR"]["ITR3"]


i3 = itr3(sm, "44ADA with capital gains and a loss")
ok(i3["PARTA_PL"]["PersumptiveInc44ADA"]["TotPersumptiveInc44ADA"] == 600000 and i3["ScheduleCGFor23"]["CurrYrLosses"]["InLossSetOff"]["LtclSetOff12_5Per"] == 0,
   "ITR-3 Part A-P&L 62: 44ADA 50% of 12 lakh")
# (a) a consultant (44ADA) who also sold listed shares: 4 lakh of 112A gain - over 1.25 lakh, so not ITR-4
ca_ = person("Asha Demo Consultant", "ZZDPA0070A", 70)
w = myreturn.answer(u, ca_, ay, {"business": {"kind": "44ADA", "code": "14001", "name": "Asha Demo Consulting", "digital": 2400000},
                                 "cg_rows": [{"asset": "equity", "name": "Demo Infra", "isin": "INE000Z01077", "acquired": "2019-02-01", "sold": "2025-09-10",
                                              "sale": 900000, "cost": 500000}],
                                 "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-08-20"}, "regime": "new", "regime_seen": True, "reviewed": True})
g3 = w["regimes"]["new"]
ok(w["form"] == {"form": "ITR-3", "why": "why_biz_more"} and g3["business"]["income"] == 1200000 and g3["tax"]["on_112a"] == 34375,
   f"44ADA 24 lakh -> 12 lakh, 112A 12.5% of (4 lakh - 1.25 lakh) = 34,375, ITR-3: {w['form']} {g3['tax']['on_112a']}")
ok(w["dates"]["due"] == 20260831 and w["dates"]["kind"] == "original", f"ITR-3 without audit is due 31 August: filed 20 August is on time: {w['dates']['due']}")
i3 = itr3(ca_, "(a) 44ADA + listed shares")
bp3 = i3["ITR3ScheduleBP"]["BusinessIncOthThanSpec"]
ok(i3["PARTA_PL"]["PersumptiveInc44ADA"]["GrsReceipt"] == 2400000 and i3["PARTA_PL"]["NatOfBus44ADA"][0]["CodeADA"] == "14001"
   and bp3["ProfBfrTaxPL"] == 1200000 and bp3["ProfitLossInclRefrdSec"]["ProfitLossUs44ADA"] == 1200000 and bp3["BalancePLOthThanSpecBus"] == 0
   and bp3["DeemedProfitBusUs"]["Section44ADA"] == 1200000 and bp3["NetPLAftAdjBusOthThanSpec"] == 1200000 and i3["PartB-TI"]["ProfBusGain"]["TotProfBusGain"] == 1200000,
   f"Part A-P&L 62 and Schedule BP: the 44ADA income out of the P&L profit and back as deemed: {bp3['DeemedProfitBusUs']}")
ok(i3["Schedule112A"]["Balance112A"] == 400000 and {x["SecCode"]: x["SplRateInc"] for x in i3["ScheduleSI"]["SplCodeRateTax"]} == {"2A": 275000}
   and i3["PartA_GEN2"]["AuditInfo"]["IncDclrdUs"] == "Y" and i3["PartA_GEN1"]["FilingStatus"]["ItrFilingDueDate"] == "2026-08-31"
   and i3["PartB-TI"]["GrossTotalIncome"] == 1600000 and i3["Form_ITR3"]["FormName"] == "ITR-3",
   f"Schedule 112A, Schedule SI (2A on 2.75 lakh), income declared under 44ADA, due date: {i3['ScheduleSI']}")
# (b) a transporter with 12 goods carriages: 44AE is closed (more than 10) - his own profit and loss, no regular books
fl = person("Tara Demo Fleet", "ZZDPT0071B", 71)
w = myreturn.answer(u, fl, ay, {"business": {"kind": "44AE", "code": "11008", "name": "Tara Demo Fleet", "digital": 5200000, "cash": 100000,
                                             "gp": 1600000, "expenses": 700000, "np": 900000, "debtors": 300000, "creditors": 150000, "cash_in_hand": 40000,
                                             "vehicles": [{"reg": f"TS09ZZ{n_:04d}", "weight_kg": 16000, "months": 12} for n_ in range(12)]},
                                "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-08-20"}, "regime": "new", "regime_seen": True, "reviewed": True})
bz = w["regimes"]["new"]["business"]
ok(w["form"] == {"form": "ITR-3", "why": "why_biz_limit"} and bz["pl"] and not bz["presumptive"] and bz["income"] == 900000 and not w["ca_needed"],
   f"12 goods carriages: 44AE closed, the 9 lakh net profit typed is the income, no audit (53 lakh < 1 crore): {w['form']} {bz['income']}")
i3 = itr3(fl, "(b) 44AE 12 vehicles, typed P&L")
nb3, bs3 = i3["PARTA_PL"]["NoBooksOfAccPL"], i3["PARTA_BS"]["NoBooksOfAccBS"]
ok((nb3["GrossReceipt"], nb3["GrsRcptAccPayeeOrBankMode"], nb3["GrsRcptOtherMode"], nb3["GrossProfit"], nb3["Expenses"], nb3["NetProfit"], nb3["TotBusinessProfession"])
   == (5300000, 5200000, 100000, 1600000, 700000, 900000, 900000) and nb3["NetProfitPrf"] == 0
   and bs3 == {"TotSundryDbtAmt": 300000, "TotSundryCrdAmt": 150000, "CashBalAmt": 40000} and "GoodsDtlsUs44AE" not in i3["PARTA_PL"],
   f"Part A-P&L 64 (no regular books) and Part A-BS: {nb3} {bs3}")
bp3 = i3["ITR3ScheduleBP"]["BusinessIncOthThanSpec"]
ok(bp3["ProfBfrTaxPL"] == 900000 and bp3["BalancePLOthThanSpecBus"] == 900000 and bp3["DeemedProfitBusUs"]["TotDeemedProfitBusUs"] == 0
   and i3["ITR3ScheduleBP"]["IncChrgUnHdProftGain"] == 900000 and i3["PartA_GEN2"]["AuditInfo"]["LiableSec44AAflg"] == "Y"
   and i3["PartA_GEN2"]["AuditInfo"]["IncDclrdUs"] == "N" and i3["PartA_GEN2"]["NatOfBus"]["NatureOfBusiness"][0]["Code"] == "11008",
   f"Schedule BP from the P&L profit, books liable (s.44AA), the nature of business: {i3['PartA_GEN2']['AuditInfo']}")
# (c) a trader under 44AD who also sold crypto: VDA income is never ITR-4
vt = person("Vikram Demo Trader", "ZZDPV0072C", 72)
w = myreturn.answer(u, vt, ay, {"business": {"kind": "44AD", "code": "09028", "name": "Vikram Demo Stores", "digital": 3000000, "cash": 200000},
                                "vda": [{"name": "Demo Coin", "acquired": "2024-05-01", "transferred": "2025-11-20", "cost": 100000, "sale": 300000}],
                                "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-08-20"}, "regime": "new", "regime_seen": True, "reviewed": True})
g3 = w["regimes"]["new"]
ok(w["form"] == {"form": "ITR-3", "why": "why_biz_more"} and g3["business"]["income"] == 196000 and g3["tax"]["on_115bbh"] == 60000,
   f"44AD 6% of 30 lakh + 8% of 2 lakh = 1,96,000; 30% of the 2 lakh VDA gain; ITR-3: {w['form']} {g3['business']['income']}")
i3 = itr3(vt, "(c) 44AD + VDA")
ok(i3["PARTA_PL"]["PersumptiveInc44AD"]["TotPersumptiveInc44AD"] == 196000 and i3["PARTA_PL"]["PersumptiveInc44AD"]["PersumptiveInc44AD8Per"] == 16000
   and i3["ScheduleVDA"]["TotIncCapGain"] == 200000 and i3["PartB-TI"]["CapGain"]["CapGains30Per115BBH"] == 200000
   and {x["SecCode"]: x["SplRateIncTax"] for x in i3["ScheduleSI"]["SplCodeRateTax"]} == {"5BBH": 60000}
   and i3["ITR3ScheduleBP"]["BusinessIncOthThanSpec"]["DeemedProfitBusUs"]["Section44AD"] == 196000,
   f"Part A-P&L 61 (44AD), Schedule VDA, Schedule SI 5BBH: {i3['ScheduleVDA'].get('TotIncCapGain')}")
# a business on its own figures (no presumptive basis chosen), with the simple balance sheet; then over the audit limit -> a CA
w = myreturn.answer(u, vt, ay, {"vda": [], "business": {"kind": "business", "code": "09028", "name": "Vikram Demo Stores", "digital": 4000000, "cash": 500000,
                                                         "gp": 900000, "expenses": 500000, "stock": 300000}})
ok(w["form"] == {"form": "ITR-3", "why": "why_biz_books"} and w["regimes"]["new"]["business"]["income"] == 400000 and not w["ca_needed"],
   f"own P&L: gross profit 9 lakh less 5 lakh expenses = 4 lakh (above 6% / 8% - no audit): {w['form']} {w['regimes']['new']['business']['income']}")
i3 = itr3(vt, "own profit and loss, no regular books")
ok(i3["PARTA_PL"]["NoBooksOfAccPL"]["NetProfit"] == 400000 and i3["PARTA_BS"]["NoBooksOfAccBS"] == {"TotStkInTradAmt": 300000}
   and i3["PartA_GEN2"]["NatOfBus"]["NatureOfBusiness"][0]["Code"] == "09028", "Part A-P&L 64 and the stock in Part A-BS")
w = myreturn.answer(u, vt, ay, {"business": {"kind": "business", "code": "09028", "digital": 12000000, "cash": 3000000, "np": 1000000}})
ok((w["ca_needed"] or {}).get("why") == "ca_audit_turnover" and (w["ca_needed"] or {}).get("limit") == 10000000,
   f"1.5 crore turnover, 20% in cash: over the 1 crore audit limit (s.44AB(a)) - a CA: {w['ca_needed']}")
try:
    myreturn.export(vt, ay)
    ok(False, "a tax audit case: no JSON from My return")
except Exception as e:  # noqa: BLE001
    ok(getattr(e, "status_code", 0) == 409 and "get a CA" in str(getattr(e, "detail", "")), f"a tax audit case: no JSON, get a CA: {getattr(e, 'detail', e)}")
w = myreturn.answer(u, vt, ay, {"business": {"kind": "business", "code": "09028", "digital": 2000000, "np": 50000}, "edits": {"other": {"deposits": 900000}}})
ok((w["ca_needed"] or {}).get("why") == "ca_audit_lower", f"50,000 profit, below the 6% presumptive 1,20,000, with income over the exemption: s.44AB(e) - a CA: {w['ca_needed']}")

# --- wave 3 (2026-10-07): residential status, foreign income and assets, clubbing, relief u/s 89, the updated return ---------------
CC = {n.upper(): c for c, n in myreturn.countries()}
US, UK = CC["UNITED STATES OF AMERICA"], CC["UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND"]
# A a non-resident (40 days in India): only Indian income; no 87A, no senior band at 65, no 80TTB; ITR-2 with his country and TIN
nr = clients.save(u, {"name": "Nikhil Demo Abroad", "pan": "ZZDPN0080A", "status": "individual", "dob": "1960-05-05", "email": "nikhil.demo@demo.example",
                      "phone": "9000000080", "address": "Flat 80, Demo Residency, Madhapur, Hyderabad 500081"})["id"]
w = myreturn.answer(u, nr, ay, {"edits": {"other": {"deposits": 800000, "savings": 30000}},
                                "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20", "days_fy": "40", "days_4y": "200", "citizen": True,
                                            "res_country": US, "res_tin": "ZZ-DEMO-80"},
                                "foreign_rows": [{"country": US, "head": "salary", "amount": 5000000, "tax_paid": 900000, "employer": "Demo Corp Inc"}],
                                "regime": "new", "regime_seen": True, "reviewed": True})
gn, go = w["regimes"]["new"], w["regimes"]["old"]
ok(w["res"]["status"] == "NR" and w["res"]["code"] == "NRI" and w["form"] == {"form": "ITR-2", "why": "why_nonres"} and w["band"] == "below60",
   f"40 days in India: non-resident, ITR-2, the below-60 band at 65: {w['res']} {w['form']} {w['band']}")
ok(gn["salary"]["gross"] == 0 and not w["return"]["extra"]["foreign"][0]["counts"] and gn["tax"]["total"] == 830000 and gn["tax"]["rebate"] == 0 and gn["tax"]["tax"] == 23920,
   f"the US salary is not taxed in India; no 87A on 8.3 lakh: {gn['tax']['tax']}")
ok(go["via"]["d80TTB"] == 0 and go["via"]["d80TTA"] == 10000 and gn["interest"]["b"] > 0,
   f"old regime: 80TTA (10,000), not 80TTB; advance tax due at 65 (no s.207(2)): 234B {gn['interest']['b']}")
i2 = itr2(nr, "a non-resident")
fs = i2["PartA_GEN1"]["FilingStatus"]
ok(fs["ResidentialStatus"] == "NRI" and fs["ConditionsResStatus"] == "5" and fs["JurisdictionResPrevYr"]["JurisdictionResPrevYrDtls"][0] == {"JurisdictionResidence": US, "TIN": "ZZ-DEMO-80"}
   and fs["TotalPrStayIndiaPrevYr"] == 40 and fs["TotalPrStayIndia4PrecYr"] == 200 and "ScheduleFSI" not in i2 and "BenefitUs115HFlg" not in fs,
   f"FilingStatus: NRI, condition 5, the country of residence and TIN, the days: {fs.get('JurisdictionResPrevYr')}")
# B back in India after 9 years abroad: resident but not ordinarily resident - foreign income out, 87A in, Schedule FA not asked
rn = clients.save(u, {"name": "Rekha Demo Returnee", "pan": "ZZDPR0081B", "status": "individual", "dob": "1984-08-08", "email": "rekha.demo@demo.example",
                      "phone": "9000000081", "address": "Flat 81, Demo Residency, Madhapur, Hyderabad 500081"})["id"]
w = myreturn.answer(u, rn, ay, {"edits": {"other": {"deposits": 600000}},
                                "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20", "days_fy": "250", "nr_years": "9", "citizen": True},
                                "foreign_rows": [{"country": UK, "head": "salary", "amount": 2000000, "employer": "Demo Ltd"}, {"country": UK, "head": "interest", "amount": 100000}],
                                "fa_rows": [{"kind": "bank", "country": UK, "name": "Demo Bank plc", "account": "81", "opened": "2016-01-01", "peak": 500000, "closing": 300000}],
                                "regime": "new", "regime_seen": True, "reviewed": True})
gn = w["regimes"]["new"]
ok(w["res"]["status"] == "RNOR" and w["res"]["condition"] == "3" and w["form"]["form"] == "ITR-2" and gn["tax"]["total"] == 600000 and gn["tax"]["tax"] == 0
   and gn["tax"]["rebate"] == 10000 and not any(x["what"] == "fa_missing" for x in w["checks"]),
   f"RNOR (9 of 10 years abroad): the UK salary and interest out, 87A in, no Schedule FA check: {w['res']['status']} {gn['tax']['tax']}")
i2 = itr2(rn, "an RNOR")
ok(i2["PartA_GEN1"]["FilingStatus"]["ResidentialStatus"] == "NOR" and i2["PartA_GEN1"]["FilingStatus"]["ConditionsResStatus"] == "3"
   and i2["PartA_GEN1"]["FilingStatus"]["BenefitUs115HFlg"] == "N" and "ScheduleFA" not in i2 and "ScheduleFSI" not in i2, "ITR-2: NOR, condition 3, no Schedule FA / FSI")
w = myreturn.answer(u, rn, ay, {"foreign_rows": [{"country": UK, "head": "business", "amount": 400000, "controlled": True}]})
ok((w["ca_needed"] or {}).get("why") == "ca_foreign_business", f"an RNOR's foreign business controlled in India counts - a CA's job: {w['ca_needed']}")
myreturn.answer(u, rn, ay, {"foreign_rows": []})
# C the 120-day visitor and the deemed resident: the 15 lakh of income other than from foreign sources worked out from the return
vv = clients.save(u, {"name": "Vivek Demo Visitor", "pan": "ZZDPV0082C", "status": "individual", "dob": "1979-09-09", "email": "vivek.demo@demo.example",
                      "phone": "9000000082", "address": "Flat 82, Demo Residency, Madhapur, Hyderabad 500081"})["id"]
base_v = {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20", "days_fy": "150", "days_4y": "400", "citizen": True, "visiting": True}
w = myreturn.answer(u, vv, ay, {"edits": {"other": {"deposits": 1800000}}, "answers": base_v, "regime": "new", "regime_seen": True, "reviewed": True})
ok(w["res"]["status"] == "RNOR" and w["res"]["condition"] == "6", f"a citizen visiting 150 days with 18 lakh of Indian income: RNOR by the 120-day rule: {w['res']}")
w = myreturn.answer(u, vv, ay, {"edits": {"other": {"deposits": 1000000}}})
ok(w["res"]["status"] == "NR", f"the same visit with 10 lakh: the 182-day rule - non-resident: {w['res']['status']}")
w = myreturn.answer(u, vv, ay, {"edits": {"other": {"deposits": 2000000}}, "answers": {"days_fy": "20", "visiting": False}})
ok(w["res"]["status"] == "RNOR" and w["res"]["condition"] == "7" and w["res"]["deemed"], f"20 days, 20 lakh, taxed nowhere else: deemed resident (s.6(1A)), RNOR: {w['res']}")
itr2(vv, "a deemed resident")
w = myreturn.answer(u, vv, ay, {"answers": {"taxed_elsewhere": True}})
ok(w["res"]["status"] == "NR", "liable to tax in another country: not deemed resident")
# D a resident with US salary, a US dividend and a UK flat - Schedule FSI, TR (relief u/s 90), FA; Form 67
fg = clients.save(u, {"name": "Farah Demo Global", "pan": "ZZDPF0083D", "status": "individual", "dob": "1981-01-01", "email": "farah.demo@demo.example",
                      "phone": "9000000083", "address": "Flat 83, Demo Residency, Madhapur, Hyderabad 500081"})["id"]
FR = [{"country": US, "head": "salary", "amount": 3000000, "tax_paid": 600000, "sec": "90", "article": "16", "tin": "ZZ-US-83", "employer": "Demo Corp Inc",
       "address": "1 Demo Way", "city": "Seattle", "zip": "98101"},
      {"country": US, "head": "dividend", "amount": 200000, "tax_paid": 50000, "sec": "90", "article": "10", "tin": "ZZ-US-83"},
      {"country": UK, "head": "house", "amount": 600000, "municipal_tax": 20000, "tax_paid": 30000, "sec": "90", "tin": "ZZ-UK-83", "address": "Flat 3, Demo Court, London", "zip": "SW1A1AA"}]
w = myreturn.answer(u, fg, ay, {"edits": {"other": {"deposits": 500000}}, "foreign_rows": FR,
                                "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20"}, "regime": "new", "regime_seen": True, "reviewed": True})
gn = w["regimes"]["new"]
ok(any(x["what"] == "fa_missing" and x["level"] == "red" for x in w["checks"]), "foreign income without Schedule FA: a red check")
FA = [{"kind": "bank", "country": US, "name": "Demo Bank NA", "address": "2 Demo Plaza, Seattle", "zip": "98101", "account": "000083", "status": "OWNER",
       "opened": "2019-01-10", "peak": 900000, "closing": 500000, "income": 10000},
      {"kind": "equity", "country": US, "name": "Demo Corp Inc", "address": "1 Demo Way, Seattle", "zip": "98101", "nature": "Company", "opened": "2021-04-01",
       "cost": 800000, "peak": 1500000, "closing": 1200000, "income": 200000},
      {"kind": "property", "country": UK, "address": "Flat 3, Demo Court, London", "zip": "SW1A1AA", "status": "DIRECT", "opened": "2018-06-01", "cost": 9000000,
       "income": 600000, "nature": "Rent", "taxed": 406000, "sch": "HP", "sch_no": "1"}]
w = myreturn.answer(u, fg, ay, {"fa_rows": FA})
gn = w["regimes"]["new"]
t = gn["tax"]
want = sum(min(paid, round(inc * t["tax"] / t["total"])) for inc, paid in ((3000000, 600000), (200000, 50000), (406000, 30000)))
ok(w["res"]["status"] == "ROR" and w["form"] == {"form": "ITR-2", "why": "why_foreign"} and gn["salary"]["gross"] == 3000000 and t["total"] == 4031000
   and gn["houses"][0]["net"] == 406000 and gn["relief"]["s90"] == want and gn["net_tax"] == t["tax"] - want and not any(x["what"] == "fa_missing" for x in w["checks"]),
   f"ROR: 30 lakh US salary, 2 lakh dividend, a UK flat (net 4,06,000): total 40,31,000; relief u/s 90 {gn['relief']['s90']} = lower of foreign tax and Indian tax at the average rate")
i2 = itr2(fg, "foreign income and assets")
fsi = {x["CountryCodeExcludingIndia"]: x for x in i2["ScheduleFSI"]["ScheduleFSIDtls"]}
tr = i2["ScheduleTR1"]
tti = i2["PartB_TTI"]["ComputationOfTaxLiability"]
ok(fsi[US]["IncFromSal"]["IncFrmOutsideInd"] == 3000000 and fsi[US]["IncFromSal"]["TaxReliefinInd"] == 600000 and fsi[US]["IncOthSrc"]["IncFrmOutsideInd"] == 200000
   and fsi[US]["IncFromSal"]["DTAAReliefUs90or90A"] == "16" and fsi[UK]["IncFromHP"]["IncFrmOutsideInd"] == 406000 and fsi[UK]["TaxIdentificationNo"] == "ZZ-UK-83",
   f"Schedule FSI per country and head: {fsi[US]['TotalCountryWise']} {fsi[UK]['TotalCountryWise']}")
ok(tr["TotalTaxPaidOutsideIndia"] == 680000 and tr["TotalTaxReliefOutsideIndia"] == want and tr["TaxReliefOutsideIndiaDTAA"] == want and len(tr["ScheduleTR"]) == 2
   and tti["TaxRelief"]["Section90"] == want and tti["TaxRelief"]["TotTaxRelief"] == want and tti["NetTaxLiability"] == tti["GrossTaxLiability"] - want,
   f"Schedule TR and Part B-TTI: relief u/s 90 {tti['TaxRelief']}, net tax {tti['NetTaxLiability']}")
fa = i2["ScheduleFA"]
sal_us = next(x for x in i2["ScheduleS"]["Salaries"] if x["NameOfEmployer"] == "Demo Corp Inc")
hp_uk = i2["ScheduleHP"]["PropertyDetails"][0]["AddressDetailWithZipCode"]
ok(fa["DetailsForiegnBank"][0]["ForeignAccountNumber"] == "000083" and fa["DtlsForeignEquityDebtInterest"][0]["TotGrossAmtPaidCredited"] == 200000
   and fa["DetailsImmovableProperty"][0]["IncTaxSch"] == "HP" and i2["PartB_TTI"]["AssetOutIndiaFlag"] == "YES"
   and sal_us["AddressDetail"]["StateCode"] == "99" and sal_us["AddressDetail"]["ZipCode"] == "98101" and hp_uk["CountryCode"] == UK and hp_uk["StateCode"] == "99",
   f"Schedule FA (bank, equity, property), the US employer (state 99, ZIP) and the UK flat (country, ZIP): {hp_uk}")
w = myreturn.answer(u, fg, ay, {"business": {"kind": "44ADA", "code": "14001", "name": "Farah Demo Consulting", "digital": 1000000}, "answers": {"filed_on": "2026-08-20"}})
i3 = itr3(fg, "foreign income with a profession (44ADA)")
ok(i3["ScheduleFSI"]["ScheduleFSIDtls"][0]["IncFromBusiness"]["IncFrmOutsideInd"] == 0 and i3["ScheduleFA"]["DetailsForiegnBank"][0]["Bankname"] == "Demo Bank NA",
   "ITR-3 Schedule FSI (with its business block) and Schedule FA")
myreturn.answer(u, fg, ay, {"business": {"kind": ""}})
# E clubbing: a minor child's interest (1,500 exempt), not the child's own earnings; the spouse's dividend and flat from a gift
cl = clients.save(u, {"name": "Geeta Demo Parent", "pan": "ZZDPG0084E", "status": "individual", "dob": "1983-03-03", "email": "geeta.demo@demo.example",
                      "phone": "9000000084", "address": "Flat 84, Demo Residency, Madhapur, Hyderabad 500081"})["id"]
w = myreturn.answer(u, cl, ay, {"edits": {"other": {"deposits": 900000}},
                                "club_rows": [{"name": "Demo Child", "relation": "minor_child", "head": "interest", "amount": 50000},
                                              {"name": "Demo Child", "relation": "minor_child", "head": "other", "amount": 20000, "skill": True},
                                              {"name": "Demo Spouse", "pan": "ZZDPS0084F", "relation": "spouse", "head": "dividend", "amount": 30000},
                                              {"name": "Demo Spouse", "pan": "ZZDPS0084F", "relation": "spouse", "head": "house", "amount": 240000, "address": "Flat 85, Demo Towers"}],
                                "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20"}, "regime": "new", "regime_seen": True, "reviewed": True})
gn = w["regimes"]["new"]
ok(w["form"] == {"form": "ITR-2", "why": "why_club"} and gn["other"] == 900000 + 48500 + 30000 and gn["houses"][0]["net"] == 168000 and gn["tax"]["total"] == 1146500,
   f"clubbed: 48,500 of the child's interest (1,500 exempt, s.10(32)), not the 20,000 she earned; the spouse's 30,000 dividend and 1,68,000 from the flat: {gn['tax']['total']}")
i2 = itr2(cl, "clubbing")
spi = i2["ScheduleSPI"]["SpecifiedPerson"]
ok([(x["SpecifiedPersonName"], x["AmtIncluded"], x["HeadIncIncluded"]) for x in spi] == [("Demo Child", 48500, "OS"), ("Demo Spouse", 30000, "OS"), ("Demo Spouse", 168000, "HP")]
   and spi[1]["ReltnShip"] == "Spouse" and i2["ScheduleEI"]["OthersInc"]["OthersIncDtls"][0] == {"Category": "SRSC", "SubCategory": "10(32)", "OthAmount": 1500}
   and i2["ScheduleEI"]["TotalExemptInc"] == 1500 and i2["ScheduleHP"]["PropertyDetails"][0]["PropertyOwner"] == "SP",
   f"Schedule SPI, Schedule EI 10(32), the spouse's flat in Schedule HP: {spi}")
# F salary arrears of FY 2019-20 and 2021-22 received now: relief u/s 89 (new regime too) - ITR-1 Section89, ITR-2 Part B-TTI
ar = clients.save(u, {"name": "Sanjay Demo Arrears", "pan": "ZZDPA0085F", "status": "individual", "dob": "1980-10-10", "email": "sanjay.demo@demo.example",
                      "phone": "9000000085", "address": "Flat 85, Demo Residency, Madhapur, Hyderabad 500081"})["id"]
w = myreturn.answer(u, ar, ay, {"employers": {"0": {"name": "Demo Employer Ltd", "tan": "HYDD00085F", "gross_17_1": 1500000}},
                                "arrears": [{"fy": "2019-20", "amount": 300000, "income": 300000}, {"fy": "2021-22", "amount": 200000, "income": 300000}],
                                "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20"}, "regime": "new", "regime_seen": True, "reviewed": True})
rl = w["regimes"]["new"]["relief"]
ok(rl["now_with"] == 97500 and rl["now_without"] == 0 and rl["past"] == 33800 and rl["s89"] == 63700 and rl["form10e"] and w["regimes"]["new"]["net_tax"] == 33800
   and w["form"]["form"] == "ITR-1", f"s.89: 97,500 extra now less 33,800 extra then = 63,700 relief (new regime): {rl.get('rows89')}")
d1, r1 = itr_json.assemble(myreturn.facts(ar, ay), "ITR-1")
for x in r1["errors"][:10]:
    print("   -", x["path"], "|", x["message"][:110])
tc1 = d1["ITR"]["ITR1"]["ITR1_TaxComputation"]
ok(r1["valid"] and tc1["Section89"] == 63700 and tc1["NetTaxLiability"] == tc1["GrossTaxLiability"] - 63700, f"ITR-1: Section89 and the net tax: {tc1}")
i2 = itr2(ar, "relief u/s 89")
ok(i2["PartB_TTI"]["ComputationOfTaxLiability"]["TaxRelief"]["Section89"] == 63700, "ITR-2 Part B-TTI relief u/s 89")
# G an updated return for AY 2024-25 (income of 4 lakh left out): 19 months after the AY ended - 50% additional tax
w = myreturn.answer(u, ar, ay, {"itru": {"ay": "2024-25", "filed": "original", "orig_income": 600000, "added": 400000, "tds": 20000, "regime": "new",
                                         "reason": "2", "on": "2026-10-07"}})
iu = w["itru"]
ok(iu["ok"] and iu["tax_before"] == 0 and iu["tax_after"] == 62400 and iu["i234a"] == 16848 and iu["i234b"] == 19344 and iu["i234c"] == 2137 and iu["pct"] == 50
   and iu["additional"] == 50364 and iu["pay"] == 151093 and iu["updated_by"] == 20290331 and iu["schema"] is False,
   f"ITR-U AY 2024-25: tax 62,400 + 234A 16,848 + 234B 19,344 + 234C 2,137 (wave 4), 50% additional 50,364 = 1,51,093: "
   f"{[iu.get(k2) for k2 in ('extra_tax', 'i234a', 'i234b', 'i234c', 'pct', 'additional', 'pay')]}")
w = myreturn.answer(u, ar, ay, {"itru": {"ay": "2023-24", "filed": "none", "orig_income": 0, "added": 900000, "regime": "new", "on": "2026-10-07"}})
ok(w["itru"]["ok"] and w["itru"]["pct"] == 60 and w["itru"]["fee_234f"] == 5000, f"AY 2023-24, no return filed: 60% (third year) and the 234F fee: {w['itru']['pct']} {w['itru']['fee_234f']}")
w = myreturn.answer(u, ar, ay, {"itru": {"ay": "2024-25", "filed": "original", "orig_income": 600000, "added": 400000, "regime": "new", "on": "2026-10-07", "bars": ["search"]}})
ok(not w["itru"]["ok"] and w["itru"]["why"] == "itru_bar_search" and w["itru"]["pay"] == 0, "a search: no updated return")
try:
    myreturn.answer(u, ar, ay, {"itru": {"ay": ay}})
    ok(False, "an updated return is for an earlier year")
except Exception as e:  # noqa: BLE001
    ok(getattr(e, "status_code", 0) == 400, "an updated return is for an earlier year only")

# --- wave 4 (2026-10-08): the gaps after wave 3 ----------------------------------------------------------------------------------
import io  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402


def pdf_of(lines):
    b_ = io.BytesIO()
    c_ = canvas.Canvas(b_, pagesize=A4)
    y_ = 800
    for ln_ in lines:
        c_.setFont("Helvetica", 8.5)
        c_.drawString(36, y_, ln_)
        y_ -= 13
        if y_ < 50:
            c_.showPage()
            y_ = 800
    c_.save()
    return b_.getvalue()


def f16_of(emp, tan, pan, salary, tds, c80c):
    """A dummy Form 16 (Parts A and B) as TRACES / an employer lay it out - the demo's lines, another employer's figures."""
    s_ = lambda n: myreturn._inr(n) + ".00"  # noqa: E731, SLF001
    return pdf_of(["FORM NO. 16 [See rule 31(1)(a)]", "PART A", "Certificate under section 203 of the Income-tax Act, 1961 for tax deducted at source on salary",
                   "Name and address of the Employer/Specified Bank", f"{emp}, Demo Tech Park, Hyderabad 500081",
                   "Name and address of the Employee/ Specified senior citizen", "DEMO EMPLOYEE, Flat 90, Demo Residency, Hyderabad",
                   "PAN of the Deductor TAN of the Deductor PAN of the Employee/ specified senior citizen", f"AAACD0090C {tan} {pan}",
                   "Assessment Year 2026-27 Period with the Employer From 01-Apr-2025 To 31-Mar-2026", f"Total (Rs.) {s_(salary)} {s_(tds)} {s_(tds)}",
                   "PART B (Annexure-I)", "A Whether opting out of taxation u/s 115BAC(1A)? No", "1. Gross Salary",
                   f"(a) Salary as per provisions contained in section 17(1) {s_(salary)}", f"(d) Total {s_(salary)}",
                   "4. Less: Deductions under section 16", "(a) Standard deduction under section 16(ia) 75,000.00",
                   "10. Deductions under Chapter VI-A Gross Amount Deductible Amount",
                   f"(a) Deduction in respect of life insurance premia, contributions to provident fund etc. under section 80C {s_(c80c)} {s_(c80c)}"])


Q = {"answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-07-20"}, "regime_seen": True, "reviewed": True}
# W1 a revised Form 16 from the same employer (same TAN): asked, replaced; a second employer (another TAN): kept, std deduction / 80C once
jc = person("Vikram Demo Two Jobs", "ZZDPJ0090A", 90)
myreturn.add_doc(u, jc, ay, "Form 16 - Demo Alpha.pdf", f16_of("DEMO ALPHA PRIVATE LIMITED", "HYDD00090A", "ZZDPJ0090A", 800000, 40000, 100000))
q = myreturn.add_doc(u, jc, ay, "Form 16 - Demo Alpha revised.pdf", f16_of("DEMO ALPHA PRIVATE LIMITED", "HYDD00090A", "ZZDPJ0090A", 900000, 50000, 100000))
ok((q.get("ask") or {}).get("why") == "same_tan" and q["ask"]["tan"] == "HYDD00090A" and q["ask"]["employer"] == "DEMO ALPHA PRIVATE LIMITED"
   and len([x for x in myreturn.state(jc, ay)["docs"] if x["kind"] == "form16"]) == 1, f"a second Form 16 from the same TAN: asked first, nothing added: {q.get('ask')}")
w = myreturn.add_doc(u, jc, ay, "Form 16 - Demo Alpha revised.pdf", f16_of("DEMO ALPHA PRIVATE LIMITED", "HYDD00090A", "ZZDPJ0090A", 900000, 50000, 100000), on_same="replace")
ok([e["gross_17_1"] for e in w["return"]["employers"]] == [900000], f"replace: the revised Form 16 only (salary not doubled): {[e['gross_17_1'] for e in w['return']['employers']]}")
w = myreturn.add_doc(u, jc, ay, "Form 16 - Demo Beta.pdf", f16_of("DEMO BETA PRIVATE LIMITED", "HYDD00091B", "ZZDPJ0090A", 600000, 30000, 100000))
w = myreturn.answer(u, jc, ay, Q | {"regime": "new"})
chk = {x["what"]: x for x in w["checks"]}
ok(not w.get("ask") and sorted(e["tan"] for e in w["return"]["employers"]) == ["HYDD00090A", "HYDD00091B"] and w["regimes"]["new"]["salary"]["income"] == 1425000
   and chk.get("two_employers", {}).get("level") == "amber" and chk["two_employers"]["a"] == 150000 and chk["two_employers"]["b"] == 75000
   and chk.get("two_emp_80c", {}).get("a") == 200000 and w["regimes"]["old"]["via"]["d80C"] == 150000,
   f"a job change (another TAN): kept, 15 lakh less one 75,000; checks: std taken twice, 80C 2 lakh declared, 1.5 lakh allowed: {[(k2, v['a'], v['b']) for k2, v in chk.items()]}")
q = myreturn.add_doc(u, jc, ay, "Form 16 - Demo Beta second spell.pdf", f16_of("DEMO BETA PRIVATE LIMITED", "HYDD00091B", "ZZDPJ0090A", 100000, 0, 0), on_same="keep")
ok(len([x for x in myreturn.state(jc, ay)["docs"] if x["kind"] == "form16"]) == 3 and sum(e["gross_17_1"] for e in q["return"]["employers"]) == 1600000,
   "keep both: a second spell with the same employer - both salaries count")
i1 = myreturn.facts(jc, ay)
d1, r1 = itr_json.assemble(i1, i1["form"])
ok(r1["valid"], f"two employers: {i1['form']} JSON fits the schema ({r1['error_count']})")

# W2 s.44AB: the cash share of payments (both sides), 44AD(4) / (5); GST per GSTIN, typed and from a GSTR-3B summary
bz = person("Meena Demo Trader", "ZZDPT0091B", 91)
B = {"kind": "business", "code": "09028", "name": "Meena Demo Stores", "digital": 15000000, "cash": 0, "gp": 2000000, "expenses": 800000}
w = myreturn.answer(u, bz, ay, Q | {"business": B, "regime": "new"})
gb = w["regimes"]["new"]["business"]
ok(not w["ca_needed"] and gb["ask_pay"] and gb["audit_limit"] == 100000000, f"1.5 crore, no cash received, payments not typed: the 10 crore limit for now, and asked: {gb['audit_limit']} {gb['ask_pay']}")
w = myreturn.answer(u, bz, ay, {"business": B | {"pay_total": 12000000, "pay_cash": 1200000}})
ok((w["ca_needed"] or {}).get("why") == "ca_audit_turnover" and w["ca_needed"]["limit"] == 10000000,
   f"cash payments 10% of payments: the 10 crore proviso fails - over 1 crore, an audit: {w['ca_needed']}")
w = myreturn.answer(u, bz, ay, {"business": B | {"pay_total": 12000000, "pay_cash": 300000, "gst_rows": [{"gstin": "36ZZDPT0091B1Z5", "turnover": 15000000}]}})
ok(not w["ca_needed"] and not w["regimes"]["new"]["business"]["ask_pay"] and any(x["what"] == "gst" and x["level"] == "ok" for x in w["checks"]),
   f"cash payments 2.5%: within the 10 crore limit; GST turnover agrees: {[(x['what'], x['level']) for x in w['checks']]}")
i3 = itr3(bz, "own P&L under the 10 crore proviso, one GSTIN")
ok(i3["ScheduleGST"]["TurnoverGrsRcptForGSTIN"] == [{"GSTINNo": "36ZZDPT0091B1Z5", "AmtTurnGrossRcptGSTIN": 15000000}], f"ITR-3 Schedule GST: {i3.get('ScheduleGST')}")
try:
    myreturn.answer(u, bz, ay, {"business": B | {"gst_rows": [{"gstin": "36ZZDPT0091", "turnover": 5}]}})
    ok(False, "a bad GSTIN is refused")
except Exception as e:  # noqa: BLE001
    ok(getattr(e, "status_code", 0) == 400 and "GSTIN" in str(getattr(e, "detail", "")), f"a bad GSTIN is refused: {getattr(e, 'detail', e)}")
w = myreturn.answer(u, bz, ay, {"business": {"kind": "business", "code": "09028", "digital": 4000000, "gp": 900000, "expenses": 500000, "ad_left": "yes", "gst_rows": []},
                                "edits": {"other": {"deposits": 300000}}})
ok((w["ca_needed"] or {}).get("why") == "ca_audit_44ad4", f"left 44AD within five years, income above the exemption: s.44AD(5) / 44AB(e) - an audit: {w['ca_needed']}")
w = myreturn.answer(u, bz, ay, {"business": {"kind": "44AD", "code": "09028", "digital": 1000000, "ad_left": "yes"}, "edits": {"other": {"deposits": ""}}})
ok((w["ca_needed"] or {}).get("why") == "ca_44ad_closed", f"44AD chosen while s.44AD(4) keeps it closed: {w['ca_needed']}")
w = myreturn.answer(u, bz, ay, {"business": {"kind": "44ADA", "code": "14001", "name": "Meena Demo Design", "digital": 1800000, "gst_rows": []}})
G3B = ("GSTIN,Tax Period,Total Taxable value,Zero rated supplies,Nil rated and exempted supplies,Non-GST supplies\n"
       "36ZZDPT0091B1Z5,April 2025,500000,0,20000,0\n36ZZDPT0091B1Z5,May 2025,400000,0,0,0\n29ZZDPT0091B1Z7,April 2025,300000,50000,0,0\n")
d = myreturn.add_doc(u, bz, ay, "GSTR-3B summary FY 2025-26.csv", G3B.encode())
w = myreturn.answer(u, bz, ay, {})
gr = {x["gstin"]: x["turnover"] for x in w["return"]["business"]["gst_rows"]}
ok(d["added"]["kind"] == "gst" and gr == {"36ZZDPT0091B1Z5": 920000, "29ZZDPT0091B1Z7": 350000} and w["form"]["form"] == "ITR-4"
   and any(x["what"] == "gst" and x["level"] == "red" for x in w["checks"]), f"GSTR-3B read per GSTIN (months added up); 12.7 lakh against 18 lakh receipts - red: {gr}")
n4, d4, r4 = myreturn.export(bz, ay)
bp4 = json.loads(d4)["ITR"]["ITR4"]["ScheduleBP"]
ok(r4["valid"] and len(bp4["TurnoverGrsRcptForGSTIN"]) == 2 and bp4["TotalTurnoverGrsRcptGSTIN"] == 1270000, f"ITR-4 GST schedule, two GSTINs: {bp4.get('TurnoverGrsRcptForGSTIN')}")

# W3 losses brought forward from last year's ITR-3 (its Schedule CFL is named by AY); a business loss there - a CA's job
l3 = person("Kavya Demo Prev Three", "ZZDPK0092C", 92)
P3 = lambda cfl: {"ITR": {"ITR3": {"Form_ITR3": {"FormName": "ITR-3", "AssessmentYear": "2025"}, "PartA_GEN1": {"PersonalInfo": {"PAN": "ZZDPK0092C",  # noqa: E731
                  "AssesseeName": {"FirstName": "Kavya", "SurNameOrOrgName": "Demo Prev Three"}, "DOB": "1978-04-04"}}, "Verification": {"Date": "2025-07-28"},
                  "ScheduleCFL": cfl}}}
CFL3 = {"LossCFCurrentAssmntYear2025": {"CarryFwdLossDetail": {"DateOfFiling": "2024-07-30", "TotalSTCGPTILossCF": 20000}},
        "LossCFCurrentAssmntYear2022": {"CarryFwdLossDetail": {"DateOfFiling": "2021-07-30", "TotalLTCGPTILossCF": 15000}},
        "AdjTotBFLossInBFLA": {"LossSummaryDetail": {"TotalSTCGPTILossCF": 5000}}, "CurrentAYloss": {"LossSummaryDetail": {"TotalLTCGPTILossCF": 70000}}}
d = myreturn.add_doc(u, l3, ay, "ITR-3 AY 2025-26 filed.json", json.dumps(P3(CFL3)).encode())
w = myreturn.answer(u, l3, ay, Q | {"losses_from_prev": True})
ok(d["added"]["kind"] == "filed_prev" and w["return"]["losses_bf"] == [
    {"ay": "2021-22", "kind": "ltcl", "amount": 15000.0, "filed_on": "2021-07-30"}, {"ay": "2024-25", "kind": "stcl", "amount": 15000.0, "filed_on": "2024-07-30"},
    {"ay": "2025-26", "kind": "ltcl", "amount": 70000.0, "filed_on": "2025-07-28"}] and not w["ca_needed"],
   f"last year's ITR-3: its blocks by AY, the set-off taken off the oldest, last year's own loss: {w['return']['losses_bf']}")
CFL3["CurrentAYloss"]["LossSummaryDetail"]["BusLossOthThanSpecLossCF"] = 50000
myreturn.add_doc(u, l3, ay, "ITR-3 AY 2025-26 filed again.json", json.dumps(P3(CFL3)).encode(), on_same="replace")
w = myreturn.answer(u, l3, ay, {"losses_from_prev": True})
ok((w["ca_needed"] or {}).get("why") == "ca_bf_business_loss" and w["ca_needed"]["loss"] == 50000 and w["return"]["losses_bf_other"][0]["kind"] == "bl",
   f"a business loss brought forward (s.72): a CA's return: {w['ca_needed']}")

# W4 the exemptions' time limits, and two on one sale (54 + 54EC), split by amount
ex = person("Arjun Demo Seller", "ZZDPE0093D", 93)
H = {"asset": "house", "name": "Flat 93, Demo Towers", "acquired": "2012-05-01", "sold": "2025-06-10", "sale": 8000000, "cost": 2000000, "buyer": "Demo Buyer",
     "buyer_pan": "ZZDPB0093E", "address": "Flat 93, Demo Towers, Hyderabad", "pin": "500081", "state": "36"}
w = myreturn.answer(u, ex, ay, Q | {"cg_rows": [H | {"ex_kind": "54", "ex_amount": 3000000, "ex_on": "2026-03-01", "ex_kind_1": "54EC", "ex_amount_1": 2000000,
                                                     "ex_on_1": "2025-11-01"}], "regime": "new"})
r0 = w["return"]["cgw"]["rows"][0]
ok(r0["exempt"] == 5000000 and r0["gain"] - r0["final"] == 5000000 and [c["amount"] for c in r0["claims"]] == [3000000, 2000000]
   and [c["amount_indexed"] for c in r0["claims"]] == [3000000, r0["gain_indexed"] - 3000000],
   f"54 (30 lakh house) and 54EC (20 lakh bonds) on one sale; against the indexed gain the bonds count only up to what is left: {[(c['ex_kind'], c['amount'], c['amount_indexed']) for c in r0['claims']]}")
i2 = itr2(ex, "54 and 54EC on one sale")
dci = i2["ScheduleCGFor23"]["DeducClaimInfo"]
lt0 = i2["ScheduleCGFor23"]["LongTermCapGain23"]["SaleofLandBuild"]["SaleofLandBuildDtls"][0]
ok(dci["DeducClaimDtlsUs54"][0]["AmtDeducted"] == 3000000 and dci["DeducClaimDtlsUs54EC"][0]["AmtDeducted"] == 2000000
   and {x["ExemptionSecCode"]: x["ExemptionAmount"] for x in lt0["ExemptionOrDednUs54"]["ExemptionOrDednUs54Dtls"]} == {"54": 3000000, "54EC": 2000000},
   f"Table D: one claim under each section; Schedule CG B1 lists both: {lt0['ExemptionOrDednUs54']}")
w = myreturn.answer(u, ex, ay, {"cg_rows": [H | {"ex_rows": [{"ex_kind": "54", "ex_amount": 3000000, "ex_on": "2026-03-01"},
                                                            {"ex_kind": "54EC", "ex_amount": 2000000, "ex_on": "2026-01-15"}]}]})
r0 = w["return"]["cgw"]["rows"][0]
ok(r0["exempt"] == 3000000 and r0["claims"][1]["amount"] == 0 and r0["claims"][1]["why"] == "ex_late_54EC",
   f"bonds bought 7 months after the sale: 54EC not allowed (6 months, s.54EC): {[(c['ex_kind'], c['amount'], c['why']) for c in r0['claims']]}")
w = myreturn.answer(u, ex, ay, {"cg_rows": [H | {"ex_rows": [{"ex_kind": "54", "cgas": 3000000, "cgas_on": "2026-08-05"}]}]})
r0 = w["return"]["cgw"]["rows"][0]
ok(r0["exempt"] == 0 and r0["ex_why"] == "ex_cgas_late", f"CGAS deposit after 31 July (the due date u/s 139(1)): not counted: {r0['ex_why']}")
w = myreturn.answer(u, ex, ay, {"cg_rows": [H | {"ex_rows": [{"ex_kind": "54", "ex_amount": 3000000, "ex_on": "2028-05-01", "ex_build": "build"}]}]})
ok(w["return"]["cgw"]["rows"][0]["exempt"] == 3000000, "a house built within 3 years after the sale: 54 allowed")
w = myreturn.answer(u, ex, ay, {"cg_rows": [H | {"ex_rows": [{"ex_kind": "54", "ex_amount": 3000000, "ex_on": "2024-05-01"}]}]})
ok(w["return"]["cgw"]["rows"][0]["exempt"] == 0 and w["return"]["cgw"]["rows"][0]["ex_why"] == "ex_late_54", "a house bought 13 months before the sale: 54 not allowed")

# W5 a CAMS capital-gains statement as a PDF (its text layout)
cv = person("Neha Demo CAS", "ZZDPC0094E", 94)
CAS = pdf_of(["CAMS - Consolidated Account Statement", "Capital Gain / Loss Statement for the period 01-Apr-2025 to 31-Mar-2026",
              "Demo Bluechip Equity Fund - Direct Growth ISIN: INF000Z01045 Folio 9401",
              "Redemption 10-Sep-2025 1,000.000 3,00,000.00 15-Jun-2017 1,00,000.00 2,50,000.00",
              "Demo Liquid Fund - Direct Growth ISIN: INF000Z01052 Folio 9402", "Redemption 05-Aug-2025 200.000 2,10,000.00 01-Feb-2024 2,00,000.00"])
d = myreturn.add_doc(u, cv, ay, "CAMS capital gains FY 2025-26.pdf", CAS)
w = myreturn.answer(u, cv, ay, Q | {"regime": "new"})
rows_ = w["return"]["cgw"]["rows"]
ok(d["added"]["kind"] == "cg" and [(x["asset"], x["isin"], x["bucket"], x["final"]) for x in rows_] == [("equity", "INF000Z01045", "ltcg_112a", 50000), ("debt_mf", "INF000Z01052", "stcg_app", 10000)],
   f"CAMS PDF: an equity fund (grandfathered at the 31-01-2018 value) and a liquid fund (s.50AA): {[(x['asset'], x['bucket'], x['final']) for x in rows_]}")
itr2(cv, "a CAMS PDF")

# W6 26AS Part A2 / IV: the buyer's 194IA TDS (rent u/s 194IB in the same part is not a sale of property)
sp = person("Gopal Demo Property", "ZZDPG0095F", 95)
T26 = "\n".join(["^Annual Tax Statement^", "^Permanent Account Number (PAN)^ZZDPG0095F^Financial Year^2025-26^Assessment Year^2026-27^",
                 "^PART-I - Details of Tax Deducted at Source^",
                 "^Sr. No.^Name of Deductor^TAN of Deductor^^^^^Total Amount Paid / Credited(Rs.)^Total Tax Deducted #(Rs.)^Total TDS Deposited(Rs.)",
                 "^1^DEMO BANK LIMITED^HYDD00077B^^^^^62000.00^6200.00^6200.00",
                 "^^Sr. No.^Section^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited(Rs.)^Tax Deducted ##(Rs.)^TDS Deposited(Rs.)",
                 "^^1^194A^31-Mar-2026^F^15-May-2026^-^62000.00^6200.00^6200.00",
                 "^PART-IV - Details of Tax Deducted at Source u/s 194IA/ 194IB/ 194M/ 194S (For Seller/Landlord of Property/Contractors or Professionals/Seller of Virtual Digital Asset)^",
                 "^Sr. No.^Acknowledgement Number^Name of Deductor^PAN of Deductor^Transaction Date^Total Transaction Amount (Rs.)^Total TDS Deposited (Rs.)^Total Amount Deposited other than TDS (Rs.)",
                 "^1^DEMOACK95^DEMO BUYER NINETYFIVE^ZZDPB0095G^20-Dec-2025^9000000.00^90000.00^0.00",
                 "^^Sr. No.^TDS Certificate Number^Section^Date of Deposit^Status of Booking*^Date of Booking^Demand Payment^TDS Deposited (Rs.)^Total Amount Deposited other than TDS (Rs.)",
                 "^^1^-^194IA^05-Jan-2026^F^10-Jan-2026^0.00^90000.00^0.00",
                 "^2^DEMOACK96^DEMO TENANT^ZZDPT0096H^31-Mar-2026^600000.00^12000.00^0.00",
                 "^^1^-^194IB^05-Apr-2026^F^10-Apr-2026^0.00^12000.00^0.00",
                 "^PART-V - Details of Transactions under Proviso to section 194B^"])
d = myreturn.add_doc(u, sp, ay, "26AS ZZDPG0095F.txt", T26.encode())
w = myreturn.answer(u, sp, ay, Q | {"regime": "new", "cg_rows": [H | {"buyer_pan": "ZZDPB0095G", "buyer": "Demo Buyer Ninetyfive", "ex_kind": "54EC",
                                                                     "ex_amount": 5000000, "ex_on": "2025-09-01"}]})
ok([(x["pan"], x["tds"], x["section"]) for x in w["return"]["tds_194ia"]] == [("ZZDPB0095G", 90000.0, "194IA")] and [x["tan"] for x in w["return"]["tds"]] == ["HYDD00077B"]
   and w["regimes"]["new"]["tds"] == 96200, f"26AS Part IV: the buyer's 90,000 (194IA) - not the tenant's 194IB, not a Part I deductor: {w['return']['tds_194ia']}")
i2 = itr2(sp, "194IA from 26AS")
ok(i2["ScheduleTDS3"]["TDS3onOthThanSalDtls"][0]["PANOfBuyerTenant"] == "ZZDPB0095G" and i2["ScheduleTDS3"]["TotalTDS3OnOthThanSal"] == 90000, "Schedule TDS3 from 26AS Part A2")
pdf_text = "\n".join(["PART-IV - Details of Tax Deducted at Source u/s 194IA/ 194IB (For Seller/Landlord of Property)",
                      "Sr. No. Acknowledgement Number Name of Deductor PAN of Deductor Transaction Date Total Transaction Amount (Rs.) Total TDS Deposited (Rs.)",
                      "1 DEMOACK95 DEMO BUYER NINETYFIVE ZZDPB0095G 20-Dec-2025 90,00,000.00 90,000.00 0.00", "1 - 194IA 05-Jan-2026 F 10-Jan-2026 0.00 90,000.00 0.00",
                      "PART-V - Details of Transactions"])
ok(myreturn_read.a2_26as(pdf_text)[1] == [{"pan": "ZZDPB0095G", "name": "DEMO BUYER NINETYFIVE", "income": 9000000.0, "tds": 90000.0, "section": "194IA"}],
   "26AS PDF text: Part IV's buyer line and its 194IA entry")

# W7 the updated return of an earlier year: its special rates (111A at 15% in FY 2023-24), 234C, surcharge with marginal relief
uu = person("Lata Demo Update", "ZZDPU0097J", 97)
w = myreturn.answer(u, uu, ay, {"itru": {"ay": "2024-25", "filed": "original", "orig_income": 1000000, "add_111a": 500000, "tds": 50000, "regime": "new",
                                         "reason": "2", "on": "2026-10-07"}})
iu = w["itru"]
ok(iu["ok"] and iu["tax_before"] == 62400 and iu["tax_after"] == 140400 and iu["extra_tax"] == 78000 and iu["i234c"] == 3939,
   f"FY 2023-24: 5 lakh of 111A gains at that year's 15% (75,000 + cess); 234C of the updated tax less that of the return before: {[iu.get(k2) for k2 in ('tax_before', 'tax_after', 'i234c')]}")
w = myreturn.answer(u, uu, ay, {"itru": {"ay": "2023-24", "filed": "original", "orig_income": 4800000, "added": 300000, "tds": 1302600, "regime": "old",
                                         "reason": "2", "on": "2026-10-07"}})
iu = w["itru"]
ok(iu["ok"] and iu["tax_before"] == 1302600 and iu["tax_after"] == 1469000 and iu["surcharge"] == 70000,
   f"FY 2022-23, 51 lakh: 10% surcharge cut to 70,000 by marginal relief (no longer 'ask a CA'): {[iu.get(k2) for k2 in ('tax_before', 'tax_after', 'surcharge')]}")
w = myreturn.answer(u, uu, ay, {"itru": {"ay": "2025-26", "filed": "original", "orig_income": 1500000, "add_112a": 225000, "early": "yes", "regime": "new", "on": "2026-10-07"}})
ok(w["itru"]["tax_after"] - w["itru"]["tax_before"] == 10400, f"FY 2024-25, sold before 23 July 2024: 10% over 1.25 lakh = 10,000 + cess: {w['itru']['extra_tax']}")

# W8 relief u/s 89 for an earlier year over 50 lakh: that year's surcharge, worked out
s89 = person("Mohan Demo Arrears", "ZZDPM0098K", 98)
w = myreturn.answer(u, s89, ay, Q | {"employers": {"0": {"name": "Demo Employer Ltd", "tan": "HYDD00098K", "gross_17_1": 6000000}},
                                     "arrears": [{"fy": "2019-20", "amount": 1000000, "income": 4500000, "regime": "old"}], "regime": "new"})
rl = w["regimes"]["new"]["relief"]
ok(not rl["unknown89"] and rl["rows89"][0]["before"] == 1209000 and rl["rows89"][0]["after"] == 1673100 and rl["rows89"][0]["extra"] == 464100,
   f"FY 2019-20 at 45 + 10 lakh: that year's 10% surcharge in the tax with the arrears: {rl['rows89']}")

# W9 Schedule FA D-F: an account you can sign for, a trust abroad, other income from outside India
fx = person("Rhea Demo Foreign", "ZZDPF0099L", 99)
w = myreturn.answer(u, fx, ay, Q | {"answers": Q["answers"] | {"foreign": True}, "regime": "new", "fa_rows": [
    {"kind": "signing", "country": US, "name": "Demo Bank NA", "address": "1 Demo Plaza, Seattle", "zip": "98101", "holder": "Demo Family Trust", "account": "US9901", "peak": 800000},
    {"kind": "trust", "country": US, "name": "Demo Family Trust", "address": "2 Demo Road, Seattle", "zip": "98102", "trustees": "Demo Trustee", "trustees_addr": "3 Demo Lane",
     "settlor": "Demo Settlor", "settlor_addr": "4 Demo Lane", "beneficiaries": "Rhea Demo Foreign", "beneficiaries_addr": "Hyderabad", "opened": "2020-01-01"},
    {"kind": "income", "country": US, "name": "Demo Agency", "address": "5 Demo Street, Seattle", "zip": "98103", "income": 50000, "nature": "Royalty", "taxed": 50000,
     "sch": "OS", "sch_no": "1"}]})
i2 = itr2(fx, "Schedule FA D-F")
fa = i2["ScheduleFA"]
ok(fa["DetailsOfAccntsHvngSigningAuth"][0]["NameMentionedInAccnt"] == "Demo Family Trust" and fa["DetailsOfAccntsHvngSigningAuth"][0]["IncAccuredTaxFlag"] == "N"
   and fa["DetailsOfTrustOutIndiaTrustee"][0]["NameOfSettlor"] == "Demo Settlor" and fa["DetailsOfOthSourcesIncOutsideIndia"][0]["IncDrvTaxFlag"] == "Y"
   and fa["DetailsOfOthSourcesIncOutsideIndia"][0]["IncOfferedAmt"] == 50000, f"Schedule FA tables of signing authority, trusts and other income: {list(fa)}")

# W10 the old regime chosen in the save that first adds a business: checked against that form's due date (ITR-4: 31 August)
rg = person("Sanya Demo Regime", "ZZDPR0100M", 100)
myreturn.answer(u, rg, ay, {"employers": {"0": {"name": "Demo Employer Ltd", "tan": "HYDD00100M", "gross_17_1": 900000}},
                            "answers": {"father": "Demo Father", "state": "36", "filed_on": "2026-08-20"}})
w = myreturn.answer(u, rg, ay, {"business": {"kind": "44ADA", "code": "14001", "name": "Sanya Demo Studio", "digital": 1000000}, "regime": "old"})
ok(w["regime"] == "old" and w["old_ok"] and w["form"]["form"] == "ITR-4" and w["dates"]["due"] == 20260831,
   f"filed 20 August: ITR-1 would be late, but with the business added in the same save it is ITR-4 (due 31 August) - the old regime is open: {w['form']} {w['dates']['due']}")
try:
    myreturn.answer(u, rg, ay, {"business": {"kind": ""}, "regime": "old"})
    ok(False, "the business taken out in the same save: ITR-1 is late, the old regime closed")
except Exception as e:  # noqa: BLE001
    st_ = myreturn.state(rg, ay)
    ok(getattr(e, "status_code", 0) == 400 and st_["business"]["kind"] == "44ADA", f"the business taken out with the old regime: refused, nothing saved: {getattr(e, 'detail', e)}")

# W11 (2026-10-10) Schedule FA table B: a financial interest in a company or firm abroad - ITR-2, then ITR-3 (with a profession);
# a status typed that the table does not take is said its way (OWNER -> DIRECT for B / C, DIRECT -> OWNER for A1)
fb = person("Kabir Demo Entity", "ZZDPK0101N", 101)
w = myreturn.answer(u, fb, ay, Q | {"answers": Q["answers"] | {"foreign": True}, "regime": "new", "fa_rows": [
    {"kind": "financial", "country": US, "name": "Demo Ventures LLC", "address": "6 Demo Avenue, Austin", "zip": "73301", "nature": "Limited liability company",
     "status": "OWNER", "opened": "2021-06-15", "cost": 1500000, "income": 40000, "inc_nature": "Share of profit", "taxed": 40000, "sch": "OS", "sch_no": "1"},
    {"kind": "property", "country": UK, "name": "Flat", "address": "7 Demo Mews, London", "zip": "E1 6AN", "status": "OWNER", "opened": "2019-03-01", "cost": 9000000},
    {"kind": "bank", "country": US, "name": "Demo Bank NA", "address": "1 Demo Plaza, Seattle", "zip": "98101", "account": "US0101", "status": "DIRECT",
     "opened": "2018-01-10", "peak": 300000, "closing": 250000, "income": 1200}]})
ok(not any(x["what"] == "fa_missing" for x in w["checks"]), "Schedule FA with table B: no 'foreign assets not listed' check")
fa = itr2(fb, "Schedule FA table B")["ScheduleFA"]
b = fa["DetailsFinancialInterest"][0]
ok(b["NameOfEntity"] == "Demo Ventures LLC" and b["NatureOfEntity"] == "Limited liability company" and b["NatureOfInt"] == "DIRECT" and b["DateHeld"] == "2021-06-15"
   and b["TotalInvestment"] == 1500000 and b["IncFromInt"] == 40000 and b["NatureOfInc"] == "Share of profit" and b["IncTaxAmt"] == 40000 and b["IncTaxSch"] == "OS"
   and fa["DetailsImmovableProperty"][0]["Ownership"] == "DIRECT" and fa["DetailsForiegnBank"][0]["OwnerStatus"] == "OWNER",
   f"ITR-2 Schedule FA B (DetailsFinancialInterest) and the statuses said each table's way: {b}")
myreturn.answer(u, fb, ay, {"business": {"kind": "44ADA", "code": "14001", "name": "Kabir Demo Consulting", "digital": 1000000}, "answers": {"filed_on": "2026-08-20"}})
b3 = itr3(fb, "Schedule FA table B with a profession (44ADA)")["ScheduleFA"]["DetailsFinancialInterest"][0]
ok(b3["NameOfEntity"] == "Demo Ventures LLC" and b3["IncFromInt"] == 40000, f"ITR-3 Schedule FA B: {b3}")
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
