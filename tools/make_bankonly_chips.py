"""2026-10-13 SimplyFy, "Small business - only a bank statement": a gym trainer (and any small trader / service provider) with no
books and no Form 16 - the bank statement alone goes through to an ITR-4 (presumptive, s.44AD) JSON.

Writes / updates the chips (every pattern, word, list and threshold of the path is a chip with test cases):
  bank.statement   the serial-numbered statement layout (rows, wrapped narration, page header / footer lines, opening / closing
                   balance, the holder, account, IFSC, address) - read by myreturn_read.bank_pdf_serial
  bank.classify    what a credit / debit is: counterparty patterns, own-name comparison, lender / merchant words, rules in order,
                   the classes the person taps, the pass-through check, thresholds (read by bankclass.py)
  bank.gst_gap     the GST registration limit for a service / goods supplier and whether the turnover is over it (s.22 CGST)
  bank.upload      the plain-words steps of uploading the JSON on the income-tax portal (a list the page draws)
  ui.bankonly      every word of the Classify step, the path and its notes
and adds knobs to existing chips (wizard.scenarios, wizard.docs, wizard.doc_need, wizard.asks, wizard.settings, myreturn.steps,
ui.myreturn, ui.wizard, myreturn.sniff).
Re-runnable.   Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/make_bankonly_chips.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "chips"
sys.path.insert(0, str(ROOT))
NOTE = "2026-10-13: "


def read(cid):
    return json.loads((CH / f"{cid}.json").read_text(encoding="utf-8"))


def write(c):
    (CH / f"{c['chip_id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def record_chip(cid, sett, label, desc, fields):
    """A chip that hands back its own knobs: one param per field (default = the value), expr a record of them; the one test says
    the defaults."""
    c = {"chip_id": cid, "kind": "accessor", "set": sett, "label": label, "aliases": [label.lower()[:40]],
         "params": [{"name": n, "type": "text" if isinstance(v, str) else "boolean" if isinstance(v, bool) else "number" if isinstance(v, (int, float)) else "json",
                     "default": v, "label": n.replace("_", " ")} for n, v in fields.items()],
         "expr": {"vop": "record", "fields": {n: f"${n}" for n in fields}}, "returns": "record", "version": 1, "status": "published",
         "description_nl": NOTE + desc, "test_cases": [{"args": {}, "expect_value": fields}]}
    old = CH / f"{cid}.json"
    if old.exists():
        o = read(cid)
        c["version"] = o["version"] + (0 if o["params"] == c["params"] else 1)
    write(c)
    print("wrote", cid)


# --- the statement reader ----------------------------------------------------------------------------------------------------
STATEMENT = {
    "row_start": r"^\s*(\d{1,6})\s+(\d{1,2}[ \-/.][A-Za-z]{3}[ \-/.]\d{2,4}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\s*(.*)$",
    "table_head": r"(?i)^\s*#?\s*(?:sr\.?\s*no\.?\s*)?date\b.*\b(?:description|narration|particulars|details)\b",
    "opening": r"(?i)opening\s+balance\D{0,12}(-?[\d,]+\.\d{2})",
    "closing": r"(?im)^\s*closing\s+balance\D{0,12}(-?[\d,]+\.\d{2})",
    "holder": [r"(?m)^([^\n]+)\nAccount No\.?\s*\d+\s*\nAccount Statement",
               r"(?mi)^Account Statement[^\n]*\n([^\n]+)\n(?:CRN|[^\n]*\n[^\n]*MICR)",
               r"(?im)^\s*(?:account holder|customer name|account name|name)\s*[:\-]\s*(.+?)\s*$"],
    "account": r"(?i)Account\s*(?:No|Number)\.?\s*:?\s*(\d{6,18})",
    "ifsc": r"(?i)\bIFSC(?:\s*Code)?\s*:?\s*([A-Z]{4}0[A-Z0-9]{6})\b",
    "ifsc_banks": {"KKBK": "Kotak Mahindra Bank", "HDFC": "HDFC Bank", "ICIC": "ICICI Bank", "SBIN": "State Bank of India", "UTIB": "Axis Bank",
                   "PUNB": "Punjab National Bank", "BARB": "Bank of Baroda", "CNRB": "Canara Bank", "IDIB": "Indian Bank", "YESB": "Yes Bank",
                   "INDB": "IndusInd Bank", "IDFB": "IDFC First Bank", "FDRL": "Federal Bank", "UBIN": "Union Bank of India", "BKID": "Bank of India",
                   "KARB": "Karnataka Bank", "RATN": "RBL Bank", "SIBL": "South Indian Bank", "MAHB": "Bank of Maharashtra", "CBIN": "Central Bank of India"},
    "address": r"(?ms)^Account Statement[^\n]*\n[^\n]+\n(?:CRN[^\n]*\n)?(.+?)\n[^\n]*MICR",
    "pin": r"\b([1-9]\d{5})\b",
    "page_join": [r"(Page\s+\d+\s+of)\s*\n\s*(\d+)", r"\1 \2"],
    "skip_lines": [r"^\s*Account Statement\b", r"^\s*Account No\.?\b", r"^\s*Statement Generated\b", r"^\s*Page\s+\d+\s+of\s+\d+",
                   r"^\s*[A-Za-z ]*Account Transactions\s*$", r"^\s*#?\s*(?:Sr\.?\s*No\.?\s*)?Date\s+(?:Description|Narration|Particulars)",
                   r"^\s*$", r"^\s*Opening Balance\b", r"^\s*-\s+-\s+Opening Balance"],
    "stop_lines": [r"^\s*Important Information", r"^\s*Closing Balance\b", r"^\s*Statement Summary", r"^\s*End of Statement", r"^\s*Legends?\b",
                   r"^\s*Total\s+(?:Debit|Credit|Withdrawal|Deposit)"],
    "amount": r"-?\d[\d,]*\.\d{2}",
    "ref": r"(?:^|\s)((?:UPI|IMPS|NEFT|RTGS|CHQ|NACH|ATM|POS|MB|IB|ECS)[-/]?[A-Z0-9*]{5,})\s*$",
    "date_formats": ["%d %b %Y", "%d-%b-%Y", "%d/%b/%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"],
    "tolerance": 0.01,
    "min_rows": 1,
    "marks": {"debit": ["dr", "d"], "credit": ["cr", "c"]},
    "bad_rows_shown": 8,
}

# --- what a credit / debit is --------------------------------------------------------------------------------------------------
LENDERS = ["kreditbee", "krazybee", "navi", "slice", "paytm postpaid", "postpaid", "lazypay", "simpl", "zestmoney", "kissht", "moneyview",
           "money view", "cashe", "earlysalary", "early salary", "fibe", "stashfin", "mpokket", "truebalance", "true balance", "dhani",
           "indiabulls", "bajaj finserv", "bajaj finance", "hdb financial", "tata capital", "aditya birla", "poonawalla", "fullerton",
           "muthoot", "manappuram", "iifl", "lendingkart", "capital float", "flexsalary", "olyv", "nira finance", "smartcoin", "moneytap",
           "loantap", "branch international", "credy", "rupeeredee", "fatakpay", "ramfin", "snapmint", "kredx", "axio", "freo", "payme india",
           "home credit", "hero fincorp", "piramal", "ujjivan", "satin", "creditaccess", "jana small", "finserv", "microfin", "fincorp",
           "capital limit", "capital ltd", "capital serv", "capital pvt", "finance lim", "finance ltd", "finance pvt", "nbfc", " capital ", " finance ", " finserv ", " fincorp ",
           "loan", "emi "]
MERCHANTS = ["zomato", "swiggy", "blinkit", "zepto", "bigbasket", "amazon", "flipkart", "myntra", "meesho", "uber", "ola ", "rapido",
             "irctc", "makemytrip", "bookmyshow", "netflix", "spotify", "google play", "apple", "jio", "airtel", "vodafone", "bsnl",
             "phonepe merchant", "razorpay", "payu", "cashfree", "billdesk", "paytm", "cred", "dmart", "reliance", "star bazaar",
             "more retail", "decathlon", "croma", "nykaa", "pharmeasy", "1mg", "apollo pharmacy", "medplus", "petrol", "fuel", "metro",
             "bescom", "electricity", "insurance", "lic ", "mutual fund", "groww", "zerodha", "upstox", "cult.fit", "cultfit"]
CLASSIFY = {
    "ui_credit": ["receipt", "cash", "own", "loan", "other"],
    "ui_debit": ["personal", "business", "own", "loan"],
    "cash_choice_for": ["cash"],
    "default_credit": "receipt",
    "default_debit": "personal",
    "counterparty": [r"^UPI/([^/]*)/", r"^(?:REV-)?UPI/([^/]*)/", r"^(?:NEFT|RTGS|IMPS)[-/ ]*(?:CR[-/ ]*|DR[-/ ]*)?[A-Z0-9*]{6,}\s+(.+?)(?:\s+[A-Z0-9*]{8,})?$",
                     r"^NACH[-A-Z]*\s*[-0-9A-Z]*\s*[-]?\s*\d*\s+(.+?)(?:\s+\d[\d ]*)?$", r"^(?:CLG TO|CLG FROM|BY CLG|TO|BY)\s+(.+?)(?:\s+\d.*)?$"],
    "name_noise": r"[^a-z ]+",
    "name_min_letters": 3,
    "name_max": 40,
    "own_min_letters": 5,
    "own_ratio": 0.85,
    "own_words": ["self", "own a/c", "own account", "to self", "from self", "sweep", "fd closure", "fd proceeds", "td closure", "rd closure", "redemption"],
    "credit_rules": [
        {"kind": "own", "by": "holder"},
        {"kind": "interest", "words": ["int.pd", "int pd", "int.cr", " interest ", "sb int", "int credit", "int.coll"]},
        {"kind": "refund", "words": ["rev-", "reversal", "reversed", "refund", "chargeback", "cashback", "imps return", "return of"]},
        {"kind": "own", "by": "own_words"},
        {"kind": "loan", "words": LENDERS},
        {"kind": "cash", "words": ["cash dep", "by cash", "cash deposit", "cdm", "csh dep", "cash-dep"]},
        {"kind": "salary", "words": ["salary", "sal cr", "payroll"]},
        {"kind": "ask", "words": ["credit by p", "phonepe credit", "credit line", "wallet load", "added to wallet", "pocket"]},
        {"kind": "ask", "words": [" limite", " ltd", " pvt", " private ", " llp", " corporation", " enterprises", " bank "]},
        {"kind": "refund", "words": MERCHANTS},
    ],
    "debit_rules": [
        {"kind": "own", "by": "holder"},
        {"kind": "own", "by": "own_words"},
        {"kind": "loan", "words": LENDERS + ["nach", "ecs ", "si cr", "auto debit"]},
        {"kind": "tax", "words": ["income tax", "gst ", "tds ", "advance tax", "challan"]},
        {"kind": "personal", "words": MERCHANTS},
    ],
    "kind_class": {"receipt": "receipt", "cash": "cash", "own": "own", "loan": "loan", "refund": "other", "interest": "other",
                   "salary": "other", "ask": "ask", "personal": "personal", "tax": "business", "business": "business"},
    "income_kinds": ["interest"],
    "salary_kinds": ["salary"],
    "passthrough": {"days": 2, "tolerance": 1.0, "min_amount": 5000, "share": 0.5},
    "watch": {"round_to": 1000, "min_amount": 10000, "share": 0.5},
    "group_show": 12,
    "common_codes": ["20023", "20020", "20021", "21001", "21005", "17006", "14009", "09021", "10008", "09002"],
    "top_names": 6,
}

# --- GST registration limit --------------------------------------------------------------------------------------------------
GST_PARAMS = {
    "supply": ("text", "services", "goods or services"),
    "turnover": ("number", 0, "aggregate turnover of the year"),
    "special_state": ("boolean", False, "a special-category state (Manipur, Mizoram, Nagaland, Tripura for services)"),
    "services_limit": ("number", 2000000, "services: Rs 20 lakh - s.22(1) CGST Act, notification 10/2017-CT"),
    "services_limit_special": ("number", 1000000, "services, special-category state: Rs 10 lakh"),
    "goods_limit": ("number", 4000000, "goods: Rs 40 lakh - notification 10/2019-CT"),
    "goods_limit_special": ("number", 2000000, "goods, special-category state: Rs 20 lakh"),
    "near_pct": ("number", 80, "within this percent of the limit: say so"),
}
SPECIAL_STATES = ["Manipur", "Mizoram", "Nagaland", "Tripura"]
SPECIAL_CODES = ["20", "22", "23", "30"]

UPLOAD_STEPS = [
    "Download the JSON file from {product} to your phone or computer. Do not open or edit it.",
    "Go to incometax.gov.in and log in with your PAN and password. Keep your mobile near you for the OTP.",
    "Click e-File, then Income Tax Returns, then File Income Tax Return.",
    "Choose Assessment Year 2026-27, mode Online, and your status Individual. Click Continue.",
    "Choose Upload (import) a JSON file instead of filling the form, pick the ITR-4 JSON, and upload it.",
    "The portal checks the file. If it says errors, tell us the message - do not change the file yourself.",
    "Check the summary, tick the declaration, and pay any tax due through e-Pay Tax (a challan), then come back to Submit.",
    "Verify the return - Aadhaar OTP is quickest. The return is not filed until it is verified (within 30 days).",
]


def gst_chip():
    p = [{"name": n, "type": t, "default": d, "label": lbl} for n, (t, d, lbl) in GST_PARAMS.items()]
    sup = {"op": "eq", "left": "$supply", "right": "goods"}
    lim = {"vop": "choose", "cases": [
        {"when": {"op": "all", "items": [sup, "$special_state"]}, "then": "$goods_limit_special"},
        {"when": sup, "then": "$goods_limit"},
        {"when": "$special_state", "then": "$services_limit_special"}], "else": "$services_limit"}
    expr = {"vop": "record", "fields": {
        "limit": lim,
        "over": {"op": "gt", "left": "$turnover", "right": lim},
        "near": {"op": "all", "items": [
            {"op": "ge", "left": {"vop": "mul", "a": "$turnover", "b": 100}, "right": {"vop": "mul", "a": lim, "b": "$near_pct"}},
            {"op": "le", "left": "$turnover", "right": lim}]},
        "special": "$special_state"}}

    def t(args, over, near, limit):
        return {"args": args, "expect_value": {"limit": limit, "over": over, "near": near, "special": bool(args.get("special_state"))}}
    c = {"chip_id": "bank.gst_gap", "kind": "accessor", "set": "bank", "label": "Bank only: the GST registration limit and whether the turnover is over it",
         "aliases": ["bank only: the gst registration limit"], "params": p, "expr": expr, "returns": "record", "version": 1, "status": "published",
         "description_nl": NOTE + "A service supplier is liable to register under GST above Rs 20 lakh aggregate turnover in the year (Rs 10 lakh in the special-"
         "category states Manipur, Mizoram, Nagaland and Tripura); a goods supplier above Rs 40 lakh (Rs 20 lakh). s.22(1) CGST Act 2017, notifications "
         "10/2017-CT and 10/2019-CT. {product} warns - it does not register.",
         "test_cases": [t({}, False, False, 2000000), t({"turnover": 1700000}, False, True, 2000000), t({"turnover": 2000001}, True, False, 2000000),
                        t({"turnover": 1500000, "special_state": True}, True, False, 1000000),
                        t({"supply": "goods", "turnover": 3000000}, False, False, 4000000),
                        t({"supply": "goods", "turnover": 2500000, "special_state": True}, True, False, 2000000)]}
    write(c)
    print("wrote bank.gst_gap")


TOUR_MASK = {
    "patterns": [
        {"id": "pan", "regex": r"\b[A-Za-z]{5}[0-9]{4}[A-Za-z]\b"},
        {"id": "aadhaar", "regex": r"\b[2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4}\b"},
        {"id": "phone", "regex": r"(?:\+91[ -]?)?\b[6-9][0-9]{9}\b"},
        {"id": "account", "regex": r"\b[0-9]{9,18}\b"},
        {"id": "email", "regex": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"},
        {"id": "upi_id", "regex": r"\b[A-Za-z0-9._-]{2,}@[a-z]{2,}\b"},
        {"id": "upi_ref", "regex": r"\bUPI-[0-9*]{6,}\b"},
        {"id": "pin", "regex": r"\b[1-9][0-9]{5}\b"},
        {"id": "ifsc", "regex": r"\b[A-Z]{4}0[A-Z0-9]{6}\b"},
    ],
    "selectors": ["[data-sens]", "#whoami", "#userpop .head", "input[type=password]", ".bk-who b", ".wz-ask-f input"],
    "blur_px": 9,
    "min_word": 3,
    "audit": True,
}


def check_chip():
    """What a read bank statement adds to the Check step: a red one when it does not add up, an amber one while credits are undecided."""
    p = [{"name": "what", "type": "text", "default": "bank_recon", "label": "bank_recon or bank_undecided"},
         {"name": "recon_ok", "type": "boolean", "default": True, "label": "the statement adds up"},
         {"name": "undecided", "type": "number", "default": 0, "label": "credit groups not decided"}]
    bad = {"op": "eq", "left": "$recon_ok", "right": False}
    lvl = {"vop": "choose", "cases": [
        {"when": {"op": "all", "items": [{"op": "eq", "left": "$what", "right": "bank_recon"}, bad]}, "then": "bad"},
        {"when": {"op": "all", "items": [{"op": "eq", "left": "$what", "right": "bank_undecided"}, {"op": "gt", "left": "$undecided", "right": 0}]},
         "then": "warn"}], "else": "ok"}
    expr = {"vop": "record", "fields": {"what": "$what", "level": lvl, "word": {"vop": "choose", "cases": [
        {"when": {"op": "eq", "left": "$what", "right": "bank_recon"}, "then": "lv_bank_recon"}], "else": "lv_bank_undecided"},
        "a": "$undecided", "b": 0, "gap": 0}}

    def t(args, level):
        what = args.get("what", "bank_recon")
        return {"args": args, "expect_value": {"what": what, "level": level, "word": "lv_bank_recon" if what == "bank_recon" else "lv_bank_undecided",
                                               "a": args.get("undecided", 0), "b": 0, "gap": 0}}
    c = {"chip_id": "bank.check", "kind": "accessor", "set": "bank", "label": "Bank only: the checks a read bank statement adds",
         "aliases": ["bank only: the checks a read bank statement adds"], "params": p, "expr": expr, "returns": "record", "version": 1,
         "status": "published", "description_nl": NOTE + "bank_recon is red when opening + credits - debits is not the closing balance or an entry is "
         "missing; bank_undecided is amber while credit groups are left as Not sure.",
         "test_cases": [t({}, "ok"), t({"recon_ok": False}, "bad"), t({"what": "bank_undecided", "undecided": 2}, "warn"),
                        t({"what": "bank_undecided", "recon_ok": False}, "ok")]}
    write(c)
    print("wrote bank.check")


def main():
    record_chip("bank.statement", "bank", "Bank only: how a serial-numbered bank statement is read",
                "The layout of a bank statement PDF whose rows start with a serial number and a date, the narration wraps onto the next "
                "lines and the amount and balance close the row; its page headers and footers; the holder, account and address.", STATEMENT)
    record_chip("bank.classify", "bank", "Bank only: what each credit and debit of a bank statement is",
                "Counterparty patterns, the holder-name comparison, lender and merchant words, the rules in order (first match wins), the "
                "classes the person taps, the pass-through check and the watch thresholds. Words are matched in the lower-case narration.",
                CLASSIFY)
    gst_chip()
    record_chip("bank.upload", "bank", "Bank only: the steps of uploading the JSON on the income-tax portal",
                "Plain words, in order - the page draws them as a numbered list.", {"steps": UPLOAD_STEPS, "portal": "incometax.gov.in"})
    record_chip("bank.special_states", "bank", "Bank only: the special-category states for the GST limit",
                "Services: Manipur, Mizoram, Nagaland, Tripura (notification 10/2017-CT). Compared with the state of the person's address.",
                {"states": SPECIAL_STATES, "codes": SPECIAL_CODES})
    check_chip()
    record_chip("tour.mask", "tour", "Tour recorder: what is blurred when a real record is shown (privacy mask)",
                "TOUR_MASK=1 (or a tour's \"mask\": true) blurs, before every frame, anything matching these patterns, every element matching these "
                "selectors (data-sens is the attribute the pages put on names and numbers), and every word of the file named by TOUR_MASK_WORDS "
                "(the holder's and counterparties' names, read at record time - never kept in the repo). A leak left on screen fails the recording.",
                TOUR_MASK)


if __name__ == "__main__":
    main()
