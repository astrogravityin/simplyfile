"""2026-10-13 SimplyFy "Small business - only a bank statement", part 2: the words (ui.bankonly and the new keys of ui.myreturn /
ui.wizard) and the knobs added to existing chips (wizard.scenarios, wizard.docs, wizard.doc_need, wizard.asks, wizard.settings,
wizard.next_step, myreturn.steps, myreturn.sources, myreturn.settings). Re-runnable (each edit is skipped when already there).
Run from D:/Simplyfile after tools/make_bankonly_chips.py:  .venv/Scripts/python.exe tools/make_bankonly_part2.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "chips"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import make_bankonly_chips as m1  # noqa: E402

NOTE = m1.NOTE
read, write = m1.read, m1.write

READER_WORDS = {
    "fd_bank_rows": "Entries read",
    "fd_bank_recon": "Adds up",
    "recon_ok_short": "Yes - opening + credits - debits = closing",
    "recon_bad_short": "No - some entries are missing or unclear",
    "recon_bad": ("This statement does not add up. {rows} entries were read (the last is number {read}); opening {opening} + credits {credits} "
                  "- debits {debits} should come to {closing}, and {gaps} entries do not fit the running balance (entry numbers: {at}). Download the "
                  "original PDF again from your bank's net banking or app - all pages, not a photo or a print - and upload that. {product} does not use a "
                  "statement that does not add up."),
    "s_classify": "Classify",
    "go_classify": "Classify the money",
    "old_closed": "The old regime can only be chosen in a return filed by the due date ({due}) - a belated return is under the new regime.",
    "c_bank_recon": "Bank statement adds up",
    "lv_bank_recon": "The statement does not add up - upload the original PDF again, all pages.",
    "c_bank_undecided": "Money to classify",
    "lv_bank_undecided": "Some money in is still marked Not sure and is left out of your turnover.",
}
BANKONLY_WORDS = {
    "title": "Where did the money come from?",
    "lede": ("This is what your bank statement says. Money paid by customers is your business turnover. Your own money moving between your "
             "accounts, loans and refunds are not. We have guessed each one - tap to change."),
    "stmt": "{rows} entries, {from} to {to} - opening {opening}, closing {closing}",
    "recon_ok": "The statement adds up: opening {opening} + credits {credits} - debits {debits} = closing {closing}.",
    "recon_bad": "This statement does not add up, so its figures are not used. Upload the original PDF again (all pages) from net banking.",
    "tab_in": "Money in",
    "tab_out": "Money out",
    "c_receipt": "Customer receipts",
    "c_cash": "Cash takings",
    "c_own": "Own money",
    "c_loan": "Loan",
    "c_other": "Not income",
    "c_ask": "Not sure",
    "d_personal": "Personal",
    "d_business": "Business cost",
    "d_own": "Own money",
    "d_loan": "Loan repayment",
    "d_ask": "Not sure",
    "n_payments": "{n} payments",
    "dates": "{first} to {last}",
    "f_through": "An equal amount went out within {days} days - is this a loan or own money passing through?",
    "f_round": "Round amounts - is this a customer?",
    "more": "Show {n} more",
    "fewer": "Show fewer",
    "sum_h": "What this makes",
    "sum_receipt": "Business turnover (UPI and bank receipts)",
    "sum_cash": "Cash takings (deposits you say are fees)",
    "sum_own": "Own money moved (left out)",
    "sum_loan": "Loans (not income)",
    "sum_other": "Refunds, reversals, interest (not turnover)",
    "sum_ask": "Not decided yet (left out)",
    "line": "Turnover {digital} received by UPI or bank at {rd}% = {p6}, cash {cash} at {rc}% = {p8}. Presumptive profit under s.44AD: {profit}.",
    "line_none": "No customer receipts counted yet - tap the groups that are your customers.",
    "line_rule": "s.44AD: {rd}% of the turnover received through a bank or UPI, {rc}% of cash; loans, own money and refunds are not turnover.",
    "res_h": "Your return so far",
    "res_income": "Total income",
    "res_tax": "Income tax",
    "res_fee": "Late fee and interest",
    "res_pay": "To pay",
    "res_refund": "Refund",
    "res_regime": "{regime} regime - the cheaper one is chosen for you on the next steps.",
    "res_nil": "No income tax - the income is below the basic exemption.",
    "contact_h": "Still needed to file",
    "contact_p": "Type what is missing - nothing else is asked.",
    "tap_h": "Tap what each one is",
    "none_out": "No money out.",
    "code_name": "Name of the business",
    "docs_h": "Statement",
    "undecided": "{n} groups worth {amount} are not decided and are left out of your turnover. Tap what they are.",
    "interest": "Interest of {amount} on your savings is income from other sources - it is added for you.",
    "salary": "Salary credits of {amount} found - these are not business turnover. Give the Form 16 so the salary can be added.",
    "confirm": "Looks right - continue",
    "gst_over": ("Your turnover of {turnover} is above {limit}, the GST registration limit for a {supply} supplier (s.22 CGST Act). You may have to "
                 "register for GST - ask a GST practitioner. This does not change the income-tax return."),
    "gst_near": "Your turnover of {turnover} is close to the GST registration limit of {limit}. Above it you must register for GST.",
    "supply_services": "services",
    "supply_goods": "goods",
    "need_h": "Still needed to file",
    "need_pan": "PAN",
    "need_dob": "Date of birth",
    "need_mobile": "Mobile number",
    "need_address": "Address",
    "need_email": "E-mail address",
    "need_father": "Father's name",
    "need_code": "What the business does (the department's code)",
    "need_ok": "Nothing more is needed - the JSON is ready on the last step.",
    "late": "Filed after the due date of {due}: late fee under s.234F {fee} and interest under s.234A, 234B and 234C {interest} are in the amount to pay.",
    "code_h": "What does the business do?",
    "code_p": "The department wants one code for the work. The common ones are first.",
    "code_pick": "Pick the nearest",
    "code_common": "Common",
    "code_all": "All",
    "upload_h": "How to upload the JSON on the income-tax portal",
    "upload_p": "Takes about five minutes. You need your PAN, password and mobile (for the OTP).",
    "path_label": "Small business - only a bank statement",
    "path_sub": "No books, no Form 16 - the bank statement alone makes an ITR-4 (tax on a fixed share of receipts)",
    "debit_note": "Presumptive tax: costs are not claimed, so money out does not change the tax. It is shown for completeness.",
    "show_out": "Money out ({n} groups)",
}
WIZARD_WORDS = {
    "a_mobile": "Your mobile number (10 digits) - the return needs one",
    "a_address": "Your address (flat, street, area, city, PIN) - the return needs one",
    "bad_mobile": "That is not a mobile number - 10 digits, starting 6, 7, 8 or 9.",
    "a_email": "Your e-mail address - the return and the portal's mails go here",
    "a_father": "Your father's name - the return's declaration asks for it",
    "bad_email": "That does not look like an e-mail address.",
}
ASK_BASE = {"client": False, "files": 1, "pans": 1, "name": "X", "dob": "2000-01-01", "who": "individual", "karta_name": "", "karta_pan": "",
            "clash": False, "nri": False, "resident": "", "partners_need": False, "gstin_need": False, "company_need": False}


def refresh(c):
    """Every no-args test of a record chip answers what the chip now answers; the others are checked."""
    from core import engine  # noqa: PLC0415
    import store  # noqa: F401,PLC0415
    engine.refresh()
    for t in c["test_cases"]:
        got = engine.run(c["chip_id"], t["args"])
        if not t["args"] and isinstance(t.get("expect_value"), dict):
            t["expect_value"] = got
        else:
            assert got == t["expect_value"], (c["chip_id"], t["args"], got, t["expect_value"])


def done(c, note):
    c["version"] += 1
    if note and note not in c.get("description_nl", ""):
        c["description_nl"] = c.get("description_nl", "") + " " + NOTE + note
    write(c)
    c2 = read(c["chip_id"])
    refresh(c2)
    write(c2)
    print("edited", c["chip_id"])


def add_fields(cid, fields, note):
    c = read(cid)
    have = {p["name"]: p for p in c["params"]}
    new = False
    for n, v in fields.items():
        if n in have:
            new = new or have[n]["default"] != v
            have[n]["default"] = v
        else:
            new = True
            c["params"].append({"name": n, "type": "text", "default": v, "label": n.replace("_", " ")})
        c["expr"]["fields"][n] = f"${n}"
    if new:
        done(c, note)


def edit_default(cid, name, fn, note):
    c = read(cid)
    p = next(p for p in c["params"] if p["name"] == name)
    new = fn(json.loads(json.dumps(p["default"])))
    if new != p["default"]:
        p["default"] = new
        done(c, note)


def main():
    add_fields("ui.myreturn", READER_WORDS, "the serial-numbered bank statement: entries read, whether it adds up, the Classify step's name.")
    m1.record_chip("ui.bankonly", "ui", "Small business, only a bank statement: words",
                   "Every word of the Classify step (customer receipts, own money, loan, not income), the 6% / 8% line, the GST limit warning, what is "
                   "still needed, and how to upload the JSON on the income-tax portal.", BANKONLY_WORDS)
    add_fields("ui.wizard", WIZARD_WORDS, "the bank-statement-only path: the mobile and address questions.")

    def src(d):
        if "bank" not in d["person"]:
            d["person"] = d["person"] + ["bank"]
        if "bank" not in d["banks"]:
            d["banks"] = d["banks"] + ["bank"]
        return d
    edit_default("myreturn.sources", "order", src, "a bank statement names the holder, the address and the refund account.")

    def quest(q):
        return q + [x for x in ("supply",) if x not in q]
    edit_default("myreturn.settings", "questions", quest, "supply: goods or services (the GST limit of a bank-only filing).")

    def ansd(d):
        d.setdefault("supply", "")
        return d
    edit_default("myreturn.settings", "answer_defaults", ansd, "supply.")

    c = read("myreturn.steps")
    if "bank_open" not in {p["name"] for p in c["params"]}:
        c["params"].append({"name": "bank_open", "type": "boolean", "default": False, "label": "a bank statement is read and its money is not yet classified"})
        c["expr"]["fields"]["done"]["fields"]["classify"] = {"op": "eq", "left": "$bank_open", "right": False}
        c["expr"]["fields"]["now"]["cases"].insert(1, {"when": {"op": "eq", "left": "$bank_open", "right": True}, "then": "classify"})
        for t in c["test_cases"]:
            t["expect_value"]["done"]["classify"] = True
        c["test_cases"] += [
            {"args": {"has_docs": True, "has_income": True, "bank_open": True},
             "expect_value": {"done": {"gather": True, "check": True, "choose": False, "review": False, "classify": False}, "now": "classify"}},
            {"args": {"bank_open": True}, "expect_value": {"done": {"gather": False, "check": False, "choose": False, "review": False, "classify": False}, "now": "gather"}}]
        done(c, "classify - a read bank statement's money is classified before the checks.")

    c = read("wizard.next_step")
    if "classify" not in {p["name"] for p in c["params"]}:
        c["params"].append({"name": "classify", "type": "boolean", "default": False, "label": "a bank statement's money still to classify"})
        c["expr"]["cases"].insert(1, {"when": {"op": "eq", "left": "$classify", "right": True}, "then": "classify"})
        c["test_cases"] += [{"args": {"required_missing": 0, "typed": 2, "red": 1, "classify": True}, "expect_value": "classify"},
                            {"args": {"required_missing": 1, "typed": 0, "red": 0, "classify": True}, "expect_value": "gather"}]
        done(c, "classify after the documents when a bank statement's money is not yet classified.")

    c = read("wizard.doc_need")
    if "except_for" not in {p["name"] for p in c["params"]}:
        c["params"].append({"name": "except_for", "type": "json", "default": [], "label": "picks that make this document optional"})
        c["expr"]["cases"].insert(1, {"when": {"op": "lt", "left": {"vop": "count", "items": {"vop": "missing", "want": "$except_for", "have": "$picked"}},
                                               "right": {"vop": "count", "items": "$except_for"}}, "then": "optional"})
        c["test_cases"] += [
            {"args": {"required_for": ["any"], "optional_for": [], "picked": ["bankonly"], "except_for": ["bankonly"]}, "expect_value": "optional"},
            {"args": {"required_for": ["any"], "optional_for": [], "picked": ["salary"], "except_for": ["bankonly"]}, "expect_value": "required"}]
        done(c, "except_for: a pick (bankonly) makes the AIS and 26AS optional.")

    def docs(rows):
        for r in rows:
            r.setdefault("except_for", ["bankonly"] if r["id"] in ("ais", "26as") else [])
            if r["id"] == "bank" and "bankonly" not in r["required_for"]:
                r["required_for"] = r["required_for"] + ["bankonly"]
                r["what"] = "Receipts with no TDS, cash deposits, interest the AIS may not show. On the bank-statement-only path it is the only document."
                r["where"] = "Net banking or the bank's app > Statements > the whole financial year, as the original PDF (all pages), Excel or CSV."
        return rows
    edit_default("wizard.docs", "rows", docs, "the bank-statement-only path: the bank statement is required, the AIS and 26AS optional.")

    def scen(rows):
        if not any(r["id"] == "bankonly" for r in rows):
            rows.insert(0, {"id": "bankonly", "group": "income", "art": "services", "label": BANKONLY_WORDS["path_label"], "sub": BANKONLY_WORDS["path_sub"],
                         "sec": "s.44AD", "not_for": ["huf", "firm", "llp", "aop", "company", "trust"], "only_for": [],
                         "implies": ["business", "services", "presumptive"], "excludes": ["books", "audit"]})
        return rows
    edit_default("wizard.scenarios", "rows", scen, "the bank-statement-only path (bankonly): a small business with no books - presumptive, ITR-4.")

    def asks_list(rows):
        for x in ({"id": "mobile", "input": "text", "to": "return"}, {"id": "address", "input": "text", "to": "return"},
                  {"id": "email", "input": "text", "to": "return"}, {"id": "father", "input": "text", "to": "return"}):
            if x not in rows:
                rows.append(x)
        return rows
    edit_default("wizard.settings", "asks", asks_list, "the mobile number and address questions of the bank-statement-only path.")

    c = read("wizard.asks")
    if "bank_only" not in {p["name"] for p in c["params"]}:
        for n, d, t in (("bank_only", False, "boolean"), ("mobile", "", "text"), ("address", "", "text")):
            c["params"].append({"name": n, "type": t, "default": d, "label": n.replace("_", " ")})
        for n in ("mobile", "address"):
            c["expr"]["values"].append({"vop": "choose", "cases": [{"when": {"op": "all", "items": [
                {"op": "gt", "left": "$files", "right": 0}, {"op": "eq", "left": "$bank_only", "right": True}, {"op": "eq", "left": f"${n}", "right": ""}]},
                "then": n}], "else": ""})
        c["test_cases"] += [{"args": ASK_BASE | {"bank_only": True}, "expect_value": ["mobile", "address"]},
                            {"args": ASK_BASE | {"bank_only": True, "mobile": "9999900000", "address": "x"}, "expect_value": []}]
        done(c, "bank_only: the mobile and the address are asked when the statement did not give them.")


    c = read("wizard.asks")
    if "email" not in {p["name"] for p in c["params"]}:
        for n in ("email", "father"):
            c["params"].append({"name": n, "type": "text", "default": "", "label": n})
            c["expr"]["values"].append({"vop": "choose", "cases": [{"when": {"op": "all", "items": [
                {"op": "gt", "left": "$files", "right": 0}, {"op": "eq", "left": "$bank_only", "right": True}, {"op": "eq", "left": f"${n}", "right": ""}]},
                "then": n}], "else": ""})
        c["test_cases"] += [{"args": ASK_BASE | {"bank_only": True, "mobile": "9999900000", "address": "x"}, "expect_value": ["email", "father"]},
                            {"args": ASK_BASE | {"bank_only": True, "mobile": "9999900000", "address": "x", "email": "a@b.co", "father": "Z"}, "expect_value": []}]
        c["test_cases"] = [t for t in c["test_cases"] if not (t["args"].get("bank_only") and t["args"].get("mobile") == "9999900000" and "email" not in t["args"] and t["expect_value"] == [])]
        c["test_cases"] = [t for t in c["test_cases"] if not (t["args"].get("bank_only") and t["args"].get("mobile") == "" and t["expect_value"] == ["mobile", "address"])] + [
            {"args": ASK_BASE | {"bank_only": True}, "expect_value": ["mobile", "address", "email", "father"]}]
        done(c, "email and father's name: the return needs them too.")


if __name__ == "__main__":
    m1.main()
    main()
