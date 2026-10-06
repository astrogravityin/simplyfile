"""2026-10-06 My return: presumptive business / profession (44AD, 44ADA) and ITR-4. Writes / updates the chips once.
Run from D:/Simplyfile:  python tools/make_business_chips.py
Hand-edit the chips afterwards if you like - this is only how they were first made."""
import json
from pathlib import Path

CH = Path(__file__).resolve().parent.parent / "chips"
NOTE = "2026-10-06: "


def load(cid):
    return json.loads((CH / f"{cid}.json").read_text(encoding="utf-8"))


def save(c):
    (CH / f"{c['chip_id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", c["chip_id"], "v", c["version"])


def add_params(cid, items, note):
    """New knobs on a record chip (params -> fields), its no-args test expecting them too."""
    c = load(cid)
    have = {p["name"] for p in c["params"]}
    for k, v in items.items():
        if k in have:
            c["params"] = [p for p in c["params"] if p["name"] != k]
        c["params"].append({"name": k, "type": "text" if isinstance(v, str) else "json", "default": v, "label": k.replace("_", " ")})
        c["expr"]["fields"][k] = "$" + k
        for t in c["test_cases"]:
            if isinstance(t.get("expect_value"), dict) and not t.get("args"):
                t["expect_value"][k] = v
    c["version"] += 1
    c["description_nl"] += " " + NOTE + note
    save(c)


# --- 1 the presumptive income -------------------------------------------------------------------------------------------
v = lambda name: "$" + name  # noqa: E731
receipts = {"vop": "add", "a": "$digital", "b": "$cash"}
pct = lambda a, b: {"vop": "div", "a": {"vop": "mul", "a": a, "b": b}, "b": 100}  # noqa: E731
deemed = {"vop": "choose", "cases": [
    {"when": {"op": "eq", "left": "$kind", "right": "44ADA"}, "then": pct(receipts, "$ada_pct")},
    {"when": {"op": "eq", "left": "$kind", "right": "44AD"}, "then": {"vop": "add", "a": pct("$digital", "$ad_digital_pct"), "b": pct("$cash", "$ad_cash_pct")}}],
    "else": 0}
cash_share = {"vop": "choose", "cases": [{"when": {"op": "gt", "left": receipts, "right": 0}, "then": {"vop": "div", "a": {"vop": "mul", "a": "$cash", "b": 100}, "b": receipts}}], "else": 0}
low_cash = {"op": "le", "left": cash_share, "right": "$cash_pct_max"}
limit = {"vop": "choose", "cases": [
    {"when": {"op": "eq", "left": "$kind", "right": "44ADA"}, "then": {"vop": "choose", "cases": [{"when": low_cash, "then": "$ada_limit_low_cash"}], "else": "$ada_limit"}},
    {"when": {"op": "eq", "left": "$kind", "right": "44AD"}, "then": {"vop": "choose", "cases": [{"when": low_cash, "then": "$ad_limit_low_cash"}], "else": "$ad_limit"}}],
    "else": 0}
biz = {"chip_id": "myreturn.business", "kind": "accessor", "set": "myreturn", "label": "My return: presumptive business or profession income",
       "aliases": ["44ada", "44ad", "presumptive income"],
       "params": [{"name": n, "type": t, "default": d, "label": lbl} for n, t, d, lbl in [
           ("kind", "text", "", "44ADA (profession) / 44AD (business) / empty"),
           ("digital", "number", 0, "receipts by bank / digital modes"),
           ("cash", "number", 0, "receipts in cash"),
           ("declared", "number", 0, "income the person declares (may be more than the deemed)"),
           ("ada_pct", "number", 50, "44ADA: deemed income, percent of receipts"),
           ("ad_digital_pct", "number", 6, "44AD: percent of digital turnover"),
           ("ad_cash_pct", "number", 8, "44AD: percent of cash turnover"),
           ("cash_pct_max", "number", 5, "cash at most this percent of receipts lifts the limit"),
           ("ada_limit", "number", 5000000, "44ADA: receipts limit"),
           ("ada_limit_low_cash", "number", 7500000, "44ADA: receipts limit when cash is low"),
           ("ad_limit", "number", 20000000, "44AD: turnover limit"),
           ("ad_limit_low_cash", "number", 30000000, "44AD: turnover limit when cash is low")]],
       "expr": {"vop": "record", "fields": {
           "receipts": receipts, "deemed": {"vop": "round_to", "value": deemed},
           "income": {"vop": "round_to", "value": {"vop": "largest", "values": [deemed, "$declared"]}},
           "limit": limit, "over_limit": {"vop": "choose", "cases": [{"when": {"op": "gt", "left": receipts, "right": limit}, "then": True}], "else": False},
           "cash_share": {"vop": "round_to", "value": cash_share, "digits": 1}}},
       "returns": "record", "version": 1, "status": "published",
       "description_nl": NOTE + "presumptive income of a profession (44ADA: 50% of receipts) or a business (44AD: 6% of digital, 8% "
       "of cash turnover), or what the person declares if more. The limit: 44ADA 50 lakh (75 lakh when cash is 5% or less), 44AD 2 "
       "crore (3 crore). Over the limit, presumptive income is not open - books and ITR-3.",
       "test_cases": [
           {"args": {"kind": "44ADA", "digital": 1800000, "cash": 0}, "expect_value": {"receipts": 1800000, "deemed": 900000, "income": 900000, "limit": 7500000, "over_limit": False, "cash_share": 0}},
           {"args": {"kind": "44ADA", "digital": 1800000, "declared": 1000000}, "expect_value": {"receipts": 1800000, "deemed": 900000, "income": 1000000, "limit": 7500000, "over_limit": False, "cash_share": 0}},
           {"args": {"kind": "44AD", "digital": 1000000, "cash": 100000}, "expect_value": {"receipts": 1100000, "deemed": 68000, "income": 68000, "limit": 20000000, "over_limit": False, "cash_share": 9.1}},
           {"args": {"kind": "44ADA", "digital": 5000000, "cash": 1000000}, "expect_value": {"receipts": 6000000, "deemed": 3000000, "income": 3000000, "limit": 5000000, "over_limit": True, "cash_share": 16.7}},
           {"args": {}, "expect_value": {"receipts": 0, "deemed": 0, "income": 0, "limit": 0, "over_limit": False, "cash_share": 0}}]}
save(biz)

# --- 2 which form: presumptive income -> ITR-4, or ITR-3 when anything ITR-4 cannot hold ----------------------------------
f = load("myreturn.form")
if not any(p["name"] == "business" for p in f["params"]):
    inner = f["expr"]
    f["params"].append({"name": "business", "type": "boolean", "default": False, "label": "presumptive business / profession income (44AD, 44ADA)"})
    f["params"].append({"name": "over_limit", "type": "boolean", "default": False, "label": "receipts over the presumptive limit"})
    simple = {"op": "eq", "left": {"vop": "get", "value": inner, "path": "form"}, "right": "ITR-1"}
    f["expr"] = {"vop": "choose", "cases": [
        {"when": {"op": "all", "items": [{"op": "eq", "left": "$business", "right": True}, {"op": "eq", "left": "$over_limit", "right": True}]},
         "then": {"vop": "record", "fields": {"form": "ITR-3", "why": "why_biz_limit"}}},
        {"when": {"op": "all", "items": [{"op": "eq", "left": "$business", "right": True}, simple]},
         "then": {"vop": "record", "fields": {"form": "ITR-4", "why": "why_presumptive"}}},
        {"when": {"op": "eq", "left": "$business", "right": True},
         "then": {"vop": "record", "fields": {"form": "ITR-3", "why": "why_biz_more"}}}],
        "else": inner}
    f["test_cases"] += [
        {"args": {"total": 900000, "business": True}, "expect_value": {"form": "ITR-4", "why": "why_presumptive"}},
        {"args": {"total": 900000, "business": True, "ltcg_112a": 300000}, "expect_value": {"form": "ITR-3", "why": "why_biz_more"}},
        {"args": {"total": 900000, "business": True, "over_limit": True}, "expect_value": {"form": "ITR-3", "why": "why_biz_limit"}}]
    f["version"] += 1
    f["description_nl"] += " " + NOTE + "presumptive business or profession income (44AD / 44ADA) with nothing ITR-1 would refuse is ITR-4 (Sugam); with more (other gains, a third house, foreign assets ...) or receipts over the limit it is ITR-3."
    save(f)

# --- 3 the ITR-4 schema, and where its figures go ------------------------------------------------------------------------
s = load("itr.settings")
forms = next(p for p in s["params"] if p["name"] == "forms")
if "ITR-4" not in forms["default"]:
    forms["default"]["ITR-4"] = {"schema": "schemas/itr/ITR-4_2026_Main_V1.1.json", "root": "ITR4"}
    for t in s["test_cases"]:
        ev = t.get("expect_value")
        if isinstance(ev, dict) and isinstance(ev.get("forms"), dict) and not t.get("args"):
            ev["forms"]["ITR-4"] = forms["default"]["ITR-4"]
    s["version"] += 1
    s["description_nl"] += " " + NOTE + "ITR-4 (Sugam) AY 2026-27 schema V1.1 (the department's, 30-Jun-2026)."
    save(s)

m = load("itr.map")
mp = next(p for p in m["params"] if p["name"] == "forms")
rename = {"ITR1.Form_ITR1": "ITR4.Form_ITR4", "ITR1.ITR1_IncomeDeductions": "ITR4.IncomeDeductions", "ITR1.ITR1_TaxComputation": "ITR4.TaxComputation",
          "ITR1.TaxPayments": "ITR4.ScheduleIT", "ITR1.": "ITR4."}
skip = {"ITR1.TaxPayments.TotalTaxPayments"}
rows = []
for r in mp["default"]["ITR-1"]:
    if r["path"] in skip:
        continue
    p = r["path"]
    for a, b in rename.items():
        if p.startswith(a):
            p = b + p[len(a):]
            break
    r2 = dict(r, path=p)
    if p == "ITR4.Form_ITR4.FormName":
        r2["from"] = "=ITR-4"
    if p == "ITR4.FilingStatus.ItrFilingDueDate":
        r2["from"] = "filing.due"
    rows.append(r2)
rows += [
    {"path": "ITR4.ScheduleIT.TotalTaxPayments", "from": "tax2.paid"},
    {"path": "ITR4.FilingStatus.Form10IEAEarlierAYOldRegime", "from": "=NA"},
    {"path": "ITR4.PersonalInfo.Status", "from": "=I"},
    {"path": "ITR4.IncomeDeductions.IncomeFromBusinessProf", "from": "biz.income"},
    {"path": "ITR4.ScheduleBP.NatOfBus44ADA", "from": "biz.nature_ada"},
    {"path": "ITR4.ScheduleBP.PersumptiveInc44ADA.GrsReceipt", "from": "biz.ada_receipts"},
    {"path": "ITR4.ScheduleBP.PersumptiveInc44ADA.GrsTrnOverBank44ADA", "from": "biz.ada_digital"},
    {"path": "ITR4.ScheduleBP.PersumptiveInc44ADA.GrsTotalTrnOverInCash44ADA", "from": "biz.ada_cash"},
    {"path": "ITR4.ScheduleBP.PersumptiveInc44ADA.TotPersumptiveInc44ADA", "from": "biz.ada_income"},
    {"path": "ITR4.ScheduleBP.NatOfBus44AD", "from": "biz.nature_ad"},
    {"path": "ITR4.ScheduleBP.PersumptiveInc44AD.GrsTotalTrnOver", "from": "biz.ad_receipts"},
    {"path": "ITR4.ScheduleBP.PersumptiveInc44AD.GrsTrnOverBank", "from": "biz.ad_digital"},
    {"path": "ITR4.ScheduleBP.PersumptiveInc44AD.GrsTotalTrnOverInCash", "from": "biz.ad_cash"},
    {"path": "ITR4.ScheduleBP.PersumptiveInc44AD.PersumptiveInc44AD6Per", "from": "biz.ad_6"},
    {"path": "ITR4.ScheduleBP.PersumptiveInc44AD.PersumptiveInc44AD8Per", "from": "biz.ad_8"},
    {"path": "ITR4.ScheduleBP.PersumptiveInc44AD.TotPersumptiveInc44AD", "from": "biz.ad_income"},
    {"path": "ITR4.ScheduleBP.TurnoverGrsRcptForGSTIN", "from": "biz.gst_rows"},
    {"path": "ITR4.ScheduleBP.TotalTurnoverGrsRcptGSTIN", "from": "biz.gst_turnover"},
]
mp["default"]["ITR-4"] = rows
m["version"] += 1
m["description_nl"] += " " + NOTE + "ITR-4: ITR-1's rows at ITR-4's paths, plus Schedule BP (44ADA / 44AD: nature, receipts by mode, income) and the GSTIN turnover."
save(m)

# --- 4 settings and words -------------------------------------------------------------------------------------------------
add_params("myreturn.settings", {"business_sections": ["194J", "194JA", "194JB", "194C", "194H", "194O", "194M"]},
           "business_sections - TDS sections whose amount paid is a receipt of a business or profession (shown beside the receipts typed).")
add_params("ui.myreturn", {
    "why_presumptive": "Income from a profession or business worked out on the presumptive basis (44ADA / 44AD), with nothing ITR-1 would refuse - ITR-4 (Sugam).",
    "why_biz_more": "Presumptive business or profession income together with something ITR-4 cannot hold (other capital gains, foreign assets, a directorship...) - ITR-3.",
    "why_biz_limit": "Receipts are above the presumptive limit, so the income cannot be worked out on the presumptive basis - books of account and ITR-3.",
    "rv_biz": "Business or profession",
    "rv_biz_p": "A freelancer, consultant or contractor without books: 44ADA (doctors, lawyers, engineers, architects, consultants, IT professionals - 50% of receipts) or 44AD (any other business - 6% of bank receipts, 8% of cash). Receipts come from your bank statement and invoices; the department's view of them is in the AIS and 26AS.",
    "biz_kind": "Kind", "biz_none": "None", "biz_ada": "Profession - 44ADA", "biz_ad": "Business - 44AD",
    "biz_code": "Nature of the work (code)", "biz_name": "Trade name (or your name)",
    "biz_digital": "Receipts by bank / UPI / cheque", "biz_cash": "Receipts in cash", "biz_declared": "Income you declare (if more than the presumptive)",
    "biz_gstin": "GSTIN (if registered)", "biz_gst_turnover": "Turnover in GST returns",
    "biz_income": "Presumptive income {income} on receipts {receipts}", "biz_seen": "The department has seen {amount} paid to you (TDS 194J / 194C...)",
    "biz_seen_more": "Receipts typed are less than the {amount} the department has seen paid to you - check your bank statement.",
    "biz_over": "Receipts {receipts} are over the {limit} limit - presumptive income is not open; this needs books and ITR-3.",
    "biz_pick": "Pick the nature of the work",
    "k_bank": "Bank statement", "k_bank_why": "For a profession or business with no Form 16: the receipts in the year. Kept with your return.",
    "src_h": "Where each document comes from",
    "src_rows": "Form 16|Your employer (TRACES), by 15 June|Salary, exemptions, deductions declared, TDS on salary"
                "||Form 26AS|Income Tax Department - incometax.gov.in > e-File > Income Tax Returns > View Form 26AS (TRACES)|Every TDS / TCS credited to your PAN"
                "||AIS and TIS|Income Tax Department - incometax.gov.in > Services > AIS|Interest, dividends, sales of shares and funds, business receipts, tax you paid (advance, self-assessment)"
                "||Pre-filled JSON|Income Tax Department - e-File > Income Tax Returns > Download Pre-Filled Data|Who you are, banks, salary, TDS, taxes paid"
                "||Filed return (JSON)|You - e-File > Income Tax Returns > View Filed Returns|Last year's figures, your date of birth, to compare"
                "||Bank statement|Your bank - net banking > statements|Receipts of a profession or business with no TDS"
                "||GST returns|gst.gov.in > Returns > View filed returns|Turnover of a GST-registered business"
                "||Capital gains statement|Your broker / CAMS / KFintech|Each sale of shares and funds"
                "||Proofs|Lender, insurer, LIC, PPF, NPS, landlord|Home loan interest, 80C, 80D, rent (old regime)"},
    "the business card on Check (44ADA / 44AD), the ITR-4 reasons, and where each document comes from.")
print("done")
