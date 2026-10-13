"""2026-10-13 s.234F only bites a person who was REQUIRED to file: chip myreturn.must_file (s.139(1) and its 7th proviso, Rule 12AB),
the words (ui.myreturn mf_*), the three confirm questions (answers foreign_travel, electricity, current_deposits) and chip
chat.fee_234f's new `required` knob. Re-runnable.   .venv/Scripts/python.exe tools/make_mustfile_chip.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import make_bankonly_part2 as m2  # noqa: E402

NOTE = "2026-10-13: "
P = [("income", "number", 0, "total income before Chapter VI-A, 10A, 54 ... (gross total income)"),
     ("limit", "number", 400000, "the basic exemption limit (maximum amount not chargeable to tax) of the regime and age band"),
     ("deposits_savings", "number", 0, "deposits in savings account(s) in the year"),
     ("current_deposits", "boolean", False, "the person confirms: Rs 1 crore or more deposited in current account(s)"),
     ("foreign_travel", "boolean", False, "the person confirms: more than Rs 2 lakh spent on foreign travel"),
     ("electricity", "boolean", False, "the person confirms: electricity bill more than Rs 1 lakh"),
     ("tds", "number", 0, "TDS and TCS in the year"),
     ("senior", "boolean", False, "a resident senior citizen (60+)"),
     ("turnover", "number", 0, "business turnover / gross receipts"),
     ("receipts", "number", 0, "gross receipts of a profession"),
     ("savings_limit", "number", 5000000, "7th proviso: savings deposits Rs 50 lakh or more"),
     ("tds_limit", "number", 25000, "7th proviso: TDS + TCS Rs 25,000 or more"),
     ("tds_limit_senior", "number", 50000, "7th proviso: Rs 50,000 for a resident senior citizen"),
     ("turnover_limit", "number", 6000000, "7th proviso: business turnover more than Rs 60 lakh"),
     ("receipts_limit", "number", 1000000, "7th proviso: professional receipts more than Rs 10 lakh")]
V = lambda n: f"${n}"  # noqa: E731
YES = lambda n: {"op": "eq", "left": V(n), "right": True}  # noqa: E731
CONDS = [
    ("income", {"op": "gt", "left": V("income"), "right": V("limit")}),
    ("current", YES("current_deposits")),
    ("savings", {"op": "ge", "left": V("deposits_savings"), "right": V("savings_limit")}),
    ("travel", YES("foreign_travel")),
    ("electricity", YES("electricity")),
    ("tds", {"op": "any", "items": [
        {"op": "all", "items": [{"op": "not", "item": V("senior")}, {"op": "ge", "left": V("tds"), "right": V("tds_limit")}]},
        {"op": "all", "items": [V("senior"), {"op": "ge", "left": V("tds"), "right": V("tds_limit_senior")}]}]}),
    ("turnover", {"op": "gt", "left": V("turnover"), "right": V("turnover_limit")}),
    ("receipts", {"op": "gt", "left": V("receipts"), "right": V("receipts_limit")}),
]


def case(**kw):
    a = {n: d for n, _t, d, _l in P}
    a.update(kw)
    return a


def want(why):
    return {"required": bool(why), "why": why}


def main():
    expr = {"vop": "record", "fields": {
        "required": {"op": "any", "items": [c for _n, c in CONDS]},
        "why": {"vop": "choose", "cases": [{"when": c, "then": n} for n, c in CONDS], "else": ""}}}
    tests = [
        {"args": {}, "expect_value": want("")},
        {"args": case(income=72290), "expect_value": want("")},
        {"args": case(income=400001), "expect_value": want("income")},
        {"args": case(income=72290, current_deposits=True), "expect_value": want("current")},
        {"args": case(income=72290, deposits_savings=5000000), "expect_value": want("savings")},
        {"args": case(income=72290, deposits_savings=4999999), "expect_value": want("")},
        {"args": case(income=72290, foreign_travel=True), "expect_value": want("travel")},
        {"args": case(income=72290, electricity=True), "expect_value": want("electricity")},
        {"args": case(income=72290, tds=25000), "expect_value": want("tds")},
        {"args": case(income=72290, tds=30000, senior=True), "expect_value": want("")},
        {"args": case(income=72290, tds=50000, senior=True), "expect_value": want("tds")},
        {"args": case(income=72290, turnover=6000001), "expect_value": want("turnover")},
        {"args": case(income=72290, turnover=6000000), "expect_value": want("")},
        {"args": case(income=72290, receipts=1000001), "expect_value": want("receipts")},
    ]
    c = {"chip_id": "myreturn.must_file", "kind": "accessor", "set": "myreturn", "label": "My return: is the person required to file (s.139(1))",
         "aliases": ["my return: is the person required to file"],
         "params": [{"name": n, "type": t, "default": d, "label": lbl} for n, t, d, lbl in P], "expr": expr, "returns": "record", "version": 1,
         "status": "published",
         "description_nl": NOTE + "A return is compulsory when total income before Chapter VI-A exceeds the basic exemption limit, or - 7th proviso to "
         "s.139(1), Rule 12AB - Rs 1 crore deposited in current accounts, Rs 50 lakh in savings, more than Rs 2 lakh spent on foreign travel or "
         "Rs 1 lakh on electricity, TDS + TCS of Rs 25,000 (Rs 50,000 senior), business turnover over Rs 60 lakh or professional receipts over "
         "Rs 10 lakh. Otherwise filing is voluntary: no late fee under s.234F (chip chat.fee_234f is asked only when this says required), and a "
         "belated return is still allowed (s.139(4)). why = the first reason that applies.",
         "test_cases": tests}
    p = ROOT / "chips" / "myreturn.must_file.json"
    if p.exists():
        c["version"] = json.loads(p.read_text(encoding="utf-8"))["version"] + 1
    m2.write(c)
    print("wrote myreturn.must_file")
    words = {
        "mf_h": "Filing is not compulsory for you",
        "mf_p": ("Your income of {income} is below the basic exemption of {limit}, and none of the other conditions that make a return compulsory "
                 "(s.139(1)) applies, so no late fee (s.234F) is charged. It is still recommended: a filed return is the proof of income for a "
                 "bank loan, a visa or a credit card, and it puts the year on record. You can file it after the due date, until {belated} (s.139(4))."),
        "mf_savings": "Credits in your savings account this year: {amount} - below the Rs 50 lakh test.",
        "mf_confirm": "Please confirm - any one of these makes a return compulsory:",
        "mf_travel": "More than Rs 2 lakh spent on foreign travel in the year",
        "mf_elec": "An electricity bill of more than Rs 1 lakh in the year",
        "mf_current": "Rs 1 crore or more deposited in current accounts",
        "mf_req_h": "Filing is compulsory for you",
        "mf_why_income": "your income is above the basic exemption limit",
        "mf_why_current": "Rs 1 crore or more was deposited in current accounts",
        "mf_why_savings": "Rs 50 lakh or more was deposited in savings accounts",
        "mf_why_travel": "more than Rs 2 lakh was spent on foreign travel",
        "mf_why_electricity": "the electricity bill was more than Rs 1 lakh",
        "mf_why_tds": "TDS and TCS came to Rs 25,000 or more (Rs 50,000 for a senior citizen)",
        "mf_why_turnover": "business turnover is above Rs 60 lakh",
        "mf_why_receipts": "professional receipts are above Rs 10 lakh",
        "mf_req_p": "A return is compulsory because {why}. Filing after the due date of {due} carries the late fee under s.234F.",
    }
    m2.add_fields("ui.myreturn", words, "s.234F only where filing is compulsory: the voluntary-return note and its confirm questions.")

    def quest(q):
        return q + [x for x in ("foreign_travel", "electricity", "current_deposits") if x not in q]
    m2.edit_default("myreturn.settings", "questions", quest, "confirm questions of the s.139(1) 7th proviso.")

    def ansd(d):
        for x in ("foreign_travel", "electricity", "current_deposits"):
            d.setdefault(x, False)
        return d
    m2.edit_default("myreturn.settings", "answer_defaults", ansd, "confirm questions of the s.139(1) 7th proviso.")


if __name__ == "__main__":
    main()
