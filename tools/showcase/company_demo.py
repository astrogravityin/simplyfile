"""Two made-up companies for ITR-6 (2026-10-11) - every name, PAN, CIN, address and figure invented and plainly marked demo.

  Zenith Demo Traders Private Limited   trading, s.115BAA (22% + 10% surcharge, no MAT), PAN ZZDCZ0061K
  Kaveri Demo Fabricators Private Ltd   manufacturing, normal provisions (25%, turnover of FY 2023-24 within 400 crore) - losses
                                        brought forward wipe out the income, so MAT u/s 115JB is the tax and becomes a credit; additional
                                        depreciation on new machinery; one old loss lapsed; PAN ZZDCK0062L

Each has its documents as a CA's client sends them: the final accounts (Schedule III trading / manufacturing account, P&L, balance
sheet), the computation of income (with the Form 29B book-profit rows for MAT), the fixed-asset schedule (blocks, 180-day split),
and the 26AS text export - every figure row carries its SF Ref, so Intake & map tags them as the CA would.

    python tools/showcase/company_demo.py     ->  tools/tour_video/showcase/company/<company>/   (gitignored)
Imported by tools/e2e_itr6.py and tools/showcase/pre_companies.py (the showcase seed)."""
from __future__ import annotations

import io
from pathlib import Path

from openpyxl import Workbook

AY = "2026-27"

COMPANIES = {
    "zenith": {
        "client": {"name": "Zenith Demo Traders Private Limited", "status": "company", "pan": "ZZDCZ0061K", "gst": "36ZZDCZ0061K1Z5",
                   "email": "accounts@zenith.demo.example", "phone": "9000000061", "dob": "2018-06-14",
                   "address": "Plot 61, Demo Trade Park, Madhapur, Hyderabad 500081", "father": "",
                   "banks": [{"bank": "DEMO BANK LIMITED", "branch": "Madhapur", "type": "Current", "account": "006100610061", "ifsc": "DEMO0000061"}],
                   "notes": "DEMO company - made-up figures for the ITR-6 walk-through.",
                   "parties": [{"name": "Demo Seva Trust", "address": "Demo Colony, Secunderabad 500003", "pan": "ZZDTS0063Q", "relation": "", "mode": ""}],
                   "company": {"cin": "U51909TG2018PTC000061", "incorporated": "2018-06-14", "kind": "private", "option": "115BAA",
                               "option_ay": "2021-22", "option_ack": "610061006100610", "option_date": "2021-11-15", "manufacturing": False,
                               "msme": True, "nature_code": "09018", "trade_name": "Zenith Demo Traders",
                               "directors": [{"name": "Ravi Demo Kumar", "din": "00000061", "pan": "ZZDPK0061A", "designation": "MD", "father": "Sri Demo Kumar",
                                              "address": "Flat 6, Demo Towers, Madhapur, Hyderabad 500081"},
                                             {"name": "Sita Demo Rani", "din": "00000062", "pan": "ZZDPR0062B", "designation": "DIR", "father": "Sri Demo Rao",
                                              "address": "Flat 7, Demo Towers, Madhapur, Hyderabad 500081"}],
                               "shareholders": [{"name": "Ravi Demo Kumar", "pan": "ZZDPK0061A", "pct": 60, "shares": 600000, "face": 10, "issue": 10,
                                                 "allotted": "2018-06-14", "address": "Flat 6, Demo Towers, Madhapur, Hyderabad 500081"},
                                                {"name": "Sita Demo Rani", "pan": "ZZDPR0062B", "pct": 40, "shares": 400000, "face": 10, "issue": 10,
                                                 "allotted": "2018-06-14", "address": "Flat 7, Demo Towers, Madhapur, Hyderabad 500081"}]}},
        "year": {"turnover_py": 1620000000, "s79_ok": True, "dividend_paid": 200000, "dividend_paid_on": "2026-09-15", "bf_losses": [], "mat_credit": []},
        "pl": [("TRADING ACCOUNT", None, None),
               ("Revenue from operations - sale of goods", 185000000, "sales"), ("Opening stock of traded goods", 12000000, "opening_stock"),
               ("Purchases of stock-in-trade", 154000000, "purchases"), ("Freight and carriage inward", 1800000, "carriage"),
               ("Closing stock of traded goods", 14500000, "closing_stock"),
               ("STATEMENT OF PROFIT AND LOSS", None, None),
               ("Interest income on fixed deposits", 600000, "interest_income"), ("Dividend income", 250000, "dividend"),
               ("Salaries and wages", 9200000, "salaries"), ("Bonus", 600000, "bonus"), ("Contribution to provident fund", 720000, "pf"),
               ("Rent", 2400000, "rent"), ("Power and fuel", 480000, "power"), ("Advertisement", 1200000, "advertisement"),
               ("Travelling", 540000, "travel"), ("Legal and professional charges", 660000, "professional"), ("Telephone and internet", 180000, "telephone"),
               ("Auditor's remuneration", 300000, "audit_fee"), ("Insurance", 240000, "insurance"), ("Donation", 100000, "donation"),
               ("Other expenses", 320000, "other_expenses"), ("Finance costs - interest", 900000, "interest"),
               ("Depreciation and amortisation", 840000, "depreciation"), ("Provision for current tax", 3500000, "tax_provision_pl")],
        "bs": [("BALANCE SHEET AS AT 31.03.2026", None, None),
               ("Share capital - issued, subscribed and paid up", 10000000, "capital"), ("Surplus in statement of profit and loss", 34370000, "pl_surplus"),
               ("Long-term borrowings - term loan from bank (secured)", 6000000, "secured_bank"), ("Trade payables", 21000000, "creditors"),
               ("Other current liabilities", 1830000, "other_liabilities"), ("Provision for income tax", 3500000, "tax_provision"),
               ("Provision for bonus", 200000, "emp_provision"),
               ("Property, plant and equipment - gross block", 7000000, "gross_block"), ("Less: accumulated depreciation", 2500000, "acc_depreciation"),
               ("Non-current investments", 4000000, "investments"), ("Security deposits", 1200000, "deposits"), ("Inventories - stock-in-trade", 14500000, "stock"),
               ("Trade receivables", 31000000, "debtors"), ("Balances with banks", 16065000, "bank"), ("Cash on hand", 300000, "cash"),
               ("Short-term loans and advances", 1800000, "advances_given"), ("Advance tax and TDS", 3535000, "tax_balances")],
        "comp": [("COMPUTATION OF TOTAL INCOME - AY 2026-27", None, None),
                 ("Profit before tax as per statement of profit and loss", 13870000, "ITR6 BP profit"),
                 ("Add: Depreciation as per books", 840000, "ITR6 BP book_dep"),
                 ("Add: Donation - not a business expense", 100000, "ITR6 BP s37"),
                 ("Add: Interest on late payment of TDS", 20000, "ITR6 BP s37"),
                 ("Add: Bonus provision not paid by the due date (s.43B)", 200000, "ITR6 BP s43b"),
                 ("Less: Dividend income - other sources", 250000, "ITR6 BP dividend"),
                 ("Less: Interest income - other sources", 600000, "ITR6 BP os_income"),
                 ("INCOME FROM OTHER SOURCES", None, None),
                 ("Dividend from Demo Holdings Limited", 250000, "ITR6 OS dividend"),
                 ("Interest on fixed deposits with Demo Bank", 600000, "ITR6 OS deposit"),
                 ("DONATIONS", None, None),
                 ("Demo Seva Trust", 100000, "ITR6 80G 50q")],
        "dep": [("pm15", "Plant and machinery", 3000000, 400000, 200000, 0, 0, 0), ("furn10", "Furniture and fittings", 800000, 0, 0, 0, 0, 0),
                ("pm40", "Computers", 300000, 0, 150000, 0, 0, 0)],
        "tds": [("DEMO BANK LIMITED", "HYDD00061B", "194A", 600000, 60000), ("DEMO HOLDINGS LIMITED", "HYDD00064C", "194", 250000, 25000)],
        "paid": [("15-Jun-2025", 500000, "0061001", 61001), ("15-Sep-2025", 1100000, "0061001", 61002), ("15-Dec-2025", 1050000, "0061001", 61003),
                 ("15-Mar-2026", 800000, "0061001", 61004)]},
    "kaveri": {
        "client": {"name": "Kaveri Demo Fabricators Private Limited", "status": "company", "pan": "ZZDCK0062L", "gst": "36ZZDCK0062L1Z3",
                   "email": "accounts@kaveri.demo.example", "phone": "9000000062", "dob": "2015-02-02",
                   "address": "Survey 62, Demo Industrial Area, Patancheru, Sangareddy 502319", "father": "",
                   "banks": [{"bank": "DEMO BANK LIMITED", "branch": "Patancheru", "type": "Cash credit", "account": "006200620062", "ifsc": "DEMO0000062"}],
                   "notes": "DEMO company - made-up figures for the ITR-6 walk-through (MAT, losses, additional depreciation).",
                   "company": {"cin": "U28999TG2015PTC000062", "incorporated": "2015-02-02", "kind": "private", "option": "normal",
                               "manufacturing": True, "msme": False, "nature_code": "04060", "trade_name": "Kaveri Demo Fabricators",
                               "directors": [{"name": "Kiran Demo Reddy", "din": "00000063", "pan": "ZZDPR0063C", "designation": "MD", "father": "Sri Demo Reddy",
                                              "address": "Villa 3, Demo Enclave, Patancheru 502319"},
                                             {"name": "Lata Demo Reddy", "din": "00000064", "pan": "ZZDPR0064D", "designation": "DIR", "father": "Sri Demo Naidu",
                                              "address": "Villa 3, Demo Enclave, Patancheru 502319"}],
                               "shareholders": [{"name": "Kiran Demo Reddy", "pan": "ZZDPR0063C", "pct": 55, "shares": 2750000, "face": 10, "issue": 12,
                                                 "allotted": "2015-02-02", "address": "Villa 3, Demo Enclave, Patancheru 502319"},
                                                {"name": "Lata Demo Reddy", "pan": "ZZDPR0064D", "pct": 25, "shares": 1250000, "face": 10, "issue": 12,
                                                 "allotted": "2015-02-02", "address": "Villa 3, Demo Enclave, Patancheru 502319"},
                                                {"name": "Demo Ventures LLP", "pan": "ZZDFV0065E", "pct": 20, "shares": 1000000, "face": 10, "issue": 30,
                                                 "allotted": "2021-08-20", "address": "Demo Plaza, Banjara Hills, Hyderabad 500034"}]}},
        "year": {"turnover_py": 620000000, "s79_ok": True, "dividend_paid": 0, "dividend_paid_on": "",
                 "bf_losses": [{"ay": "2017-18", "business": 500000, "dep": 0, "filed_on": "2017-10-30", "filed_ok": True},
                               {"ay": "2023-24", "business": 11000000, "dep": 0, "filed_on": "2023-10-28", "filed_ok": True},
                               {"ay": "2024-25", "business": 0, "dep": 4000000, "filed_on": "2024-10-29", "filed_ok": True}],
                 "mat_credit": [{"ay": "2022-23", "amount": 600000}]},
        "pl": [("MANUFACTURING ACCOUNT", None, None),
               ("Opening stock of raw material", 6000000, "opening_raw"), ("Opening work-in-progress", 2000000, "opening_wip"),
               ("Raw material purchased", 210000000, "raw_purchases"), ("Direct wages", 18000000, "direct_wages"),
               ("Factory power and fuel", 9500000, "factory_power"), ("Factory expenses", 4000000, "factory_exp"),
               ("Closing stock of raw material", 7000000, "closing_raw"), ("Closing work-in-progress", 2500000, "closing_wip"),
               ("TRADING ACCOUNT", None, None),
               ("Revenue from operations - sale of fabricated products", 300000000, "sales"), ("Opening stock of finished goods", 10000000, "opening_stock"),
               ("Closing stock of finished goods", 12000000, "closing_stock"),
               ("STATEMENT OF PROFIT AND LOSS", None, None),
               ("Interest income", 400000, "interest_income"), ("Salaries", 11000000, "salaries"), ("Bonus", 900000, "bonus"),
               ("Contribution to provident fund", 1200000, "pf"), ("Rent", 600000, "rent"), ("Repairs to machinery", 1800000, "repairs_machinery"),
               ("Insurance", 500000, "insurance"), ("Advertisement", 400000, "advertisement"), ("Travelling", 800000, "travel"),
               ("Legal and professional charges", 1000000, "professional"), ("Auditor's remuneration", 400000, "audit_fee"),
               ("Corporate social responsibility expenditure", 600000, "csr_exp"), ("Other expenses", 1200000, "other_expenses"),
               ("Finance costs - interest", 12000000, "interest"), ("Depreciation and amortisation", 14000000, "depreciation"),
               ("Provision for current tax (MAT)", 2800000, "tax_provision_pl"), ("Deferred tax", 600000, "deferred_tax_pl")],
        "bs": [("BALANCE SHEET AS AT 31.03.2026", None, None),
               ("Share capital - issued, subscribed and paid up", 50000000, "capital"), ("Securities premium", 10000000, "securities_premium"),
               ("Surplus in statement of profit and loss", 2600000, "pl_surplus"), ("Term loans from banks (secured)", 90000000, "secured_bank"),
               ("Loans from directors", 15000000, "director_loans"), ("Deferred tax liability (net)", 4600000, "deferred_tax"),
               ("Trade payables", 48000000, "creditors"), ("Current maturities of long-term debt", 12000000, "current_maturities"),
               ("Other current liabilities", 6000000, "other_liabilities"), ("Provision for income tax", 2800000, "tax_provision"),
               ("Provision for employee benefits", 1800000, "emp_provision"),
               ("Property, plant and equipment - gross block", 180000000, "gross_block"), ("Less: accumulated depreciation", 65000000, "acc_depreciation"),
               ("Capital work-in-progress", 12000000, "cwip"), ("Security deposits", 3000000, "deposits"), ("Inventories - raw material", 7000000, "raw_material"),
               ("Inventories - work-in-progress", 2500000, "wip"), ("Inventories - finished goods", 12000000, "stock"), ("Trade receivables", 64000000, "debtors"),
               ("Balances with banks", 13200000, "bank"), ("Cash on hand", 200000, "cash"), ("Short-term loans and advances", 6000000, "advances_given"),
               ("Advance tax and TDS", 2190000, "tax_balances"), ("Other current assets", 5710000, "other_current")],
        "comp": [("COMPUTATION OF TOTAL INCOME - AY 2026-27", None, None),
                 ("Profit before tax as per statement of profit and loss", 16000000, "ITR6 BP profit"),
                 ("Add: Depreciation as per books", 14000000, "ITR6 BP book_dep"),
                 ("Add: CSR expenditure (Explanation 2 to s.37(1))", 600000, "ITR6 BP csr"),
                 ("Add: Leave encashment provision unpaid (s.43B)", 300000, "ITR6 BP s43b"),
                 ("Add: MSME dues unpaid beyond 45 days (s.43B(h))", 250000, "ITR6 BP s43b"),
                 ("Add: Professional fees - TDS not deducted (s.40(a)(ia))", 100000, "ITR6 BP s40"),
                 ("Less: Interest income - other sources", 400000, "ITR6 BP os_income"),
                 ("Less: s.43B items of last year paid this year", 150000, "ITR6 BP s43b_paid"),
                 ("INCOME FROM OTHER SOURCES", None, None),
                 ("Interest on deposits with Demo Bank", 400000, "ITR6 OS deposit"),
                 ("BOOK PROFIT U/S 115JB (FORM 29B)", None, None),
                 ("Net profit after tax as per statement of profit and loss", 12600000, "ITR6 MAT pat"),
                 ("Add: Income-tax provision including deferred tax", 3400000, "ITR6 MAT add_tax"),
                 ("Less: Lower of brought-forward loss or unabsorbed depreciation as per books", 2000000, "ITR6 MAT less_bf")],
        "dep": [("pm15", "Plant and machinery", 60000000, 10000000, 4000000, 2000000, 10000000, 4000000, 200000),
                ("bldg10", "Factory building", 25000000, 0, 0, 0, 0, 0, 0), ("pm40", "Computers", 1000000, 500000, 0, 0, 0, 0, 0),
                ("furn10", "Furniture and fittings", 1200000, 0, 0, 0, 0, 0, 0)],
        "tds": [("DEMO BANK LIMITED", "HYDD00062B", "194A", 400000, 40000), ("DEMO STEEL BUYERS LIMITED", "HYDD00066E", "194Q", 150000000, 150000),
                ("DEMO INFRA PROJECTS LIMITED", "HYDD00067F", "194Q", 100000000, 100000)],
        "paid": [("15-Jun-2025", 300000, "0062001", 62001), ("15-Sep-2025", 600000, "0062001", 62002), ("15-Dec-2025", 600000, "0062001", 62003),
                 ("15-Mar-2026", 400000, "0062001", 62004)]},
}


def _book(title: str, sections: list[tuple], ref_prefix: str = "ITR6 {t} ") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Accounts"
    ws.append([title + "  (DEMO - made-up figures)"])
    ws.append(["Financial year ended 31.03.2026 - for AY " + AY])
    ws.append([])
    table = ""
    for label, amount, item in sections:
        if amount is None:
            table = "BS" if "BALANCE" in label.upper() else "PL"
            ws.append([])
            ws.append([label, "Amount (Rs)", "SF Ref"])
            continue
        ws.append([label, amount, item if item.startswith("ITR6") else ref_prefix.format(t=table) + item])
    ws.column_dimensions["A"].width = 70
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _dep(name: str, rows: list[tuple]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Fixed assets"
    ws.append([name + " - Statement of depreciation as per the Income-tax Act (DEMO)"])
    ws.append([])
    ws.append(["Block of assets", "WDV as on 01.04.2025", "Additions - put to use 180 days or more", "Additions - put to use less than 180 days",
               "Sale / deletion", "New P&M - 180 days or more", "New P&M - less than 180 days", "Additional depreciation b/f", "SF Ref"])
    for r in rows:
        blk, label, *nums = r
        nums = (list(nums) + [0] * 7)[:7]
        ws.append([label] + nums + [f"ITR6 DEP {blk}"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _26as(c: dict, x: dict) -> bytes:
    pan, name = c["pan"], c["name"].upper()
    lines = ["^Annual Tax Statement^", f"^Permanent Account Number (PAN)^{pan}^Current Status of PAN^Active^Financial Year^2025-26^Assessment Year^{AY}^",
             f"^Name of Assessee^{name}^", "^PART-I - Details of Tax Deducted at Source^",
             "^Sr. No.^Name of Deductor^TAN of Deductor^^^^^Total Amount Paid / Credited(Rs.)^Total Tax Deducted #(Rs.)^Total TDS Deposited(Rs.)"]
    for i, (who, tan, sec, gross, tax) in enumerate(x["tds"], 1):
        lines += [f"^{i}^{who}^{tan}^^^^^{gross:.2f}^{tax:.2f}^{tax:.2f}",
                  "^^Sr. No.^Section^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited(Rs.)^Tax Deducted ##(Rs.)^TDS Deposited(Rs.)",
                  f"^^1^{sec}^31-Mar-2026^F^15-May-2026^-^{gross:.2f}^{tax:.2f}^{tax:.2f}"]
    lines += ["^PART-III - Details of Tax Paid (other than TDS or TCS)^",
              "^Sr. No.^Major Head^Minor Head^Tax (Rs.)^Surcharge (Rs.)^Education Cess (Rs.)^Others (Rs.)^Total Tax (Rs.)^BSR Code^Date of Deposit^Challan Serial Number^Remarks**"]
    for i, (on, amt, bsr, serial) in enumerate(x["paid"], 1):
        lines.append(f"^{i}^0020^100^{amt:.2f}^0.00^0.00^0.00^{amt:.2f}^{bsr}^{on}^{serial}^")
    return ("\n".join(lines) + "\n").encode("utf-8")


def documents(key: str) -> list[tuple[str, bytes]]:
    """(file name, bytes) for one demo company, in the order a CA would upload them."""
    x = COMPANIES[key]
    c = x["client"]
    short = c["name"].replace(" Private Limited", "")
    return [(f"01 Final accounts - {short} FY 2025-26.xlsx", _book(c["name"] + " - Final accounts", x["pl"] + x["bs"])),
            (f"02 Computation of income - {short} AY {AY}.xlsx", _book(c["name"] + " - Computation of income", x["comp"])),
            (f"03 Fixed asset schedule - {short} FY 2025-26.xlsx", _dep(c["name"], x["dep"])),
            (f"04 26AS - {c['pan']} - AY {AY}.txt", _26as(c, x))]


if __name__ == "__main__":
    out = Path("tools/tour_video/showcase/company")
    for key in COMPANIES:
        d = out / key
        d.mkdir(parents=True, exist_ok=True)
        for name, data in documents(key):
            (d / name).write_bytes(data)
        print("wrote", d, len(documents(key)), "files")
