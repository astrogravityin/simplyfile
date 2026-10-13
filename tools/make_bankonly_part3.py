"""2026-10-13 "Small business - only a bank statement", part 3: Chip Chat FAQ rows, the Guide me steps (guide.wizard, guide.myreturn) and
the worked example (wizard.cases row bank_only: documents from tools/showcase/make_bankonly_demo.py, a tour with the Classify, tax and
JSON steps). Re-runnable.   Run from D:/Simplyfile after part 1 / 2:  .venv/Scripts/python.exe tools/make_bankonly_part3.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_bankonly_part2 as m2  # noqa: E402

ALL = ["firm_admin", "partner", "reviewer", "auditor", "preparer", "self"]
FAQ_ROWS = [
    {"id": "bank_only", "q": "I only have a bank statement - no books, no Form 16. Can I file?",
     "words": "only bank statement no books no form 16 small business trainer gym tutor shop presumptive 44AD itr-4 upi receipts no accounts",
     "a": ("Yes, if your turnover is under 2 crore (3 crore when almost all of it is digital). In New filing pick Small business - only a bank "
           "statement and upload the statement. Tap which money is from customers and which is your own money or a loan. Tax is on 6% of "
           "what came by UPI or bank (8% of cash) - ITR-4. You get the JSON to upload on the income-tax portal."),
     "roles": ALL, "go": "#/wizard", "live": ""},
    {"id": "gst_limit", "q": "Do I need GST registration?",
     "words": "gst registration limit threshold 20 lakh 40 lakh services goods turnover register gym",
     "a": ("A service provider has to register above Rs 20 lakh of turnover in a year (Rs 10 lakh in Manipur, Mizoram, Nagaland and Tripura); a "
           "supplier of goods above Rs 40 lakh (Rs 20 lakh there). Below that, GST registration is optional. The Classify step warns when your "
           "turnover is above the limit."),
     "roles": ALL, "go": "#/myreturn", "live": ""},
    {"id": "own_money", "q": "Which money in my bank statement counts as business turnover?",
     "words": "which money counts turnover own transfer loan refund interest classify customer receipts upi statement",
     "a": ("Money paid by customers by UPI or bank. Not your own money moved between your accounts, loans (also from apps), refunds and "
           "reversals, or interest. Cash you deposited counts, at 8%, if it is your takings. Only you can tell some apart - tap each group."),
     "roles": ALL, "go": "#/myreturn", "live": ""},
]
GUIDE_WIZARD = {"title": "Small business - only a bank statement",
                "say": ("A trainer, a tutor, a shop-keeper with no books and no Form 16? Pick Small business - only a bank statement. The statement "
                        "is the only document, and the form is ITR-4 on a fixed share of receipts."),
                "target": "[data-pick='bankonly']|.wz-what|.wz-start"}
GUIDE_MYRETURN = [
    ("What each one gave", {"title": "Classify the money",
                            "say": ("A bank statement read row by row: money in, grouped by who paid. Tap Customer receipts, Cash takings, Own money, "
                                    "Loan or Not income - the turnover and the profit change at once. Own money, loans, refunds and interest never count."),
                            "target": ".bk-list|.mr-rail-card", "open": ".mr-node[data-step='classify']"}),
    ("Classify the money", {"title": "Turnover, profit and the GST limit",
                            "say": ("Customer receipts at 6% (cash at 8%) are the presumptive profit under 44AD. The late fee under 234F applies only "
                                    "where filing was compulsory. A turnover over the GST limit is flagged here too."),
                            "target": ".bk-summary|.mr-rail-card", "open": ".mr-node[data-step='classify']"}),
]
CASE = {"id": "bank_only", "who": "individual", "ay": "2026-27", "title": "Small business - only a bank statement (ITR-4)",
        "line": "Anil Trainer Demo runs a small gym with no books: one bank statement, the money classified, ITR-4 on 6% of the UPI receipts.",
        "folder": "case-bank-only", "batches": [["1 Bank statement - Demo Savings - FY 2025-26.pdf"]], "picks": ["bankonly"],
        "client": "ZZ ANIL KUMAR DEMO", "form": "ITR-4", "opens": "myreturn",
        "answers": {"pan": "ZZDPK0066M", "dob": "1990-01-01", "mobile": "9000000066", "email": "anil.trainer@demo.example", "father": "Demo Father"},
        "say": {"intro": "A gym trainer with no books and no Form 16 - only a bank statement. Start a new filing and pick An individual.",
                "what": "One card does it: Small business - only a bank statement. The form says ITR-4, with its reason.",
                "upload": ("The statement alone, dropped in. It is read row by row and checked: opening plus credits minus debits must be the "
                           "closing balance."),
                "client": ("The statement names the holder, the address and the refund account. Only the PAN, date of birth, mobile, e-mail and "
                           "father's name are asked."),
                "review": "Review: nothing missing - one button into My return, at the Classify step."},
        "more": [
            {"chapter": "Classify the money in",
             "say": ("Money in, grouped by who paid, each one guessed: customers, own money, a loan, a refund. Tap to change - the PhonePe credit is "
                     "Not sure until you say what it is."),
             "do": [{"wait_for": ".bk-list", "timeout": 30}, {"wait": 1.5}, {"highlight_target": ".bk-list", "optional": True, "timeout": 5}, {"wait": 2},
                    {"click": ".bk-row.cls-ask [data-cls='loan']", "optional": True}, {"wait": 2},
                    {"select": "#bk-code", "value": "20023", "optional": True}, {"wait": 2}]},
            {"chapter": "Turnover, profit and the GST limit",
             "say": ("Customer receipts only are the turnover. At 6% they give the presumptive profit under 44AD; cash would be 8%. Below the GST "
                     "limit, nothing to register."),
             "do": [{"highlight_target": "#bk-summary", "optional": True, "timeout": 5}, {"wait": 3}]},
            {"chapter": "Tax, and is filing compulsory?",
             "say": ("The new regime against the old, and the tax. At this income filing is not compulsory, so there is no late fee under 234F - "
                     "but it is recommended, as proof of income for a loan or a visa."),
             "do": [{"click": "[data-next='check']"}, {"wait": 2}, {"click": "[data-next='choose']"}, {"wait_for": ".mr-regs", "timeout": 15}, {"wait": 1},
                    {"highlight_target": ".mr-regs", "optional": True, "timeout": 5}, {"wait": 2}]},
            {"chapter": "The ITR-4 JSON and how to upload it",
             "say": ("The JSON is checked against the department's ITR-4 schema. Download it, then follow the steps: log in, e-File, upload the JSON, "
                     "pay, verify."),
             "do": [{"click": ".mr-node[data-step='file']"}, {"wait_for": "#mr-json", "timeout": 20, "optional": True}, {"wait": 1},
                    {"highlight_target": ".mr-file", "optional": True, "timeout": 5}, {"wait": 2},
                    {"highlight_target": ".mr-up", "optional": True, "timeout": 5}, {"wait": 2}]}],
        "film": "sf-case-bank-only"}


def main():
    def faq(rows):
        have = {r["id"] for r in rows}
        return rows + [r for r in FAQ_ROWS if r["id"] not in have]
    m2.edit_default("chat.faq", "rows", faq, "I only have a bank statement; the GST limit; which money is turnover.")

    def gw(c):
        if GUIDE_WIZARD["title"] not in {x["title"] for x in c}:
            i = next(n for n, x in enumerate(c) if x["title"] == "What applies")
            c.insert(i + 1, dict(GUIDE_WIZARD))
        return c
    m2.edit_default("guide.wizard", "steps", gw, "the bank-statement-only path.")

    def gm(c):
        for after, st in GUIDE_MYRETURN:
            if st["title"] not in {x["title"] for x in c}:
                i = next(n for n, x in enumerate(c) if x["title"] == after)
                c.insert(i + 1, dict(st))
        return c
    m2.edit_default("guide.myreturn", "steps", gm, "the Classify step and the GST limit.")

    def cases(rows):
        return [CASE if r["id"] == CASE["id"] else r for r in rows] if any(r["id"] == CASE["id"] for r in rows) else rows + [CASE]
    m2.edit_default("wizard.cases", "rows", cases, "worked example: small business, only a bank statement (ITR-4).")


if __name__ == "__main__":
    main()
