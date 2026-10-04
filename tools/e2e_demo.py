"""python tools/e2e_demo.py

End to end, every screen, every role, on a throw-away data folder - with the demo client's files.
Portal admin -> CA firm signs up -> papers -> approval -> team -> client -> intake & map -> reconcile -> compute -> sign-off
-> file (closed) -> reopen. Each step asserts what the screen must show; prints PASS / FAIL per step."""
import io
import os
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.chdir(HERE)
os.environ["TV_DATA"] = tempfile.mkdtemp(prefix="sf-e2e-")
from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402

D = HERE / "Requirements" / "Demo E2E - Shree Ganesh Agarwal HUF"   # gitignored: the demo files stay on this PC
AY = "2026-27"
results = []


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


def stage(s):
    return next(r["stage"] for r in s.get("/api/lists/clients", params={"ay": AY}).json()["rows"] if r["id"] == S["cid"])


def session(email, pw):
    s = TestClient(app.app)
    r = s.post("/api/auth/signin", json={"identity": email, "password": pw})
    assert r.status_code == 200, r.text
    return s


admin = TestClient(app.app)
assert admin.post("/api/auth/first-account", json={"email": "admin@valuestream.test", "password": "Admin-pass-123"}).status_code == 200
admin.post("/api/users", json={"email": "pvr@pvr.test", "password": "Pvr-pass-1234", "display_name": "P V Rao"})
ca = session("pvr@pvr.test", "Pvr-pass-1234")
S = {}


@step("1 Sign-up: no firm -> Filing shut, only My firm")
def _():
    assert ca.get("/api/clients/settings").status_code == 403
    acc = ca.get("/api/bootstrap").json()["access"]
    assert acc["firm"]["allowed"] and not acc["clients"]["allowed"] and not acc["approvals"]["allowed"]
    S["fid"] = ca.post("/api/firm/start", json={"kind": "ca_firm"}).json()["id"]


@step("2 Firm details: full Aadhaar refused, bad GSTIN caught, good saved")
def _():
    good = {"name": "Prabhakar PVR & Co", "pan": "AAFFP1234C", "tan": "HYDP12345E", "gstin": "36AAFFP1234C1Z5", "frn": "012345S",
            "membership_no": "212345", "owner_name": "P V Rao", "aadhaar_last4": "4821", "phone": "+91 98490 12345",
            "email": "pvr@pvr.test", "address": "Banjara Hills, Hyderabad", "consent": True}
    assert ca.put("/api/firm", json=good | {"aadhaar_last4": "482148214821"}).status_code == 400
    assert ca.put("/api/firm", json=good | {"gstin": "36AAFFX1234C1Z5"}).json()["ready"]["say"] == "gstin_pan"
    f = ca.put("/api/firm", json=good).json()
    assert f["ready"]["say"] == "need_docs" and f["steps"]["s_details"] and not f["steps"]["s_docs"]
    return f"missing papers: {f['ready']['missing']}"


@step("3 Papers + submit; frozen while waiting")
def _():
    assert ca.post(f"/api/firm/{S['fid']}/move", json={"action": "submit"}).status_code == 400
    for k in ("owner_aadhaar", "pan_card", "tan_letter", "gst_cert"):
        assert ca.post(f"/api/firm/docs/{k}", files={"file": (f"{k}.pdf", b"%PDF-1.4 demo")}).status_code == 200
    assert ca.post(f"/api/firm/{S['fid']}/move", json={"action": "submit"}).json()["state"] == "submitted"
    assert ca.put("/api/firm", json={"name": "x"}).status_code == 409
    assert ca.get("/api/clients/settings").status_code == 403


@step("4 Portal admin: queue, papers, return with note, resubmit, approve")
def _():
    q = admin.get("/api/approvals?state=submitted").json()["rows"]
    assert len(q) == 1 and q[0]["sla"] == "on_time"
    assert admin.get(f"/api/firm/{S['fid']}/docs/{q[0]['docs'][0]['id']}").status_code == 200
    assert admin.post(f"/api/firm/{S['fid']}/move", json={"action": "return"}).status_code == 400
    assert admin.post(f"/api/firm/{S['fid']}/move", json={"action": "return", "note": "GST certificate is blurred"}).json()["state"] == "returned"
    ca.post("/api/firm/docs/gst_cert", files={"file": ("gst_clear.pdf", b"%PDF-1.4 clear")})
    assert ca.post(f"/api/firm/{S['fid']}/move", json={"action": "submit"}).json()["state"] == "submitted"
    f = admin.post(f"/api/firm/{S['fid']}/move", json={"action": "approve"}).json()
    assert f["state"] == "approved"
    assert ca.get("/api/firm").json()["firm"]["steps"]["s_approved"]


@step("5 Team: partner + preparer added with one-time passwords")
def _():
    for email, role in (("partner@pvr.test", "partner"), ("ravi@pvr.test", "preparer")):
        r = ca.post("/api/firm/team", json={"name": email.split("@")[0], "email": email, "role": role}).json()
        s = TestClient(app.app)
        s.post("/api/auth/signin", json={"identity": email, "password": r["password"]})
        assert s.get("/api/clients/settings").status_code == 403, "must change the one-time password first"
        assert s.post("/api/auth/password", json={"current": r["password"], "password": f"{role}-own-Pass-9", "confirm": f"{role}-own-Pass-9"}).status_code == 200
        S[role] = s
    return f"team: {[m['role'] for m in ca.get('/api/firm').json()['team']]}"


@step("6 Clients: preparer adds the HUF; admin cannot see it")
def _():
    p = S["preparer"]
    cl = p.post("/api/clients", json={"name": "Shree Ganesh Agarwal HUF", "relation": "Ganesh Prasad Agarwal (Karta)", "status": "huf",
                                      "pan": "AAAHG4321K", "gst": "36AAAHG4321K1Z8", "email": "ganesh.agarwal.huf@example.com"}).json()
    S["cid"] = cl["id"]
    assert p.put(f"/api/clients/{cl['id']}/years/{AY}", json={"form": "ITR-3", "audit": True}).status_code == 200
    assert admin.get(f"/api/clients/{cl['id']}").status_code == 404
    assert p.post(f"/api/clients/{cl['id']}/archive", json={"archived": True}).status_code == 403, "preparer cannot archive"


@step("7 Intake: upload statement, headings, amount column, totals add up")
def _():
    p, ib = S["preparer"], f"/api/intake/{S['cid']}/{AY}"
    f = p.post(ib, files={"file": ("02 Client statement.xlsx", (D / "02 Client statement - IT Stmt, Dep & Loans AY 2026-27.xlsx").read_bytes())}).json()
    S["file"] = f["id"]
    v = p.get(f"{ib}/{f['id']}").json()
    g = {x["heading"][:30]: x for x in v["groups"]}
    assert "TOTAL INCOME STATEMENT" in g, list(g)
    ti = g["TOTAL INCOME STATEMENT"]
    assert ti["net"] == 20736500 and ti["stated"] == 20736500 and ti["agrees"], ti
    dep = next(x for k, x in g.items() if k.startswith("Statement regarding deprec"))
    assert dep["net"] == 2130000, dep
    loans = next(x for k, x in g.items() if k.startswith("Statement of loans"))
    assert loans["net"] == 8000000, loans
    tds = next(x for k, x in g.items() if k.startswith("Less: TDS"))
    return f"groups: " + "; ".join(f"{x['heading'][:28]}={x['net']:,.0f}" + (f" (stated {x['stated']:,.0f} {'ok' if x['agrees'] else 'DIFF'})" if x['stated'] is not None else "") for x in v["groups"]) + f" | TDS+adv {tds['net']:,.0f}"


@step("8 Map: accept suggestions, type the one left, all tagged")
def _():
    p, ib = S["preparer"], f"/api/intake/{S['cid']}/{AY}"
    v = p.post(f"{ib}/{S['file']}/accept").json()
    left = {x["key"]: "ITR3 BP" for x in v["rows"] if x["state"] == "untagged" and "40(a)" in x["label"]}
    v = p.put(f"{ib}/{S['file']}/tags", json={"tags": left}).json()
    open_ = [x["label"] for x in v["rows"] if x["state"] in ("untagged", "invalid")]
    assert not open_, open_
    return f"counts {v['counts']}"


@step("9 Reconcile: 26AS + AIS + TIS -> 1 red (Lakshmi); stage moves by itself to Review once explained")
def _():
    p, rb = S["preparer"], f"/api/recon/{S['cid']}/{AY}"
    for name in ("03 26AS - AAAHG4321K - AY 2026-27.txt", "04 AIS - AAAHG4321K - FY 2025-26.csv", "05 TIS - AAAHG4321K - FY 2025-26.csv"):
        assert p.post(rb, files={"file": (name, (D / name).read_bytes())}).status_code == 200, name
    d = p.get(rb).json()
    reds = [x for x in d["findings"] if x["severity"] == "red"]
    assert d["summary"]["red"] == 1 and "LAKSHMI" in reds[0]["title"].upper(), d["summary"]
    assert stage(p) == "reconciling", "the red keeps it in Reconciling, by itself"
    p.put(f"{rb}/notes/{reds[0]['id']}", json={"note": "Deductor revised TDS return to 36,000; credit as per 26AS."})
    assert stage(p) == "review", "explained -> Review, nobody picked it"
    return f"summary {d['summary']}"


@step("10 Compute: income 2,07,36,500  tax 74,39,640  TDS 3,06,000  paid 72,00,000  refund 66,360")
def _():
    k = S["preparer"].get(f"/api/compute/{S['cid']}/{AY}").json()
    assert k["income"] == 20736500, k["income"]
    assert k["tax"]["total"] == 7439640, k["tax"]
    assert k["tds_total"] == 306000 and k["paid_total"] == 7200000, (k["tds_total"], k["paid_total"])
    assert k["balance"]["kind"] == "refund" and k["balance"]["amount"] == 66360, k["balance"]
    for part in ("computation.xlsx", "utility.zip", "3cd.xlsx"):
        assert S["preparer"].get(f"/api/compute/{S['cid']}/{AY}/{part}").status_code == 200
    z = zipfile.ZipFile(io.BytesIO(S["preparer"].get(f"/api/compute/{S['cid']}/{AY}/utility.zip").content))
    return f"utility zip: {z.namelist()}"


@step("11 3CD schedule: clause 18 carries the depreciation, not the opening WDV")
def _():
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(S["preparer"].get(f"/api/compute/{S['cid']}/{AY}/3cd.xlsx").content), data_only=True)
    rows = [r for r in wb.active.iter_rows(values_only=True) if r and str(r[0] or "").strip().startswith("18")]
    amts = [r[-1] if isinstance(r[-1], (int, float)) else next((v for v in reversed(r) if isinstance(v, (int, float))), None) for r in rows]
    assert sum(a for a in amts if a) == 2130000, rows
    return f"clause 18 rows: {len(rows)}, total {sum(a for a in amts if a):,.0f}"


@step("12 Sign-off: preparer refused (no button), partner signs")
def _():
    cb = f"/api/compute/{S['cid']}/{AY}"
    assert S["preparer"].post(f"{cb}/signoff", json={"on": True}).status_code == 403
    assert not S["preparer"].get("/api/bootstrap").json()["access"]["compute"]["functions"]["signoff"]
    assert S["partner"].post(f"{cb}/signoff", json={"on": True}).json()["signed"]


@step("13 File today (audit case: due 31 Oct): original / belated by the dates, closed, writes refused")
def _():
    cb, ib = f"/api/compute/{S['cid']}/{AY}", f"/api/intake/{S['cid']}/{AY}"
    assert stage(S["partner"]) == "signed"
    assert S["partner"].post(f"{cb}/file", json={"ack_no": "4567"}).status_code == 409, "15-digit ack"
    assert S["partner"].post(f"{cb}/file", json={"ack_no": "456789012345678", "filed_on": "2099-01-01"}).status_code == 409, "not in the future"
    fl = S["partner"].post(f"{cb}/file", json={"ack_no": "456789012345678"}).json()
    assert fl["locked"] and all(fl["steps"].values()) and fl["current"]["kind"] in ("original", "belated", "updated"), fl["current"]
    assert stage(S["partner"]) == "filed"
    assert S["preparer"].post(ib, files={"file": ("more.csv", b"a,1")}).status_code == 409
    return f"due {fl['dates']['due']} · revise by {fl['dates']['revise_by']} · ITR-U by {fl['dates']['updated_by']}"


@step("14 Revised return u/s 139(5) (ITR-U after 31 Dec): preparer refused; partner opens, re-uploads statement (replace), files revised")
def _():
    cb, ib = f"/api/compute/{S['cid']}/{AY}", f"/api/intake/{S['cid']}/{AY}"
    assert S["preparer"].post(f"{cb}/revise").status_code == 403
    rv = S["partner"].post(f"{cb}/revise").json()
    assert rv["revising"] and not rv["locked"] and not rv["signed"]
    data = (D / "02 Client statement - IT Stmt, Dep & Loans AY 2026-27.xlsx").read_bytes()
    dup = S["preparer"].post(ib, files={"file": ("02 Client statement.xlsx", data)})
    assert dup.status_code == 409 and dup.json()["detail"]["replace"] == S["file"], "same statement -> offered as a replacement"
    rep = S["preparer"].post(f"{ib}?replace={S['file']}", files={"file": ("02 Client statement.xlsx", data)}).json()
    assert rep["id"] == S["file"] and rep["counts"]["tagged"] == rep["counts"]["rows"], "refs kept on unchanged rows"
    S["partner"].post(f"{cb}/signoff", json={"on": True})
    fl = S["partner"].post(f"{cb}/file", json={"ack_no": "456789012345679"}).json()
    assert fl["current"]["kind"] in ("revised", "updated") and fl["current"]["revises"] == "456789012345678"
    assert [f["status"] for f in fl["filings"]] == ["superseded", "current"]


@step("14b Undo a wrong 'filed' (reason needed): revised withdrawn, original stands again, revision open; discard closes")
def _():
    cb = f"/api/compute/{S['cid']}/{AY}"
    assert S["partner"].post(f"{cb}/withdraw", json={}).status_code == 409
    wd = S["partner"].post(f"{cb}/withdraw", json={"note": "Ack typed wrong"}).json()
    assert wd["revising"] and wd["current"]["ack_no"] == "456789012345678" and wd["filings"][-1]["status"] == "withdrawn"
    dc = S["partner"].post(f"{cb}/discard").json()
    assert dc["locked"] and stage(S["partner"]) == "filed"


@step("15 Self-filer: the HUF signs up on its own, one client = itself")
def _():
    admin.post("/api/users", json={"email": "ganesh@huf.test", "password": "Ganesh-pass-12", "display_name": "Ganesh"})
    g = session("ganesh@huf.test", "Ganesh-pass-12")
    fid = g.post("/api/firm/start", json={"kind": "self"}).json()["id"]
    g.put("/api/firm", json={"name": "Shree Ganesh Agarwal HUF", "pan": "AAAHG4321K", "owner_name": "Ganesh Prasad Agarwal",
                             "aadhaar_last4": "1111", "phone": "9800012345", "email": "ganesh@huf.test", "consent": True})
    for k in ("owner_aadhaar", "pan_card"):
        g.post(f"/api/firm/docs/{k}", files={"file": (f"{k}.jpg", b"jpg")})
    g.post(f"/api/firm/{fid}/move", json={"action": "submit"})
    admin.post(f"/api/firm/{fid}/move", json={"action": "approve"})
    rows = g.get("/api/lists/clients").json()["rows"]
    assert [r["pan"] for r in rows] == ["AAAHG4321K"], rows
    assert g.post("/api/clients", json={"name": "Other", "status": "individual", "pan": "ABCPX1234K"}).status_code == 409
    assert S["preparer"].get(f"/api/clients/{rows[0]['id']}").status_code == 404, "the CA firm cannot see the self-filer"


@step("16 Suspend: firm's Filing shuts at once")
def _():
    admin.post(f"/api/firm/{S['fid']}/move", json={"action": "suspend", "note": "KYC expired"})
    assert S["partner"].get(f"/api/compute/{S['cid']}/{AY}").status_code == 403
    admin.post(f"/api/firm/{S['fid']}/move", json={"action": "restore"})
    assert S["partner"].get(f"/api/compute/{S['cid']}/{AY}").status_code == 200


@step("16b 234A/B/C by itself: demo paid advance tax in time -> nil; override and clear")
def _():
    p, cb = S["partner"], f"/api/compute/{S['cid']}/{AY}"
    d = p.get(cb).json()
    assert d["interest_auto"]["total"] == 0 and d["interest"] == 0 and d["balance"]["amount"] == 66360, d["interest_auto"]
    assert d["refund_interest"]["say"] == "r_small", "66,360 is under 10% of the tax: no 244A interest"
    r = p.put(cb, json={"refund_on": "2026-12-15"}).json()      # allowed on a filed year: the refund comes after filing
    assert r["refund_interest"]["to"] == 20261215
    return f"234A {d['interest_auto']['a']} · 234B {d['interest_auto']['b']} · 234C {d['interest_auto']['c']}"


@step("16c ITR-3 JSON in the CBDT format: fits the official schema; figures, codes, TDS, challans, balance sheet and P&L in place")
def _():
    p, cb = S["partner"], f"/api/compute/{S['cid']}/{AY}"
    c = p.get(f"/api/clients/{S['cid']}").json()
    body = {k: c.get(k) for k in ("name", "relation", "status", "pan", "gst", "email", "address", "banks", "partners", "notes", "dob", "nri")}
    body |= {"phone": "9800012345", "father": "Ram Prasad Agarwal", "signer_pan": "ABCPA1234D", "dob": "1998-04-15",
             "address": "8-2-293/A, Road No. 12, Banjara Hills, Hyderabad 500034"}
    assert p.put(f"/api/clients/{S['cid']}", json=body).status_code == 200
    rev = p.post(f"{cb}/revise").json() if p.get(cb).json()["locked"] else None   # a filed year takes no new statement: revise
    up = p.post(f"/api/intake/{S['cid']}/{AY}", files={"file": ("books.xlsx", (D / "10 Client books - Trading, P&L and Balance Sheet AY 2026-27.xlsx").read_bytes())}).json()
    assert up["counts"]["tagged"] == 33, up["counts"]
    rep = p.get(f"{cb}/itr-check").json()
    assert rep["valid"], rep["errors"][:5]
    b = rep["books"]
    assert b["items"] == 33 and b["bs_diff"] == 0 and b["bs_sources"] == 37750000 and b["pl_diff"] == 0, b
    if rev:
        p.post(f"{cb}/discard")
    import json as _j
    doc = _j.loads(p.get(f"{cb}/itr.json").content)["ITR"]["ITR3"]
    assert doc["PartB-TI"]["TotalIncome"] == 20736500 and doc["PartB_TTI"]["Refund"]["RefundDue"] == 66360
    assert {t["TDSSection"] for t in doc["ScheduleTDS2"]["TDSOthThanSalaryDtls"]} == {"94A", "4-IB"}
    assert len(doc["ScheduleIT"]["TaxPayment"]) == 4 and doc["PartA_GEN1"]["FilingStatus"]["ItrFilingDueDate"] == "2026-10-31"
    assert doc["PartA_GEN2"]["AuditInfo"]["LiableSec44ABflg"] == "Y" and doc["Verification"]["Capacity"] == "K"
    return f"valid against {rep['schema']}, {rep['filled']} values placed; BS tallies {b['bs_sources']:,.0f}, P&L PBT = business profit {b['pl_profit']:,.0f}"


@step("16e Form 3CB-3CD JSON in the CBDT format: Part A, the CA firm as auditor, clauses 18 / 31(a) / 31(b)")
def _():
    p, cb = S["partner"], f"/api/compute/{S['cid']}/{AY}"
    rep = p.get(f"{cb}/3cd-check").json()
    import json as _j
    doc = _j.loads(p.get(f"{cb}/3cd.json").content)["FORM3CB"]["F3CB"]
    S["3cd"] = (rep, doc)
    assert rep["valid"], [f"{e['path']}: {e['message']}" for e in rep["errors"][:12]]
    assert doc["OtherInformation1"]["MembershipNo"] == "212345" and doc["OtherInformation1"]["FirmRegNum"] == "012345S"
    assert len(doc["Form3cdDeprAllw"]) == 4 and sum(x["DepAllowable"] for x in doc["Form3cdDeprAllw"]) == 2130000
    assert {x["DescBlockAssets"] for x in doc["Form3cdDeprAllw"]} == {"1", "11", "3"}
    assert len(doc["Form3cdAmtSec269ssDetail"]) == 3 and sum(x["AmtLoanDeposit"] for x in doc["Form3cdAmtSec269ssDetail"]) == 8000000
    assert len(doc["Form3cdAmtSec269tDetail"]) == 2 and doc["PartA"]["Status"] == 2
    return f"valid against {rep['schema']}, {rep['filled']} values placed"


@step("16d Auto-suggest: the final accounts without any SF Ref -> every row gets the right BS / PL item")
def _():
    import openpyxl
    src = openpyxl.load_workbook(D / "10 Client books - Trading, P&L and Balance Sheet AY 2026-27.xlsx")
    want = {}
    wb = openpyxl.Workbook(); ws = wb.active
    for r in src.active.iter_rows(values_only=True):
        ws.append([r[0], r[1]])
        if r[1] and isinstance(r[1], (int, float)):
            want[ws.max_row] = r[2]
    buf = io.BytesIO(); wb.save(buf)
    p = S["partner"]
    cl = p.post("/api/clients", json={"name": "Agarwal Traders Books Test", "status": "individual", "pan": "ABCPT1234K"}).json()
    p.put(f"/api/clients/{cl['id']}/years/{AY}", json={"form": "ITR-3"})
    ib = f"/api/intake/{cl['id']}/{AY}"
    f = p.post(ib, files={"file": ("books-no-refs.xlsx", buf.getvalue())}).json()
    v = p.get(f"{ib}/{f['id']}").json()
    got = {x["row"]: x["suggestion"] for x in v["rows"]}
    wrong = {r: (want[r], got.get(r)) for r in want if got.get(r) != want[r]}
    assert not wrong, wrong
    return f"{len(want)}/{len(want)} rows suggested right"


@step("17 Form 3CEB: transfer pricing moves the due date to 30 Nov")
def _():
    p = S["partner"]
    p.put(f"/api/clients/{S['cid']}/years/{AY}", json={"tp": True})
    d = p.get(f"/api/compute/{S['cid']}/{AY}").json()["dates"]
    assert d["due"] == int(AY[:4]) * 10000 + 1130, d
    p.put(f"/api/clients/{S['cid']}/years/{AY}", json={"tp": False})
    return f"due {d['due']}"


@step("18 ITR-U (AY 2025-26 slabs, past 31 Dec 2025): more tax -> confirmation -> filed with 140B additional tax")
def _():
    p, ay = S["partner"], "2025-26"
    p.put(f"/api/clients/{S['cid']}/years/{ay}", json={"form": "ITR-3", "audit": True})
    ib, rb, cb = f"/api/intake/{S['cid']}/{ay}", f"/api/recon/{S['cid']}/{ay}", f"/api/compute/{S['cid']}/{ay}"
    f = p.post(ib, files={"file": ("statement.xlsx", (D / "02 Client statement - IT Stmt, Dep & Loans AY 2026-27.xlsx").read_bytes())}).json()
    v = p.post(f"{ib}/{f['id']}/accept").json()
    p.put(f"{ib}/{f['id']}/tags", json={"tags": {x["key"]: "ITR3 BP" for x in v["rows"] if x["state"] == "untagged"}})
    p.post(rb, files={"file": ("26as.txt", (D / "03 26AS - AAAHG4321K - AY 2026-27.txt").read_bytes())})
    for x in p.get(rb).json()["findings"]:
        if x["severity"] == "red":
            p.put(f"{rb}/notes/{x['id']}", json={"note": "explained"})
    d = p.get(cb).json()
    assert d["interest_auto"]["total"] > 0 and d["interest_auto"]["a"] > 0, "late, unpaid by the due date: 234A/B/C by itself"
    p.post(f"{cb}/signoff", json={"on": True})                # AY 2025-26 slabs (Finance Act 2024): more tax to pay -> ITR-U allowed
    d = p.get(cb).json()
    assert d["dates"]["kind"] == "updated" and d["itr_u"], (d["dates"], d["itr_u"])
    assert d["itr_u"]["ok"] and d["itr_u"]["pct"] == 25, d["itr_u"]
    assert p.post(f"{cb}/file", json={"ack_no": "111122223333444"}).status_code == 409, "the confirmation is needed"
    fl = p.post(f"{cb}/file", json={"ack_no": "111122223333444", "itru_confirm": True}).json()
    assert fl["current"]["kind"] == "updated" and fl["current"]["itr_u"]["additional"] == d["itr_u"]["additional"]
    return f"further tax {d['itr_u']['extra']:,.0f} -> 140B @ {d['itr_u']['pct']}% = {d['itr_u']['additional']:,.0f}"


@step("19 s.207(2): resident individual aged 60+ with no business income -> no 234B/C (234A stays); under 60 -> charged")
def _():
    import openpyxl
    p, ay = S["partner"], "2025-26"
    sen = p.post("/api/clients", json={"name": "Ramesh Senior", "status": "individual", "pan": "ABCPR1234K", "dob": "1958-06-10"}).json()
    assert p.post("/api/clients", json={"name": "X", "status": "individual", "pan": "ABCPX1234K", "dob": "10/06/1958"}).status_code == 400
    p.put(f"/api/clients/{sen['id']}/years/{ay}", json={"form": "ITR-2"})
    wb = openpyxl.Workbook()
    for row in [["", "TOTAL INCOME STATEMENT"], ["", "Interest on FD with HDFC Bank", "", 4000000], ["", "Interest on SB a/c", "", 50000]]:
        wb.active.append(row)
    buf = io.BytesIO(); wb.save(buf)
    ib, rb, cb = f"/api/intake/{sen['id']}/{ay}", f"/api/recon/{sen['id']}/{ay}", f"/api/compute/{sen['id']}/{ay}"
    f = p.post(ib, files={"file": ("fd.xlsx", buf.getvalue())}).json()
    p.post(f"{ib}/{f['id']}/accept")
    p.post(rb, files={"file": ("26as.txt", (D / "03 26AS - AAAHG4321K - AY 2026-27.txt").read_bytes())})
    d = p.get(cb).json()
    ia = d["interest_auto"]
    assert ia["exempt"] and ia["b"] == 0 and ia["c"] == 0, ia
    p.put(f"/api/clients/{sen['id']}", json={"name": "Ramesh Senior", "status": "individual", "pan": "ABCPR1234K", "dob": "1968-06-10"})
    young = p.get(cb).json()["interest_auto"]
    assert not young["exempt"], "59: not a senior citizen"
    return f"senior: 234A {ia['a']:,} 234B 0 234C 0 | at 57: 234B {young['b']:,} 234C {young['c']:,}"


for r in results:
    print(f"{r[0]}  {r[1]}" + (f"\n      {r[2]}" if r[2] else ""))
print(f"\n{sum(r[0] == 'PASS' for r in results)}/{len(results)} passed")
