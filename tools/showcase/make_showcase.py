"""Showcase pack for a CA firm (Demo CA Filing Firm): placeholder papers for the firm's sign-up, and five FICTIONAL clients whose
files walk every scenario the portal has. Then the whole thing is driven through the portal (test client, throw-away data)
so the recording script quotes exactly what each screen will show."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import openpyxl
from openpyxl.styles import Font

ROOT = Path(_R + r"")
OUT = ROOT / "Requirements" / "Showcase - Demo CA Filing Firm"
DEMO = ROOT / "Requirements" / "Demo E2E - Shree Ganesh Agarwal HUF"
OUT.mkdir(parents=True, exist_ok=True)
B = Font(bold=True)


# --- placeholder papers: plainly NOT identity documents ----------------------------------------------------------------
def pdf(path: Path, lines: list[str]) -> None:
    """A one-page PDF of plain text lines (no images, no look-alike layout)."""
    esc = lambda t: t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")  # noqa: E731
    body = ["BT /F1 22 Tf 60 760 Td (" + esc(lines[0]) + ") Tj ET"]
    y = 720
    for ln in lines[1:]:
        body.append(f"BT /F1 12 Tf 60 {y} Td (" + esc(ln) + ") Tj ET")
        y -= 20
    body.append("0.85 0.1 0.1 rg BT /F1 40 Tf 1 0 0 1 70 380 Tm (DEMO PLACEHOLDER) Tj ET")
    stream = "\n".join(body).encode("latin-1")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


PAPERS = OUT / "A Firm papers - placeholders"
PAPERS.mkdir(exist_ok=True)
for fname, what in [("1 Owner Aadhaar (masked) - PLACEHOLDER.pdf", "Owner's Aadhaar (masked e-Aadhaar)"),
                    ("2 PAN card - PLACEHOLDER.pdf", "Firm PAN card"), ("3 TAN allotment letter - PLACEHOLDER.pdf", "TAN allotment letter"),
                    ("4 GST registration REG-06 - PLACEHOLDER.pdf", "GST registration certificate (REG-06)"),
                    ("5 ICAI registration - PLACEHOLDER.pdf", "ICAI firm registration / certificate of practice")]:
    pdf(PAPERS / fname, [f"PLACEHOLDER - {what}", "This is NOT an identity document and carries no real details.",
                         "It only lets the upload and approval flow of SimplyFile be shown in a demo.",
                         "Before relying on the firm's account, replace it with the real paper",
                         "(My firm > Papers > Replace)."])


# --- client files ----------------------------------------------------------------------------------------------------
def book(path: Path, sheets: dict) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(list(r))
        ws.column_dimensions["B"].width = 58
        for c in "CDEFGH":
            ws.column_dimensions[c].width = 16
    wb.save(path)


def s26(path: Path, pan: str, name: str, fy: str, ay: str, deductors: list, challans: list) -> None:
    L = ["^Annual Tax Statement^", f"^Permanent Account Number (PAN)^{pan}^Current Status of PAN^Active^Financial Year^{fy}^Assessment Year^{ay}^",
         f"^Name of Assessee^{name.upper()}^", "^PART-I - Details of Tax Deducted at Source^",
         "^Sr. No.^Name of Deductor^TAN of Deductor^^^^^Total Amount Paid / Credited(Rs.)^Total Tax Deducted #(Rs.)^Total TDS Deposited(Rs.)"]
    for i, (dn, tan, sec, gross, tax, day) in enumerate(deductors, 1):
        L += [f"^{i}^{dn.upper()}^{tan}^^^^^{gross:.2f}^{tax:.2f}^{tax:.2f}",
              "^^Sr. No.^Section^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited(Rs.)^Tax Deducted ##(Rs.)^TDS Deposited(Rs.)",
              f"^^1^{sec}^{day}^F^15-May-{day[-4:]}^-^{gross:.2f}^{tax:.2f}^{tax:.2f}"]
    L += ["^PART-III - Details of Tax Paid (other than TDS or TCS)^",
          "^Sr. No.^Major Head^Minor Head^Tax (Rs.)^Surcharge (Rs.)^Education Cess (Rs.)^Others (Rs.)^Total Tax (Rs.)^BSR Code^Date of Deposit^Challan Serial Number^Remarks**"]
    for i, (minor, amt, day, serial) in enumerate(challans, 1):
        L.append(f"^{i}^0021^{minor}^{amt:.2f}^0.00^0.00^0.00^{amt:.2f}^0510308^{day}^{serial}^")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def head(name, pan, ay):
    return [(name.upper(),), (f"PAN : {pan}      Assessment Year {ay}",), ()]


C = {}
# 1 - the demo HUF, as it is
d1 = OUT / "C1 Shree Ganesh Agarwal HUF (ITR-3, tax audit)"
d1.mkdir(exist_ok=True)
for f in DEMO.iterdir():
    if f.name[:2] in ("01", "02", "03", "04", "05", "10"):
        shutil.copy(f, d1 / f.name)
C[1] = d1

# 2 - senior citizen, no business income, late return
d2 = OUT / "C2 Ramesh Iyer (senior citizen, late return)"
d2.mkdir(exist_ok=True)
book(d2 / "Ramesh Iyer - Income statement AY 2026-27.xlsx", {"IT Statement": head("Ramesh Iyer", "BXRPI5821K", "2026-27") + [
    ("", "TOTAL INCOME STATEMENT", "", "Amount (Rs)"), ("", "Income from house property"),
    ("", "Rent received from Sai Medicals, Mylapore", "", 360000), ("", "Less: Standard deduction @ 30%", "", 108000),
    ("", "Income from other sources"), ("", "Interest on FD with Indian Bank", "", 1800000), ("", "Interest on SB a/c", "", 60000),
    (), ("", "Income returned", "", 2112000), (),
    ("", "Less: TDS as per certificates from"), ("", "Indian Bank", "", 180000),
    ("", "Self assessment tax paid on", "20.09.26", 57120)]})
s26(d2 / "Ramesh Iyer - 26AS AY 2026-27.txt", "BXRPI5821K", "Ramesh Iyer", "2025-26", "2026-27",
    [("Indian Bank", "CHEI04567B", "194A", 1800000, 180000, "31-Mar-2026")], [(300, 57120, "20-Sep-2026", 31107)])
C[2] = d2

# 3 - partnership firm, ITR-5, tax audit, short advance tax
d3 = OUT / "C3 Sri Venkateswara Traders (firm, ITR-5, 3CB-3CD)"
d3.mkdir(exist_ok=True)
book(d3 / "Sri Venkateswara Traders - IT Stmt, Dep, Loans, 40A(2)(b) AY 2026-27.xlsx", {
    "IT Statement": head("Sri Venkateswara Traders", "AAFFS4721M", "2026-27") + [
        ("", "TOTAL INCOME STATEMENT", "", "Amount (Rs)"), ("", "Income from business"),
        ("", "Net profit as per Profit & Loss account", "", 4250000), ("", "Add: Depreciation as per books", "", 380000),
        ("", "Less: Depreciation as per Income-tax Rules, 1962", "", 450000), ("", "Income from other sources"),
        ("", "Interest on FD with State Bank of India", "", 120000), (), ("", "Income returned", "", 4300000), (),
        ("", "Less: TDS as per certificates from"), ("", "State Bank of India", "", 12000), ("", "Krishna Constructions Pvt Ltd", "", 60000),
        ("", "Advance tax paid on", "15.06.25", 150000), ("", "", "15.09.25", 300000), ("", "", "15.12.25", 300000), ("", "", "15.03.26", 200000)],
    "Depreciation": [("Statement regarding depreciation as per Income-tax Rules (Form 3CD clause 18)",), (),
                     ("Sl", "Block of assets", "WDV 01.04.2025", "Additions", "Depreciation", "WDV 31.03.2026", "Rate %"),
                     (1, "Plant & Machinery", 1800000, 400000, 330000, 1870000, 15), (2, "Furniture & Fittings", 500000, 0, 50000, 450000, 10),
                     (3, "Computers", 150000, 50000, 70000, 130000, 40)],
    "Loans": [("Statement of loans / deposits accepted (Form 3CD clause 31)",), (),
              ("Sl", "Name of lender", "PAN of lender", "Amount accepted", "Mode", "Amount repaid", "Mode"),
              (1, "Venkata Lakshmi", "ABCPL4455M", 1200000, "Bank transfer", 500000, "Bank transfer"),
              (2, "Suresh Kumar", "ABCPK7788N", 800000, "Cheque", 0, "")],
    "40A(2)(b)": [("Statement regarding the payments to persons specified in s.40A(2)(b) (Form 3CD clause 23)",), (),
                  ("Sl", "Name", "Relation", "PAN", "Nature of payment", "Amount paid"),
                  (1, "Lakshmi Rao", "Wife of partner", "ABCPR9911K", "Rent for godown", 600000)]})
book(d3 / "Sri Venkateswara Traders - Trading, P&L and Balance Sheet AY 2026-27.xlsx", {"Final accounts": head("Sri Venkateswara Traders", "AAFFS4721M", "2026-27") + [
    ("TRADING AND PROFIT AND LOSS ACCOUNT FOR THE YEAR ENDED 31.03.2026", "Amount (Rs)"),
    ("Sales", 32000000), ("Opening stock", 4000000), ("Purchases", 24500000), ("Carriage inward", 500000), ("Closing stock", 4500000),
    ("Salaries and wages", 1400000), ("Rent", 600000), ("Power and fuel", 200000), ("Telephone and internet", 50000), ("Travelling", 150000),
    ("Audit fee", 75000), ("Professional charges", 125000), ("Other expenses", 180000), ("Interest on loans", 90000), ("Depreciation as per books", 380000),
    (), ("BALANCE SHEET AS AT 31.03.2026", "Amount (Rs)"),
    ("Partners' capital accounts", 9100000), ("Secured loan - SBI cash credit", 1000000), ("Unsecured loans from relatives", 1500000),
    ("Fixed assets - gross block", 4000000), ("Less: accumulated depreciation", 1200000), ("Investments - fixed deposits", 1200000),
    ("Closing stock", 4500000), ("Sundry debtors", 3800000), ("Cash in hand", 120000), ("Balance with banks", 980000),
    ("Deposits", 200000), ("Loans and advances", 300000), ("Sundry creditors", 2200000), ("Provisions", 100000)]})
s26(d3 / "Sri Venkateswara Traders - 26AS AY 2026-27.txt", "AAFFS4721M", "Sri Venkateswara Traders", "2025-26", "2026-27",
    [("State Bank of India", "HYDS12345F", "194A", 120000, 12000, "31-Mar-2026"),
     ("Krishna Constructions Private Limited", "HYDK67890G", "194C", 3000000, 60000, "31-Mar-2026")],
    [(100, 150000, "15-Jun-2025", 41101), (100, 300000, "15-Sep-2025", 41102), (100, 300000, "15-Dec-2025", 41103), (100, 200000, "15-Mar-2026", 41104)])
C[3] = d3

# 4 - professional, 87A rebate, refund with 244A interest
d4 = OUT / "C4 Kiran Kumar Rao (professional, refund + 244A)"
d4.mkdir(exist_ok=True)
book(d4 / "Kiran Kumar Rao - Income statement AY 2026-27.xlsx", {"IT Statement": head("Kiran Kumar Rao", "BKRPR4417H", "2026-27") + [
    ("", "TOTAL INCOME STATEMENT", "", "Amount (Rs)"), ("", "Income from profession"),
    ("", "Net profit as per Profit & Loss account", "", 960000), ("", "Income from other sources"), ("", "Interest on SB a/c", "", 15000),
    (), ("", "Income returned", "", 975000), (),
    ("", "Less: TDS as per certificates from"), ("", "Nova Software Pvt Ltd", "", 120000), ("", "Orbit Analytics LLP", "", 60000)]})
s26(d4 / "Kiran Kumar Rao - 26AS AY 2026-27.txt", "BKRPR4417H", "Kiran Kumar Rao", "2025-26", "2026-27",
    [("Nova Software Private Limited", "HYDN11223A", "194J", 1200000, 120000, "31-Mar-2026"),
     ("Orbit Analytics LLP", "HYDO44556B", "194J", 600000, 60000, "31-Mar-2026")], [])
C[4] = d4

# 5 - AY 2025-26: original filed, income missed, updated return (ITR-U) with 140B
d5 = OUT / "C5 Meera Nair AY 2025-26 (ITR-U)"
d5.mkdir(exist_ok=True)
base5 = head("Meera Nair", "AYMPN6630Q", "2025-26") + [
    ("", "TOTAL INCOME STATEMENT", "", "Amount (Rs)"), ("", "Income from house property"),
    ("", "Rent received from Zenith Pharma Pvt Ltd", "", 480000), ("", "Less: Standard deduction @ 30%", "", 144000),
    ("", "Income from other sources"), ("", "Interest on FD with Canara Bank", "", 600000)]
tds5 = [(), ("", "Less: TDS as per certificates from"), ("", "Canara Bank", "", 60000), ("", "Zenith Pharma Pvt Ltd (TDS on rent)", "", 48000)]
book(d5 / "Meera Nair - Income statement AY 2025-26 (as filed in July 2025).xlsx",
     {"IT Statement": base5 + [(), ("", "Income returned", "", 936000)] + tds5})
book(d5 / "Meera Nair - Income missed in the original return AY 2025-26.xlsx",
     {"Missed income": head("Meera Nair", "AYMPN6630Q", "2025-26") + [
         ("", "STATEMENT OF INCOME NOT SHOWN IN THE ORIGINAL RETURN", "", "Amount (Rs)"),
         ("", "Interest on FD with Federal Bank (found in AIS)", "", 900000)]})
s26(d5 / "Meera Nair - 26AS AY 2025-26.txt", "AYMPN6630Q", "Meera Nair", "2024-25", "2025-26",
    [("Canara Bank", "BLRC03344D", "194A", 600000, 60000, "31-Mar-2025"),
     ("Zenith Pharma Private Limited", "HYDZ55667E", "194I(b)", 480000, 48000, "31-Mar-2025")], [])
C[5] = d5
print("files written")
