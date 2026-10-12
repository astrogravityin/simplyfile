"""python tools/e2e_itr6.py

Company returns (ITR-6), end to end through the API on a throw-away data folder, with the two demo companies' documents
(tools/showcase/company_demo.py - invented): CA firm -> company clients (CIN, option, directors, shareholders) -> Intake & map ->
Reconcile (26AS) -> Compute & close (the company's year: turnover, losses and MAT credit brought forward) -> a schema-valid ITR-6 JSON
-> sign-off -> filed. Then the edge cases: the 115BAA option, MAT and its credit, losses carried and lapsed (s.72, s.79), 234B / 234C,
the company master's checks and the tenant wall. Prints PASS / FAIL per step."""
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tools" / "showcase"))
os.chdir(HERE)
os.environ["TV_DATA"] = tempfile.mkdtemp(prefix="sf-e2e-itr6-")
from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402
import company_demo as demo  # noqa: E402

AY = demo.AY
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
    assert s.post("/api/auth/signin", json={"identity": email, "password": pw}).status_code == 200
    return s


admin = TestClient(app.app)
assert admin.post("/api/auth/first-account", json={"email": "admin@valuestream.test", "password": "Admin-pass-123"}).status_code == 200
admin.post("/api/users", json={"email": "ca@demo.test", "password": "Demo-pass-1234", "display_name": "Demo Partner"})
ca = session("ca@demo.test", "Demo-pass-1234")


@step("0 A CA firm, approved (the Filing screens open)")
def _():
    fid = ca.post("/api/firm/start", json={"kind": "ca_firm"}).json()["id"]
    ca.put("/api/firm", json={"name": "Demo CA Filing Firm", "pan": "AAFFP1234C", "tan": "HYDP12345E", "gstin": "36AAFFP1234C1Z5", "frn": "012345S",
                              "membership_no": "212345", "owner_name": "Demo Partner", "aadhaar_last4": "4821", "phone": "9000000001",
                              "email": "ca@demo.test", "address": "Somajiguda, Hyderabad 500082", "consent": True})
    for k in ("owner_aadhaar", "pan_card", "tan_letter", "gst_cert"):
        ca.post(f"/api/firm/docs/{k}", files={"file": (f"{k}.pdf", b"%PDF-1.4 demo")})
    ca.post(f"/api/firm/{fid}/move", json={"action": "submit"})
    assert admin.post(f"/api/firm/{fid}/move", json={"action": "approve"}).json()["state"] == "approved"
    assert ca.get("/api/clients/settings").status_code == 200


@step("1 Company master: status Company needs PAN letter C; a bad CIN, DIN, shareholding and 115BAB without manufacturing are refused")
def _():
    k = ca.get("/api/clients/settings").json()
    st = next(s for s in k["statuses"] if s["id"] == "company")
    assert st["form"] == "ITR-6" and st["pan_letter"] == "C" and "ITR-6" in k["forms"] and k["company"]["kinds"], st
    base = demo.COMPANIES["zenith"]["client"]
    bad = [(base | {"pan": "ZZDPZ0061K"}, "pan"), (base | {"company": base["company"] | {"cin": "U12"}}, "CIN"),
           (base | {"company": base["company"] | {"directors": [{"name": "X", "din": "12"}]}}, "DIN"),
           (base | {"company": base["company"] | {"shareholders": [{"name": "A", "pct": 70}, {"name": "B", "pct": 40}]}}, "100%"),
           (base | {"company": base["company"] | {"option": "115BAB", "manufacturing": False}}, "115BAB")]
    for body, why in bad:
        r = ca.post("/api/clients", json=body)
        assert r.status_code == 400, (why, r.status_code, r.text)
    return "5 bad masters refused with a message each"


def make(key):
    x = demo.COMPANIES[key]
    r = ca.post("/api/clients", json=x["client"] | {"ay": AY})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    c = ca.get(f"/api/clients/{cid}").json()
    assert c["company"]["cin"] == x["client"]["company"]["cin"] and len(c["company"]["directors"]) == len(x["client"]["company"]["directors"])
    y = ca.get(f"/api/compute/{cid}/{AY}").json()
    assert y["client"]["form"] == "ITR-6", y["client"]
    files = {}
    for name, data in demo.documents(key):
        if name.endswith(".txt"):
            assert ca.post(f"/api/recon/{cid}/{AY}", files={"file": (name, data)}).status_code == 200, name
        else:
            f = ca.post(f"/api/intake/{cid}/{AY}", files={"file": (name, data)})
            assert f.status_code == 200, (name, f.text)
            files[name] = f.json()
    for f in files.values():
        v = ca.get(f"/api/intake/{cid}/{AY}/{f['id']}").json()
        open_ = [(r["label"], r["ref"]) for r in v["rows"] if r["state"] in ("untagged", "invalid")]
        assert not open_, open_
    rb = f"/api/recon/{cid}/{AY}"
    for fnd in ca.get(rb).json()["findings"]:
        if fnd["severity"] == "red":
            ca.put(f"{rb}/notes/{fnd['id']}", json={"note": "TDS u/s 194Q by buyers on sales; income in the books as revenue from operations."})
    d = ca.put(f"/api/compute/{cid}/{AY}", json={"company": x["year"]}).json()
    S[key] = cid
    return d


@step("2 Zenith (trading, 115BAA): documents mapped, 26AS read; 22% + 10% surcharge + 4% cess, no MAT, no 80G, 80M allowed")
def _():
    d = make("zenith")
    co = d["company"]
    assert co["option"] == "115BAA" and co["rate"]["rate"] == 22 and co["rate"]["flat"] and not co["rate"]["mat"], co["rate"]
    assert co["dep"]["total"] == 755000, co["dep"]
    bp = next(h for h in d["heads"] if h["id"] == "BP")["net"]
    assert bp == 13425000, bp
    assert d["gti"] == 14275000 and d["deductions"] == 200000 and d["income"] == 14075000, (d["gti"], d["deductions"], d["income"])
    assert co["d80g"]["total"] == 0 and co["d80m"]["deduction"] == 200000, (co["d80g"], co["d80m"])
    assert d["tax"]["total"] == 3542400 and d["tax"]["basis"] == "normal" and co["mat"]["mat"] == 0, d["tax"]
    assert d["tds_total"] == 85000 and d["paid_total"] == 3450000, (d["tds_total"], d["paid_total"])
    assert d["dates"]["due_rule"] == 20261031, d["dates"]
    return f"income {d['income']:,} tax {d['tax']['total']:,} (25.168%) · 234C {d['interest_auto']['c']:,} · balance {d['balance']['kind']} {d['balance']['amount']:,}"


@step("3 Zenith ITR-6 JSON: valid against the CBDT schema; Part A-GEN, BS / P&L tally, Schedule BP, DEP, OS, VI-A, SH, TTI in place")
def _():
    cb = f"/api/compute/{S['zenith']}/{AY}"
    rep = ca.get(f"{cb}/itr-check").json()
    assert rep["valid"], [f"{e['path']}: {e['message']}" for e in rep["errors"][:15]]
    b = rep["books"]
    assert b["bs_diff"] == 0 and b["pl_diff"] == 0 and not b["unknown"] and not b["skipped"], b
    doc = json.loads(ca.get(f"{cb}/itr.json").content)["ITR"]["ITR6"]
    g1 = doc["PartA_GEN1"]
    assert g1["OrgFirmInfo"]["CINissuedByMCA"] == "U51909TG2018PTC000061" and g1["OrgFirmInfo"]["StatusOrCompanyType"] == "7"
    assert g1["FilingStatus"]["Section115BA"] == "115BAA" and g1["FilingStatus"]["Section115BAAY"] == "2021-22"
    assert g1["FilingStatus"]["ItrFilingDueDate"] == "2026-10-31" and g1["FilingStatus"]["GrossReceipt"] == "Y"
    assert [p["Designation"] for p in doc["PartA_GEN2For6"]["KeyPersons"]] == ["MD", "DIR"]
    assert len(doc["ScheduleSH"]["ShrhldngUnlistedCompany"]["DtlsSHEndPreviousYearUC"]) == 2
    bp = doc["CorpScheduleBP"]["BusinessIncOthThanSpec"]
    assert bp["ProfBfrTaxPL"] == 13870000 and bp["DepreciationAllowITAct32"]["TotDeprAllowITAct"] == 755000 and doc["CorpScheduleBP"]["IncChrgUnHdProftGain"] == 13425000
    assert doc["ScheduleDEP"]["SummaryFromDeprSch"]["TotalDepreciation"] == 755000
    assert doc["PartB-TI"]["TotalIncome"] == 14075000 and doc["ScheduleVIA"]["DeductUndChapVIA"]["Section80M"] == 200000
    tti = doc["PartB_TTI"]["ComputationOfTaxLiability"]
    assert tti["TaxPayableOnTI"]["TaxAtNormalRates"] == 3096500 and tti["NetTaxLiability"] == 3542400 and "ScheduleMAT" not in doc
    assert doc["Verification"]["Declaration"]["Capacity"] == "MD" and doc["Verification"]["Declaration"]["AssesseeVerPAN"] == "ZZDPK0061A"
    assert doc["PARTA_BSFor6FrmAY13"]["TotalAssets"] == 76900000 and doc["PARTA_PL"]["DebitsToPL"]["DebitPlAcnt"]["PBT"] == 13870000
    return f"valid against {rep['schema']}, {rep['filled']} values placed; BS {b['bs_sources']:,.0f} = assets; PBT {b['pl_profit']:,.0f}"


@step("4 Kaveri (manufacturing, normal, MAT): additional depreciation, b/f loss and unabsorbed depreciation set off, an old loss lapsed")
def _():
    d = make("kaveri")
    co = d["company"]
    assert co["rate"]["rate"] == 25 and co["rate"]["why"] == "why_low" and co["rate"]["mat"], co["rate"]
    pm = next(b for b in co["dep"]["blocks"] if b["id"] == "pm15")
    assert pm["addl"] == 2600000 and pm["addl_carry"] == 400000 and co["dep"]["total"] == 16320000, (pm, co["dep"]["total"])
    bp = next(h for h in d["heads"] if h["id"] == "BP")["net"]
    assert bp == 14380000, bp
    rows = {(r["ay"], r["kind"]): r for r in co["bfla"]}
    assert not rows[("2017-18", "business")]["ok"] and rows[("2017-18", "business")]["why"] == "lo_lapsed"
    assert rows[("2023-24", "business")]["used"] == 11000000 and rows[("2024-25", "dep")]["used"] == 3780000 and rows[("2024-25", "dep")]["left"] == 220000
    assert d["gti"] == 0 and d["income"] == 0 and co["normal"]["total"] == 0
    return f"BP {bp:,} -> GTI 0 after b/f loss 1,10,00,000 and unabsorbed depreciation 37,80,000 (2,20,000 carried)"


@step("5 Kaveri MAT: book profit 1.4 crore -> MAT 23,36,880 is the tax; the whole of it becomes a MAT credit; the old credit waits")
def _():
    d = ca.get(f"/api/compute/{S['kaveri']}/{AY}").json()
    co = d["company"]
    assert co["book_profit"] == 14000000 and co["book_from"] == "mat_rows", co["book_profit"]
    assert co["mat"]["mat"] == 2336880 and co["mat"]["pays_mat"] and co["credit_new"] == 2336880 and co["mat"]["credit_used"] == 0, co["mat"]
    assert d["tax"]["total"] == 2336880 and d["tax"]["basis"] == "mat"
    assert d["tds_total"] == 290000 and d["paid_total"] == 1900000
    ia = d["interest_auto"]
    assert ia["b"] == 0 and ia["c"] > 0, ia                          # advance tax over 90%: no 234B; short instalments: 234C
    return f"MAT {co['mat']['mat']:,} · 234B {ia['b']:,} · 234C {ia['c']:,} · {d['balance']['kind']} {d['balance']['amount']:,}"


@step("6 Kaveri ITR-6 JSON: valid; Schedule MAT / MATC, BFLA, CFL, UD, DPM with additional depreciation, the manufacturing account")
def _():
    cb = f"/api/compute/{S['kaveri']}/{AY}"
    rep = ca.get(f"{cb}/itr-check").json()
    assert rep["valid"], [f"{e['path']}: {e['message']}" for e in rep["errors"][:15]]
    assert rep["books"]["bs_diff"] == 0 and rep["books"]["pl_diff"] == 0, rep["books"]
    doc = json.loads(ca.get(f"{cb}/itr.json").content)["ITR"]["ITR6"]
    assert doc["ScheduleMAT"]["BookProfUs115JB"] == 14000000 and doc["PartB-TI"]["DeemedTotIncSec115JB"] == 14000000
    mc = doc["ScheduleMATC"]
    assert mc["MATCredGrossCurAY"] == 2336880 and mc["UtilMATCredAvl"][0]["AssYr"] == "2022-23" and mc["AmtMATLiabAllAssYrAvailSubseqYr"] == 2936880
    assert doc["ScheduleBFLA"]["TotalBFLossSetOff"]["TotBFLossSetoff"] == 11000000 and doc["ScheduleBFLA"]["TotalBFLossSetOff"]["TotUnabsorbedDeprSetoff"] == 3780000
    assert doc["ITRScheduleUD"]["ScheduleUD"][0]["BalCFNY"] == 220000
    dd = doc["ScheduleDPM"]["PlantMachinery"]["Rate15"]["DepreciationDetail"]
    assert dd["AddlnDeprOnGT180DayAdditions"] == 2000000 and dd["AddlnDeprOnLessThan180DayAdditions"] == 400000 and dd["TotalDepreciation"] == 13100000
    assert doc["ManufacturingAccount"]["CostOfGoodsPrdcd"] == 240000000 and doc["TradingAccount"]["GrossProfitFrmBusProf"] == 62000000
    tti = doc["PartB_TTI"]["ComputationOfTaxLiability"]
    assert tti["TaxPayableOnDeemedTI"]["TotalTax"] == 2336880 and tti["GrossTaxPayable"] == 2336880
    return f"valid; {rep['filled']} values; MAT credit carried {mc['AmtMATLiabAllAssYrAvailSubseqYr']:,}"


@step("7 Edge - MAT credit used: the same company with a lower book profit -> normal tax is higher, credit set off up to the difference")
def _():
    cid = S["kaveri"]
    y = demo.COMPANIES["kaveri"]["year"] | {"bf_losses": []}          # no losses left: the normal tax is due
    d = ca.put(f"/api/compute/{cid}/{AY}", json={"company": y}).json()
    co = d["company"]
    assert not co["mat"]["pays_mat"] and co["mat"]["credit_used"] == 600000, co["mat"]
    assert d["tax"]["total"] == co["normal"]["total"] - 600000 and d["tax"]["credit_used"] == 600000
    ca.put(f"/api/compute/{cid}/{AY}", json={"company": demo.COMPANIES["kaveri"]["year"]})
    return f"normal {co['normal']['total']:,} > MAT {co['mat']['mat']:,}: credit 6,00,000 of AY 2022-23 set off"


@step("8 Edge - s.79: 51% of the voting power changed -> the business loss is lost, unabsorbed depreciation is not; a late return loses its loss (s.80)")
def _():
    cid = S["kaveri"]
    y = demo.COMPANIES["kaveri"]["year"]
    co = ca.put(f"/api/compute/{cid}/{AY}", json={"company": y | {"s79_ok": False}}).json()["company"]
    rows = {(r["ay"], r["kind"]): r for r in co["bfla"]}
    assert rows[("2023-24", "business")]["why"] == "lo_s79" and rows[("2024-25", "dep")]["ok"]
    late = [r | {"filed_ok": False} if r["ay"] == "2023-24" else r for r in y["bf_losses"]]
    co = ca.put(f"/api/compute/{cid}/{AY}", json={"company": y | {"bf_losses": late}}).json()["company"]
    assert next(r for r in co["bfla"] if r["ay"] == "2023-24")["why"] == "lo_late"
    ca.put(f"/api/compute/{cid}/{AY}", json={"company": y})


@step("9 Edge - 115BAA vs normal: the same Zenith under normal provisions pays 25% x 1.07 x 1.04 and MAT is checked; turnover blank -> 30% flagged")
def _():
    cid = S["zenith"]
    c = ca.get(f"/api/clients/{cid}").json()
    body = {k: c[k] for k in ("name", "status", "pan", "gst", "email", "phone", "dob", "address", "banks", "notes", "parties")} | {"company": c["company"] | {"option": "normal"}}
    assert ca.put(f"/api/clients/{cid}", json=body).status_code == 200
    d = ca.get(f"/api/compute/{cid}/{AY}").json()
    assert d["company"]["rate"]["rate"] == 25 and d["company"]["rate"]["mat"] and d["company"]["d80g"]["total"] == 50000, d["company"]["rate"]
    ca.put(f"/api/compute/{cid}/{AY}", json={"company": demo.COMPANIES["zenith"]["year"] | {"turnover_py": 0}})
    d2 = ca.get(f"/api/compute/{cid}/{AY}").json()
    assert d2["company"]["rate"]["rate"] == 30 and "co_w_turnover" in d2["company"]["warnings"]
    ca.put(f"/api/clients/{cid}", json=body | {"company": c["company"]})
    ca.put(f"/api/compute/{cid}/{AY}", json={"company": demo.COMPANIES["zenith"]["year"]})
    assert ca.get(f"/api/compute/{cid}/{AY}").json()["tax"]["total"] == 3542400
    return f"normal: tax {d['tax']['total']:,} (80G 50,000 allowed); turnover blank: 30%"


@step("10 Edge - 234B: no advance tax paid -> 1% a month from 1 April; due date 30 Nov with Form 3CEB")
def _():
    cid = S["zenith"]
    rb = f"/api/recon/{cid}/{AY}"
    x = demo.COMPANIES["zenith"]
    no_adv = demo._26as(x["client"], x | {"paid": []})
    fid = next(f["id"] for f in ca.get(rb).json()["files"])
    ca.delete(f"{rb}/{fid}")
    assert ca.post(rb, files={"file": ("26AS no advance.txt", no_adv)}).status_code == 200
    d = ca.get(f"/api/compute/{cid}/{AY}").json()
    assert d["paid_total"] == 0 and d["interest_auto"]["b"] > 0 and d["interest_auto"]["c"] > 0, d["interest_auto"]
    ca.put(f"/api/clients/{cid}/years/{AY}", json={"tp": True})
    assert ca.get(f"/api/compute/{cid}/{AY}").json()["dates"]["due"] == 20261130
    ca.put(f"/api/clients/{cid}/years/{AY}", json={"tp": False})
    fid = next(f["id"] for f in ca.get(rb).json()["files"])
    ca.delete(f"{rb}/{fid}")
    ca.post(rb, files={"file": demo.documents("zenith")[-1]})
    for fnd in ca.get(rb).json()["findings"]:
        if fnd["severity"] == "red":
            ca.put(f"{rb}/notes/{fnd['id']}", json={"note": "explained"})
    return f"234B {d['interest_auto']['b']:,} · 234C {d['interest_auto']['c']:,}"


@step("11 Tax audit: a company's audit report is Form 3CA-3CD, Status 5")
def _():
    cid = S["kaveri"]
    ca.put(f"/api/clients/{cid}/years/{AY}", json={"audit": True})
    rep = ca.get(f"/api/compute/{cid}/{AY}/3cd-check").json()
    assert rep["form"] == "3CA", rep["form"]
    doc = json.loads(ca.get(f"/api/compute/{cid}/{AY}/3cd.json").content)
    part = next(iter(doc.values()))
    part = next(iter(part.values())) if "PartA" not in part else part
    assert part["PartA"]["Status"] == 5, part["PartA"]
    itr = ca.get(f"/api/compute/{cid}/{AY}/itr-check").json()
    assert itr["valid"], itr["errors"][:5]
    return f"3CA: {rep['error_count']} items left for the CA to fill (clauses not in the books)"


@step("12 Sign-off and file; the year closes; the computation Excel carries MAT")
def _():
    cid = S["kaveri"]
    cb = f"/api/compute/{cid}/{AY}"
    assert ca.post(f"{cb}/signoff", json={"on": True}).json()["signed"]
    fl = ca.post(f"{cb}/file", json={"ack_no": "626262626262626"}).json()
    assert fl["locked"] and fl["current"]["kind"] in ("original", "belated"), fl["current"]
    assert ca.put(cb, json={"company": demo.COMPANIES["kaveri"]["year"]}).status_code == 409, "a filed year takes no change"
    import openpyxl, io  # noqa: E401
    wb = openpyxl.load_workbook(io.BytesIO(ca.get(f"{cb}/computation.xlsx").content))
    txt = " ".join(str(c) for r in wb.active.iter_rows(values_only=True) for c in r if c)
    assert "115JB" in txt, "MAT in the computation"


@step("13 Tenant wall: another firm's partner cannot see the companies")
def _():
    admin.post("/api/users", json={"email": "other@demo.test", "password": "Other-pass-1234", "display_name": "Other"})
    o = session("other@demo.test", "Other-pass-1234")
    fid = o.post("/api/firm/start", json={"kind": "ca_firm"}).json()["id"]
    o.put("/api/firm", json={"name": "Other CA", "pan": "AAFFO1234C", "tan": "HYDO12345E", "gstin": "36AAFFO1234C1Z5", "frn": "012346S",
                             "membership_no": "212346", "owner_name": "Other", "aadhaar_last4": "1111", "phone": "9000000002",
                             "email": "other@demo.test", "address": "Hyderabad 500001", "consent": True})
    for k in ("owner_aadhaar", "pan_card", "tan_letter", "gst_cert"):
        o.post(f"/api/firm/docs/{k}", files={"file": (f"{k}.pdf", b"%PDF-1.4 demo")})
    o.post(f"/api/firm/{fid}/move", json={"action": "submit"})
    admin.post(f"/api/firm/{fid}/move", json={"action": "approve"})
    for cid in S.values():
        assert o.get(f"/api/clients/{cid}").status_code in (403, 404)
        assert o.get(f"/api/compute/{cid}/{AY}").status_code in (403, 404)
        assert o.put(f"/api/compute/{cid}/{AY}", json={"company": {}}).status_code in (403, 404)


for r in results:
    print(f"{r[0]}  {r[1]}" + (f"\n      {r[2]}" if r[2] else ""))
print(f"\n{sum(r[0] == 'PASS' for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[0] == "PASS" for r in results) else 1)
