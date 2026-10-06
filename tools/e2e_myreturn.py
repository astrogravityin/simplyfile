"""My return end to end, in a scratch data folder (2026-10-06): a self-filer's client, the four demo documents read, the checks,
both regimes, the form, and the ITR JSON checked against the department's schema. Run from the repo root after
tools/showcase/make_myreturn_demo.py:

    python tools/e2e_myreturn.py
"""
import os
import sys
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
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
