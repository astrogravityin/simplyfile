"""2026-10-07 My return writes ITR-3: presumptive business (44AD / 44ADA / 44AE) in ITR-3 with capital gains, special-rate
income and the rest; a business or profession without presumptive income - typed receipts, gross profit, expenses, net
profit and the simple balance-sheet figures (ITR-3 Part A-P&L / Part A-BS "no regular books of account"); a tax audit
(s.44AB) or a business loss flagged - a CA's job (the CA-firm side). Writes / updates the chips - each step can be run
again (the ITR-3 rows of My return are made again from the ITR-2 rows, so a later ITR-2 row comes across on a re-run).
Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/make_itr3_myreturn.py"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "chips"
NOTE = "2026-10-07: "
sys.path.insert(0, str(ROOT))


def load(cid):
    return json.loads((CH / f"{cid}.json").read_text(encoding="utf-8"))


def write(c):
    (CH / f"{c['chip_id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", c["chip_id"], "v", c["version"])


def save(c, note=""):
    old = (CH / f"{c['chip_id']}.json")
    before = json.loads(old.read_text(encoding="utf-8")) if old.exists() else None
    if before is not None:
        a, b = dict(before), dict(c)
        for x in (a, b):
            x.pop("version", None)
            x.pop("description_nl", None)
        if a == b:
            print("same", c["chip_id"])
            return
        c["version"] = before["version"] + 1
    if note and note not in c.get("description_nl", ""):
        c["description_nl"] = (c.get("description_nl", "") + " " + NOTE + note).strip()
    write(c)


def knob(c, name, default, label=None):
    """A knob on a record chip that hands its params back (settings, words): param, field, and the no-args test."""
    changed = True
    for p in c["params"]:
        if p["name"] == name:
            changed = p["default"] != default        # 2026-10-08: an unchanged word keeps its test's answer ({product} is filled there)
            p["default"] = default
            break
    else:
        c["params"].append({"name": name, "type": "text" if isinstance(default, str) else "json", "default": default, "label": label or name.replace("_", " ")})
    c["expr"]["fields"][name] = "$" + name
    for t in c["test_cases"]:
        if isinstance(t.get("expect_value"), dict) and not t.get("args") and changed:
            t["expect_value"][name] = default


def yes(cond):
    return {"vop": "choose", "cases": [{"when": cond, "then": True}], "else": False}


def eq(a, b):
    return {"op": "eq", "left": a, "right": b}


def all_(*xs):
    return {"op": "all", "items": list(xs)}


def any_(*xs):
    return {"op": "any", "items": list(xs)}


def not_(x):
    return {"op": "not", "item": x}


def in_set(v, s):
    return {"op": "in_set", "value": v, "set": s}


def gt(a, b):
    return {"op": "gt", "left": a, "right": b}


def lt(a, b):
    return {"op": "lt", "left": a, "right": b}


def add(a, b):
    return {"vop": "add", "a": a, "b": b}


def sub(a, b):
    return {"vop": "sub", "a": a, "b": b}


def P(name, typ, default, label):
    return {"name": name, "type": typ, "default": default, "label": label}


# --- 1 myreturn.business_pl: presumptive or the person's own profit and loss --------------------------------------------
kind_set = all_(not_(eq("$kind", "")))
pl = any_(in_set("$kind", "$pl_kinds"), all_(not_(eq("$kind", "")), eq("$over_limit", True)))
prof = in_set("$kind", "$prof_kinds")
turnover = add("$digital", "$cash")
net = {"vop": "choose", "cases": [{"when": not_(eq("$np", 0)), "then": "$np"}], "else": sub("$gp", "$expenses")}
bpl = {"chip_id": "myreturn.business_pl", "kind": "accessor", "set": "myreturn",
       "label": "My return: presumptive income or the person's own profit and loss (no regular books)",
       "aliases": ["no books of account", "business profit and loss", "noaccountcase"],
       "params": [
           P("kind", "text", "", "44ADA / 44AD / 44AE (presumptive), business / profession (own profit and loss), or empty"),
           P("over_limit", "boolean", False, "presumptive income closed (receipts over the limit, more than 10 goods carriages) - chip myreturn.business"),
           P("presumptive_income", "number", 0, "the presumptive income (chip myreturn.business)"),
           P("digital", "number", 0, "receipts by bank / digital modes"),
           P("cash", "number", 0, "receipts in cash"),
           P("gp", "number", 0, "gross profit typed"),
           P("expenses", "number", 0, "expenses typed"),
           P("np", "number", 0, "net profit typed (blank: gross profit less expenses)"),
           P("pl_kinds", "json", ["business", "profession"], "kinds worked out from the person's own profit and loss"),
           P("prof_kinds", "json", ["44ADA", "profession"], "kinds that are a profession (Part A-P&L 64(ii), s.44AA(1))"),
           P("books_prof_receipts", "number", 150000, "s.44AA(1) / Rule 6F: a profession with receipts above this keeps books"),
           P("books_income", "number", 250000, "s.44AA(2)(i): business income above this - books"),
           P("books_turnover", "number", 2500000, "s.44AA(2)(i): turnover above this - books")],
       "expr": {"vop": "record", "fields": {
           "pl": yes(pl), "presumptive": yes(all_(kind_set, not_(pl))), "profession": yes(prof), "turnover": turnover,
           "net": {"vop": "choose", "cases": [{"when": pl, "then": net}], "else": 0},
           "income": {"vop": "choose", "cases": [{"when": pl, "then": net}, {"when": kind_set, "then": "$presumptive_income"}], "else": 0},
           "loss": yes(all_(pl, lt(net, 0))),
           "liable_44aa": yes(all_(pl, {"op": "any", "items": [all_(prof, gt(turnover, "$books_prof_receipts")),
                                                                  all_(not_(prof), any_(gt(net, "$books_income"), gt(turnover, "$books_turnover")))]}))}},
       "returns": "record", "version": 1, "status": "published",
       "description_nl": NOTE + "which basis the business income is on. 44ADA / 44AD / 44AE within their limits: presumptive (chip "
       "myreturn.business). Over the limit (44AD / 44ADA receipts, more than 10 goods carriages for 44AE) or a business / profession "
       "the person reports on their own figures: the net profit typed (or gross profit less expenses) - ITR-3 Part A-P&L item 64 "
       "(\"no regular books of account\"), Schedule BP. loss: a net loss - not carried in My return (a CA). liable_44aa: s.44AA - "
       "a profession with receipts over 1.5 lakh, a business with income over 2.5 lakh or turnover over 25 lakh keeps books "
       "(ITR-3 Part A-GEN2 LiableSec44AAflg).",
       "test_cases": [
           {"args": {"kind": "44ADA", "presumptive_income": 900000, "digital": 1800000},
            "expect_value": {"pl": False, "presumptive": True, "profession": True, "turnover": 1800000, "net": 0, "income": 900000, "loss": False, "liable_44aa": False}},
           {"args": {"kind": "44AE", "over_limit": True, "presumptive_income": 900000, "digital": 4800000, "gp": 1500000, "expenses": 600000, "np": 900000},
            "expect_value": {"pl": True, "presumptive": False, "profession": False, "turnover": 4800000, "net": 900000, "income": 900000, "loss": False, "liable_44aa": True}},
           {"args": {"kind": "business", "digital": 2000000, "gp": 400000, "expenses": 250000},
            "expect_value": {"pl": True, "presumptive": False, "profession": False, "turnover": 2000000, "net": 150000, "income": 150000, "loss": False, "liable_44aa": False}},
           {"args": {"kind": "profession", "digital": 900000, "gp": 900000, "expenses": 1000000},
            "expect_value": {"pl": True, "presumptive": False, "profession": True, "turnover": 900000, "net": -100000, "income": -100000, "loss": True, "liable_44aa": True}},
           {"args": {}, "expect_value": {"pl": False, "presumptive": False, "profession": False, "turnover": 0, "net": 0, "income": 0, "loss": False, "liable_44aa": False}}]}
save(bpl)

# --- 2 myreturn.audit_44ab: a tax audit - out of My return, a CA's job -------------------------------------------------
low_cash = {"op": "any", "items": [{"op": "le", "left": "$turnover", "right": 0},
                                   {"op": "le", "left": {"vop": "div", "a": {"vop": "mul", "a": "$cash", "b": 100}, "b": "$turnover"},
                                    "right": "$cash_pct_max"}]}
limit = {"vop": "choose", "cases": [
    {"when": all_(eq("$profession", True), low_cash), "then": "$prof_limit_low_cash"},
    {"when": eq("$profession", True), "then": "$prof_limit"},
    {"when": low_cash, "then": "$biz_limit_low_cash"}], "else": "$biz_limit"}
over = all_(eq("$pl", True), gt("$turnover", limit))
lower = all_(eq("$pl", True), eq("$presumptive_open", True), lt("$net", "$deemed"), eq("$above_exemption", True))
aud = {"chip_id": "myreturn.audit_44ab", "kind": "accessor", "set": "myreturn",
       "label": "My return: does the business need a tax audit (s.44AB)?",
       "aliases": ["tax audit", "44ab", "audit limit"],
       "params": [
           P("pl", "boolean", False, "income from the person's own profit and loss (chip myreturn.business_pl)"),
           P("profession", "boolean", False, "a profession (s.44AB(b)) rather than a business (s.44AB(a))"),
           P("turnover", "number", 0, "receipts / turnover of the year"),
           P("cash", "number", 0, "of which in cash"),
           P("net", "number", 0, "net profit"),
           P("deemed", "number", 0, "what the presumptive scheme would have made it (6% / 8%, 50%)"),
           P("presumptive_open", "boolean", False, "the presumptive scheme was open (within its limit) and not chosen"),
           P("above_exemption", "boolean", False, "total income above the amount not chargeable to tax"),
           P("cash_pct_max", "number", 5, "s.44AB provisos: cash at most this percent of receipts lifts the limit"),
           P("biz_limit", "number", 10000000, "s.44AB(a): business turnover above 1 crore"),
           P("biz_limit_low_cash", "number", 100000000, "s.44AB(a) proviso: 10 crore when cash is 5% or less"),
           P("prof_limit", "number", 5000000, "s.44AB(b): professional receipts above 50 lakh"),
           P("prof_limit_low_cash", "number", 7500000, "s.44AB(b) proviso: 75 lakh when cash is 5% or less")],
       "expr": {"vop": "record", "fields": {
           "audit": yes(any_(over, lower)), "limit": limit,
           "why": {"vop": "choose", "cases": [{"when": over, "then": "ca_audit_turnover"}, {"when": lower, "then": "ca_audit_lower"}], "else": ""}}},
       "returns": "record", "version": 1, "status": "published",
       "description_nl": NOTE + "s.44AB for an individual / HUF filing from My return: (a) business turnover over 1 crore (10 crore when "
       "cash receipts are 5% or less), (b) professional receipts over 50 lakh (75 lakh), (d) / (e) the presumptive scheme open but a "
       "lower profit declared with income above the basic exemption. Any of them: the accounts are audited by a chartered accountant "
       "- My return does not file it (the CA-firm side: Intake, Reconcile, Compute, Tax audit). ponytail: cash payments are not asked "
       "- the cash receipts stand for both (the proviso asks both at 5% or less); 44AD(4) (left the scheme within five years) not asked.",
       "test_cases": [
           {"args": {"pl": True, "turnover": 15000000, "cash": 3000000, "net": 1200000},
            "expect_value": {"audit": True, "limit": 10000000, "why": "ca_audit_turnover"}},
           {"args": {"pl": True, "turnover": 15000000, "cash": 0, "net": 1200000},
            "expect_value": {"audit": False, "limit": 100000000, "why": ""}},
           {"args": {"pl": True, "profession": True, "turnover": 6000000, "cash": 1000000, "net": 2000000},
            "expect_value": {"audit": True, "limit": 5000000, "why": "ca_audit_turnover"}},
           {"args": {"pl": True, "turnover": 2000000, "net": 50000, "deemed": 120000, "presumptive_open": True, "above_exemption": True},
            "expect_value": {"audit": True, "limit": 100000000, "why": "ca_audit_lower"}},
           {"args": {"pl": True, "turnover": 2000000, "net": 50000, "deemed": 120000, "presumptive_open": True},
            "expect_value": {"audit": False, "limit": 100000000, "why": ""}},
           {"args": {}, "expect_value": {"audit": False, "limit": 100000000, "why": ""}}]}
save(aud)

# --- 3 which form: a business on its own profit and loss is ITR-3 ----------------------------------------------------------
f = load("myreturn.form")
if not any(p["name"] == "books" for p in f["params"]):
    f["params"].append(P("books", "boolean", False, "business / profession income from the person's own profit and loss (not presumptive)"))
    f["expr"]["cases"].insert(1, {"when": all_(eq("$business", True), eq("$books", True)),
                                  "then": {"vop": "record", "fields": {"form": "ITR-3", "why": "why_biz_books"}}})
    f["test_cases"].append({"args": {"total": 900000, "business": True, "books": True}, "expect_value": {"form": "ITR-3", "why": "why_biz_books"}})
    save(f, "books - business or profession income from the person's own profit and loss (no presumptive basis): ITR-3 (why_biz_books).")

# --- 4 settings: the kinds, the P&L kinds' presumptive twin, the nature-of-business codes for them ------------------------
s = load("myreturn.settings")
knob(s, "biz_kinds", ["", "44ADA", "44AD", "44AE", "business", "profession"], "business kinds a person may pick")
knob(s, "pl_as", {"business": "44AD", "profession": "44ADA"}, "own-P&L kinds: the presumptive section that would have applied (limits, s.44AB(e))")
knob(s, "pl_codes", {"business": ["ITR-3", "PartA_GEN2.NatOfBus.NatureOfBusiness", "Code"], "profession": ["ITR-3", "PartA_GEN2.NatOfBus.NatureOfBusiness", "Code"]},
     "own-P&L kinds: where the department's ITR-3 schema lists the nature-of-business codes [form, path, field]")
save(s, "biz_kinds (business / profession on the person's own profit and loss, besides 44ADA / 44AD / 44AE); pl_as (their presumptive twin, "
     "for the limits and s.44AB(e)); pl_codes (their nature-of-business codes, from the ITR-3 schema).")

# --- 5 the JSON words: the TDS head of a business receipt, Y / N ------------------------------------------------------------
j = load("myreturn.json")
knob(j, "tds_heads", {"business": "BP", "other": "OS"}, "Schedule TDS2 head of income: a business receipt (194J, 194C ...) or other sources")
knob(j, "yn", {"true": "Y", "false": "N"}, "a yes / no flag in the department's JSON")
knob(j, "cfl_blocks_itr3", ["LossCFCurrentAssmntYear2026", "LossCFCurrentAssmntYear2025", "LossCFCurrentAssmntYear2024", "LossCFCurrentAssmntYear2023",
                            "LossCFCurrentAssmntYear2022", "LossCFCurrentAssmntYear2021", "LossCFCurrentAssmntYear", "LossCFFromPrevYrToAY"],
     "ITR-3 Schedule CFL: the block of the 1st ... 8th year before (named by the loss's AY: 2025-26 ... 2018-19)")
knob(j, "cfl_summary_zero_itr3", ["BusLossOthThanSpecLossCF", "LossFrmSpecBusCF", "LossFrmSpecifiedBusCF", "OthSrcLossRaceHorseCF"],
     "ITR-3 Schedule CFL summaries: the business-loss and race-horse columns My return never carries (nil)")
knob(j, "code_54f", "54F", "the 54F exemption's code in ITR-3's ExemptionOrDednUs54 tables")
save(j, "tds_heads (ITR-3 Schedule TDS2: BP for a receipt of the business, OS otherwise); yn; ITR-3 Schedule CFL block names (by AY) and "
     "its nil business-loss columns; code_54f.")

# --- 6 ITR-3 for My return: its own rows (the CA side's ITR-3 rows read a trial balance) ---------------------------------
st = load("itr.settings")
knob(st, "own_maps", {"ITR-3": "ITR-3 myreturn"}, "My return's own itr.map rows for a form the CA side fills from books")
save(st, "own_maps - My return's ITR-3 has its own itr.map rows (ITR-3 myreturn); the CA side's ITR-3 rows (a trial balance) stay as they are.")

import store  # noqa: E402,F401 - registers the chips, as the app does
import itr_json  # noqa: E402

m = load("itr.map")
mp = next(p for p in m["params"] if p["name"] == "forms")
s3 = itr_json.schema_at("schemas/itr/ITR-3_2026_Main_V1.1.json")
FIX = {  # ITR-2 path (after ITR2 -> ITR3) -> ITR-3 path; None = not in ITR-3 (another row says it)
    "ITR3.PartA_GEN1.FilingStatus.OptOutNewTaxRegime": "ITR3.PartA_GEN1.FilingStatus.F10IEACurrAYOldRegime",
    "ITR3.PartB-TI.DeductionsUnderScheduleVIA": "ITR3.PartB-TI.DeductionsUndSchVIADtl.TotDeductUndSchVIA",
    "ITR3.PartB_TTI.ComputationOfTaxLiability.Rebate87A": "ITR3.PartB_TTI.ComputationOfTaxLiability.TaxPayableOnTI.Rebate87A",
    "ITR3.PartB_TTI.ComputationOfTaxLiability.TaxPayableOnRebate": "ITR3.PartB_TTI.ComputationOfTaxLiability.TaxPayableOnTI.TaxPayableOnRebate",
    "ITR3.PartB_TTI.ComputationOfTaxLiability.TotalSurcharge": "ITR3.PartB_TTI.ComputationOfTaxLiability.TaxPayableOnTI.TotalSurcharge",
    "ITR3.PartB_TTI.ComputationOfTaxLiability.EducationCess": "ITR3.PartB_TTI.ComputationOfTaxLiability.TaxPayableOnTI.EducationCess",
    "ITR3.PartB_TTI.ComputationOfTaxLiability.GrossTaxLiability": "ITR3.PartB_TTI.ComputationOfTaxLiability.TaxPayableOnTI.GrossTaxLiability",
    "ITR3.ScheduleOS.IncFrmLottery.DateRange.Upto15Of9": "ITR3.ScheduleOS.IncFrmLottery.DateRange.Up16Of6To15Of9",
    "ITR3.Schedule112A.TotalBalance112A": None,
}
FROM = {"ITR3.PartA_GEN1.FilingStatus.ItrFilingDueDate": "filing.due_rule",   # ITR-3: the Act's due date for the form
        "ITR3.Form_ITR3.FormName": "form"}
SRC = {"cg_st_other": "cg3_st_other", "cg_na": "cg3_na", "cfl": "cfl3"}      # whole blocks shaped for ITR-3 (myreturn.cg_facts)
EACH = {"cg_st_prop": "cg3_st_prop", "cg_lt_prop": "cg3_lt_prop",             # lists shaped for ITR-3: every field of the item, as named
        "fsi_rows": "fsi_rows3"}                                              # 2026-10-07 wave 3: ITR-3 Schedule FSI has a business block too
ITEM = {"ITR3.ScheduleTDS2.TDSOthThanSalaryDtls": {"HeadOfIncome": "head"}}
RENAME = {"ITR3.Schedule112A.Schedule112ADtls": {"LTCGBeforelowerB1B2": "LTCGBeforelower6and11"}}


def item_fields(path):
    v = s3["definitions"]["ITR3"]
    for k in path.split(".")[1:]:
        v = itr_json._ref(s3, itr_json._ref(s3, v)["properties"][k])  # noqa: SLF001
    return list(itr_json._ref(s3, v["items"])["properties"])  # noqa: SLF001
rows, dropped = [], []
for r in mp["default"]["ITR-2"]:
    r = copy.deepcopy(r)
    p = r["path"].replace("ITR2.", "ITR3.", 1).replace("Form_ITR2", "Form_ITR3")
    p = FIX.get(p, p)
    if p is None:
        dropped.append(r["path"])
        continue
    if not itr_json._has(s3, "ITR3", p.split(".", 1)[1]):  # noqa: SLF001
        dropped.append(r["path"])
        continue
    r["path"] = p
    if p in FROM:
        r["from"] = FROM[p]
    if r.get("from") in SRC:
        r["from"] = SRC[r["from"]]
    if r.get("each") in EACH:
        r["each"], r["item"] = EACH[r["each"]], {k: k for k in item_fields(p)}
    if p in ITEM:
        r["item"] |= ITEM[p]
    for a, b in RENAME.get(p, {}).items():
        r["item"][b] = r["item"].pop(a)
    rows.append(r)
B = "ITR3.ITR3ScheduleBP.BusinessIncOthThanSpec."
PL, NB, BS, GEN2 = "ITR3.PARTA_PL.", "ITR3.PARTA_PL.NoBooksOfAccPL.", "ITR3.PARTA_BS.NoBooksOfAccBS.", "ITR3.PartA_GEN2."
z = {"skip_zero": True}
rows += [
    {"path": "ITR3.PartA_GEN1.FilingStatus.IncFrmBusOrProf", "from": "biz3.has"},
    {"path": "ITR3.Verification.Date", "from": "today"},
    {"path": "ITR3.Verification.Place", "from": "client.city"},
    {"path": "ITR3.PartA_GEN1.FilingStatus.OptOldRegimeCurrAY", "from": "regime_opt_out"},
    {"path": GEN2 + "AuditInfo.LiableSec44AAflg", "from": "biz3.books_44aa"},
    {"path": GEN2 + "AuditInfo.IncDclrdUs", "from": "biz3.declared_us"},
    {"path": GEN2 + "AuditInfo.LiableSec44ABflg", "from": "=N"},
    {"path": GEN2 + "NatOfBus.NatureOfBusiness", "from": "biz3.nature_pl", **z},
    # 2026-10-08 wave 4: Schedule GST - the turnover per GSTIN (typed, or read from a GSTR-3B summary)
    {"path": "ITR3.ScheduleGST.TurnoverGrsRcptForGSTIN", "each": "gst_rows3", "item": {"GSTINNo": "gstin", "AmtTurnGrossRcptGSTIN": "turnover"}},
    # Part A-P&L 61-63: presumptive income (44AD / 44ADA / 44AE)
    {"path": PL + "NatOfBus44AD", "from": "biz.nature_ad", **z},
    {"path": PL + "PersumptiveInc44AD.GrsTrnOverOrReceipt", "from": "biz.ad_receipts", **z},
    {"path": PL + "PersumptiveInc44AD.GrsTrnOverBank", "from": "biz.ad_digital", **z},
    {"path": PL + "PersumptiveInc44AD.GrsTotalTrnOverInCash", "from": "biz.ad_cash", **z},
    {"path": PL + "PersumptiveInc44AD.PersumptiveInc44AD6Per", "from": "biz.ad_6", **z},
    {"path": PL + "PersumptiveInc44AD.PersumptiveInc44AD8Per", "from": "biz.ad_8", **z},
    {"path": PL + "PersumptiveInc44AD.TotPersumptiveInc44AD", "from": "biz.ad_income", **z},
    {"path": PL + "NatOfBus44ADA", "from": "biz.nature_ada", **z},
    {"path": PL + "PersumptiveInc44ADA.GrsReceipt", "from": "biz.ada_receipts", **z},
    {"path": PL + "PersumptiveInc44ADA.GrsTrnOverBank44ADA", "from": "biz.ada_digital", **z},
    {"path": PL + "PersumptiveInc44ADA.GrsTotalTrnOverInCash44ADA", "from": "biz.ada_cash", **z},
    {"path": PL + "PersumptiveInc44ADA.TotPersumptiveInc44ADA", "from": "biz.ada_income", **z},
    {"path": PL + "NatOfBus44AE", "from": "biz.nature_ae", **z},
    {"path": PL + "GoodsDtlsUs44AE", "each": "ae_rows", "item": {"RegNumberGoodsCarriage": "reg", "OwnedLeasedHiredFlag": "own", "TonnageCapacity": "tons",
                                                                  "HoldingPeriod": "months", "PresumptiveIncome": "income"}},
    {"path": PL + "TotalNumOfMonths", "from": "biz3.ae_months", **z},
    {"path": PL + "TotalPrsumptvIncUs44EGoods", "from": "biz.ae_income", **z},
    {"path": PL + "TotalPrsumptvIncUs44E", "from": "biz.ae_income", **z},
    # Part A-P&L 64: no regular books of account (business, then profession)
    {"path": NB + "GrossReceipt", "from": "biz3.nb.receipts"},
    {"path": NB + "GrsRcptAccPayeeOrBankMode", "from": "biz3.nb.bank"},
    {"path": NB + "GrsRcptOtherMode", "from": "biz3.nb.other"},
    {"path": NB + "GrossProfit", "from": "biz3.nb.gp"},
    {"path": NB + "Expenses", "from": "biz3.nb.expenses"},
    {"path": NB + "NetProfit", "from": "biz3.nb.np"},
    {"path": NB + "GrossReceiptPrf", "from": "biz3.nbp.receipts"},
    {"path": NB + "GrsRcptAccPayeeOrBankModePrf", "from": "biz3.nbp.bank"},
    {"path": NB + "GrsRcptOtherModePrf", "from": "biz3.nbp.other"},
    {"path": NB + "GrossProfitPrf", "from": "biz3.nbp.gp"},
    {"path": NB + "ExpensesPrf", "from": "biz3.nbp.expenses"},
    {"path": NB + "NetProfitPrf", "from": "biz3.nbp.np"},
    {"path": NB + "TotBusinessProfession", "from": "biz3.nb_total"},
    {"path": BS + "TotSundryDbtAmt", "from": "biz3.bs.debtors", **z},
    {"path": BS + "TotSundryCrdAmt", "from": "biz3.bs.creditors", **z},
    {"path": BS + "TotStkInTradAmt", "from": "biz3.bs.stock", **z},
    {"path": BS + "CashBalAmt", "from": "biz3.bs.cash_in_hand", **z},
    # Schedule BP: the P&L's profit, the presumptive part out (item 3) and back in as deemed (item 36)
    {"path": B + "ProfBfrTaxPL", "from": "biz3.pl_profit"},
    {"path": B + "PLUs44sChapXIIG", "from": "biz3.deemed"},
    {"path": B + "ProfitLossInclRefrdSec.ProfitLossUs44AD", "from": "biz3.ad"},
    {"path": B + "ProfitLossInclRefrdSec.ProfitLossUs44ADA", "from": "biz3.ada"},
    {"path": B + "ProfitLossInclRefrdSec.ProfitLossUs44AE", "from": "biz3.ae"},
    {"path": B + "BalancePLOthThanSpecBus", "from": "biz3.balance"},
    {"path": B + "AdjustedPLOthThanSpecBus", "from": "biz3.balance"},
    {"path": B + "AdjustPLAfterDeprOthSpecInc", "from": "biz3.balance"},
    {"path": B + "TotAfterAddToPLDeprOthSpecInc", "from": "biz3.balance"},
    {"path": B + "PLAftAdjDedBusOthThanSpec", "from": "biz3.balance"},
    {"path": B + "DeemedProfitBusUs.Section44AD", "from": "biz3.ad"},
    {"path": B + "DeemedProfitBusUs.Section44ADA", "from": "biz3.ada"},
    {"path": B + "DeemedProfitBusUs.Section44AE", "from": "biz3.ae"},
    {"path": B + "DeemedProfitBusUs.TotDeemedProfitBusUs", "from": "biz3.deemed"},
    {"path": B + "NetPLAftAdjBusOthThanSpec", "from": "biz3.net"},
    {"path": B + "NetPLBusOthThanSpec7A7B7C", "from": "biz3.net"},
    {"path": B + "IncomeOtherThanRule", "from": "biz3.net"},
    {"path": "ITR3.ITR3ScheduleBP.IncChrgUnHdProftGain", "from": "biz3.net"},
    # the business head through Part B-TI, CYLA and BFLA
    {"path": "ITR3.PartB-TI.ProfBusGain.ProfGainNoSpecBus", "from": "biz3.net"},
    {"path": "ITR3.PartB-TI.ProfBusGain.TotProfBusGain", "from": "biz3.net"},
    {"path": "ITR3.PartB-TI.DeductionsUndSchVIADtl.PartBchapterVIA", "from": "via.total"},
    {"path": "ITR3.ScheduleCYLA.BusProfExclSpecProf.IncCYLA.IncOfCurYrUnderThatHead", "from": "biz3.net"},
    {"path": "ITR3.ScheduleCYLA.BusProfExclSpecProf.IncCYLA.IncOfCurYrAfterSetOff", "from": "biz3.net"},
    {"path": "ITR3.ScheduleBFLA.BusProfExclSpecProf.IncBFLA.IncOfCurYrUndHeadFromCYLA", "from": "biz3.net"},
    {"path": "ITR3.ScheduleBFLA.BusProfExclSpecProf.IncBFLA.IncOfCurYrAfterSetOffBFLosses", "from": "biz3.net"},
]
bad = [r["path"] for r in rows if not itr_json._has(s3, "ITR3", r["path"].split(".", 1)[1])]  # noqa: SLF001
assert not bad, bad
print("ITR-3 myreturn:", len(rows), "rows;", "left out:", dropped)
if mp["default"].get("ITR-3 myreturn") != rows:
    mp["default"]["ITR-3 myreturn"] = rows
    for t in m["test_cases"]:
        ev = t.get("expect_value")
        if isinstance(ev, dict) and isinstance(ev.get("forms"), dict) and not t.get("args"):
            ev["forms"]["ITR-3 myreturn"] = rows
    m["version"] += 1
    n = ("ITR-3 myreturn - My return's own ITR-3: every ITR-2 row at its ITR-3 path (Part B-TTI's tax under TaxPayableOnTI, the "
         "old regime as Form 10-IEA F10IEACurrAYOldRegime, the Act's due date, a business receipt's TDS under head BP), plus Part A-GEN2 "
         "(44AA, income declared under 44AD / 44ADA / 44AE, nature of business), Part A-P&L 61-63 (presumptive) and 64 (no regular "
         "books: receipts by mode, gross profit, expenses, net profit), Part A-BS no-books figures, Schedule BP, the business head in "
         "Part B-TI / CYLA / BFLA. Made by tools/make_itr3_myreturn.py from the ITR-2 rows.")
    if n not in m["description_nl"]:
        m["description_nl"] += " " + NOTE + n
    write(m)

# --- 7 words ----------------------------------------------------------------------------------------------------------------
u = load("ui.myreturn")
W = {
    "why_biz_books": "Business or profession income worked out from your own figures (receipts, gross profit, expenses, net profit - not presumptive) - ITR-3.",
    "biz_business": "Business - my own profit and loss (not presumptive)",
    "biz_profession": "Profession - my own profit and loss (not presumptive)",
    "pl_h": "Profit and loss (no regular books of account)",
    "pl_p": "Presumptive income is not open here (or not chosen): type the year's figures - the receipts above, then gross profit, expenses and net profit. "
            "The balance-sheet figures on 31 March are optional. They go into ITR-3 Part A-P&L and Part A-BS for those who do not keep regular books.",
    "biz_gp": "Gross profit", "biz_expenses": "Expenses", "biz_np": "Net profit (blank: gross profit less expenses)",
    "biz_debtors": "Sundry debtors (31 March)", "biz_creditors": "Sundry creditors (31 March)", "biz_stock": "Stock in trade (31 March)",
    "biz_cash_in_hand": "Cash in hand (31 March)",
    "pl_income": "Business income {income} (net profit) on receipts {receipts}",
    "ca_h": "This return needs a chartered accountant",
    "ca_audit_turnover": "Receipts of {receipts} are over the {limit} tax-audit limit (section 44AB): the accounts must be audited by a chartered accountant "
                         "and the audit report filed before the return. My return does not do audits - get a CA. {product}'s CA-firm side "
                         "(Intake, Reconcile, Compute, Tax audit) handles them.",
    "ca_audit_lower": "The profit typed ({net}) is below the presumptive {deemed} and your income is above the basic exemption: section 44AB(e) needs a tax "
                      "audit by a chartered accountant. My return does not do audits - get a CA ({product}'s CA-firm side handles them), or take the presumptive basis.",
    "ca_loss": "A business loss ({net}) is carried forward only with books of account and a return a CA prepares - My return does not file it. Get a CA "
               "({product}'s CA-firm side handles books, audits and losses).",
}
for k, v in W.items():
    knob(u, k, v)
save(u, "ITR-3 from My return: the own-profit-and-loss kinds and fields, why_biz_books, and the CA messages (tax audit s.44AB, a business loss).")
print("done")
