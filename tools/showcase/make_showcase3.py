"""Ten dummy ITR JSONs over the last three years (AY 2023-24 to 2025-26), made by SimplyFile's own CBDT exporter in a
throw-away portal - then scenarios C16-C25 driven through Import old returns -> showcase3_expected.json."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import os
import runpy
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
g = runpy.run_path(str(HERE / "make_showcase.py"))
book, s26, head, OUT = g["book"], g["s26"], g["head"], g["OUT"]
DUMMY = OUT / "D Old returns - dummy ITR JSON (AY 2023-24 to 2025-26)"
DUMMY.mkdir(exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix="sf-itr-src-"))
HDR = ("", "TOTAL INCOME STATEMENT", "", "Amount (Rs)", "SF Ref")
sys.path.insert(0, _R + r"")
os.chdir(_R + r"")
os.environ["TV_DATA"] = tempfile.mkdtemp(prefix="sf-show3-")
from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402
import itr_json  # noqa: E402

adm = TestClient(app.app)
adm.post("/api/auth/first-account", json={"email": "admin@valuestream.test", "password": "Admin-pass-123"})
PAPERS = OUT / "A Firm papers - placeholders"


def firm(email, name, pan):
    adm.post("/api/users", json={"email": email, "password": "Firm-pass-123", "display_name": name})
    c = TestClient(app.app)
    c.post("/api/auth/signin", json={"identity": email, "password": "Firm-pass-123"})
    fid = c.post("/api/firm/start", json={"kind": "ca_firm"}).json()["id"]
    c.put("/api/firm", json={"name": name, "pan": pan, "tan": "HYDP12345E", "gstin": f"36{pan}1Z5", "frn": "012345S", "membership_no": "212345",
                             "owner_name": "Demo Partner", "aadhaar_last4": "4821", "phone": "9000000001", "email": email, "address": "Hyderabad", "consent": True})
    for k, f in [("owner_aadhaar", "1"), ("pan_card", "2"), ("tan_letter", "3"), ("gst_cert", "4")]:
        p = next(PAPERS.glob(f"{f} *.pdf"))
        c.post(f"/api/firm/docs/{k}", files={"file": (p.name, p.read_bytes())})
    c.post(f"/api/firm/{fid}/move", json={"action": "submit"})
    assert adm.post(f"/api/firm/{fid}/move", json={"action": "approve"}).json()["state"] == "approved"
    return c


def ok(r):
    assert r.status_code == 200, r.text[:500]
    return r.json()


SRC = firm("maker@example.com", "Return Maker & Co", "AAFFR1234C")        # makes the dummy returns
SRC2 = firm("maker2@example.com", "Return Maker Two", "AAFFR5678C")       # the revised return of the same PAN


def make_return(c, n, client, ay, rows, deductors, challans, filed_on, ack, fname, edit=None):
    """A client-year in the throw-away portal, filed on `filed_on`, exported as the CBDT ITR JSON."""
    cid = ok(c.post("/api/clients", json=client | {"ay": ay}))["id"]
    ok(c.put(f"/api/clients/{cid}/years/{ay}", json={"form": "ITR-5" if client["status"] in ("firm", "llp") else "ITR-3", "audit": client["pan"] in ("AAAHG4321K", "AAFFS4721M")}))
    x = WORK / f"{n}.xlsx"
    book(x, {"IT Statement": head(client["name"], client["pan"], ay) + [HDR] + rows})
    f = ok(c.post(f"/api/intake/{cid}/{ay}", files={"file": (x.name, x.read_bytes())}))
    ok(c.post(f"/api/intake/{cid}/{ay}/{f['id']}/accept"))
    t = WORK / f"{n}.txt"
    fy = f"{int(ay[:4]) - 1}-{ay[2:4]}"
    s26(t, client["pan"], client["name"], fy, ay, deductors, challans)
    ok(c.post(f"/api/recon/{cid}/{ay}", files={"file": (t.name, t.read_bytes())}))
    for r in ok(c.get(f"/api/recon/{cid}/{ay}"))["findings"]:
        if r["severity"] == "red":
            ok(c.put(f"/api/recon/{cid}/{ay}/notes/{r['id']}", json={"note": "Checked."}))
    ok(c.post(f"/api/compute/{cid}/{ay}/signoff", json={"on": True}))
    kind = ok(c.post(f"/api/compute/{cid}/{ay}/file", json={"ack_no": ack, "filed_on": filed_on}))["current"]["kind"]
    doc, rep = itr_json.build(cid, ay)
    if edit:
        edit(doc)
    (DUMMY / fname).write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    k = ok(c.get(f"/api/compute/{cid}/{ay}"))
    return {"file": fname, "kind": kind, "income": k["income"], "tax": k["tax"]["total"], "balance": k["balance"], "valid": rep["valid"]}


def p(name, pan, status="individual", **kw):
    return {"name": name, "pan": pan, "status": status, "dob": kw.pop("dob", "1980-01-01"), "father": kw.pop("father", "-"),
            "email": kw.pop("email", f"{name.split()[0].lower()}@example.com"), "phone": kw.pop("phone", "9800000000"),
            "address": kw.pop("address", "Hyderabad 500001"),
            "banks": [{"bank": "State Bank of India", "branch": "Main", "type": "Savings", "account": "30123456789", "ifsc": "SBIN0000001"}]} | kw


BP = lambda v: [("", "Income from business"), ("", "Net profit as per Profit & Loss account", "", v)]  # noqa: E731
OS = lambda v, bank="State Bank of India": [("", "Income from other sources"), ("", f"Interest on FD with {bank}", "", v)]  # noqa: E731
HP = lambda rent, who: [("", "Income from house property"), ("", f"Rent received from {who}", "", rent), ("", "Less: Standard deduction @ 30%", "", round(rent * 0.3))]  # noqa: E731
TDS = lambda *pairs: [(), ("", "Less: TDS as per certificates from")] + [("", w, "", v) for w, v in pairs]  # noqa: E731

R = {}
agarwal = p("Shree Ganesh Agarwal HUF", "AAAHG4321K", "huf", dob="1998-04-15", father="Ram Prasad Agarwal", signer_pan="ABCPA1234D",
            relation="Ganesh Prasad Agarwal", address="8-2-293/A, Road No. 12, Banjara Hills, Hyderabad 500034")
R[1] = make_return(SRC, 1, agarwal, "2025-26", BP(14000000) + HP(2200000, "Bright Retail Pvt Ltd") + OS(600000, "HDFC Bank") + TDS(("HDFC Bank", 60000), ("Bright Retail Pvt Ltd", 220000)),
                   [("HDFC Bank Limited", "HYDH01234A", "194A", 600000, 60000, "31-Mar-2025"), ("Bright Retail Private Limited", "HYDB05678B", "194I", 2200000, 220000, "31-Mar-2025")],
                   [(100, 1000000, "15-Jun-2024", 11), (100, 1500000, "15-Sep-2024", 12), (100, 1500000, "15-Dec-2024", 13), (100, 1200000, "15-Mar-2025", 14)],
                   "2025-10-28", "512345678901234", "01 ITR-3 AY 2025-26 - Shree Ganesh Agarwal HUF - AAAHG4321K.json")
kiran = p("Kiran Kumar Rao", "BKRPR4417H", dob="1988-11-23", father="Mohan Rao", address="Flat 402, Aditya Enclave, Kondapur, Hyderabad 500084")
R[2] = make_return(SRC, 2, kiran, "2023-24", [("", "Income from profession"), ("", "Net profit as per Profit & Loss account", "", 600000)] + OS(10000, "ICICI Bank") +
                   TDS(("Nova Software Pvt Ltd", 60000)), [("Nova Software Private Limited", "HYDN11223A", "194J", 600000, 60000, "31-Mar-2023")], [],
                   "2023-07-24", "312345678901234", "02 ITR-3 AY 2023-24 - Kiran Kumar Rao - BKRPR4417H.json")
SRC_K2 = firm("maker3@example.com", "Return Maker Three", "AAFFR9012C")
R[3] = make_return(SRC_K2, 3, kiran, "2024-25", [("", "Income from profession"), ("", "Net profit as per Profit & Loss account", "", 740000)] + OS(10000, "ICICI Bank") +
                   TDS(("Nova Software Pvt Ltd", 74000)), [("Nova Software Private Limited", "HYDN11223A", "194J", 740000, 74000, "31-Mar-2024")], [],
                   "2024-07-22", "412345678901234", "03 ITR-3 AY 2024-25 - Kiran Kumar Rao - BKRPR4417H.json")
svt = p("Sri Venkateswara Traders", "AAFFS4721M", "firm", dob="2012-04-01", father="Narasimha Rao", signer_pan="ABCPV1234E",
        relation="Venkata Rao (managing partner)", address="12-2-718, Mehdipatnam, Hyderabad 500028",
        partners=[{"name": "Venkata Rao", "pan": "ABCPV1234E", "share": "50"}, {"name": "Srinivas Rao", "pan": "ABCPS5678F", "share": "50"}])
R[4] = make_return(SRC, 4, svt, "2025-26", BP(5900000) + OS(100000) + TDS(("State Bank of India", 10000), ("Krishna Constructions Pvt Ltd", 80000)),
                   [("State Bank of India", "HYDS12345F", "194A", 100000, 10000, "31-Mar-2025"), ("Krishna Constructions Private Limited", "HYDK67890G", "194C", 4000000, 80000, "31-Mar-2025")],
                   [(100, 300000, "15-Jun-2024", 21), (100, 500000, "15-Sep-2024", 22), (100, 500000, "15-Dec-2024", 23), (100, 520000, "15-Mar-2025", 24)],
                   "2025-10-30", "522345678901234", "04 ITR-5 AY 2025-26 - Sri Venkateswara Traders - AAFFS4721M.json")
lnt = p("Lakshmi Narayana Textiles", "AAGFL5512K", "firm", dob="2015-06-01", father="Narayana Murthy", signer_pan="ACBPM2211L",
        relation="Satya Murthy (managing partner)", address="Shop 14, Begum Bazar, Hyderabad 500012", email="accounts@lntextiles.example.com",
        partners=[{"name": "Satya Murthy", "pan": "ACBPM2211L", "share": "60"}, {"name": "Lakshmi Murthy", "pan": "ACBPM3322M", "share": "40"}])
R[5] = make_return(SRC, 5, lnt, "2025-26", BP(2400000) + OS(60000, "Canara Bank") + TDS(("Canara Bank", 6000)),
                   [("Canara Bank", "HYDC01122N", "194A", 60000, 6000, "31-Mar-2025")],
                   [(100, 120000, "15-Jun-2024", 31), (100, 220000, "15-Sep-2024", 32), (100, 220000, "15-Dec-2024", 33), (100, 182000, "15-Mar-2025", 34)],
                   "2025-07-29", "532345678901234", "05 ITR-5 AY 2025-26 - Lakshmi Narayana Textiles - AAGFL5512K.json")
ravi = p("Ravi Teja", "BRTPT6620Q", dob="1990-02-02", father="Subba Rao", address="Plot 7, Dwarakanagar, Visakhapatnam 530016")
R[6] = make_return(SRC, 6, ravi, "2023-24", BP(820000) + OS(25000) + TDS(("Vizag Steel Traders", 16400)),
                   [("Vizag Steel Traders", "VPNV04455P", "194C", 820000, 16400, "31-Mar-2023")], [(300, 30000, "20-Jul-2023", 41)],
                   "2023-07-26", "342345678901234", "06 ITR-3 AY 2023-24 - Ravi Teja - BRTPT6620Q.json")
sunita = p("Sunita Rao", "CSRPR7731B", dob="1984-09-14", father="Ramachandra Rao", address="21, Banjara Green Colony, Hyderabad 500034")
R[7] = make_return(SRC, 7, sunita, "2025-26", HP(480000, "Little Stars Play School") + OS(500000, "Axis Bank") + TDS(("Axis Bank", 50000), ("Little Stars Play School", 48000)),
                   [("Axis Bank Limited", "HYDA03344Q", "194A", 500000, 50000, "31-Mar-2025"), ("Little Stars Play School", "HYDL05566R", "194I", 480000, 48000, "31-Mar-2025")], [],
                   "2025-07-20", "552345678901234", "07 ITR-3 AY 2025-26 - Sunita Rao - CSRPR7731B (original).json")


def revised(doc):           # the same person's revised return: section 17, pointing at the original's receipt
    fs = doc["ITR"]["ITR3"]["PartA_GEN1"]["FilingStatus"]
    fs["ReturnFileSec"] = 17
    fs["ReceiptNo"], fs["OrigRetFiledDate"] = "552345678901234", "2025-07-20"


R[8] = make_return(SRC2, 8, sunita, "2025-26", HP(480000, "Little Stars Play School") + OS(500000, "Axis Bank") +
                   [("", "Interest on FD with IDFC First Bank (found in AIS)", "", 150000)] + TDS(("Axis Bank", 50000), ("Little Stars Play School", 48000)),
                   [("Axis Bank Limited", "HYDA03344Q", "194A", 500000, 50000, "31-Mar-2025"), ("Little Stars Play School", "HYDL05566R", "194I", 480000, 48000, "31-Mar-2025")],
                   [(300, 32000, "18-Nov-2025", 81)], "2025-11-20", "552345678909999", "08 ITR-3 AY 2025-26 - Sunita Rao - CSRPR7731B (revised).json", edit=revised)
irfan = p("Mohammed Irfan", "AMIPI8842C", dob="1987-12-01", father="Mohammed Yusuf", address="16-4-210, Chanchalguda, Hyderabad 500024")
R[9] = make_return(SRC, 9, irfan, "2024-25", BP(1150000) + OS(40000) + TDS(("Deccan Logistics Pvt Ltd", 23000)),
                   [("Deccan Logistics Private Limited", "HYDD06677S", "194C", 1150000, 23000, "31-Mar-2024")], [(300, 50000, "12-Nov-2024", 91)],
                   "2024-11-15", "462345678901234", "09 ITR-3 AY 2024-25 - Mohammed Irfan - AMIPI8842C (belated).json")
deepa = p("Deepa Krishnan", "BDKPK9953D", dob="1986-05-25", father="Krishnan Nair", nri=True, address="12 Orchard Road, #08-02, Singapore 238838")
R[10] = make_return(SRC, 10, deepa, "2025-26", HP(600000, "Kochi Diagnostics") + OS(300000, "Federal Bank NRO") + TDS(("Kochi Diagnostics", 180000), ("Federal Bank", 90000)),
                    [("Kochi Diagnostics", "CHNK07788T", "195", 600000, 180000, "31-Mar-2025"), ("Federal Bank Limited", "CHNF01234E", "195", 300000, 90000, "31-Mar-2025")], [],
                    "2025-07-25", "562345678901234", "10 ITR-3 AY 2025-26 - Deepa Krishnan - BDKPK9953D (NRI).json")
for k, v in R.items():
    print(k, v)

# --- the firm side: Demo CA Filing Firm with its clients as they stand, then C16-C25 through Import old returns ---------------------
c = firm("demo@valuestream.in", "Demo CA Filing Firm", "AAFFP1234C")
ex = {}
for who, ay in [(agarwal, "2026-27"), (kiran, "2026-27"), (svt, "2026-27")]:
    ex[who["pan"]] = ok(c.post("/api/clients", json=who | {"ay": ay}))["id"]
# this year as it stands for the trend: Kiran filed on 20 Aug 2026 (C4), Sri Venkateswara computed (C3)
for pan, folder, form in [("BKRPR4417H", "C4 Kiran Kumar Rao (professional, refund + 244A)", "ITR-3"), ("AAFFS4721M", "C3 Sri Venkateswara Traders (firm, ITR-5, 3CB-3CD)", "ITR-5")]:
    cid = ex[pan]
    ok(c.put(f"/api/clients/{cid}/years/2026-27", json={"form": form, "audit": form == "ITR-5"}))
    for x in (OUT / folder).glob("*.xlsx"):
        ok(c.post(f"/api/intake/{cid}/2026-27/{ok(c.post(f'/api/intake/{cid}/2026-27', files={'file': (x.name, x.read_bytes())}))['id']}/accept"))
    for t in (OUT / folder).glob("*.txt"):
        ok(c.post(f"/api/recon/{cid}/2026-27", files={"file": (t.name, t.read_bytes())}))
cid = ex["BKRPR4417H"]
ok(c.post(f"/api/compute/{cid}/2026-27/signoff", json={"on": True}))
ok(c.post(f"/api/compute/{cid}/2026-27/file", json={"ack_no": "567890123456789", "filed_on": "2026-08-20"}))


def imp(fname, body):
    data = (DUMMY / fname).read_bytes()
    pv = c.post("/api/itrimport/read", files={"file": (fname, data)})
    out = {"preview": {k: pv.json()["facts"].get(k) for k in ("form", "ay", "kind", "name", "pan", "income", "tax_net", "refund", "payable", "nri")} if pv.status_code == 200 else pv.text,
           "match": [m["name"] for m in pv.json().get("match", [])] if pv.status_code == 200 else []}
    r = c.post("/api/itrimport", files={"file": (fname, data)}, data={"body": json.dumps(body)})
    out["result"] = r.json() if r.status_code == 200 else {"refused": r.status_code, "detail": r.json().get("detail")}
    return out


F = sorted(p.name for p in DUMMY.glob("*.json"))
X = {"returns": R}
X["c16"] = imp(F[0], {"cid": ex["AAAHG4321K"], "ack_no": "512345678901234", "filed_on": "2025-10-28"})
X["c17"] = [imp(F[1], {"cid": ex["BKRPR4417H"], "ack_no": "312345678901234", "filed_on": "2023-07-24"}),
            imp(F[2], {"cid": ex["BKRPR4417H"], "ack_no": "412345678901234", "filed_on": "2024-07-22"})]
X["c18"] = imp(F[3], {"cid": ex["AAFFS4721M"], "ack_no": "522345678901234", "filed_on": "2025-10-30"})
X["c19"] = imp(F[4], {"cid": "new", "ack_no": "532345678901234", "filed_on": "2025-07-29", "also_now": True})
X["c20"] = imp(F[5], {"cid": "new", "ack_no": "342345678901234", "filed_on": "2023-07-26", "also_now": False})
X["c21"] = [imp(F[6], {"cid": "new", "ack_no": "552345678901234", "filed_on": "2025-07-20", "also_now": False})]
sun = X["c21"][0]["result"]["client"]["id"]
X["c21"].append(imp(F[7], {"cid": sun, "ack_no": "552345678909999", "filed_on": "2025-11-20"}))
X["c22"] = imp(F[8], {"cid": "new", "ack_no": "462345678901234", "filed_on": "2024-11-15", "also_now": False})
X["c23"] = imp(F[9], {"cid": "new", "ack_no": "562345678901234", "filed_on": "2025-07-25", "also_now": True})
X["c24"] = imp(F[0], {"cid": ex["AAAHG4321K"], "ack_no": "512345678901234", "filed_on": "2025-10-28"})
X["c25"] = imp(F[8], {"cid": ex["AAAHG4321K"], "ack_no": "462345678901234", "filed_on": "2024-11-15"})
lnt_id = X["c19"]["result"]["client"]["id"]
st = c.get(f"/api/itrimport/{lnt_id}/2025-26/statement?which=next")
X["c19"]["next_statement"] = {"status": st.status_code, "name": st.headers.get("content-disposition", "")}
(OUT / "D Old returns - dummy ITR JSON (AY 2023-24 to 2025-26)" / "_next.xlsx").write_bytes(st.content)
up = c.post(f"/api/intake/{lnt_id}/2026-27", files={"file": ("next.xlsx", st.content)})
X["c19"]["next_upload"] = up.json().get("counts") if up.status_code == 200 else up.text
import io, openpyxl  # noqa: E401,E402 - fill the template the way the CA would: this year's amounts in column D
wb = openpyxl.load_workbook(io.BytesIO(st.content)); ws = wb.active
for row in ws.iter_rows(min_row=5):
    if row[1].value:
        row[3].value = 2500000 if "business" in str(row[1].value).lower() else 70000
buf = io.BytesIO(); wb.save(buf)
up2 = c.post(f"/api/intake/{lnt_id}/2026-27", files={"file": ("filled.xlsx", buf.getvalue())})
X["c19"]["filled_upload"] = up2.json().get("counts") if up2.status_code == 200 else up2.text[:200]
(OUT / "D Old returns - dummy ITR JSON (AY 2023-24 to 2025-26)" / "_next.xlsx").unlink()
an = ok(c.get("/api/analytics?ay=2026-27"))
X["analytics"] = {"roll": {k: an["roll"][k] for k in ("clients", "filed", "returns")}, "years": an["roll"]["years"],
                  "leads": {k: [(x["name"], x.get("pct")) for x in v] for k, v in an["leads"].items()}}
sun_c = ok(c.get(f"/api/compute/{sun}/2025-26"))
X["c21"].append({"filings": [(f["kind"], f["status"]) for f in sun_c["filings"]]})
(HERE / "showcase3_expected.json").write_text(json.dumps(X, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
for k in [f"c{i}" for i in range(16, 26)]:
    v = X[k]
    for one in (v if isinstance(v, list) else [v]):
        print(k, json.dumps(one.get("preview") if "preview" in one else one, ensure_ascii=False)[:160], "->", json.dumps(one.get("result", ""), ensure_ascii=False)[:200])
print(json.dumps(X["analytics"], ensure_ascii=False))
print("next statement", X["c19"]["next_statement"], X["c19"]["next_upload"], X["c19"]["filled_upload"])
