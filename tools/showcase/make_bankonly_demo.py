"""A made-up bank statement PDF with the SAME LAYOUT as a Kotak-style savings statement (2026-10-13): serial number + date, the
narration wrapping onto two more lines, the reference and the amount and the running balance closing the row, the table head and
the holder / account / page footer repeated on every page, an opening-balance line, UPI credits from members, own-account
transfers both ways, a lender's credit, a PhonePe credit, interest, NACH debits and small personal spends. Every name is
invented (ZZ-names), every number a UPI id of nines - nothing here is a real person's record.

    python tools/showcase/make_bankonly_demo.py           ->  tools/tour_video/showcase/case-bank-only/ (gitignored)
    from tools.showcase.make_bankonly_demo import build   ->  build(drop=None) returns the PDF bytes; drop=<serial> leaves that entry
                                                              out (the running balance then does not fit: "does not add up")
Returns also the truth: build_with_truth() -> (pdf, {"credits": ..., "receipts": ..., ...}) for the e2e test."""
import io
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
_ROOT = Path(__file__).resolve().parents[2]   # repo root: paths never depend on the folder it is started from

HOLDER = "ZZ ANIL KUMAR DEMO"
ACCOUNT = "9900000000042"
IFSC = "KKBK0000042"
MEMBERS = ["ZZ RAVI TEJA DEMO", "ZZ SITA MAHALAKSHMI DEMO", "ZZ KIRAN BABU DEMO", "ZZ LAVANYA DEMO", "ZZ MOHAN RAO DEMO", "ZZ PRIYA SHARMA DEMO",
           "ZZ VENKAT DEMO", "ZZ ASHA LATHA DEMO", "ZZ NIKHIL DEMO", "ZZ DIVYA DEMO", "ZZ SURESH DEMO", "ZZ HEMANTH DEMO"]
FEES = [500, 800, 1000, 1200, 1500, 2000, 2500, 3000]
MERCHANTS = ["ZOMATO", "BLINKIT", "SWIGGY", "BIGBASKET", "DEMO PHARMACY"]
LENDER = "ZZ KREDITBEE DEMO FINANCE"
ROWS_PER_PAGE = 24


def _money(v: float) -> str:
    n = f"{abs(v):.2f}"
    whole, frac = n.split(".")
    head, tail = whole[:-3], whole[-3:]
    while len(head) > 2:
        tail = head[-2:] + "," + tail
        head = head[:-2]
    return (head + "," + tail if head else tail) + "." + frac


def entries(seed: int = 42, n_members: int = 12, months: int = 12) -> tuple[list[dict], float]:
    """The year's entries (date, narration lines, ref, credit, debit, kind) and the opening balance."""
    rnd = random.Random(seed)
    out = []
    d0 = date(2025, 4, 1)
    for m in range(months):
        base = date(2025 + (3 + m) // 12, (3 + m) % 12 + 1, 1)
        for i, who in enumerate(MEMBERS[:n_members]):
            if rnd.random() < 0.15:
                continue
            day = base + timedelta(days=rnd.randint(0, 26))
            out.append({"date": day, "nar": [f"UPI/{who}/5{rnd.randint(10**10, 10**11 - 1)}/Payment", "from Ph"], "ref": f"UPI-5{rnd.randint(10**7, 10**8 - 1)}",
                        "credit": float(rnd.choice(FEES)), "kind": "receipt"})
        for _ in range(rnd.randint(2, 4)):
            day = base + timedelta(days=rnd.randint(0, 27))
            m_ = rnd.choice(MERCHANTS)
            out.append({"date": day, "nar": [f"UPI/{m_}/6{rnd.randint(10**10, 10**11 - 1)}/{m_.title()} Payment"], "ref": f"UPI-6{rnd.randint(10**7, 10**8 - 1)}",
                        "debit": float(rnd.randint(90, 900)), "kind": "personal"})
        if m % 3 == 0:                                            # a loan comes in and goes out the same day
            day = base + timedelta(days=rnd.randint(2, 9))
            out.append({"date": day, "nar": [f"NEFT AXISP00{rnd.randint(10**6, 10**7 - 1)} {LENDER}", f"NEFT-{rnd.randint(10**9, 10**10 - 1)}"], "ref": "",
                        "credit": 15000.0, "kind": "loan"})
            out.append({"date": day, "nar": [f"UPI/{HOLDER}/7{rnd.randint(10**10, 10**11 - 1)}/UPI"], "ref": f"UPI-7{rnd.randint(10**7, 10**8 - 1)}",
                        "debit": 15000.0, "kind": "own"})
        if m % 4 == 1:                                            # money moved in from the holder's other account
            day = base + timedelta(days=rnd.randint(10, 20))
            out.append({"date": day, "nar": [f"UPI/{HOLDER}/8{rnd.randint(10**10, 10**11 - 1)}/UPI"], "ref": f"UPI-8{rnd.randint(10**7, 10**8 - 1)}",
                        "credit": 8000.0, "kind": "own"})
        if m % 3 == 2:                                            # PhonePe credit, then moved on
            day = base + timedelta(days=rnd.randint(10, 20))
            out.append({"date": day, "nar": [f"UPI/PhonePe/9{rnd.randint(10**10, 10**11 - 1)}/C01 Credit by P"], "ref": f"UPI-9{rnd.randint(10**7, 10**8 - 1)}",
                        "credit": 10000.0, "kind": "ask"})
            out.append({"date": day, "nar": [f"UPI/{HOLDER}/7{rnd.randint(10**10, 10**11 - 1)}/UPI"], "ref": f"UPI-7{rnd.randint(10**7, 10**8 - 1)}",
                        "debit": 10000.0, "kind": "own"})
        out.append({"date": base + timedelta(days=27), "nar": [f"NACH-DR-{rnd.randint(10**15, 10**16 - 1)}- {LENDER}"], "ref": "", "debit": 2450.0, "kind": "loan"})
    out.append({"date": date(2025, 6, 30), "nar": ["Int.Pd:9900000000042:01-04-2025 to 30-06-2025"], "ref": "", "credit": 142.0, "kind": "interest"})
    out.append({"date": date(2025, 12, 31), "nar": ["Int.Pd:9900000000042:01-10-2025 to 31-12-2025"], "ref": "", "credit": 187.0, "kind": "interest"})
    out.append({"date": date(2025, 8, 12), "nar": ["REV-UPI/DEMO CARD BILL/4000000000/Refund"], "ref": "", "credit": 1299.0, "kind": "refund"})
    out.sort(key=lambda e: e["date"])
    return out, 1150.25


def build_with_truth(drop: int | None = None, **kw) -> tuple[bytes, dict]:
    ents, opening = entries(**kw)
    bal = opening
    lines_per_row = []
    truth = {"opening": opening, "credits": 0.0, "debits": 0.0, "receipt": 0.0, "own": 0.0, "loan": 0.0, "ask": 0.0, "interest": 0.0, "refund": 0.0, "rows": 0}
    for n, e in enumerate(ents, 1):
        amt = e.get("credit") or e.get("debit")
        bal = round(bal + (e.get("credit", 0.0) - e.get("debit", 0.0)), 2)
        e["n"], e["bal"] = n, bal
        truth["rows"] += 1
        if e.get("credit"):
            truth["credits"] += e["credit"]
            if e["kind"] in truth:
                truth[e["kind"]] += e["credit"]
        else:
            truth["debits"] += e["debit"]
        truth["closing"] = bal
        if drop == n:                                              # the entry is left out of the printout, the balance still moved
            continue
        first = f"{n} {e['date'].strftime('%d %b %Y')} {e['nar'][0]}"
        tail = (e["ref"] + " " if e["ref"] else "") + f"{_money(amt)} {_money(bal)}"
        rest = e["nar"][1:]
        if len(first) > 70 and not rest:
            cut = first.rfind(" ", 0, 70)
            first, rest = first[:cut], [first[cut + 1:]]
        lines_per_row.append([first] + rest + [tail])
    pages = [lines_per_row[i:i + ROWS_PER_PAGE] for i in range(0, len(lines_per_row), ROWS_PER_PAGE)] or [[]]
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    total = len(pages)
    for p, rows in enumerate(pages, 1):
        y = 800

        def put(s: str, bold: bool = False):
            nonlocal y
            c.setFont("Helvetica-Bold" if bold else "Helvetica", 8.5)
            c.drawString(36, y, s)
            y -= 13
        if p == 1:
            put("Account Statement01 Apr 2025 - 31 Mar 2026", True)
            put(HOLDER)
            put("CRN xx*****42")
            put("Flat 42, Demo Residency, Demo Road")
            put("Madhapur, Hyderabad - 500081")
            put("Telangana - India")
            put(f"MICR 500485042   IFSC Code {IFSC}")
            put(f"Account No. {ACCOUNT}")
            put("Account Type  Savings")
            put("Branch Demo Branch, Madhapur")
            put("Account Status Active")
            put("Currency INDIAN RUPEE")
        put("Savings Account Transactions", True)
        put("# Date Description Chq/Ref. No. Withdrawal (Dr.) Deposit (Cr.) Balance")
        if p == 1:
            put(f"- - Opening Balance - - - {_money(opening)}")
        for row in rows:
            for ln in row:
                put(ln)
        y = 60
        put(HOLDER)
        put(f"Account No. {ACCOUNT}")
        put("Account Statement 01 Apr 2025 - 31 Mar 2026")
        put(f"Statement Generated on 13 Oct 2026, 17:25 Page {p} of")
        put(str(total))
        c.showPage()
    c.setFont("Helvetica", 8.5)
    c.drawString(36, 800, "Important Information")
    c.drawString(36, 787, "This is a made-up demo statement. No real bank, person or account.")
    c.showPage()
    c.save()
    truth = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in truth.items()}
    return b.getvalue(), truth


def build(drop: int | None = None, **kw) -> bytes:
    return build_with_truth(drop, **kw)[0]


if __name__ == "__main__":
    out = (_ROOT / "tools/tour_video/showcase/case-bank-only")
    out.mkdir(parents=True, exist_ok=True)
    pdf, truth = build_with_truth()
    (out / "1 Bank statement - Demo Savings - FY 2025-26.pdf").write_bytes(pdf)
    print("written", out, truth)
