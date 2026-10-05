"""Ten more FICTIONAL showcase clients (C6-C15) for Demo CA Filing Firm - last year's filings and how they get updated, plus the
cases a practice meets every season - then each one driven through the portal (throw-away data) -> showcase2_expected.json."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import os
import runpy
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
g = runpy.run_path(str(HERE / "make_showcase.py"))          # book(), s26(), head() - and C1-C5 rewritten as they were
book, s26, head, OUT = g["book"], g["s26"], g["head"], g["OUT"]
HDR = ("", "TOTAL INCOME STATEMENT", "", "Amount (Rs)", "SF Ref")


def stmt(name, pan, ay, rows):
    return {"IT Statement": head(name, pan, ay) + [HDR] + rows}


CASES = []


def case(n, folder, client, ay, year, files, story):
    d = OUT / f"C{n} {folder}"
    d.mkdir(exist_ok=True)
    for fname, kind, data in files:
        (book(d / fname, data) if kind == "xlsx" else s26(d / fname, *data))
    CASES.append({"n": n, "dir": d, "client": client, "ay": ay, "year": year, "story": story})


# C6 - AY 2025-26 belated return u/s 139(4): filed in November 2025, 234A + 234B
case(6, "Lakshmi Devi AY 2025-26 (belated return)", {"name": "Lakshmi Devi", "status": "individual", "pan": "CLDPD3381F", "dob": "1972-08-19",
     "father": "Ranganath Rao", "email": "lakshmi.devi@example.com", "phone": "9866012345", "address": "3-6-145, Himayatnagar, Hyderabad 500029",
     "banks": [{"bank": "Union Bank of India", "branch": "Himayatnagar", "type": "Savings", "account": "520101234567890", "ifsc": "UBIN0815870"}]},
     "2025-26", {"form": "ITR-3"},
     [("Lakshmi Devi - Income statement AY 2025-26.xlsx", "xlsx", stmt("Lakshmi Devi", "CLDPD3381F", "2025-26", [
         ("", "Income from house property"), ("", "Rent received from Vasavi Clinics, Himayatnagar", "", 600000),
         ("", "Less: Standard deduction @ 30%", "", 180000), ("", "Income from other sources"), ("", "Interest on FD with Union Bank of India", "", 900000),
         (), ("", "Income returned", "", 1320000), (), ("", "Less: TDS as per certificates from"), ("", "Union Bank of India", "", 90000),
         ("", "Self assessment tax paid on", "15.11.25", 21250)])),
      ("Lakshmi Devi - 26AS AY 2025-26.txt", "txt", ("CLDPD3381F", "Lakshmi Devi", "2024-25", "2025-26",
                                                      [("Union Bank of India", "HYDU02211C", "194A", 900000, 90000, "31-Mar-2025")],
                                                      [(300, 21250, "15-Nov-2025", 51201)]))],
     {"file": [("2025-11-20", "234567890123451")]})

# C7 - AY 2026-27 revised return u/s 139(5): original in July, FD interest missed, revised before 31 December
case(7, "Suresh Reddy (revised return)", {"name": "Suresh Reddy", "status": "individual", "pan": "BSRPR2290K", "dob": "1981-01-30",
     "father": "Narayana Reddy", "email": "suresh.reddy@example.com", "phone": "9849112345", "address": "Plot 21, Kavuri Hills, Madhapur, Hyderabad 500081",
     "banks": [{"bank": "Axis Bank", "branch": "Madhapur", "type": "Current", "account": "917020012345678", "ifsc": "UTIB0001234"}]},
     "2026-27", {"form": "ITR-3"},
     [("Suresh Reddy - Income statement AY 2026-27 (as filed in July 2026).xlsx", "xlsx", stmt("Suresh Reddy", "BSRPR2290K", "2026-27", [
         ("", "Income from business"), ("", "Net profit as per Profit & Loss account", "", 1800000), ("", "Income from other sources"),
         ("", "Interest on SB a/c", "", 20000), (), ("", "Income returned", "", 1820000), (), ("", "Less: TDS as per certificates from"),
         ("", "Sri Sai Infra Projects Pvt Ltd", "", 50000), ("", "Advance tax paid on", "15.09.25", 60000), ("", "", "15.12.25", 60000), ("", "", "15.03.26", 50000)])),
      ("Suresh Reddy - FD interest missed AY 2026-27.xlsx", "xlsx", {"Missed income": head("Suresh Reddy", "BSRPR2290K", "2026-27") + [
          ("", "STATEMENT OF INCOME NOT SHOWN IN THE ORIGINAL RETURN", "", "Amount (Rs)"), ("", "Interest on FD with Kotak Mahindra Bank (found in AIS)", "", 250000)]}),
      ("Suresh Reddy - 26AS AY 2026-27.txt", "txt", ("BSRPR2290K", "Suresh Reddy", "2025-26", "2026-27",
                                                     [("Sri Sai Infra Projects Private Limited", "HYDS33445K", "194C", 2500000, 50000, "31-Mar-2026")],
                                                     [(100, 60000, "15-Sep-2025", 61301), (100, 60000, "15-Dec-2025", 61302), (100, 50000, "15-Mar-2026", 61303)]))],
     {"file": [("2026-07-25", "678901234567801")], "revise_with": "FD interest missed", "file_revised": "678901234567802"})

# C8 - AY 2025-26: a missed deduction found after 31 December - an ITR-U cannot lower tax, so SimplyFile refuses it
case(8, "Anjali Sharma AY 2025-26 (ITR-U not allowed)", {"name": "Anjali Sharma", "status": "individual", "pan": "DASPS7712M", "dob": "1985-05-05",
     "father": "Rakesh Sharma", "email": "anjali.sharma@example.com", "phone": "9811012345", "address": "C-14, Sector 50, Noida 201301",
     "banks": [{"bank": "Punjab National Bank", "branch": "Sector 50 Noida", "type": "Savings", "account": "0123000100123456", "ifsc": "PUNB0012300"}]},
     "2025-26", {"form": "ITR-3"},
     [("Anjali Sharma - Income statement AY 2025-26 (as filed in July 2025).xlsx", "xlsx", stmt("Anjali Sharma", "DASPS7712M", "2025-26", [
         ("", "Income from house property"), ("", "Rent received from Bright Kids Montessori", "", 360000), ("", "Less: Standard deduction @ 30%", "", 108000),
         ("", "Income from other sources"), ("", "Interest on FD with Punjab National Bank", "", 700000), (), ("", "Income returned", "", 952000), (),
         ("", "Less: TDS as per certificates from"), ("", "Punjab National Bank", "", 70000)])),
      ("Anjali Sharma - Municipal tax not claimed AY 2025-26.xlsx", "xlsx", {"Not claimed": head("Anjali Sharma", "DASPS7712M", "2025-26") + [
          ("", "STATEMENT OF DEDUCTION NOT CLAIMED IN THE ORIGINAL RETURN", "", "Amount (Rs)", "SF Ref"),
          ("", "Less: Municipal taxes paid to Noida Authority", "", 24000, "ITR3 HP")]}),
      ("Anjali Sharma - 26AS AY 2025-26.txt", "txt", ("DASPS7712M", "Anjali Sharma", "2024-25", "2025-26",
                                                      [("Punjab National Bank", "DELP01122A", "194A", 700000, 70000, "31-Mar-2025")], []))],
     {"file": [("2025-07-30", "789012345678901")], "revise_with": "Municipal tax", "itru_refused": True})

# C9 - old regime or new? A businessman with 80C / 80D / 80CCD(1B): SimplyFile shows both
case(9, "Vijay Kumar (old vs new regime)", {"name": "Vijay Kumar", "status": "individual", "pan": "AVKPK5520D", "dob": "1979-12-12",
     "father": "Sampath Kumar", "email": "vijay.kumar@example.com", "phone": "9840212345", "address": "45, 2nd Cross, Jayanagar 4th Block, Bengaluru 560011",
     "banks": [{"bank": "HDFC Bank", "branch": "Jayanagar", "type": "Current", "account": "50200011223344", "ifsc": "HDFC0000047"}]},
     "2026-27", {"form": "ITR-3"},
     [("Vijay Kumar - Income statement AY 2026-27.xlsx", "xlsx", stmt("Vijay Kumar", "AVKPK5520D", "2026-27", [
         ("", "Income from business"), ("", "Net profit as per Profit & Loss account", "", 1500000), ("", "Income from other sources"),
         ("", "Interest on FD with HDFC Bank", "", 100000), (), ("", "Deductions under Chapter VI-A"),
         ("", "Life insurance premium, PPF and ELSS - section 80C", "", 150000, "ITR3 VIA 80C"),
         ("", "Health insurance premium (self and parents) - section 80D", "", 50000, "ITR3 VIA 80D"),
         ("", "NPS contribution - section 80CCD(1B)", "", 50000, "ITR3 VIA 80CCD1B"), (),
         ("", "Income returned", "", 1600000), (), ("", "Less: TDS as per certificates from"), ("", "HDFC Bank", "", 10000),
         ("", "Advance tax paid on", "15.06.25", 20000), ("", "", "15.09.25", 35000), ("", "", "15.12.25", 35000), ("", "", "15.03.26", 25000)])),
      ("Vijay Kumar - 26AS AY 2026-27.txt", "txt", ("AVKPK5520D", "Vijay Kumar", "2025-26", "2026-27",
                                                    [("HDFC Bank Limited", "BLRH01234C", "194A", 100000, 10000, "31-Mar-2026")],
                                                    [(100, 20000, "15-Jun-2025", 71401), (100, 35000, "15-Sep-2025", 71402), (100, 35000, "15-Dec-2025", 71403),
                                                     (100, 25000, "15-Mar-2026", 71404)]))],
     {"compare_regimes": True})

# C10 - a doctor above Rs 1 crore: surcharge 15% and marginal relief
case(10, "Dr Harish Menon (surcharge)", {"name": "Dr Harish Menon", "status": "individual", "pan": "AHMPM9034L", "dob": "1968-03-21",
     "father": "Krishnan Menon", "email": "harish.menon@example.com", "phone": "9847012345", "address": "Menon Clinic, MG Road, Kochi 682016",
     "banks": [{"bank": "Federal Bank", "branch": "MG Road Kochi", "type": "Current", "account": "10120200012345", "ifsc": "FDRL0001012"}]},
     "2026-27", {"form": "ITR-3", "audit": True},
     [("Dr Harish Menon - Income statement AY 2026-27.xlsx", "xlsx", stmt("Dr Harish Menon", "AHMPM9034L", "2026-27", [
         ("", "Income from profession"), ("", "Net profit as per Profit & Loss account", "", 12000000), ("", "Income from other sources"),
         ("", "Interest on FD with Federal Bank", "", 500000), (), ("", "Income returned", "", 12500000), (),
         ("", "Less: TDS as per certificates from"), ("", "Lakeshore Hospitals Ltd", "", 1200000), ("", "Federal Bank", "", 50000),
         ("", "Advance tax paid on", "15.06.25", 400000), ("", "", "15.09.25", 800000), ("", "", "15.12.25", 800000), ("", "", "15.03.26", 800000)])),
      ("Dr Harish Menon - 26AS AY 2026-27.txt", "txt", ("AHMPM9034L", "Dr Harish Menon", "2025-26", "2026-27",
                                                        [("Lakeshore Hospitals Limited", "CHNL04567D", "194J", 12000000, 1200000, "31-Mar-2026"),
                                                         ("Federal Bank Limited", "CHNF01234E", "194A", 500000, 50000, "31-Mar-2026")],
                                                        [(100, 400000, "15-Jun-2025", 81501), (100, 800000, "15-Sep-2025", 81502),
                                                         (100, 800000, "15-Dec-2025", 81503), (100, 800000, "15-Mar-2026", 81504)]))],
     {})

# C11 - a non-resident: rent and NRO interest in India, TDS u/s 195 - and no rebate u/s 87A
case(11, "Arjun Pillai (non-resident)", {"name": "Arjun Pillai", "status": "individual", "pan": "BAPPP6611N", "dob": "1983-09-09", "nri": True,
     "father": "Gopalan Pillai", "email": "arjun.pillai@example.com", "phone": "9895012345", "address": "Flat 9B, Marina Heights, Dubai Marina, Dubai, UAE",
     "banks": [{"bank": "South Indian Bank", "branch": "Thrissur NRI", "type": "NRO Savings", "account": "0123053000012345", "ifsc": "SIBL0000123"}]},
     "2026-27", {"form": "ITR-3"},
     [("Arjun Pillai - Income statement AY 2026-27.xlsx", "xlsx", stmt("Arjun Pillai", "BAPPP6611N", "2026-27", [
         ("", "Income from house property"), ("", "Rent received from Trichur Textiles", "", 540000), ("", "Less: Standard deduction @ 30%", "", 162000),
         ("", "Income from other sources"), ("", "Interest on NRO FD with South Indian Bank", "", 200000, "ITR3 OS"), (), ("", "Income returned", "", 578000), (),
         ("", "Less: TDS as per certificates from"), ("", "Trichur Textiles (TDS u/s 195 on rent)", "", 162000), ("", "South Indian Bank", "", 60000)])),
      ("Arjun Pillai - 26AS AY 2026-27.txt", "txt", ("BAPPP6611N", "Arjun Pillai", "2025-26", "2026-27",
                                                     [("Trichur Textiles", "CHNT05678F", "195", 540000, 162000, "31-Mar-2026"),
                                                      ("South Indian Bank Limited", "CHNS02345G", "195", 200000, 60000, "31-Mar-2026")], []))],
     {})

# C12 - an LLP filing after its 31 August due date: belated, 234A
case(12, "Greenfield Agritech LLP (late, ITR-5)", {"name": "Greenfield Agritech LLP", "status": "llp", "pan": "AAKFG3307Q", "gst": "36AAKFG3307Q1ZP",
     "dob": "2019-06-14", "relation": "Rohit Varma (designated partner)", "father": "Prasad Varma", "signer_pan": "AQRPV3344H",
     "email": "accounts@greenfieldagri.example.com", "phone": "9848512345", "address": "Survey 112, Shamshabad, Rangareddy 501218",
     "partners": [{"name": "Rohit Varma", "pan": "AQRPV3344H", "share": "60"}, {"name": "Neha Varma", "pan": "AQRPV5566J", "share": "40"}],
     "banks": [{"bank": "ICICI Bank", "branch": "Shamshabad", "type": "Current", "account": "063405001234", "ifsc": "ICIC0000634"}]},
     "2026-27", {"form": "ITR-5"},
     [("Greenfield Agritech LLP - Income statement AY 2026-27.xlsx", "xlsx", stmt("Greenfield Agritech LLP", "AAKFG3307Q", "2026-27", [
         ("", "Income from business"), ("", "Net profit as per Profit & Loss account", "", 2200000), ("", "Income from other sources"),
         ("", "Interest on FD with ICICI Bank", "", 80000), (), ("", "Income returned", "", 2280000), (),
         ("", "Less: TDS as per certificates from"), ("", "Telangana State Seeds Development Corp", "", 100000), ("", "ICICI Bank", "", 8000),
         ("", "Advance tax paid on", "15.09.25", 150000), ("", "", "15.12.25", 200000), ("", "", "15.03.26", 150000)])),
      ("Greenfield Agritech LLP - 26AS AY 2026-27.txt", "txt", ("AAKFG3307Q", "Greenfield Agritech LLP", "2025-26", "2026-27",
                                                                [("Telangana State Seeds Development Corporation", "HYDT07788H", "194C", 5000000, 100000, "31-Mar-2026"),
                                                                 ("ICICI Bank Limited", "HYDI04455J", "194A", 80000, 8000, "31-Mar-2026")],
                                                                [(100, 150000, "15-Sep-2025", 91601), (100, 200000, "15-Dec-2025", 91602), (100, 150000, "15-Mar-2026", 91603)]))],
     {"file": [("2026-09-10", "890123456789012")]})

# C13 - old regime with a self-occupied house: interest on the housing loan, loss capped at Rs 2 lakh
case(13, "Prakash Joshi (house-property loss, old regime)", {"name": "Prakash Joshi", "status": "individual", "pan": "BPJPJ4450R", "dob": "1976-07-07",
     "father": "Madhav Joshi", "email": "prakash.joshi@example.com", "phone": "9822012345", "address": "B-402, Gokul Residency, Kothrud, Pune 411038",
     "banks": [{"bank": "Bank of Maharashtra", "branch": "Kothrud", "type": "Savings", "account": "60123456789", "ifsc": "MAHB0000456"}]},
     "2026-27", {"form": "ITR-3"},
     [("Prakash Joshi - Income statement AY 2026-27.xlsx", "xlsx", stmt("Prakash Joshi", "BPJPJ4450R", "2026-27", [
         ("", "Income from business"), ("", "Net profit as per Profit & Loss account", "", 1200000),
         ("", "Income from house property (self-occupied)"), ("", "Interest on housing loan - SBI Home Loans", "", 350000, "ITR3 HP"),
         ("", "Deductions under Chapter VI-A"), ("", "PPF, LIC and principal on housing loan - section 80C", "", 150000, "ITR3 VIA 80C"),
         (), ("", "Income returned", "", 850000), (), ("", "Less: TDS as per certificates from"), ("", "Pune Auto Components Pvt Ltd", "", 40000),
         ("", "Advance tax paid on", "15.12.25", 20000), ("", "", "15.03.26", 20000)])),
      ("Prakash Joshi - 26AS AY 2026-27.txt", "txt", ("BPJPJ4450R", "Prakash Joshi", "2025-26", "2026-27",
                                                      [("Pune Auto Components Private Limited", "PNEP01234K", "194C", 2000000, 40000, "31-Mar-2026")],
                                                      [(100, 20000, "15-Dec-2025", 10171), (100, 20000, "15-Mar-2026", 10172)]))],
     {"regime": "old"})

# C14 - books and 26AS disagree and nobody has explained it: the year stays in Reconciling
case(14, "Fathima Begum (open mismatch)", {"name": "Fathima Begum", "status": "individual", "pan": "CFBPB2208H", "dob": "1990-10-10",
     "father": "Abdul Rahim", "email": "fathima.begum@example.com", "phone": "9849312345", "address": "18-2-45, Charminar Road, Hyderabad 500002",
     "banks": [{"bank": "Canara Bank", "branch": "Charminar", "type": "Savings", "account": "1234101012345", "ifsc": "CNRB0001234"}]},
     "2026-27", {"form": "ITR-3"},
     [("Fathima Begum - Income statement AY 2026-27.xlsx", "xlsx", stmt("Fathima Begum", "CFBPB2208H", "2026-27", [
         ("", "Income from business"), ("", "Net profit as per Profit & Loss account", "", 900000), ("", "Income from other sources"),
         ("", "Interest on SB a/c", "", 50000), (), ("", "Income returned", "", 950000), (),
         ("", "Less: TDS as per certificates from"), ("", "Noor Garments", "", 8000)])),
      ("Fathima Begum - 26AS AY 2026-27.txt", "txt", ("CFBPB2208H", "Fathima Begum", "2025-26", "2026-27",
                                                      [("Zen Retail Private Limited", "HYDZ09876L", "194C", 600000, 12000, "31-Mar-2026")], []))],
     {"leave_red": True})

# C15 - AY 2025-26 filed on time with a refund; a wrong acknowledgement number undone and filed again; not yet carried into 2026-27
case(15, "Gopal Krishna AY 2025-26 (undo a wrong filing)", {"name": "Gopal Krishna", "status": "individual", "pan": "AGKPK7781S", "dob": "1964-04-04",
     "father": "Venkata Krishna", "email": "gopal.krishna@example.com", "phone": "9440012345", "address": "12-1-34, Brodipet, Guntur 522002",
     "banks": [{"bank": "Andhra Pragathi Grameena Bank", "branch": "Brodipet", "type": "Savings", "account": "91234567890", "ifsc": "APGB0001234"}]},
     "2025-26", {"form": "ITR-3"},
     [("Gopal Krishna - Income statement AY 2025-26.xlsx", "xlsx", stmt("Gopal Krishna", "AGKPK7781S", "2025-26", [
         ("", "Income from house property"), ("", "Rent received from Guntur Medical Stores", "", 240000), ("", "Less: Standard deduction @ 30%", "", 72000),
         ("", "Income from other sources"), ("", "Interest on FD with State Bank of India", "", 600000), (), ("", "Income returned", "", 768000), (),
         ("", "Less: TDS as per certificates from"), ("", "State Bank of India", "", 60000)])),
      ("Gopal Krishna - 26AS AY 2025-26.txt", "txt", ("AGKPK7781S", "Gopal Krishna", "2024-25", "2025-26",
                                                      [("State Bank of India", "HYDS05566M", "194A", 600000, 60000, "31-Mar-2025")], []))],
     {"file": [("2025-07-20", "901234567890000")], "undo": "Acknowledgement number typed wrong - 0000 instead of 1234", "refile": ("2025-07-20", "901234567891234")})

print("files for", len(CASES), "cases written")

# --- drive every case through the portal ----------------------------------------------------------------------------
sys.path.insert(0, _R + r"")
os.chdir(_R + r"")
os.environ["TV_DATA"] = tempfile.mkdtemp(prefix="sf-show2-")
from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402

adm = TestClient(app.app)
adm.post("/api/auth/first-account", json={"email": "admin@valuestream.test", "password": "Admin-pass-123"})
adm.post("/api/users", json={"email": "demo@valuestream.in", "password": "Uncle-pass-123", "display_name": "Demo Partner"})
c = TestClient(app.app)
c.post("/api/auth/signin", json={"identity": "demo@valuestream.in", "password": "Uncle-pass-123"})
fid = c.post("/api/firm/start", json={"kind": "ca_firm"}).json()["id"]
c.put("/api/firm", json={"name": "Demo CA Filing Firm", "pan": "AAFFP1234C", "tan": "HYDP12345E", "gstin": "36AAFFP1234C1Z5", "frn": "012345S",
                         "membership_no": "212345", "owner_name": "Demo Partner", "aadhaar_last4": "4821", "phone": "9000000001",
                         "email": "demo@valuestream.in", "address": "Hyderabad", "consent": True})
for k, f in [("owner_aadhaar", "1"), ("pan_card", "2"), ("tan_letter", "3"), ("gst_cert", "4")]:
    p = next((OUT / "A Firm papers - placeholders").glob(f"{f} *.pdf"))
    c.post(f"/api/firm/docs/{k}", files={"file": (p.name, p.read_bytes())})
c.post(f"/api/firm/{fid}/move", json={"action": "submit"})
assert adm.post(f"/api/firm/{fid}/move", json={"action": "approve"}).json()["state"] == "approved"


def ok(r):
    assert r.status_code == 200, r.text[:400]
    return r.json()


def up(cid, ay, path, kind="intake"):
    return ok(c.post(f"/api/{kind}/{cid}/{ay}", files={"file": (path.name, path.read_bytes())}))


def mapped(cid, ay, f):
    ib = f"/api/intake/{cid}/{ay}/{f['id']}"
    v = ok(c.post(f"{ib}/accept"))
    return {"rows": v["counts"]["rows"], "left": [x["label"] for x in v["rows"] if x["state"] in ("untagged", "invalid")]}


def comp(cid, ay):
    k = ok(c.get(f"/api/compute/{cid}/{ay}"))
    return {"stage": k["stage"], "regime": k["regime"], "heads": [(h["id"], h["net"]) for h in k["heads"]], "income": k["income"],
            "deductions": k["deductions"], "tax": {x: k["tax"].get(x) for x in ("tax", "rebate", "surcharge", "surcharge_rate", "relief", "cess", "total")},
            "tds": k["tds_total"], "paid": k["paid_total"], "interest": k["interest_auto"], "balance": k["balance"],
            "refund_interest": k["refund_interest"].get("interest"), "dates": k["dates"], "itr_u": k["itr_u"], "open_red": k["open_red"],
            "current": (k["current"] or {}).get("kind"), "filings": [(f["kind"], f["status"], f["ack_no"]) for f in k["filings"]]}


def sign_file(cid, ay, ack, on="", extra=None):
    ok(c.post(f"/api/compute/{cid}/{ay}/signoff", json={"on": True}))
    return ok(c.post(f"/api/compute/{cid}/{ay}/file", json={"ack_no": ack, "filed_on": on} | (extra or {})))["current"]["kind"]


X = {}
for k in CASES:
    cid = ok(c.post("/api/clients", json=k["client"] | {"ay": k["ay"]}))["id"]
    ay, s, d = k["ay"], k["story"], k["dir"]
    ok(c.put(f"/api/clients/{cid}/years/{ay}", json=k["year"]))
    files = sorted(d.glob("*.xlsx"))
    first = [f for f in files if not any(w in f.name for w in ("missed", "not claimed"))]
    later = [f for f in files if f not in first]
    r = {"name": k["client"]["name"], "ay": ay, "map": [mapped(cid, ay, up(cid, ay, f)) for f in first]}
    for t in d.glob("*.txt"):
        up(cid, ay, t, "recon")
    rc = ok(c.get(f"/api/recon/{cid}/{ay}"))
    r["recon"] = {"summary": rc["summary"], "red": [x["title"] for x in rc["findings"] if x["severity"] == "red"]}
    if not s.get("leave_red"):
        for x in rc["findings"]:
            if x["severity"] == "red":
                ok(c.put(f"/api/recon/{cid}/{ay}/notes/{x['id']}", json={"note": "Checked with the client."}))
    if s.get("regime"):
        ok(c.put(f"/api/compute/{cid}/{ay}", json={"regime": s["regime"]}))
    if s.get("compare_regimes"):
        r["new"] = comp(cid, ay)
        ok(c.put(f"/api/compute/{cid}/{ay}", json={"regime": "old"}))
        r["old"] = comp(cid, ay)
        ok(c.put(f"/api/compute/{cid}/{ay}", json={"regime": "new"}))
    r["compute"] = comp(cid, ay)
    for on, ack in s.get("file", []):
        r["filed_kind"] = sign_file(cid, ay, ack, on)
        r["after_file"] = comp(cid, ay)
    if s.get("undo"):
        ok(c.post(f"/api/compute/{cid}/{ay}/withdraw", json={"note": s["undo"]}))
        on, ack = s["refile"]
        r["refiled_kind"] = sign_file(cid, ay, ack, on)
        r["after_refile"] = comp(cid, ay)
    if s.get("revise_with"):
        ok(c.post(f"/api/compute/{cid}/{ay}/revise", json={"note": ""}))
        for f in later:
            r.setdefault("map_later", []).append(mapped(cid, ay, up(cid, ay, f)))
        r["revising"] = comp(cid, ay)
        if s.get("itru_refused"):
            ok(c.post(f"/api/compute/{cid}/{ay}/signoff", json={"on": True}))
            bad = c.post(f"/api/compute/{cid}/{ay}/file", json={"ack_no": "789012345678999", "filed_on": "", "itru_confirm": True})
            r["itru_refusal"] = [bad.status_code, bad.json().get("detail")]
            ok(c.post(f"/api/compute/{cid}/{ay}/discard", json={"note": ""}))
            r["after_discard"] = comp(cid, ay)
        else:
            r["revised_kind"] = sign_file(cid, ay, s["file_revised"])
            r["after_revise"] = comp(cid, ay)
    itr = ok(c.get(f"/api/compute/{cid}/{ay}/itr-check"))
    r["itr_valid"], r["itr_missing"] = itr["valid"], [e["field"] for e in itr["errors"]][:5]
    X[f"c{k['n']}"] = r
    cm = r.get("after_revise") or r.get("after_refile") or r.get("after_file") or r.get("after_discard") or r["compute"]
    print(f"C{k['n']} {r['name']} {ay} | map {r['map']} | red {r['recon']['red']} | income {cm['income']} tax {cm['tax']['total']} "
          f"int {cm['interest'].get('total')} bal {cm['balance']} 244A {cm['refund_interest']} | {cm['current']} | stage {cm['stage']}")
an = ok(c.get("/api/analytics?ay=2026-27"))
X["analytics_2026"] = {"roll": {k: an["roll"][k] for k in ("clients", "filed", "on_time", "tax", "refund", "interest", "interest_bc")},
                       "leads": {k: [x["name"] for x in v] for k, v in an["leads"].items()}}
X["analytics_2025"] = {"leads": {k: [x["name"] for x in v] for k, v in ok(c.get("/api/analytics?ay=2025-26"))["leads"].items()}}
(HERE / "showcase2_expected.json").write_text(json.dumps(X, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
print(json.dumps(X["analytics_2026"], ensure_ascii=False))
