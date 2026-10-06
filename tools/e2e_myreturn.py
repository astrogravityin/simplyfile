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
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
