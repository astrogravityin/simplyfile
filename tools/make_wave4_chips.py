"""2026-10-08 My return, wave 4 (law): the gaps closed after wave 3 -
  1 a second Form 16 from the same employer (same TAN) is asked about (replace - a revised Form 16 - or keep both); two employers'
    standard deduction / Chapter VI-A counted once (check myreturn.check_employers);
  2 s.44AB: the cash share of receipts AND payments (the 10 crore / 75 lakh provisos), s.44AD(4) / (5) (left 44AD within five years);
  3 GST turnover per GSTIN (typed, or read from a GSTR-3B summary) - check myreturn.checks "gst";
  4 losses brought forward from last year's ITR-3 (its Schedule CFL layout);
  5 the time limits of 54 / 54F (1 year before - 2 years after, 3 years to build), 54EC (6 months) and the CGAS deposit (by the
    s.139(1) due date) - chip myreturn.cg_window;
  6 several exemptions on one sale (54 + 54EC ...), split by amount (knob ex_max);
  7 a CAMS / KFintech capital-gains PDF (chip myreturn.read cas_pdf);
  8 the buyer's 194IA TDS from 26AS Part A2 / Part IV (chip myreturn.read a2_26as);
  9 the updated return of an earlier year: that year's special rates (111A / 112A / 112 / 115BB ...), surcharge with marginal
    relief, and 234C (chips myreturn.year_rates / year_tax / itru);
 10 relief u/s 89 for an earlier year with that year's surcharge (chip myreturn.arrear_row on myreturn.year_tax);
 11 Schedule FA tables of signing authority, trusts and other income from outside India (tools/make_wave3_map.py FA_KINDS);
 12 (myreturn.py only: the old regime chosen in the save that first adds a business is checked against the new form's due date).
Writes / updates the chips - every chip's cases are worked out and checked against figures said by hand. Re-runnable.
Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/make_wave4_chips.py   (then tools/make_wave3_map.py, tools/make_itr3_myreturn.py)
Law: Income-tax Act 1961 as amended by the Finance Act 2025 (AY 2026-27, FY 2025-26); earlier years by the Finance Acts of their year."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "chips"
NOTE = "2026-10-08: "
sys.path.insert(0, str(ROOT))


def load(cid):
    return json.loads((CH / f"{cid}.json").read_text(encoding="utf-8"))


def write(c):
    (CH / f"{c['chip_id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_chip(cid, args):
    from core import engine  # noqa: PLC0415
    import store  # noqa: F401,PLC0415 - registers the portal's chips
    engine.refresh()
    return engine.run(cid, args)


def save(c, note=""):
    """Write a changed chip (version + 1, the note once); the no-args test answers what the chip now answers ({product} filled)."""
    path = CH / f"{c['chip_id']}.json"
    before = json.loads(path.read_text(encoding="utf-8"))
    a, b = dict(before), dict(c)
    for x in (a, b):
        x.pop("version", None)
        x.pop("description_nl", None)
        x.pop("test_cases", None)
    if a == b:
        print("same", c["chip_id"])
        return
    c["version"] = before["version"] + 1
    if note and note not in c.get("description_nl", ""):
        c["description_nl"] = c.get("description_nl", "") + " " + NOTE + note
    write(c)
    for t in c["test_cases"]:
        if not t.get("args") and isinstance(t.get("expect_value"), dict):
            t["expect_value"] = run_chip(c["chip_id"], {})
        else:
            got = run_chip(c["chip_id"], t["args"])
            assert got == t["expect_value"], (c["chip_id"], t["args"], got, t["expect_value"])
    write(c)
    print("wrote", c["chip_id"], "v", c["version"])


def knob(c, name, default, label):
    """A knob on a record chip that hands its params back: the param and the field."""
    for p in c["params"]:
        if p["name"] == name:
            p["default"] = default
            break
    else:
        c["params"].append({"name": name, "type": "text" if isinstance(default, str) else "boolean" if isinstance(default, bool)
                            else "number" if isinstance(default, (int, float)) else "json", "default": default, "label": label})
    if c["expr"].get("vop") == "record":
        c["expr"]["fields"][name] = "$" + name


def V(op, **kw):
    return {"vop": op, **kw}


def T(op, **kw):
    return {"op": op, **kw}


def CHIP(cid, args=None):
    return {"chip": cid, "args": args or {}}


def GET(value, path):
    return V("get", value=value, path=path)


def CHOOSE(cases, other):
    return {"vop": "choose", "cases": [{"when": w, "then": t} for w, t in cases], "else": other}


def YES(cond):
    return CHOOSE([(cond, True)], False)


def MX(*v):
    return V("largest", values=list(v))


def MN(*v):
    return V("smallest", values=list(v))


def ADD(*v):
    return V("total", values=list(v))


def SUB(a, b):
    return V("sub", a=a, b=b)


def MUL(a, b):
    return V("mul", a=a, b=b)


def DIV(a, b):
    return V("div", a=a, b=b)


def RND(v):
    return V("round_to", value=v)


def TPL(text, **fields):
    return V("template", text=text, values=V("record", fields=fields))


def OR0(v):
    return V("coalesce", values=[v, 0])


def EQ(a, b):
    return T("eq", left=a, right=b)


def GE(a, b):
    return T("ge", left=a, right=b)


def GT(a, b):
    return T("gt", left=a, right=b)


def LE(a, b):
    return T("le", left=a, right=b)


def LT(a, b):
    return T("lt", left=a, right=b)


def ALL(*items):
    return T("all", items=list(items))


def ANY(*items):
    return T("any", items=list(items))


def NOT(item):
    return T("not", item=item)


def IN(v, s):
    return T("in_set", value=v, set=s)


def P(name, default, label, typ=None):
    typ = typ or ("boolean" if isinstance(default, bool) else "number" if isinstance(default, (int, float)) else "text" if isinstance(default, str) else "json")
    return {"name": name, "type": typ, "default": default, "label": label}


def record_of(params):
    return V("record", fields={p["name"]: "$" + p["name"] for p in params})


def chip(cid, label, aliases, params, expr, desc, cases, returns="record"):
    aliases = list(dict.fromkeys(aliases))       # re-run: an alias added once stays once
    c = {"chip_id": cid, "kind": "accessor", "set": "myreturn", "label": label, "aliases": aliases, "params": params, "expr": expr,
         "returns": returns, "version": 1, "status": "published", "description_nl": NOTE + desc, "test_cases": []}
    old = CH / f"{cid}.json"
    if old.exists():
        o = json.loads(old.read_text(encoding="utf-8"))
        c["version"] = o.get("version", 1) + (0 if (o.get("params"), o.get("expr")) == (params, expr) else 1)
        od = o.get("description_nl", "")
        if od and not od.startswith(NOTE + desc):                             # a chip of an earlier wave keeps its history
            c["description_nl"] = od if NOTE + desc in od else od + " " + NOTE + desc
    write(c)
    seen = set()
    for args, want in cases:                     # every case: the answer worked out, checked against what was said by hand
        if json.dumps(args, sort_keys=True) in seen:      # re-run: an earlier run's case read back from the chip is not added twice
            continue
        seen.add(json.dumps(args, sort_keys=True))
        got = run_chip(cid, args)
        if isinstance(want, dict):
            bad = {k2: (got.get(k2), v) for k2, v in want.items() if got.get(k2) != v}
        else:
            bad = {"value": (got, want)} if got != want else {}
        assert not bad, (cid, args, bad)
        c["test_cases"].append({"args": args, "expect_value": got})
    write(c)
    print("wrote", cid, f"({len(c['test_cases'])} cases)")


RATES = CHIP("myreturn.rates")
CGR = CHIP("myreturn.cg_rules")

# --- 1 a second Form 16 from the same employer; two employers ------------------------------------------------------------------
chip("myreturn.doc_clash", "My return: a document like one already in - ask first?", ["second form 16", "same tan", "replace or keep"],
     [P("kind", "", "the kind of the document just read"), P("one_per_kind", [], "kinds a return holds one of (chip myreturn.settings one_per_kind)"),
      P("same_kind", 0, "documents of that kind already in (another file)"), P("tan_kinds", [], "kinds one per employer (chip myreturn.settings tan_kinds)"),
      P("same_tan", 0, "documents of that kind already in for the same employer (TAN)")],
     V("record", fields={"why": CHOOSE([(ALL(IN("$kind", "$one_per_kind"), GT("$same_kind", 0)), "same"),
                                        (ALL(IN("$kind", "$tan_kinds"), GT("$same_tan", 0)), "same_tan")], "")}),
     "A second AIS / 26AS / pre-filled JSON / filed return is asked about (replace it, or keep both); a second Form 16 from the same employer "
     "(the same TAN) too - a revised Form 16 replaces the first, two Form 16s for two spells with one employer are both kept. A Form 16 "
     "from another TAN is a second employer (a job change): kept, no question - and check myreturn.check_employers looks at the two.",
     [({"kind": "ais", "one_per_kind": ["ais", "26as"], "same_kind": 1}, {"why": "same"}),
      ({"kind": "form16", "one_per_kind": ["ais"], "tan_kinds": ["form16"], "same_kind": 1, "same_tan": 1}, {"why": "same_tan"}),
      ({"kind": "form16", "one_per_kind": ["ais"], "tan_kinds": ["form16"], "same_kind": 1, "same_tan": 0}, {"why": ""}),
      ({"kind": "bank", "one_per_kind": ["ais"], "tan_kinds": ["form16"], "same_kind": 3}, {"why": ""})])

STD = GET(RATES, TPL("std_deduction.{r}", r="$regime"))
CAP80C = GET(RATES, "cap_80c")
TWO = GE("$employers", 2)
chip("myreturn.check_employers", "My return: two employers in a year - standard deduction and 80C counted once", ["two employers", "job change", "standard deduction twice"],
     [P("employers", 0, "employers this year (Form 16s of different TANs)"), P("regime", "new", "the regime of the return"),
      P("via_given", 0, "80C + 80CCC + 80CCD(1) as the Form 16s gave them, added up"), P("part", "std", "std - the standard deduction; via - Chapter VI-A")],
     V("record", fields={
         "what": CHOOSE([(EQ("$part", "via"), "two_emp_80c")], "two_employers"),
         "level": CHOOSE([(ALL(TWO, EQ("$part", "std")), "amber"), (ALL(TWO, EQ("$part", "via"), GT("$via_given", CAP80C)), "amber")], "ok"),
         "a": CHOOSE([(EQ("$part", "via"), "$via_given")], MUL("$employers", STD)),
         "b": CHOOSE([(EQ("$part", "via"), CAP80C)], STD),
         "gap": CHOOSE([(EQ("$part", "via"), MX(SUB("$via_given", CAP80C), 0))], MX(MUL(SUB("$employers", 1), STD), 0)),
         "word": CHOOSE([(EQ("$part", "via"), "c_two_emp_80c_lv")], "c_two_employers_lv")}),
     "s.16(ia): the standard deduction is one a year (75,000 new regime / 50,000 old) however many employers paid salary - each employer's "
     "Form 16 took it off, the return takes it once (the salary of all employers is added up first). s.80C / 80CCE: 1.5 lakh in all - an "
     "investment declared to both employers counts once. The tax each employer deducted was worked out as if it were the only one: "
     "expect tax to pay. Shown as a check (amber) the person may accept.",
     [({"employers": 2, "regime": "new"}, {"level": "amber", "a": 150000, "b": 75000, "gap": 75000, "what": "two_employers"}),
      ({"employers": 1, "regime": "new"}, {"level": "ok"}),
      ({"employers": 2, "regime": "old"}, {"a": 100000, "b": 50000}),
      ({"employers": 2, "part": "via", "via_given": 250000}, {"level": "amber", "a": 250000, "b": 150000, "gap": 100000, "what": "two_emp_80c"}),
      ({"employers": 2, "part": "via", "via_given": 140000}, {"level": "ok", "gap": 0})])

# --- 2 s.44AB: cash share of receipts and payments; s.44AD(4) / (5) ----------------------------------------------------------------
AB = load("myreturn.audit_44ab")
old_cases = [(t["args"], t["expect_value"]) for t in AB["test_cases"]]
ABK = {p["name"]: p for p in AB["params"]}
AB_PARAMS = [ABK[n] for n in ("pl", "profession", "turnover", "cash", "net", "deemed", "presumptive_open", "above_exemption", "cash_pct_max",
                              "biz_limit", "biz_limit_low_cash", "prof_limit", "prof_limit_low_cash")] + [
    P("pay_total", 0, "payments of the year (all modes) - s.44AB(a) / (b) provisos"),
    P("pay_cash", -1, "of which in cash; -1 = not typed (the receipts' share stands for both until it is)"),
    P("ad_left", False, "s.44AD(4): declared income under 44AD for a year, then not under it in one of the five years after - and this year is within the five after that"),
    P("ad_business", False, "an eligible business (44AD's kind: 44AD or a business on its own profit and loss), not a profession"),
    P("kind_44ad", False, "44AD chosen this year")]
CASH_OK = ANY(LE("$turnover", 0), LE(DIV(MUL("$cash", 100), "$turnover"), "$cash_pct_max"))
PAY_KNOWN = ALL(GE("$pay_cash", 0), GT("$pay_total", 0))
PAY_OK = ANY(NOT(PAY_KNOWN), LE(DIV(MUL("$pay_cash", 100), "$pay_total"), "$cash_pct_max"))
LOW = ALL(CASH_OK, PAY_OK)
PROF = EQ("$profession", True)
LIMIT = CHOOSE([(ALL(PROF, LOW), "$prof_limit_low_cash"), (PROF, "$prof_limit"), (LOW, "$biz_limit_low_cash")], "$biz_limit")
OVER = ALL(EQ("$pl", True), GT("$turnover", LIMIT))
LOWER = ALL(EQ("$pl", True), EQ("$presumptive_open", True), LT("$net", "$deemed"), EQ("$above_exemption", True))
AD4 = ALL(EQ("$ad_left", True), EQ("$ad_business", True), EQ("$above_exemption", True))
ASK_PAY = ALL(EQ("$pl", True), NOT(PAY_KNOWN), CASH_OK, GT("$turnover", CHOOSE([(PROF, "$prof_limit")], "$biz_limit")),
              LE("$turnover", CHOOSE([(PROF, "$prof_limit_low_cash")], "$biz_limit_low_cash")))
AB_EXPR = V("record", fields={
    "audit": YES(ANY(OVER, LOWER, AD4)), "limit": LIMIT,
    "why": CHOOSE([(OVER, "ca_audit_turnover"), (LOWER, "ca_audit_lower"), (AD4, "ca_audit_44ad4")], ""),
    "ask_pay": YES(ASK_PAY), "ad_closed": YES(ALL(EQ("$ad_left", True), EQ("$kind_44ad", True)))})
B0 = {"pl": True, "turnover": 15000000, "cash": 0, "net": 1200000}
chip("myreturn.audit_44ab", AB["label"], AB["aliases"] + ["44ad(4)", "cash payments"], AB_PARAMS, AB_EXPR,
     "s.44AB(a) / (b) provisos: the higher limit (10 crore business, 75 lakh profession) needs BOTH the cash receipts AND the cash payments at "
     "5% or less of the year's receipts / payments - pay_total / pay_cash (until the payments are typed the receipts' share stands for both, "
     "and ask_pay says the payments decide the limit). s.44AD(4): one who declared income under 44AD and then not under it in any of the five "
     "years after may not use 44AD for the five years after that; s.44AD(5) with s.44AB(e): such a person with income above the basic exemption "
     "keeps books and is audited - why ca_audit_44ad4. ad_closed: 44AD chosen while it is closed.",
     old_cases + [
         (B0 | {"pay_total": 12000000, "pay_cash": 1200000}, {"audit": True, "limit": 10000000, "why": "ca_audit_turnover", "ask_pay": False}),
         (B0 | {"pay_total": 12000000, "pay_cash": 300000}, {"audit": False, "limit": 100000000, "ask_pay": False}),
         (B0, {"audit": False, "limit": 100000000, "ask_pay": True}),
         ({"pl": True, "profession": True, "turnover": 6000000, "cash": 0, "pay_total": 3000000, "pay_cash": 600000, "net": 2000000},
          {"audit": True, "limit": 5000000, "why": "ca_audit_turnover"}),
         ({"pl": True, "turnover": 4000000, "net": 400000, "ad_left": True, "ad_business": True, "above_exemption": True}, {"audit": True, "why": "ca_audit_44ad4"}),
         ({"turnover": 4000000, "ad_left": True, "ad_business": True, "above_exemption": False, "kind_44ad": True}, {"audit": False, "why": "", "ad_closed": True}),
         ({"pl": True, "profession": True, "turnover": 4000000, "ad_left": True, "ad_business": False, "above_exemption": True}, {"audit": False})])

# --- 5 the time limits of the exemptions (54 / 54F / 54EC / CGAS) ------------------------------------------------------------------
cg = load("myreturn.cg_rules")
for k2, v, lbl in [("ex_before_months", 12, "s.54 / 54F: a house bought within 1 year before the transfer ..."),
                   ("ex_after_months", 24, "s.54 / 54F: ... or 2 years after it"),
                   ("build_months", 36, "s.54 / 54F: a house built within 3 years after the transfer"),
                   ("cgas_by", "07-31", "s.54(2) / 54F(4): the gain not used by the due date of the return u/s 139(1) is deposited in the Capital Gains Accounts "
                                        "Scheme by that day - 31 July of the AY for one whose accounts are not audited (the only kind My return files)"),
                   ("ex_max", 4, "exemptions claimed against one sale (54 and 54EC on one house ...), at most")]:
    knob(cg, k2, v, lbl)
save(cg, "ex_before_months / ex_after_months / build_months (s.54, 54F), cgas_by (s.54(2), 54F(4)), ex_max (several exemptions on one sale).")

SOLD, ON = "$sold", "$on"
DATED = ALL(NOT(EQ(SOLD, "")), NOT(EQ(ON, "")))
EC = EQ("$kind", "54EC")
FROM = V("date_shift", date=SOLD, months=MUL(GET(CGR, "ex_before_months"), -1))
TO = V("date_shift", date=SOLD, months=CHOOSE([(EQ("$build", True), GET(CGR, "build_months"))], GET(CGR, "ex_after_months")))
TO_EC = V("date_shift", date=SOLD, months=GET(CGR, "ec_months"))
IN_WIN = CHOOSE([(EC, YES(ALL(GE(ON, SOLD), LE(ON, TO_EC))))], YES(ALL(GE(ON, FROM), LE(ON, TO))))
INVEST_OK = CHOOSE([(DATED, IN_WIN)], True)
CGAS_BY = TPL("{y}-{md}", y="$ay_year", md=GET(CGR, "cgas_by"))
CGAS_OK = CHOOSE([(ANY(EC, EQ("$cgas_on", ""), LE("$cgas", 0)), True)], YES(ALL(LE("$cgas_on", CGAS_BY), ANY(EQ(SOLD, ""), GE("$cgas_on", SOLD)))))
chip("myreturn.cg_window", "My return: is an exemption's investment in time? (54 / 54F / 54EC / CGAS)", ["54 time limit", "54ec 6 months", "cgas due date", "construction 3 years"],
     [P("kind", "", "54 / 54F / 54EC"), P("sold", "", "the day of the transfer (YYYY-MM-DD)"), P("on", "", "the day the house was bought / built or the bonds were bought"),
      P("build", False, "the new house is built (not bought)"), P("invested", 0, "the amount invested"), P("cgas", 0, "deposited in the Capital Gains Accounts Scheme"),
      P("cgas_on", "", "the day of the deposit"), P("ay_year", 2026, "the AY's first year (the deposit's last day is in it)")],
     V("record", fields={"invest_ok": INVEST_OK, "cgas_ok": CGAS_OK, "from": CHOOSE([(EC, SOLD)], FROM), "to": CHOOSE([(EC, TO_EC)], TO), "cgas_by": CGAS_BY,
                         "why": CHOOSE([(EQ(INVEST_OK, False), TPL("ex_late_{k}", k="$kind")), (EQ(CGAS_OK, False), "ex_cgas_late"),
                                        (ALL(NOT(DATED), GT("$invested", 0)), "ex_no_date")], "")}),
     "s.54 / 54F: the new house bought within 1 year before or 2 years after the transfer, or built within 3 years after it; s.54EC: the bonds "
     "bought within 6 months after the transfer; s.54(2) / 54F(4): what is not invested by the due date of the return u/s 139(1) counts only if "
     "deposited in the Capital Gains Accounts Scheme by that day. Out of time: not counted (invest_ok / cgas_ok false, and why). A date not "
     "typed is taken as in time and said so (ex_no_date) - Table D asks for it.",
     [({"kind": "54", "sold": "2025-06-10", "on": "2024-07-01", "invested": 1}, {"invest_ok": True, "why": ""}),
      ({"kind": "54", "sold": "2025-06-10", "on": "2024-06-01", "invested": 1}, {"invest_ok": False, "why": "ex_late_54"}),
      ({"kind": "54", "sold": "2025-06-10", "on": "2027-06-10"}, {"invest_ok": True}),
      ({"kind": "54", "sold": "2025-06-10", "on": "2027-06-11"}, {"invest_ok": False}),
      ({"kind": "54F", "sold": "2025-06-10", "on": "2028-05-01", "build": True}, {"invest_ok": True, "to": "2028-06-10"}),
      ({"kind": "54F", "sold": "2025-06-10", "on": "2028-05-01"}, {"invest_ok": False, "why": "ex_late_54F"}),
      ({"kind": "54EC", "sold": "2025-06-10", "on": "2025-12-10"}, {"invest_ok": True}),
      ({"kind": "54EC", "sold": "2025-06-10", "on": "2025-12-11"}, {"invest_ok": False, "why": "ex_late_54EC"}),
      ({"kind": "54EC", "sold": "2025-06-10", "on": "2025-06-01"}, {"invest_ok": False}),
      ({"kind": "54", "sold": "2025-06-10", "cgas": 500000, "cgas_on": "2026-07-31"}, {"cgas_ok": True, "cgas_by": "2026-07-31"}),
      ({"kind": "54", "sold": "2025-06-10", "cgas": 500000, "cgas_on": "2026-08-01"}, {"cgas_ok": False, "why": "ex_cgas_late"}),
      ({"kind": "54", "sold": "", "invested": 900000}, {"invest_ok": True, "why": "ex_no_date"})])

# --- 9 / 10 the tax of an earlier year: that year's special rates, surcharge (with marginal relief) and cess --------------------------
S4 = [{"above": 5000000, "rate": 10}, {"above": 10000000, "rate": 15}]
S37 = S4 + [{"above": 20000000, "rate": 25}, {"above": 50000000, "rate": 37}]
S25 = S4 + [{"above": 20000000, "rate": 25}]
OLD_CG = {"r111a": 15, "r112a": 10, "x112a": 100000, "r112": 20}
NEW_CG = {"r111a": 20, "r112a": 12.5, "x112a": 125000, "r112": 12.5}


def yr(sur_old, sur_new, cg_, cap_a, cap_112, rebate_special=True, **more):
    one = lambda sur: {"surcharge": sur, "cap_a": cap_a, "cap_112": cap_112, "r30": 30, "rebate_special": rebate_special} | cg_ | more  # noqa: E731
    return {"old": one(sur_old), "new": one(sur_new)}


YEARS = {
    "2015": yr([{"above": 10000000, "rate": 12}], [], OLD_CG | {"r112a": 0, "x112a": 0}, 100, 100),
    "2016": yr([{"above": 10000000, "rate": 15}], [], OLD_CG | {"r112a": 0, "x112a": 0}, 100, 100),
    "2017": yr(S4, [], OLD_CG | {"r112a": 0, "x112a": 0}, 100, 100),
    "2018": yr(S4, [], OLD_CG, 100, 100),
    "2019": yr(S37, S37, OLD_CG, 15, 100),
    "2020": yr(S37, S37, OLD_CG, 15, 100),
    "2021": yr(S37, S37, OLD_CG, 15, 100),
    "2022": yr(S37, S37, OLD_CG, 15, 15),
    "2023": yr(S37, S25, OLD_CG, 15, 15),
    "2024": yr(S37, S25, NEW_CG, 15, 15, early=OLD_CG | {"x112a": 125000}),     # the 1.25 lakh is for all of FY 2024-25
    "2025": {"old": {"surcharge": S37, "cap_a": 15, "cap_112": 15, "r30": 30, "rebate_special": True} | NEW_CG,
             "new": {"surcharge": S25, "cap_a": 15, "cap_112": 15, "r30": 30, "rebate_special": False} | NEW_CG},
}
YR_KNOBS = [P("fy", 2025, "the financial year (its first year: 2019 = FY 2019-20)"), P("regime", "old", "old / new"),
            P("early", False, "FY 2024-25 only: the gains were on transfers before 23 July 2024 (the rates before the Finance (No. 2) Act 2024)"),
            P("years", YEARS, "each FY's special rates and surcharge: 111A, 112A (and its exemption), 112, the 30% of 115BB / 115BBJ / 115BBH; the "
                              "surcharge steps; the surcharge cap on 111A / 112A (15% from FY 2019-20) and on 112 (15% from FY 2022-23); whether the 87A "
                              "rebate is against special-rate tax (not in the new regime from FY 2025-26)")]
Y = lambda f: TPL("{y}.{r}." + f, y="$fy", r="$regime")  # noqa: E731
YK = lambda f: GET("$years", Y(f))  # noqa: E731
SB = CHIP("myreturn.slabs_by_year")
SBK = lambda f: GET(SB, TPL("years.{y}.{r}." + f, y="$fy", r="$regime"))  # noqa: E731
EARLY = ALL(EQ("$early", True), EQ("$fy", 2024))
CGF = lambda f: CHOOSE([(EARLY, GET("$years", TPL("{y}.{r}.early." + f, y="$fy", r="$regime")))], YK(f))  # noqa: E731
chip("myreturn.year_rates", "My return: an earlier year's rates - slabs, rebate, special rates, surcharge, cess", ["rates of an earlier year", "surcharge history", "111a rate history"],
     YR_KNOBS,
     V("record", fields={"known": YES(GE(OR0(SBK("rebate_upto")), 1)),
                         "rebate_upto": SBK("rebate_upto"), "rebate_most": SBK("rebate_most"), "marginal": SBK("marginal"), "cess": SBK("cess"),
                         "surcharge": YK("surcharge"), "cap_a": YK("cap_a"), "cap_112": YK("cap_112"), "r30": YK("r30"), "rebate_special": YK("rebate_special"),
                         "r111a": CGF("r111a"), "r112a": CGF("r112a"), "x112a": CGF("x112a"), "r112": CGF("r112")}),
     "The numbers of an earlier year's tax (FY 2015-16 to 2025-26): the slabs, 87A and cess from chip myreturn.slabs_by_year; the special rates - "
     "111A 15% (20% from 23 July 2024), 112A 10% over 1 lakh (from FY 2018-19; 12.5% over 1.25 lakh from 23 July 2024, the 1.25 lakh for all of "
     "FY 2024-25), 112 20% with indexation (12.5% from 23 July 2024), 115BB / 115BBJ / 115BBH 30%; the surcharge - 12% over 1 crore (FY 2015-16), "
     "15% over 1 crore (2016-17), 10% / 15% over 50 lakh / 1 crore (2017-18, 2018-19), then 25% over 2 crore and 37% over 5 crore (Finance (No. 2) "
     "Act 2019; the new regime's top 25% from FY 2023-24), at most 15% on 111A / 112A gains (from FY 2019-20) and on 112 (from FY 2022-23). "
     "known false: no such year / regime (the new regime before FY 2020-21).",
     [({"fy": 2019}, {"known": True, "r111a": 15, "r112a": 10, "x112a": 100000, "cap_a": 15, "cap_112": 100, "cess": 4}),
      ({"fy": 2024, "regime": "new"}, {"r111a": 20, "r112a": 12.5, "x112a": 125000, "r112": 12.5}),
      ({"fy": 2024, "regime": "new", "early": True}, {"r111a": 15, "r112a": 10, "r112": 20}),
      ({"fy": 2016}, {"known": True, "cess": 3, "r112a": 0}),
      ({"fy": 2019, "regime": "new"}, {"known": False})])

YRC = CHIP("myreturn.year_rates", {"fy": "$fy", "regime": "$regime", "early": "$early"})
YRG = lambda f: GET(YRC, f)  # noqa: E731
RES = EQ("$resident", True)
BASIC = OR0(GET(SB, TPL("years.{y}.{r}.slabs.{b}.0.upto", y="$fy", r="$regime", b="$band")))
SLABS = GET(SB, TPL("years.{y}.{r}.slabs.{b}", y="$fy", r="$regime", b="$band"))
LEFT0 = CHOOSE([(RES, MX(SUB(BASIC, "$normal"), 0))], 0)
T111 = MX(SUB("$stcg_111a", LEFT0), 0)
LEFT1 = MX(SUB(LEFT0, "$stcg_111a"), 0)
G112A = MX(SUB("$ltcg_112a", YRG("x112a")), 0)
T112A = MX(SUB(G112A, LEFT1), 0)
LEFT2 = MX(SUB(LEFT1, G112A), 0)
T112 = MX(SUB("$ltcg_112", LEFT2), 0)
TOTAL = ADD("$normal", "$stcg_111a", "$ltcg_112a", "$ltcg_112", "$special")


def on_normal(n):
    return RND(V("slab_tax", amount=MX(n, 0), slabs=SLABS))


ON_N = on_normal("$normal")
ON_111 = RND(MUL(T111, DIV(YRG("r111a"), 100)))
ON_112A = RND(MUL(T112A, DIV(YRG("r112a"), 100)))
ON_112 = RND(MUL(T112, DIV(YRG("r112"), 100)))
ON_30 = RND(MUL(MX("$special", 0), DIV(YRG("r30"), 100)))
BEFORE = ADD(ON_N, ON_111, ON_112A, ON_112, ON_30)
REB_BASE = CHOOSE([(EQ(YRG("rebate_special"), True), ADD(ON_N, ON_111, ON_112, ON_30))], ON_N)
REBATE = CHOOSE([(NOT(RES), 0), (LE(TOTAL, YRG("rebate_upto")), MN(REB_BASE, YRG("rebate_most"))),
                 (EQ(YRG("marginal"), True), MX(0, SUB(REB_BASE, SUB(TOTAL, YRG("rebate_upto")))))], 0)
AFTER = SUB(BEFORE, REBATE)
SUR = YRG("surcharge")
RATE = OR0(V("step_rate", amount=TOTAL, steps=SUR))
AT = OR0(V("step_rate", amount=TOTAL, steps=SUR, field="above"))
PREV = OR0(V("step_rate", amount=AT, steps=SUR))


def sur_of(rate, tax_all):
    """The surcharge at one rate: the 111A / 112A tax at most cap_a, the 112 tax at most cap_112, the rest at the full rate."""
    capped_a, capped_112 = ADD(ON_111, ON_112A), ON_112
    rest = MX(SUB(tax_all, ADD(capped_a, capped_112)), 0)
    return ADD(MUL(rest, DIV(rate, 100)), MUL(capped_a, DIV(MN(rate, YRG("cap_a")), 100)), MUL(capped_112, DIV(MN(rate, YRG("cap_112")), 100)))


RAW = sur_of(RATE, AFTER)
TAX_AT = ADD(on_normal(SUB("$normal", SUB(TOTAL, AT))), ON_111, ON_112A, ON_112, ON_30)        # the income at the line: the excess off normal income
BOUND = SUB(ADD(TAX_AT, sur_of(PREV, TAX_AT), SUB(TOTAL, AT)), AFTER)
SURCH = CHOOSE([(GT(RATE, 0), RND(MX(0, MN(RAW, BOUND))))], 0)
CESS = RND(MUL(ADD(AFTER, SURCH), DIV(YRG("cess"), 100)))
YT_PARAMS = [P("fy", 2019, "the financial year (its first year)"), P("regime", "old", "old / new"), P("band", "below60", "below60 / 60to80 / 80plus that year"),
             P("resident", True, "resident that year (the unused basic exemption against special-rate gains, 87A)"),
             P("normal", 0, "income at the slab rates"), P("stcg_111a", 0, "short-term gains taxed u/s 111A"), P("ltcg_112a", 0, "long-term gains u/s 112A (before its exemption)"),
             P("ltcg_112", 0, "long-term gains u/s 112 (after indexation when that year's 112 had it)"), P("special", 0, "income at 30%: 115BB / 115BBJ / 115BBH"),
             P("early", False, "FY 2024-25: the gains were on transfers before 23 July 2024")]
chip("myreturn.year_tax", "My return: the tax of an earlier year - slabs, special rates, 87A, surcharge with marginal relief, cess", ["tax of an earlier year", "itr-u tax", "form 10e tax", "surcharge"],
     YT_PARAMS,
     V("record", fields={"known": YRG("known"), "total": TOTAL, "on_normal": ON_N, "on_111a": ON_111, "on_112a": ON_112A, "on_112": ON_112, "on_special": ON_30,
                         "rebate": REBATE, "surcharge_rate": RATE, "surcharge": SURCH, "cess": CESS,
                         "tax": CHOOSE([(EQ(YRG("known"), True), RND(ADD(AFTER, SURCH, CESS)))], 0)}),
     "An earlier year's tax as that year's Finance Act had it (chip myreturn.year_rates): the slabs on normal income; a resident's unused basic "
     "exemption against the 111A, then 112A (after its exemption), then 112 gains; the special rates; 87A (a resident with total income within "
     "the limit; never against 112A tax, s.112A(6); from FY 2025-26 in the new regime only against slab-rate tax) with the new regime's marginal "
     "relief from FY 2023-24; the surcharge on the tax - the 111A / 112A / 112 part at most 15% where that year capped it - with marginal relief "
     "(tax and surcharge at most the tax at the line plus the income over it, the excess taken off normal income); the cess on both.",
     [({"fy": 2019, "normal": 800000}, {"tax": 75400, "surcharge": 0}),
      ({"fy": 2019, "normal": 480000}, {"tax": 0, "rebate": 11500}),
      ({"fy": 2016, "normal": 800000}, {"tax": 87550}),
      ({"fy": 2023, "regime": "new", "normal": 710000}, {"tax": 10400}),
      ({"fy": 2019, "normal": 5500000}, {"surcharge_rate": 10, "surcharge": 146250, "cess": 64350, "tax": 1673100}),
      ({"fy": 2019, "normal": 5100000}, {"surcharge": 70000, "cess": 56500, "tax": 1469000}),
      ({"fy": 2023, "regime": "new", "normal": 1000000, "stcg_111a": 500000}, {"on_111a": 75000, "tax": 140400}),
      ({"fy": 2021, "normal": 100000, "stcg_111a": 300000, "ltcg_112a": 250000}, {"on_111a": 22500, "on_112a": 15000, "rebate": 0}),
      ({"fy": 2023, "regime": "new", "normal": 100000, "stcg_111a": 300000}, {"on_111a": 15000, "rebate": 15000, "tax": 0}),
      ({"fy": 2022, "normal": 4000000, "ltcg_112": 8000000}, {"surcharge_rate": 15}),
      ({"fy": 2024, "regime": "new", "normal": 1500000, "ltcg_112a": 225000}, {"on_112a": 12500}),
      ({"fy": 2024, "regime": "new", "normal": 1500000, "ltcg_112a": 225000, "early": True}, {"on_112a": 10000}),
      ({"fy": 2023, "special": 100000}, {"on_special": 30000}),
      ({"fy": 2019, "regime": "new", "normal": 800000}, {"known": False, "tax": 0})])

# s.89: Form 10E table A - each earlier year at its own slabs, special rates and surcharge
REG = CHOOSE([(EQ("$regime", ""), CHOOSE([(GE("$fy", GET(SB, "new_default_from")), "new")], "old"))], "$regime")
YT = lambda inc: CHIP("myreturn.year_tax", {"fy": "$fy", "regime": REG, "band": "$band", "normal": inc})  # noqa: E731
ar = load("myreturn.arrear_row")
ar_cases = [(t["args"], t["expect_value"]) for t in ar["test_cases"]]
chip("myreturn.arrear_row", ar["label"], ar["aliases"], ar["params"],
     V("record", fields={"regime": REG, "known": GET(YT("$income"), "known"), "before": GET(YT("$income"), "tax"),
                         "after": GET(YT(ADD("$income", "$amount")), "tax"),
                         "extra": SUB(GET(YT(ADD("$income", "$amount")), "tax"), GET(YT("$income"), "tax")), "over": False}),
     "Form 10E table A on chip myreturn.year_tax: that year's surcharge (with marginal relief) is in the tax with and without the arrears - "
     "income over 50 lakh is no longer left to a CA (over stays false).",
     [(a, w) for a, w in ar_cases if not (w.get("over") is True)] + [
         ({"fy": 2019, "income": 4500000, "amount": 1000000}, {"known": True, "before": 1209000, "after": 1673100, "extra": 464100, "over": False})])

# --- 9 the updated return: 234C, the further tax of that year ---------------------------------------------------------------------
iu = load("myreturn.itru")
iu_cases = [(t["args"], t["expect_value"]) for t in iu["test_cases"]]
params = [p for p in iu["params"] if p["name"] != "i234c"] + [P("i234c", 0, "s.234C: the further interest for the instalments short of the updated tax (that year's)")]
expr = json.loads(json.dumps(iu["expr"]))


def add_c(node):
    if isinstance(node, dict):
        if node.get("vop") == "total" and isinstance(node.get("values"), list) and len(node["values"]) == 3 and "$i234c" not in node["values"]:
            node["values"].append("$i234c")
        for v in node.values():
            add_c(v)
    elif isinstance(node, list):
        for v in node:
            add_c(v)


add_c(expr)
expr["fields"]["i234c"] = "$i234c"
chip("myreturn.itru", iu["label"], iu["aliases"] + ["234c"], params, expr,
     "i234c: the updated return's own 234C - that year's instalments (15 / 45 / 75 / 100%) short of the updated tax, less the 234C of the return "
     "before (myreturn.itru_work asks chip compute.interest for both) - joins the further tax and 234A / 234B the additional tax is worked on (s.140B(2)).",
     iu_cases + [({"filed_on": 20261007, "updated_by": 20290331, "months": 19, "months_a": 15, "months_b": 19, "extra_tax": 31200, "tax_after": 31200, "i234c": 1000},
                  {"ok": True, "i234c": 1000, "base": 42808, "pct": 50, "additional": 21404, "total": 64212})])

ir = load("myreturn.itru_rules")
knob(ir, "c_default", "mar", "advance tax of that year with no instalment dates typed: taken as paid by 15 March (the last instalment)")
save(ir, "c_default - 234C of an updated return when the advance tax's instalments are not typed.")

# --- 3 / 4 / 7 / 8 the readers and the settings ------------------------------------------------------------------------------
ck = load("myreturn.checks")
tol = next(p for p in ck["params"] if p["name"] == "tolerance")
if "gst" not in tol["default"]:
    tol["default"]["gst"] = 1000
    save(ck, "gst: the GST turnover (GSTR-3B, per GSTIN) beside the business receipts - 1,000 apart is the same.")
    for a in ({"what": "gst", "a": 1000000, "b": 1000500}, {"what": "gst", "a": 1000000, "b": 1400000}):
        ck["test_cases"].append({"args": a, "expect_value": run_chip("myreturn.checks", a)})
    assert [t["expect_value"]["level"] for t in ck["test_cases"][-2:]] == ["ok", "red"], ck["test_cases"][-2:]
    write(ck)

st = load("myreturn.settings")
for k2, v, lbl in [("tan_kinds", ["form16"], "kinds one per employer: a second one with the same TAN is asked about (replace / keep both)"),
                   ("gst_max", 20, "GSTINs typed, at most"),
                   ("itr3_cfl", {"form": "ITR-3", "block_ay": r"AY\s*(\d{4}-\d{2})",
                                 "other_fields": {"bl": "BusLossOthThanSpecLossCF", "spec": "LossFrmSpecBusCF", "specified": "LossFrmSpecifiedBusCF",
                                                  "horse": "OthSrcLossRaceHorseCF"}},
                    "last year's ITR-3: its Schedule CFL blocks are named by their AY (LossCFCurrentAssmntYear2025 ...) - which AY each is, read from the "
                    "ITR-3 schema's own block descriptions; the business / speculation / specified-business / race-horse losses it carries")]:
    knob(st, k2, v, lbl)
qs = next(p for p in st["params"] if p["name"] == "questions")["default"]
save(st, "tan_kinds (a second Form 16 from the same employer), gst_max, itr3_cfl (losses from last year's ITR-3).")

rd = load("myreturn.read")
for k2, v, lbl in [
    ("cas_pdf", {"words": ["capital gain"], "any": ["cams", "kfin", "karvy", "consolidated account statement", "mutual fund", "redemption"],
                 "scheme": r"^(?P<name>.+?)\s*(?:-\s*)?ISIN\s*:?\s*(?P<isin>IN[A-Z0-9]{10})",
                 "row": r"(?:Redemption|Redeem|Switch[ -]?Out|Sale|SWP|Transfer)\w*\s+(?P<sold>\d{1,2}-[A-Za-z]{3}-\d{4})\s+(?P<units>[\d,]+\.\d+)\s+"
                        r"(?P<sale>[\d,]+\.\d\d)\s+(?P<acquired>\d{1,2}-[A-Za-z]{3}-\d{4})\s+(?P<cost>[\d,]+\.\d\d)(?:\s+(?P<fmv>[\d,]+\.\d\d))?"},
     "a CAMS / KFintech capital-gains statement as a PDF (its text): a scheme's line names it and its ISIN, each redemption line is a sale - "
     "the redemption date, units, amount, the purchase date and cost, then (equity, bought before 1 Feb 2018) the value on 31 January 2018"),
    ("a2_26as", {"title": ["194ia"], "title_also": ["for seller", "seller of property", "sale of immovable property"],
                 "sections": ["194IA"], "pan": r"[A-Z]{5}[0-9]{4}[A-Z]", "date": r"\d{2}-[A-Za-z]{3}-\d{4}", "part": r"^\W*part[\s\-]",
                 "amount": r"-?[\d,]+\.\d\d", "section": r"194[A-Z]*", "serial": r"\d{1,4}",
                 "pdf_deductor": r"^\d+\s+\S+\s+(?P<name>.+?)\s+(?P<pan>[A-Z]{5}[0-9]{4}[A-Z])\s+(?P<on>\d{2}-[A-Za-z]{3}-\d{4})\s+(?P<amount>[\d,]+\.\d\d)\s+(?P<tds>[\d,]+\.\d\d)",
                 "pdf_entry": r"^\d+\s+\S+\s+(?P<section>194[A-Z]*)\s"},
     "26AS Part A2 (Part IV in the 2023 layout) - TDS on the sale of immovable property u/s 194IA, for the seller: each buyer (deductor, by PAN), "
     "the transaction amount and the TDS deposited; the entry lines name the section (194IA kept; 194IB rent, 194M and 194S are not a sale of property)"),
    ("gst3b", {"words": ["gstr-3b", "gstr 3b", "gstr3b", "taxable value", "outward taxable supplies"],
               "cols": [["gstin", ["gstin"]], ["zero", ["zero rated"]], ["exempt", ["nil rated", "exempted", "exempt"]], ["non_gst", ["non-gst", "non gst"]],
                        ["taxable", ["total taxable value", "taxable value", "outward taxable supplies"]]],
               "need": ["gstin", "taxable"], "add": ["taxable", "zero", "exempt", "non_gst"],
               "gstin_pattern": r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]"},
     "a GSTR-3B summary (CSV / Excel, one row a month or a year): per GSTIN the outward supplies of table 3.1 - taxable (a), zero-rated (b), "
     "nil-rated and exempt (c), non-GST (e) - added up as the turnover for ITR-3 / ITR-4's GST schedule"),
]:
    knob(rd, k2, v, lbl)
ff = next(p for p in rd["params"] if p["name"] == "filed_found")["default"]
ff["ITR-3"] = [{"word": "fd_pan", "path": "ITR3.PartA_GEN1.PersonalInfo.PAN"}, {"word": "fd_ay", "path": "ITR3.Form_ITR3.AssessmentYear"},
               {"word": "fd_total", "path": "ITR3.PartB-TI.TotalIncome"}, {"word": "fd_tax", "path": "ITR3.PartB_TTI.ComputationOfTaxLiability.NetTaxLiability"},
               {"word": "fd_refund", "path": "ITR3.PartB_TTI.Refund.RefundDue"}]
save(rd, "cas_pdf (CAMS / KFintech capital-gains PDF), a2_26as (26AS Part A2 / IV - 194IA), gst3b (GSTR-3B summary), filed_found ITR-3 (last year's ITR-3).")

# --- the words ------------------------------------------------------------------------------------------------------------------
u = load("ui.myreturn")
WORDS = {
    # 1 a second Form 16 from the same employer; two employers
    "ask_tan_h": "Already a Form 16 from {employer}",
    "ask_tan_p": "This Form 16 is from the same employer (TAN {tan}) as one already in. A revised Form 16 replaces the first; two Form 16s for two "
                 "spells with the same employer are both kept - their salaries add up.",
    "ask_replace_tan_sub": "It is a revised Form 16 - use it in place of the first (kept in History).",
    "ask_keep_tan_sub": "Two spells with this employer - keep both, both salaries count.",
    "c_two_employers": "Two employers this year",
    "c_two_employers_lv": "Each employer's Form 16 took off the standard deduction ({a} in all) - the return takes it once ({b}). The salaries are added "
                          "up first, so the tax each employer deducted may fall short: expect tax to pay.",
    "c_two_emp_80c": "Deductions on both Form 16s",
    "c_two_emp_80c_lv": "The Form 16s together declare {a} under 80C / 80CCC / 80CCD(1) - the limit is {b} in all. A deduction you declared to both "
                        "employers counts once: type the right figure on Review.",
    # 2 s.44AB cash share of payments; s.44AD(4)
    "biz_pay_total": "Payments in the year (all modes)", "biz_pay_cash": "Of which in cash",
    "biz_pay_p": "The tax-audit limit is 10 crore (75 lakh for a profession) only when cash receipts AND cash payments are each 5% or less (section 44AB). "
                 "Until the payments are typed, the receipts' share stands for both.",
    "biz_ask_pay": "Your receipts are between the two audit limits: the cash share of your payments decides whether the accounts must be audited - type them.",
    "biz_ad_left": "Left 44AD in the last five years?",
    "biz_ad_left_opts": "=No|yes=Yes - declared 44AD income for a year, then not in one of the five years after",
    "biz_ad_left_p": "Section 44AD(4): leaving the presumptive scheme closes it for five years; with income above the basic exemption the accounts must then "
                     "be kept and audited (sections 44AD(5), 44AB(e)).",
    "ca_audit_44ad4": "You left the presumptive scheme (section 44AD) within five years of using it, and your income is above the basic exemption: sections "
                      "44AD(5) and 44AB(e) need books of account and a tax audit by a chartered accountant. My return does not do audits - get a CA "
                      "({product}'s CA-firm side handles them).",
    "ca_44ad_closed": "Section 44AD(4): having left the presumptive scheme within five years of using it, you cannot use 44AD for the five years after. "
                      "Choose 'Business - my own profit and loss' and type the year's figures (ITR-3).",
    "ca_bf_business_loss": "Last year's return carries a business loss of {loss} forward (section 72): it is set off only against business income and carried "
                           "on in ITR-3's Schedule CFL from books of account - My return does not file it. Get a CA ({product}'s CA-firm side handles books and losses).",
    # 3 GST
    "gst_h": "GST turnover, per GSTIN",
    "gst_p": "Each GSTIN and its turnover for the year - taxable, zero-rated, nil-rated / exempt and non-GST outward supplies (GSTR-3B table 3.1). "
             "Drop your GSTR-3B summary on Gather to fill it, or type it.",
    "f_gst_gstin": "GSTIN", "f_gst_turnover": "Turnover (GSTR-3B)", "gst_add": "Add a GSTIN", "gst_none": "No GSTIN typed.",
    "gst_read": "From your GSTR-3B: {n} GSTIN(s), {amount} in all", "gst_remove": "Remove this GSTIN",
    "bad_gstin": "{gstin} is not a GSTIN (15 characters: state code, PAN, entity number, Z, check character).",
    "no_gst_rows": "A GSTR-3B summary, but no row with a GSTIN and a taxable value.",
    "k_gst": "GSTR-3B summary", "k_gst_why": "Your GST turnover per GSTIN - for the GST schedule of ITR-3 / ITR-4, checked against the receipts you declare.",
    "k_gst_how": "gst.gov.in > Services > Returns > Returns Dashboard > FY 2025-26 > GSTR-3B > Download (or your accountant's summary, CSV / Excel)|"
                 "One file a month or the year - each adds up per GSTIN|Drop it here",
    "c_gst": "GST turnover beside your receipts",
    # 4 losses from last year's ITR-3
    "loss_prev_how": "Drop last year's filed return (ITR-2 or ITR-3 JSON) on Gather to fill these from its Schedule CFL.",
    "loss_other": "Last year's return also carries a business loss of {amount} forward - see File: a CA files that return.",
    # 5 / 6 exemptions: time limits, several on one sale
    "ex_late_54": "The house is not within 1 year before or 2 years after the sale (3 years to build) - section 54 is not allowed on it.",
    "ex_late_54F": "The house is not within 1 year before or 2 years after the sale (3 years to build) - section 54F is not allowed on it.",
    "ex_late_54EC": "The bonds were not bought within 6 months after the sale - section 54EC is not allowed on them.",
    "ex_cgas_late": "The Capital Gains Accounts Scheme deposit is after the return's due date (31 July) - it does not count (sections 54(2), 54F(4)).",
    "ex_no_date": "Type the date of the purchase / investment - Schedule CG asks for it, and it must be in time.",
    "f_cg_ex_build": "Bought or built", "cg_build_opts": "=Bought|build=Built (3 years to finish)",
    "cg_ex_add": "Add another exemption", "cg_ex_n": "Exemption {n}", "cg_ex_remove": "Remove this exemption",
    "cg_ex_p": "One sale can carry more than one exemption (a house sold: 54 for the new house, 54EC for bonds). Each counts up to the gain still left, in this order.",
    # 9 ITR-U of an earlier year
    "f_iu_orig_income": "Income at slab rates in that return (nil if none)", "f_iu_added": "Income left out (slab rates)",
    "iu_special_h": "Capital gains and winnings of that year (taxed at their own rates)",
    "f_iu_orig_111a": "In that return: short-term gains (111A)", "f_iu_orig_112a": "In that return: long-term gains (112A)",
    "f_iu_orig_112": "In that return: long-term gains (112)", "f_iu_orig_30": "In that return: winnings / crypto (30%)",
    "f_iu_add_111a": "Left out: short-term gains (111A)", "f_iu_add_112a": "Left out: long-term gains (112A)",
    "f_iu_add_112": "Left out: long-term gains (112)", "f_iu_add_30": "Left out: winnings / crypto (30%)",
    "f_iu_early": "FY 2024-25 gains: sold before 23 July 2024?", "iu_early": "=No - the new rates|yes=Yes - 15% / 10% / 20% (indexed)",
    "iu_adv_h": "That year's advance tax, by instalment (for interest u/s 234C)",
    "f_iu_adv_q1": "Paid by 15 June", "f_iu_adv_q2": "16 June - 15 September", "f_iu_adv_q3": "16 September - 15 December", "f_iu_adv_q4": "16 December - 31 March",
    "iu_lines": "Tax on the income before|Tax on the updated income|Further tax (less TDS on the income added)|Interest u/s 234A|Interest u/s 234B|"
                "Interest u/s 234C|Additional tax u/s 140B ({pct}%)|Late fee u/s 234F|To pay",
    "iu_sur": "That year's surcharge (with marginal relief) is in the updated tax: {amount}.",
    "itru_bar_year_unknown": "That year's tax cannot be worked out here (the new regime before FY 2020-21) - ask a CA.",
    # 10 s.89
    "ar_unknown": "A year cannot be worked out (before FY 2015-16, or the new regime before 2020-21) - no relief is claimed; ask a CA.",
    # 7 / 8 the readers
    "k_cg_how": "Broker: back office > Reports > Tax P&L / Capital gains (Excel or CSV)|Mutual funds: CAMS (camsonline.com) or KFintech (mfs.kfintech.com) > "
                "Capital gains statement for FY 2025-26 (Excel, or the PDF)|Drop each one here",
    "k_26as_why": "Your tax credit as the department holds it: TDS by deductor, the buyer's TDS on a property you sold (Part A2, 194IA) and taxes you paid. "
                  "The return is checked against it.",
}
for k2, v in WORDS.items():
    knob(u, k2, v, k2)
save(u, "wave 4: a second Form 16 from the same employer, two employers, the 44AB payments test and 44AD(4), GST per GSTIN, losses from last year's "
        "ITR-3, exemption time limits and several exemptions on one sale, the ITR-U of an earlier year (special rates, surcharge, 234C).")
print("done")
