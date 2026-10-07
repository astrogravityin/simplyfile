"""2026-10-07 My return, wave 3 (law): residential status (s.6 - resident, RNOR s.6(6), non-resident; the 120-day rule and the deemed
resident of s.6(1A)), foreign income of a resident (Schedule FSI, relief u/s 90 / 90A / 91 - Schedule TR - and Schedule FA),
clubbing (s.64 - a minor child's income with the s.10(32) exemption, a spouse's / son's wife's income from assets transferred
without consideration - Schedule SPI), relief u/s 89 for salary arrears (Form 10E, slabs of every year back to FY 2015-16) and
the updated return (ITR-U, s.139(8A) / s.140B) from My return. Writes / updates the chips - every chip's cases are worked out and
checked against figures said by hand. Re-runnable: new chips are written again, changed chips are changed once (each step looks first).
Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/make_wave3_chips.py
Law: Income-tax Act 1961 as amended by the Finance Act 2025 (AY 2026-27, FY 2025-26)."""
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


def save(c, note=""):
    c["version"] += 1
    if note and note not in c.get("description_nl", ""):
        c["description_nl"] = c.get("description_nl", "") + " " + NOTE + note
    write(c)
    print("wrote", c["chip_id"], "v", c["version"])


def has_param(c, name):
    return any(p["name"] == name for p in c["params"])


def key(n):
    return json.dumps(n, sort_keys=True)


def swap(node, match, make, count):
    if match(node):
        count[0] += 1
        return make(node)
    if isinstance(node, dict):
        return {k: swap(v, match, make, count) for k, v in node.items()}
    if isinstance(node, list):
        return [swap(v, match, make, count) for v in node]
    return node


def run_chip(cid, args):
    from core import engine  # noqa: PLC0415
    import store  # noqa: F401,PLC0415 - registers the portal's chips
    engine.refresh()
    return engine.run(cid, args)


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


def ADD(a, b):
    return V("add", a=a, b=b)


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
    c = {"chip_id": cid, "kind": "accessor", "set": "myreturn", "label": label, "aliases": aliases, "params": params, "expr": expr,
         "returns": returns, "version": 1, "status": "published", "description_nl": NOTE + desc, "test_cases": []}
    old = CH / f"{cid}.json"
    if old.exists():
        o = json.loads(old.read_text(encoding="utf-8"))
        c["version"] = o.get("version", 1) + (0 if (o.get("params"), o.get("expr")) == (params, expr) else 1)
    write(c)
    for args, want in cases:                     # every case: the answer worked out, checked against what was said by hand
        got = run_chip(cid, args)
        if isinstance(want, dict):
            bad = {k2: (got.get(k2), v) for k2, v in want.items() if got.get(k2) != v}
        else:
            bad = {"value": (got, want)} if got != want else {}
        assert not bad, (cid, args, bad)
        c["test_cases"].append({"args": args, "expect_value": got})
    write(c)
    print("wrote", cid, f"({len(cases)} cases)")


# --- 1 residential status (s.6) ---------------------------------------------------------------------------------------------
RES_KNOBS = [
    P("stay_days", 182, "s.6(1)(a): in India 182 days or more in the year - resident"),
    P("short_days", 60, "s.6(1)(c): 60 days or more in the year ..."),
    P("prior_days", 365, "s.6(1)(c): ... and 365 days or more in the 4 years before"),
    P("visitor_days", 120, "s.6(1) Explanation 1(b) (Finance Act 2020): an Indian citizen / person of Indian origin visiting India with total income, other "
      "than from foreign sources, over 15 lakh - 120 days in place of 60"),
    P("rich_income", 1500000, "s.6(1) Explanation 1(b) and s.6(1A): total income other than income from foreign sources, more than this"),
    P("nr_years_rnor", 9, "s.6(6)(a): non-resident in 9 out of the 10 years before - not ordinarily resident"),
    P("days_7y_rnor", 729, "s.6(6)(a): in India 729 days or less in the 7 years before - not ordinarily resident"),
    P("codes", {"ROR": "RES", "RNOR": "NOR", "NR": "NRI"}, "ITR-2 / ITR-3 FilingStatus.ResidentialStatus"),
    P("conditions", {"stay": "1", "short": "2", "nr9": "3", "d729": "4", "nr": "5", "visitor": "6", "deemed": "7"},
      "ITR-2 / ITR-3 FilingStatus.ConditionsResStatus: the condition the status rests on (the schema's codes)"),
    P("foreign_counts", {"ROR": ["salary", "house", "interest", "dividend", "other", "stcg", "ltcg", "business"], "RNOR": [], "NR": []},
      "s.5: a resident (ordinarily) is taxed on income from anywhere; a not-ordinarily resident and a non-resident only on income received / "
      "arising in India - for an RNOR also foreign income from a business controlled in, or a profession set up in, India (s.5(1)(c) proviso)"),
    P("rnor_controlled", ["business"], "s.5(1)(c) proviso: the foreign income an RNOR is taxed on when it comes from a business controlled / profession set up in India"),
    P("fa_for", ["ROR"], "Schedule FA (foreign assets) - for a resident and ordinarily resident (the ITR-2 instructions: not for RNOR / non-resident)"),
    P("fsi_for", ["ROR", "RNOR"], "Schedule FSI / TR - not for a non-resident (ITR-2 validation rules 443, 453)"),
    P("nr_no", ["87A", "80TTB", "80DD", "80DDB", "80U", "senior_slabs", "207(2)"],
      "what a non-resident does not get: the 87A rebate, 80TTB, 80DD / 80DDB / 80U (resident individuals only), the higher basic exemption "
      "of a senior / very senior citizen (old regime - for residents), freedom from advance tax at 60+ (s.207(2))"),
]
chip("myreturn.res_rules", "My return: residential status - the rules (s.6)", ["residential status", "nri", "rnor", "182 days", "section 6"], RES_KNOBS,
     record_of(RES_KNOBS),
     "Residential status for AY 2026-27 (s.6 as amended by the Finance Act 2020): the day counts, the 15 lakh line, the RNOR tests, the schema "
     "codes, which foreign income each status is taxed on (s.5) and what a non-resident does not get.", [({}, {"stay_days": 182, "rich_income": 1500000})])
RR = CHIP("myreturn.res_rules")


def R(path):
    return GET(RR, path)


KNOWN = GE("$days_fy", 0)
VIS = ALL(ANY(EQ("$citizen", True), EQ("$pio", True)), EQ("$visiting", True))
RICH = GT("$indian_income", R("rich_income"))
JOB = ALL(EQ("$citizen", True), EQ("$left_for_job", True))
S182 = GE("$days_fy", R("stay_days"))
S60 = ALL(NOT(JOB), NOT(VIS), GE("$days_fy", R("short_days")), GE("$days_4y", R("prior_days")))
S120 = ALL(VIS, RICH, GE("$days_fy", R("visitor_days")), LT("$days_fy", R("stay_days")), GE("$days_4y", R("prior_days")))
STAY = ANY(S182, S60, S120)
DEEMED = ALL(EQ("$citizen", True), RICH, NOT(EQ("$taxed_elsewhere", True)), NOT(STAY))
RES = ANY(STAY, DEEMED)
NR9 = GE("$nr_years", R("nr_years_rnor"))
D729 = ALL(GE("$days_7y", 0), LE("$days_7y", R("days_7y_rnor")))
RNOR = ANY(DEEMED, S120, ALL(STAY, ANY(NR9, D729)))
FLAG_NR = EQ("$resident_flag", False)
BY_FLAG = ANY(NOT(KNOWN), EQ("$huf", True))
STATUS = CHOOSE([(ALL(BY_FLAG, FLAG_NR), "NR"), (BY_FLAG, "ROR"), (NOT(RES), "NR"), (RNOR, "RNOR")], "ROR")
COND = CHOOSE([(ALL(BY_FLAG, FLAG_NR), R("conditions.nr")), (BY_FLAG, R("conditions.stay")), (NOT(RES), R("conditions.nr")),
               (DEEMED, R("conditions.deemed")), (S120, R("conditions.visitor")), (ALL(STAY, NR9), R("conditions.nr9")),
               (ALL(STAY, D729), R("conditions.d729")), (S182, R("conditions.stay"))], R("conditions.short"))
RES_PARAMS = [P("days_fy", -1, "days in India in FY 2025-26 (-1: not typed - the yes / no answer decides)"),
              P("days_4y", 0, "days in India in the 4 years before (FY 2021-22 to 2024-25)"),
              P("citizen", False, "a citizen of India"), P("pio", False, "a person of Indian origin (not a citizen)"),
              P("visiting", False, "lives abroad and came on a visit to India in the year"),
              P("left_for_job", False, "a citizen who left India in the year for a job abroad, or as a crew member of an Indian ship (Explanation 1(a))"),
              P("indian_income", 0, "total income other than income from foreign sources"),
              P("taxed_elsewhere", False, "liable to tax in another country by reason of domicile or residence (s.6(1A))"),
              P("nr_years", 0, "of the 10 years before, how many as a non-resident"),
              P("days_7y", -1, "days in India in the 7 years before (-1: not typed)"),
              P("resident_flag", True, "the yes / no answer: resident (used when the days are not typed)"),
              P("huf", False, "a Hindu undivided family (s.6(2): by where control and management lie - the yes / no answer)")]
chip("myreturn.residence", "My return: residential status (resident / RNOR / non-resident)", ["residential status", "nri", "rnor", "deemed resident", "120 days"],
     RES_PARAMS,
     V("record", fields={"status": STATUS, "code": GET(R("codes"), STATUS), "condition": COND,
                         "resident": YES(NOT(EQ(STATUS, "NR"))), "ordinary": YES(EQ(STATUS, "ROR")),
                         "deemed": YES(ALL(NOT(BY_FLAG), DEEMED)), "why": TPL("res_why_{c}", c=COND), "known": YES(ALL(KNOWN, NOT(EQ("$huf", True))))}),
     "s.6(1): resident with 182 days in the year, or 60 days in the year and 365 in the 4 before - the 60 days being 182 for a citizen who "
     "left for a job abroad or as a ship's crew (Explanation 1(a)) and for a citizen / person of Indian origin on a visit (Explanation 1(b)), "
     "120 for such a visitor whose income other than from foreign sources is over 15 lakh. s.6(1A): a citizen with such income over 15 lakh "
     "not liable to tax in any other country is deemed resident. s.6(6): not ordinarily resident - non-resident in 9 of the 10 years before, "
     "or in India 729 days or less in the 7 before (a), the 120-day visitor (c), the deemed resident (d). Without the days, the yes / no answer decides.",
     [({}, {"status": "ROR", "code": "RES", "condition": "1", "resident": True, "ordinary": True, "known": False}),
      ({"resident_flag": False}, {"status": "NR", "code": "NRI", "condition": "5", "resident": False}),
      ({"days_fy": 200}, {"status": "ROR", "condition": "1", "why": "res_why_1", "known": True}),
      ({"days_fy": 100, "days_4y": 400}, {"status": "ROR", "condition": "2"}),
      ({"days_fy": 100, "days_4y": 400, "citizen": True, "left_for_job": True}, {"status": "NR", "condition": "5"}),
      ({"days_fy": 100, "days_4y": 400, "citizen": True, "visiting": True, "indian_income": 1000000}, {"status": "NR"}),
      ({"days_fy": 130, "days_4y": 400, "citizen": True, "visiting": True, "indian_income": 2000000}, {"status": "RNOR", "code": "NOR", "condition": "6"}),
      ({"days_fy": 130, "days_4y": 300, "citizen": True, "visiting": True, "indian_income": 2000000}, {"status": "RNOR", "condition": "7", "deemed": True}),
      ({"days_fy": 130, "days_4y": 300, "citizen": True, "visiting": True, "indian_income": 2000000, "taxed_elsewhere": True}, {"status": "NR", "deemed": False}),
      ({"days_fy": 130, "days_4y": 400, "pio": True, "visiting": True, "indian_income": 2000000}, {"status": "RNOR", "condition": "6"}),
      ({"days_fy": 200, "nr_years": 9}, {"status": "RNOR", "condition": "3"}),
      ({"days_fy": 200, "days_7y": 700}, {"status": "RNOR", "condition": "4"}),
      ({"days_fy": 200, "days_7y": 800, "nr_years": 2}, {"status": "ROR", "condition": "1"}),
      ({"days_fy": 30, "citizen": True, "indian_income": 2000000}, {"status": "RNOR", "condition": "7"}),
      ({"days_fy": 30}, {"status": "NR", "condition": "5"}),
      ({"days_fy": 30, "huf": True}, {"status": "ROR", "known": False}),
      ({"huf": True, "resident_flag": False}, {"status": "NR"})])

# --- 2 foreign income: which rows count, and the relief u/s 90 / 90A / 91 --------------------------------------------------------
FHEADS = {"salary": {"to": "salary", "fsi": "IncFromSal"}, "house": {"to": "house", "fsi": "IncFromHP"},
          "interest": {"to": "interest", "fsi": "IncOthSrc"}, "dividend": {"to": "dividend", "fsi": "IncOthSrc"},
          "other": {"to": "other", "fsi": "IncOthSrc"}, "stcg": {"to": "stcg_other", "fsi": "IncCapGain"},
          "ltcg": {"to": "ltcg_112", "fsi": "IncCapGain"}, "business": {"to": "business", "fsi": ""}}
FR_KNOBS = [
    P("heads", FHEADS, "foreign income by head: where it joins the return (salary - Schedule S; house - Schedule HP, the 30% and interest; interest / "
      "dividend / other - Schedule OS; a short-term gain at the slab rates, a long-term gain at 12.5% u/s 112 - Schedule CG; business - a CA) "
      "and its Schedule FSI block"),
    P("relief_secs", ["90", "90A", "91"], "s.90 (a DTAA with the country), s.90A (an agreement between specified associations), s.91 (no agreement)"),
    P("dtaa_secs", ["90", "90A"], "Schedule TR: relief where a DTAA applies (the rest is s.91)"),
    P("rate_rule", "rule 115", "the foreign income is typed in rupees - rule 115: at the SBI telegraphic-transfer buying rate on the last day of the "
      "month before the month the income is received / accrues (salary, interest, dividend)"),
    P("form67", "Form 67", "rule 128(9): Form 67 (with proof of the foreign tax) is filed on the e-filing portal on or before the end of the AY - "
      "31 March 2027 - for the relief to be allowed"),
]
chip("myreturn.foreign_rules", "My return: foreign income - the rules", ["foreign income", "dtaa", "schedule fsi", "schedule tr", "form 67", "rule 115"],
     FR_KNOBS, record_of(FR_KNOBS),
     "Foreign income for AY 2026-27: where each head joins the return, the relief sections (90 / 90A / 91), the rupee rate (rule 115) and Form 67 (rule 128).",
     [({}, {"relief_secs": ["90", "90A", "91"]})])
FRR = CHIP("myreturn.foreign_rules")
F_COUNTS = ANY(IN("$head", GET(R("foreign_counts"), "$status")),
               ALL(EQ("$status", "RNOR"), EQ("$controlled", True), IN("$head", R("rnor_controlled"))))
chip("myreturn.foreign_row", "My return: one row of foreign income - does it count?", ["foreign income", "rnor", "s.5"],
     [P("status", "ROR", "ROR / RNOR / NR (chip myreturn.residence)"), P("head", "other", "salary / house / interest / dividend / other / stcg / ltcg / business"),
      P("amount", 0, "the income in rupees (rule 115)"), P("controlled", False, "RNOR: from a business controlled in / a profession set up in India")],
     V("record", fields={"counts": YES(F_COUNTS), "to": GET(GET(FRR, "heads"), TPL("{h}.to", h="$head")),
                         "fsi": GET(GET(FRR, "heads"), TPL("{h}.fsi", h="$head")), "amount": CHOOSE([(F_COUNTS, "$amount")], 0),
                         "ca": YES(ALL(F_COUNTS, EQ("$head", "business")))}),
     "s.5: a resident and ordinarily resident is taxed on foreign income of every head; a not-ordinarily resident only on foreign income from "
     "a business controlled in / a profession set up in India; a non-resident on none of it. A foreign business or profession's income is a CA's job (books, ITR-3 Schedule BP).",
     [({"head": "salary", "amount": 100}, {"counts": True, "to": "salary", "fsi": "IncFromSal", "amount": 100, "ca": False}),
      ({"status": "RNOR", "head": "salary", "amount": 100}, {"counts": False, "amount": 0}),
      ({"status": "RNOR", "head": "business", "amount": 100, "controlled": True}, {"counts": True, "ca": True}),
      ({"status": "RNOR", "head": "interest", "amount": 100, "controlled": True}, {"counts": False}),
      ({"status": "NR", "head": "dividend", "amount": 100}, {"counts": False, "to": "dividend"}),
      ({"head": "ltcg", "amount": 100}, {"to": "ltcg_112", "fsi": "IncCapGain"})])
chip("myreturn.dtaa_relief", "My return: relief for tax paid abroad (s.90 / 90A / 91)", ["dtaa relief", "foreign tax credit", "rule 128", "section 91"],
     [P("income", 0, "the foreign income of one head from one country, included in total income"), P("tax_paid", 0, "the tax paid on it abroad, in rupees"),
      P("tax_total", 0, "the Indian tax on total income (after the 87A rebate, with surcharge and cess)"), P("income_total", 0, "total income"),
      P("sec", "90", "90 / 90A / 91")],
     V("record", fields={"indian_tax": CHOOSE([(GT("$income_total", 0), RND(DIV(MUL(MX("$income", 0), "$tax_total"), "$income_total")))], 0),
                         "relief": MX(0, MN("$tax_paid", CHOOSE([(GT("$income_total", 0), RND(DIV(MUL(MX("$income", 0), "$tax_total"), "$income_total")))], 0))),
                         "dtaa": YES(IN("$sec", GET(FRR, "dtaa_secs")))}),
     "Rule 128: the credit for foreign tax is the lower of the tax paid abroad and the Indian tax on that income - the income at the average rate "
     "of Indian tax (tax on total income / total income), source by source (Schedule FSI (e) = lower of (c) and (d)).",
     [({"income": 1000000, "tax_paid": 200000, "tax_total": 300000, "income_total": 2000000}, {"indian_tax": 150000, "relief": 150000, "dtaa": True}),
      ({"income": 1000000, "tax_paid": 100000, "tax_total": 300000, "income_total": 2000000, "sec": "91"}, {"relief": 100000, "dtaa": False}),
      ({"income": 1000000, "tax_paid": 100000, "tax_total": 0, "income_total": 900000}, {"relief": 0}),
      ({"income": -50000, "tax_paid": 1000, "tax_total": 300000, "income_total": 2000000}, {"relief": 0})])
FA_CHECK = ALL(EQ("$status", "ROR"), ANY(EQ("$foreign_income", True), EQ("$flag", True)), LE("$fa_rows", 0))
chip("myreturn.check_fa", "My return: foreign assets not listed (Schedule FA)", ["schedule fa", "foreign assets", "black money act"],
     [P("status", "ROR", "residential status"), P("foreign_income", False, "foreign income included in the return"),
      P("flag", False, "the person said they hold foreign assets"), P("fa_rows", 0, "foreign assets typed")],
     V("record", fields={"what": "fa_missing", "a": "$fa_rows", "b": 0, "gap": 0, "word": "lv_fa_missing", "level": CHOOSE([(FA_CHECK, "red")], "ok")}),
     "A resident and ordinarily resident with foreign income or foreign assets lists every foreign account, holding, property and interest held at "
     "any time in the calendar year 2025 in Schedule FA (s.139(1) fourth proviso; the Black Money Act's penalty of 10 lakh for leaving it out).",
     [({"foreign_income": True}, {"level": "red"}), ({"foreign_income": True, "fa_rows": 1}, {"level": "ok"}), ({"status": "RNOR", "flag": True}, {"level": "ok"})])

# --- 3 clubbing (s.64) ---------------------------------------------------------------------------------------------------------------
CL_REL = {"minor_child": {"sec": "64(1A)", "owner": "MI"}, "spouse": {"sec": "64(1)(iv)", "owner": "SP"}, "son_wife": {"sec": "64(1)(vi)", "owner": "OT"}}
CL_HEADS = {"interest": {"to": "interest", "spi": "OS"}, "dividend": {"to": "dividend", "spi": "OS"}, "other": {"to": "other", "spi": "OS"},
            "house": {"to": "house", "spi": "HP"}, "stcg_111a": {"to": "stcg_111a", "spi": "CG"}, "stcg": {"to": "stcg_other", "spi": "CG"},
            "ltcg_112": {"to": "ltcg_112", "spi": "CG"}, "ltcg_112a": {"to": "ltcg_112a", "spi": "CG"}}
CL_KNOBS = [
    P("relations", CL_REL, "whose income is clubbed: a minor child (s.64(1A) - all of it, with the parent whose income is the greater); the spouse "
      "(s.64(1)(iv)) and the son's wife (s.64(1)(vi)) - the income from assets transferred to them without adequate consideration. "
      "owner: Schedule HP's PropertyOwner code (MI minor, SP spouse, OT other)"),
    P("heads", CL_HEADS, "the head the clubbed income is taxed under, and its Schedule SPI code"),
    P("minor_exempt", 1500, "s.10(32): a minor child's income clubbed is exempt up to 1,500 a child"),
    P("ei_category", ["SRSC", "10(32)"], "ITR-2 Schedule EI: the 10(32) exemption's category and sub-category"),
]
chip("myreturn.club_rules", "My return: clubbing - the rules (s.64)", ["clubbing", "section 64", "minor child income", "10(32)", "schedule spi"], CL_KNOBS,
     record_of(CL_KNOBS), "Clubbing of income (s.64): whose, which head, the s.10(32) exemption of 1,500 a minor child, Schedule SPI / EI codes.",
     [({}, {"minor_exempt": 1500})])
CLR = CHIP("myreturn.club_rules")
CL_COUNTS = ALL(GT("$amount", 0), NOT(ALL(EQ("$relation", "minor_child"), ANY(EQ("$skill", True), EQ("$disabled", True)))))
chip("myreturn.club_row", "My return: one row of clubbed income", ["clubbing", "section 64"],
     [P("relation", "minor_child", "minor_child / spouse / son_wife"), P("head", "interest", "chip myreturn.club_rules heads"), P("amount", 0, "the income"),
      P("skill", False, "a minor's income from manual work, a skill, talent or specialised knowledge - not clubbed (s.64(1A) proviso)"),
      P("disabled", False, "a minor with a disability of the kind in s.80U - not clubbed (s.64(1A) proviso)")],
     V("record", fields={"counts": YES(CL_COUNTS), "amount": CHOOSE([(CL_COUNTS, "$amount")], 0),
                         "to": GET(GET(CLR, "heads"), TPL("{h}.to", h="$head")), "spi": GET(GET(CLR, "heads"), TPL("{h}.spi", h="$head")),
                         "sec": GET(GET(CLR, "relations"), TPL("{r}.sec", r="$relation")), "owner": GET(GET(CLR, "relations"), TPL("{r}.owner", r="$relation"))}),
     "s.64: a minor child's income joins the parent's (not what the child earns by manual work, skill or talent, nor a child with an 80U "
     "disability); the spouse's / son's wife's income from assets transferred without adequate consideration joins the transferor's - under the head it is.",
     [({"amount": 50000}, {"counts": True, "amount": 50000, "to": "interest", "spi": "OS", "sec": "64(1A)", "owner": "MI"}),
      ({"amount": 50000, "skill": True}, {"counts": False, "amount": 0}),
      ({"amount": 50000, "disabled": True}, {"counts": False}),
      ({"relation": "spouse", "head": "house", "amount": 240000, "skill": True}, {"counts": True, "to": "house", "spi": "HP", "owner": "SP"}),
      ({"relation": "son_wife", "head": "ltcg_112a", "amount": 10}, {"to": "ltcg_112a", "spi": "CG", "sec": "64(1)(vi)"})])
chip("myreturn.minor_exempt", "My return: a minor child's income - the 1,500 exemption (s.10(32))", ["10(32)", "minor child"],
     [P("income", 0, "the child's income clubbed in the year")],
     V("record", fields={"exempt": MN(MX("$income", 0), GET(CLR, "minor_exempt")), "included": SUB(MX("$income", 0), MN(MX("$income", 0), GET(CLR, "minor_exempt")))}),
     "s.10(32): where a minor child's income is clubbed u/s 64(1A), the parent is exempt on it up to 1,500 for each child.",
     [({"income": 50000}, {"exempt": 1500, "included": 48500}), ({"income": 1000}, {"exempt": 1000, "included": 0}), ({"income": 0}, {"exempt": 0})])

# --- 4 relief u/s 89 (salary arrears, Form 10E): the slabs of every year back to FY 2015-16 --------------------------------------
from core import engine as _e  # noqa: E402
import store as _s  # noqa: E402,F401
_e.refresh()
rates = _e.run("myreturn.rates")


def old_slabs(r5):
    return {"below60": [{"upto": 250000, "rate": 0}, {"upto": 500000, "rate": r5}, {"upto": 1000000, "rate": 20}, {"upto": None, "rate": 30}],
            "60to80": [{"upto": 300000, "rate": 0}, {"upto": 500000, "rate": r5}, {"upto": 1000000, "rate": 20}, {"upto": None, "rate": 30}],
            "80plus": [{"upto": 500000, "rate": 0}, {"upto": 1000000, "rate": 20}, {"upto": None, "rate": 30}]}


def all_bands(s):
    return {b: copy.deepcopy(s) for b in ("below60", "60to80", "80plus")}


NEW_20 = [{"upto": 250000, "rate": 0}, {"upto": 500000, "rate": 5}, {"upto": 750000, "rate": 10}, {"upto": 1000000, "rate": 15},
          {"upto": 1250000, "rate": 20}, {"upto": 1500000, "rate": 25}, {"upto": None, "rate": 30}]
NEW_23 = [{"upto": 300000, "rate": 0}, {"upto": 600000, "rate": 5}, {"upto": 900000, "rate": 10}, {"upto": 1200000, "rate": 15},
          {"upto": 1500000, "rate": 20}, {"upto": None, "rate": 30}]
NEW_24 = [{"upto": 300000, "rate": 0}, {"upto": 700000, "rate": 5}, {"upto": 1000000, "rate": 10}, {"upto": 1200000, "rate": 15},
          {"upto": 1500000, "rate": 20}, {"upto": None, "rate": 30}]
YEARS = {}
for y in range(2015, 2025):
    o = {"slabs": old_slabs(10 if y < 2017 else 5), "cess": 3 if y < 2018 else 4, "marginal": False,
         "rebate_upto": 500000 if y < 2017 or y >= 2019 else 350000, "rebate_most": {2015: 2000, 2016: 5000, 2017: 2500, 2018: 2500}.get(y, 12500)}
    YEARS[str(y)] = {"old": o}
    if y >= 2020:
        YEARS[str(y)]["new"] = {"slabs": all_bands(NEW_20 if y < 2023 else NEW_23 if y == 2023 else NEW_24), "cess": 4, "marginal": y >= 2023,
                                "rebate_upto": 500000 if y < 2023 else 700000, "rebate_most": 12500 if y < 2023 else 25000}
YEARS["2025"] = {g: {"slabs": rates["slabs"][g], "cess": rates["cess_pct"], "marginal": g == "new", "rebate_upto": rates["rebate_upto"][g],
                     "rebate_most": rates["rebate_most"][g]} for g in ("new", "old")}
SY_KNOBS = [P("years", YEARS, "individual's slab rates, 87A rebate (up to / at most; marginal relief in the new regime from FY 2023-24) and cess by "
              "financial year (the year it starts) and regime - old regime from FY 2015-16, the new regime (s.115BAC) from FY 2020-21. Finance Acts "
              "2015 to 2025: 87A 2,000 (2015-16), 5,000 (2016-17), 2,500 up to 3.5 lakh (2017-18, 2018-19), 12,500 up to 5 lakh (2019-20 on); "
              "new regime 25,000 up to 7 lakh (2023-24, 2024-25), 60,000 up to 12 lakh (2025-26); cess 3% to 2017-18, 4% from 2018-19. "
              "FY 2025-26 is chip myreturn.rates'."),
            P("new_default_from", 2023, "the new regime is the default from FY 2023-24 (Finance Act 2023); before it a year's regime is the old unless said"),
            P("surcharge_above", 5000000, "surcharge is not worked out for an earlier year: a year's income over 50 lakh - a CA")]
chip("myreturn.slabs_by_year", "My return: tax slabs of each year since FY 2015-16", ["slabs by year", "form 10e", "section 89", "earlier year tax"], SY_KNOBS,
     record_of(SY_KNOBS), "The individual's slabs, 87A rebate and cess for FY 2015-16 to FY 2025-26, both regimes - for relief u/s 89 (Form 10E) and the "
     "updated return of an earlier year.", [({}, {"new_default_from": 2023})])
SY = CHIP("myreturn.slabs_by_year")
YP = lambda f: GET(SY, TPL("years.{y}.{r}." + f, y="$fy", r="$regime"))  # noqa: E731
SLAB = RND(V("slab_tax", amount=MX("$income", 0), slabs=GET(SY, TPL("years.{y}.{r}.slabs.{b}", y="$fy", r="$regime", b="$band"))))
UPTO = YP("rebate_upto")
REB = CHOOSE([(EQ("$resident", False), 0), (LE("$income", UPTO), MN(SLAB, YP("rebate_most"))),
              (ALL(EQ(YP("marginal"), True), GT("$income", UPTO)), MX(0, SUB(SLAB, SUB("$income", UPTO))))], 0)
KNOWN_Y = GE(UPTO, 0)
CESS = RND(MUL(SUB(SLAB, REB), DIV(YP("cess"), 100)))
chip("myreturn.tax_of_year", "My return: an individual's tax for an earlier year", ["earlier year tax", "form 10e", "section 89"],
     [P("fy", 2025, "the financial year (the year it starts: 2019 = FY 2019-20)"), P("regime", "old", "old / new (new from FY 2020-21)"),
      P("band", "below60", "age band that year"), P("income", 0, "total income (at the slab rates)"), P("resident", True, "resident that year (87A)")],
     V("record", fields={"known": YES(KNOWN_Y), "slab": CHOOSE([(KNOWN_Y, SLAB)], 0), "rebate": CHOOSE([(KNOWN_Y, REB)], 0),
                         "cess": CHOOSE([(KNOWN_Y, CESS)], 0), "tax": CHOOSE([(KNOWN_Y, ADD(SUB(SLAB, REB), CESS))], 0),
                         "over": YES(GT("$income", GET(SY, "surcharge_above")))}),
     "The tax on an individual's total income of an earlier year at that year's slabs, less that year's 87A rebate (with the new regime's marginal "
     "relief from FY 2023-24), with that year's cess (chip myreturn.slabs_by_year). No surcharge: over 50 lakh is flagged. known false - no such year / regime.",
     [({"fy": 2019, "income": 800000}, {"slab": 72500, "rebate": 0, "cess": 2900, "tax": 75400, "known": True}),
      ({"fy": 2019, "income": 480000}, {"slab": 11500, "rebate": 11500, "tax": 0}),
      ({"fy": 2016, "income": 800000}, {"slab": 85000, "cess": 2550, "tax": 87550}),
      ({"fy": 2017, "income": 340000, "band": "below60"}, {"slab": 4500, "rebate": 2500, "cess": 60, "tax": 2060}),
      ({"fy": 2021, "regime": "new", "income": 1200000}, {"slab": 115000, "cess": 4600, "tax": 119600}),
      ({"fy": 2023, "regime": "new", "income": 710000}, {"slab": 26000, "rebate": 16000, "tax": 10400}),
      ({"fy": 2024, "regime": "new", "income": 1000000}, {"slab": 50000, "tax": 52000}),
      ({"fy": 2025, "regime": "new", "income": 1300000}, {"slab": 75000, "rebate": 0, "tax": 78000}),
      ({"fy": 2025, "regime": "new", "income": 1200000}, {"slab": 60000, "rebate": 60000, "tax": 0}),
      ({"fy": 2019, "regime": "new", "income": 800000}, {"known": False, "tax": 0}),
      ({"fy": 2019, "income": 480000, "resident": False}, {"rebate": 0, "tax": 11960}),
      ({"fy": 2019, "income": 6000000, "band": "60to80"}, {"over": True})])
AR_REG = CHOOSE([(EQ("$regime", ""), CHOOSE([(GE("$fy", GET(SY, "new_default_from")), "new")], "old"))], "$regime")
BEFORE = CHIP("myreturn.tax_of_year", {"fy": "$fy", "regime": AR_REG, "band": "$band", "income": "$income"})
AFTER = CHIP("myreturn.tax_of_year", {"fy": "$fy", "regime": AR_REG, "band": "$band", "income": ADD("$income", "$amount")})
chip("myreturn.arrear_row", "My return: salary arrears of one earlier year (Form 10E table A)", ["form 10e", "section 89", "arrears"],
     [P("fy", 2019, "the year the arrears belong to (the year it starts)"), P("regime", "", "that year's regime (blank: old before FY 2023-24, new from it)"),
      P("band", "below60", "age band that year"), P("income", 0, "that year's total income as assessed (without the arrears)"), P("amount", 0, "the arrears of that year received now")],
     V("record", fields={"regime": AR_REG, "known": GET(BEFORE, "known"), "before": GET(BEFORE, "tax"), "after": GET(AFTER, "tax"),
                         "extra": SUB(GET(AFTER, "tax"), GET(BEFORE, "tax")), "over": GET(AFTER, "over")}),
     "Form 10E, Annexure I table A: for each earlier year, the tax on that year's income with the arrears less the tax without them.",
     [({"fy": 2019, "income": 600000, "amount": 200000}, {"regime": "old", "before": 33800, "after": 75400, "extra": 41600, "known": True}),
      ({"fy": 2023, "income": 600000, "amount": 200000}, {"regime": "new", "before": 0, "after": 36400, "extra": 36400}),
      ({"fy": 2021, "regime": "new", "income": 600000, "amount": 100000}, {"before": 23400, "after": 33800})])
chip("myreturn.relief_89", "My return: relief u/s 89 - salary received in arrears (Form 10E)", ["section 89", "form 10e", "arrears relief"],
     [P("now_with", 0, "this year's tax with the arrears"), P("now_without", 0, "this year's tax without them"),
      P("past", 0, "the earlier years' extra tax had the arrears been taxed then (Form 10E table A, summed)"),
      P("unknown", False, "a year whose tax cannot be worked out (no such year / regime, or over 50 lakh)"),
      P("huf", False, "an HUF (no s.89 - it has no salary)"), P("salary", 0, "this year's salary")],
     V("record", fields={"now_extra": MX(0, SUB("$now_with", "$now_without")),
                         "relief": CHOOSE([(ANY(EQ("$unknown", True), EQ("$huf", True), LE("$salary", 0)), 0)], MX(0, SUB(MX(0, SUB("$now_with", "$now_without")), "$past"))),
                         "form10e": YES(ALL(NOT(EQ("$unknown", True)), GT(SUB(MX(0, SUB("$now_with", "$now_without")), "$past"), 0)))}),
     "s.89 / rule 21A: the extra tax this year because the arrears are taxed now, less the extra tax there would have been in the years they belong "
     "to - nil when that is more. Form 10E is filed before the return (the relief is refused without it). Available in the new regime too: "
     "s.115BAC(2) takes away exemptions and deductions, not relief u/s 89 (CBDT: the relief is a relief from tax). Not for an HUF; needs salary.",
     [({"now_with": 135200, "now_without": 72800, "past": 41600, "salary": 1}, {"now_extra": 62400, "relief": 20800, "form10e": True}),
      ({"now_with": 135200, "now_without": 72800, "past": 70000, "salary": 1}, {"relief": 0, "form10e": False}),
      ({"now_with": 135200, "now_without": 72800, "past": 41600, "salary": 0}, {"relief": 0}),
      ({"now_with": 135200, "now_without": 72800, "past": 0, "unknown": True, "salary": 1}, {"relief": 0}),
      ({"now_with": 135200, "now_without": 72800, "past": 0, "huf": True, "salary": 1}, {"relief": 0})])

# --- 5 the updated return (ITR-U, s.139(8A) / s.140B) --------------------------------------------------------------------------------
BARS = ["search", "survey", "requisition", "assessment", "prosecution", "other_law", "already_updated", "loss_return", "lower_tax"]
IU_KNOBS = [
    P("bars", BARS, "s.139(8A) provisos - no updated return: a search (s.132) or requisition (s.132A) started, a survey (s.133A), an assessment / "
      "reassessment / revision pending or made for the year, prosecution started, information under another law (PMLA, Black Money, Benami, "
      "SAFEMA) held, already updated once for that year, a return of loss, or one that lowers the tax / raises the refund / raises a loss. "
      "(Finance Act 2025: after a s.148A notice only where the officer ordered it is not a fit case for reassessment.)"),
    P("rate_pm", 1, "s.234A(1A) / s.234B(1A): 1% a month or part of a month on the further tax"),
    P("floor_step", 100, "rule 119A: the tax interest is worked on is rounded down to a multiple of 100"),
    P("b_min", 10000, "s.208 / s.234B: advance tax due when the year's tax, less TDS, is 10,000 or more"),
    P("b_pct", 90, "s.234B: interest when the advance tax paid is less than 90% of the assessed tax"),
    P("reasons", {"1": "Return previously not filed", "2": "Income not reported correctly", "3": "Wrong heads of income chosen",
                  "4": "Reduction of carried forward loss", "5": "Reduction of unabsorbed depreciation", "6": "Reduction of tax credit u/s 115JB / 115JD",
                  "7": "Wrong rate of tax", "8": "Others"}, "ITR-U Part A: the reasons for updating the income (the department's codes)"),
    P("schema_have", False, "the department's ITR-U schema for an earlier AY is not in schemas/itr - the JSON is not made (the computation and the steps are given)"),
]
chip("myreturn.itru_rules", "My return: updated return (ITR-U) - the rules", ["itr-u", "updated return", "139(8a)", "140b"], IU_KNOBS, record_of(IU_KNOBS),
     "The updated return (s.139(8A), Finance Act 2022; 48 months from the end of the AY and 60% / 70% for the third / fourth year by the Finance Act 2025 - "
     "the additional tax is chip close.itr_u's): who may not file one, the interest, the reason codes.", [({}, {"rate_pm": 1})])
IR = CHIP("myreturn.itru_rules")
FL = lambda v: V("floor_to", value=MX(v, 0), step=GET(IR, "floor_step"))  # noqa: E731
ASSESSED = SUB("$tax_after", "$tds")
BAPPLY = ALL(GE(ASSESSED, GET(IR, "b_min")), LT("$advance", MUL(ASSESSED, DIV(GET(IR, "b_pct"), 100))))
I234A = CHOOSE([(GT("$extra_tax", 0), RND(MUL(MUL(FL("$extra_tax"), DIV(GET(IR, "rate_pm"), 100)), MX("$months_a", 0))))], 0)
I234B = CHOOSE([(ALL(BAPPLY, GT("$extra_tax", 0)), RND(MUL(MUL(FL("$extra_tax"), DIV(GET(IR, "rate_pm"), 100)), MX("$months_b", 0))))], 0)
BASE = V("total", values=[MX("$extra_tax", 0), I234A, I234B])
U = CHIP("close.itr_u", {"net_now": BASE, "net_before": 0, "months": "$months"})
WHY = CHOOSE([(GT("$filed_on", "$updated_by"), "itru_late"), (GT(V("count", items="$bars"), 0), TPL("itru_bar_{b}", b=V("coalesce", values="$bars"))),
              (NOT(EQ("$known", True)), "itru_bar_year_unknown"), (LE("$extra_tax", 0), "itru_not_more")], "")
chip("myreturn.itru", "My return: an updated return (ITR-U) - allowed?, interest, additional tax", ["itr-u", "updated return", "140b", "additional tax"],
     [P("filed_on", 0, "the day it is filed (yyyymmdd)"), P("updated_by", 0, "the last day for it (chip close.dates updated_by: 48 months from the end of the AY)"),
      P("months", 0, "months from the end of the AY to the day of filing (a part month counts)"),
      P("months_a", 0, "234A(1A): months from the day after the due date"), P("months_b", 0, "234B(1A): months from 1 April of the AY"),
      P("extra_tax", 0, "the further tax: tax on the updated income less the tax on the income of the return before, less TDS on the income added"),
      P("tax_after", 0, "tax on the updated income"), P("tds", 0, "that year's TDS / TCS in all"), P("advance", 0, "advance tax paid that year"),
      P("bars", [], "the bars that apply (chip myreturn.itru_rules bars)"),
      P("known", True, "that year's tax can be worked out here (chip myreturn.tax_of_year known, and not over its surcharge line)")],
     V("record", fields={"why": WHY, "ok": YES(EQ(WHY, "")), "i234a": I234A, "i234b": I234B, "base": BASE, "pct": GET(U, "pct"),
                         "additional": CHOOSE([(EQ(WHY, ""), GET(U, "additional"))], 0),
                         "total": CHOOSE([(EQ(WHY, ""), ADD(BASE, GET(U, "additional")))], 0)}),
     "s.139(8A): within 48 months of the end of the AY, unless a bar applies; s.140B: the further tax with interest u/s 234A(1A) (from the day "
     "after the due date) and 234B(1A) (from 1 April of the AY, when advance tax fell short) on it, then the additional tax - 25% / 50% / 60% / 70% "
     "of that tax and interest within 12 / 24 / 36 / 48 months (chip close.itr_u). The return's own tax was paid with it; the further tax is the base.",
     [({"filed_on": 20261007, "updated_by": 20290331, "months": 19, "months_a": 15, "months_b": 19, "extra_tax": 31200, "tax_after": 31200},
       {"ok": True, "i234a": 4680, "i234b": 5928, "base": 41808, "pct": 50, "additional": 20904, "total": 62712}),
      ({"filed_on": 20261007, "updated_by": 20290331, "months": 7, "months_a": 2, "months_b": 7, "extra_tax": 5000, "tax_after": 5000},
       {"ok": True, "i234a": 100, "i234b": 0, "pct": 25, "additional": 1275}),
      ({"filed_on": 20261007, "updated_by": 20260331, "months": 55, "extra_tax": 5000}, {"ok": False, "why": "itru_late", "additional": 0}),
      ({"filed_on": 20261007, "updated_by": 20290331, "months": 19, "extra_tax": 5000, "bars": ["search"]}, {"ok": False, "why": "itru_bar_search"}),
      ({"filed_on": 20261007, "updated_by": 20290331, "months": 19, "extra_tax": 0}, {"ok": False, "why": "itru_not_more"}),
      ({"filed_on": 20261007, "updated_by": 20290331, "months": 19, "extra_tax": 5000, "known": False}, {"ok": False, "why": "itru_bar_year_unknown"}),
      ({"filed_on": 20261007, "updated_by": 20290331, "months": 40, "months_a": 38, "months_b": 40, "extra_tax": 100000, "tax_after": 300000, "tds": 0, "advance": 280000},
       {"i234b": 0, "i234a": 38000, "pct": 70, "additional": 96600})])

# --- 6 the chips that change: age band, deductions (resident), the form (clubbing) ------------------------------------------------------
ab = load("myreturn.age_band")
if not has_param(ab, "resident"):
    ab["params"].append(P("resident", True, "resident in India (a non-resident has no senior / very senior basic exemption, 80TTB or senior 80D)"))
    ab["expr"] = CHOOSE([(EQ("$resident", False), "below60")], ab["expr"])
    write(ab)
    for tc in ab["test_cases"]:
        assert run_chip("myreturn.age_band", tc["args"]) == tc["expect_value"], tc
    for args, want in [({"age": 65, "resident": False}, "below60"), ({"age": 65}, "60to80"), ({"age": 85, "resident": False}, "below60")]:
        got = run_chip("myreturn.age_band", args)
        assert got == want, (args, got)
        ab["test_cases"].append({"args": args, "expect_value": got})
    save(ab, "resident: a non-resident is in the below-60 band whatever the age - the old regime's 3 / 5 lakh basic exemption, 80TTB and the senior "
             "citizen's 80D limit are for an individual resident in India (Finance Act Part I; s.80TTB, s.80D(4)).")

dd = load("myreturn.deductions")
if not has_param(dd, "resident"):
    dd["params"].append(P("resident", True, "resident in India (80DD, 80DDB and 80U are for a resident individual / HUF)"))
    F = dd["expr"]["fields"]
    for f in ("d80DD", "d80DDB", "d80U"):
        k0 = key(F[f])
        c = [0]
        dd["expr"] = swap(dd["expr"], lambda n, k0=k0: isinstance(n, dict) and key(n) == k0, lambda n: CHOOSE([(EQ("$resident", False), 0)], copy.deepcopy(n)), c)
        print("  deductions:", f, "wrapped", c[0])
        assert c[0] >= 2, (f, c[0])
        F = dd["expr"]["fields"]
    write(dd)
    for tc in dd["test_cases"]:
        got = run_chip("myreturn.deductions", tc["args"])
        assert got == tc["expect_value"], (tc["args"], {k2: (got[k2], v) for k2, v in tc["expect_value"].items() if got.get(k2) != v})
    base = {"regime": "old", "gross_total": 1500000, "dd_nature": "1", "c80ddb": 50000, "disability": "normal", "c80c": 100000}
    for args, want in [(base, {"d80DD": 75000, "d80DDB": 40000, "d80U": 75000}), (base | {"resident": False}, {"d80DD": 0, "d80DDB": 0, "d80U": 0, "d80C": 100000, "total": 100000})]:
        got = run_chip("myreturn.deductions", args)
        assert all(got[k2] == v for k2, v in want.items()), (args, {k2: got[k2] for k2 in want})
        dd["test_cases"].append({"args": args, "expect_value": got})
    save(dd, "resident: 80DD, 80DDB and 80U are for a resident (ITR-2 validation rules 327-329) - nil for a non-resident (an RNOR is resident).")

fm = load("myreturn.form")
if not has_param(fm, "clubbing"):
    fm["params"].append(P("clubbing", False, "a spouse's / minor child's income clubbed (s.64) - shown in Schedule SPI, which ITR-1 / ITR-4 do not have"))
    CLUB_CASE = {"when": EQ("$clubbing", True), "then": V("record", fields={"form": "ITR-2", "why": "why_club"})}
    n = [0]

    def ins(node):
        if isinstance(node, dict):
            if isinstance(node.get("cases"), list):
                cs = node["cases"]
                for i, cs_ in enumerate(cs):
                    if cs_.get("when") == EQ("$foreign", True) and CLUB_CASE not in cs:
                        cs.insert(i + 1, copy.deepcopy(CLUB_CASE))
                        n[0] += 1
                        break
            for v in node.values():
                ins(v)
        elif isinstance(node, list):
            for v in node:
                ins(v)
    ins(fm["expr"])
    print("  form: clubbing case added", n[0])
    assert n[0] >= 3
    write(fm)
    for tc in fm["test_cases"]:
        got = run_chip("myreturn.form", tc["args"])
        assert got == tc["expect_value"], (tc["args"], got)
    for args, want in [({"total": 900000, "clubbing": True}, {"form": "ITR-2", "why": "why_club"}),
                       ({"total": 900000, "clubbing": True, "business": True}, {"form": "ITR-3"}),
                       ({"total": 900000, "resident": False, "business": True}, {"form": "ITR-3"}),
                       ({"total": 900000, "foreign": True}, {"form": "ITR-2", "why": "why_foreign"})]:
        got = run_chip("myreturn.form", args)
        assert all(got[k2] == v for k2, v in want.items()), (args, got)
        fm["test_cases"].append({"args": args, "expect_value": got})
    save(fm, "clubbing (s.64): income of a spouse / minor child clubbed - ITR-2 (ITR-3 with a business), for Schedule SPI; ITR-1 / ITR-4 are open to "
             "clubbed income but have no schedule naming whose it is - My return files ITR-2, which any individual may file instead. resident means "
             "resident AND ordinarily resident: an RNOR or a non-resident files ITR-2 / ITR-3 (ITR-1 / ITR-4 are for an ordinarily resident).")
print("done")
