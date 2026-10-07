"""2026-10-07 My return, wave 3: capital gains in full - Schedule 112A per scrip (grandfathering), property sales (s.50C, the
23 July 2024 choice: 12.5% without indexation or 20% with it, whichever is lower), debt funds and s.50AA, the 54 / 54EC / 54F
exemptions with the Capital Gains Account Scheme, set-off and carry-forward of losses (s.70 / 71B / 74, Schedule CFL),
gifts (s.56(2)(x)) and pre-construction interest (s.24(b), 1/5 for 5 years). Writes / updates the chips once - each step
looks first. Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/make_cg_chips.py
Law: Finance (No.2) Act 2024 as it stands for AY 2026-27 (FY 2025-26); CII FY 2025-26 = 376 (CBDT Notification 70/2025)."""
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


def save(c, note=""):
    c["version"] += 1
    if note:
        c["description_nl"] = c.get("description_nl", "") + " " + NOTE + note
    (CH / f"{c['chip_id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
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


# --- a little grammar --------------------------------------------------------------------------------------------------------
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


def TOT(*v):
    return V("total", values=list(v))


def EQ(a, b):
    return T("eq", left=a, right=b)


def ALL(*items):
    return T("all", items=list(items))


def ANY(*items):
    return T("any", items=list(items))


def NOT(item):
    return T("not", item=item)


def IN(v, s):
    return T("in_set", value=v, set=s)


ISO = r"^\d{4}-\d{2}-\d{2}$"
RULES = CHIP("myreturn.cg_rules")


def R(path):
    return GET(RULES, path)


def A(field):
    """A field of the row's asset kind (chip myreturn.cg_rules assets.<asset>.<field>)."""
    return GET(RULES, V("template", text="assets.{a}." + field, values=V("record", fields={"a": "$asset"})))


def P(name, default, label, typ=None):
    typ = typ or ("boolean" if isinstance(default, bool) else "number" if isinstance(default, (int, float)) else "text" if isinstance(default, str) else "json")
    return {"name": name, "type": typ, "default": default, "label": label}


def chip(cid, label, aliases, params, expr, desc, cases, returns="record"):
    c = {"chip_id": cid, "kind": "accessor", "set": "myreturn", "label": label, "aliases": aliases, "params": params, "expr": expr,
         "returns": returns, "version": 1, "status": "published", "description_nl": NOTE + desc, "test_cases": []}
    (CH / f"{cid}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for args, want in cases:                     # every case: the answer worked out, checked against what was said by hand
        got = run_chip(cid, args)
        if isinstance(want, dict):
            bad = {k2: (got.get(k2), v) for k2, v in want.items() if got.get(k2) != v}
        else:
            bad = {"value": (got, want)} if got != want else {}
        assert not bad, (cid, args, bad)
        c["test_cases"].append({"args": args, "expect_value": got})
    (CH / f"{cid}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", cid, f"({len(cases)} cases)")


# --- 1 the rules: asset kinds, dates, caps, set-off order -------------------------------------------------------------------
ASSETS = {
    "equity": {"months": 12, "short": "stcg_111a", "long": "ltcg_112a", "grandfather": True, "index_option": False, "s50c": False,
               "aa50_bought_from": "", "aa50_sold_from": "", "always_short": False, "ex": ["54F"], "property": False},
    "listed": {"months": 12, "short": "stcg_app", "long": "ltcg_112", "grandfather": False, "index_option": False, "s50c": False,
               "aa50_bought_from": "", "aa50_sold_from": "", "always_short": False, "ex": ["54F"], "property": False},
    "debt_mf": {"months": 24, "short": "stcg_app", "long": "ltcg_112", "grandfather": False, "index_option": False, "s50c": False,
                "aa50_bought_from": "2023-04-01", "aa50_sold_from": "", "always_short": False, "ex": ["54F"], "property": False},
    "mld": {"months": 12, "short": "stcg_app", "long": "ltcg_112", "grandfather": False, "index_option": False, "s50c": False,
            "aa50_bought_from": "", "aa50_sold_from": "", "always_short": True, "ex": [], "property": False},
    "unlisted_bond": {"months": 24, "short": "stcg_app", "long": "ltcg_112", "grandfather": False, "index_option": False, "s50c": False,
                      "aa50_bought_from": "", "aa50_sold_from": "2024-07-23", "always_short": False, "ex": [], "property": False},
    "land": {"months": 24, "short": "stcg_app", "long": "ltcg_112", "grandfather": False, "index_option": True, "s50c": True,
             "aa50_bought_from": "", "aa50_sold_from": "", "always_short": False, "ex": ["54EC", "54F"], "property": True},
    "house": {"months": 24, "short": "stcg_app", "long": "ltcg_112", "grandfather": False, "index_option": True, "s50c": True,
              "aa50_bought_from": "", "aa50_sold_from": "", "always_short": False, "ex": ["54", "54EC"], "property": True},
    "other": {"months": 24, "short": "stcg_app", "long": "ltcg_112", "grandfather": False, "index_option": False, "s50c": False,
              "aa50_bought_from": "", "aa50_sold_from": "", "always_short": False, "ex": ["54F"], "property": False},
}
RULE_KNOBS = [
    P("assets", ASSETS, "each kind of capital asset: months held to be long-term (s.2(42A) - 12 for listed securities other than units, equity-fund "
      "units and zero-coupon bonds, 24 for the rest), the bucket short / long, grandfathering (112A), the indexation option (land / building), "
      "s.50C, s.50AA (debt funds bought from 1 April 2023, market-linked debentures, unlisted bonds / debentures sold from 23 July 2024: always "
      "short-term at the slab rates) and the exemptions it may claim"),
    P("grandfather_before", "2018-02-01", "112A grandfathering (s.55(2)(ac)): bought before this day - cost is the higher of cost and the lower of FMV on 31-01-2018 and the sale value"),
    P("index_before", "2024-07-23", "proviso to s.112(1)(a): land / building bought before this day, by a resident individual / HUF - tax is the lower of 12.5% without indexation and 20% with it"),
    P("rate_indexed", 20, "proviso to s.112(1)(a): the rate with indexation"),
    P("index_residents_only", True, "the indexation choice is for residents only (rule 570 of the ITR-2 validations)"),
    P("s50c_tolerance_pct", 10, "s.50C: the stamp-duty value is the sale value only when it is more than 110% of what was received"),
    P("cii_base_year", 2001, "s.48 / s.55(2)(b): a capital asset bought before 1 April 2001 - cost is its FMV on that day, indexed from 2001-02"),
    P("cap_54", 100000000, "s.54 / s.54F: the cost of the new house counted, at most (Finance Act 2023)"),
    P("cap_54ec", 5000000, "s.54EC: bonds within 6 months, at most 50 lakh in the year and the next"),
    P("f54_houses_max", 1, "s.54F: not more than one other residential house owned on the day of transfer (other than the new one)"),
    P("ec_months", 6, "s.54EC: the bonds are bought within this many months of the transfer"),
    P("stcl_order", ["stcg_app", "stcg_111a", "ltcg_112", "ltcg_112a"], "s.70(2) / s.74(1)(a): a short-term loss is set off against these gains, in this order (slab-rate gains first, the 1.25 lakh 112A exemption last)"),
    P("ltcl_order", ["ltcg_112", "ltcg_112a"], "s.70(3) / s.74(1)(b): a long-term loss only against long-term gains, in this order"),
    P("loss_years", 8, "s.74 / s.71B: a loss is carried forward for 8 assessment years"),
    P("cf_kinds", ["original", "revised"], "s.80 / s.139(3): a capital loss is carried forward only when the return is filed by the due date (an original, or its revision)"),
    P("hp_cf_any", True, "s.80 does not name s.71B: a house-property loss is carried forward from a belated return too"),
]


def record_of(params):
    return V("record", fields={p["name"]: "$" + p["name"] for p in params})


chip("myreturn.cg_rules", "My return: capital-gains rules", ["capital gains", "holding period", "50aa", "54", "set off"], RULE_KNOBS, record_of(RULE_KNOBS),
     "The capital-gains rules My return works by (Finance (No.2) Act 2024; AY 2026-27): holding periods, buckets, grandfathering, the indexation "
     "choice for land / building bought before 23 July 2024, s.50C, s.50AA, exemption caps, set-off order and carry-forward.",
     [({}, {"rate_indexed": 20, "cap_54ec": 5000000})])

CII = {"2001": 100, "2002": 105, "2003": 109, "2004": 113, "2005": 117, "2006": 122, "2007": 129, "2008": 137, "2009": 148, "2010": 167, "2011": 184,
       "2012": 200, "2013": 220, "2014": 240, "2015": 254, "2016": 264, "2017": 272, "2018": 280, "2019": 289, "2020": 301, "2021": 317, "2022": 331,
       "2023": 348, "2024": 363, "2025": 376}
chip("myreturn.fy_of", "My return: the financial year a day falls in", ["financial year", "fy"],
     [P("date", "", "a day, YYYY-MM-DD"), P("year_starts_month", 4, "the financial year starts in April")],
     CHOOSE([(NOT(V("matches", text="$date", pattern=ISO)), None),
             (T("ge", left=V("text_pick", text="$date", pattern=r"^\d{4}-(\d{2})"), right="$year_starts_month"), ADD(V("text_pick", text="$date", pattern=r"^(\d{4})"), 0))],
            SUB(V("text_pick", text="$date", pattern=r"^(\d{4})"), 1)),
     "The year a financial year starts in (1 April 2025 to 31 March 2026 -> 2025); blank for a day that is not YYYY-MM-DD.",
     [({"date": "2025-04-01"}, 2025), ({"date": "2026-03-31"}, 2025), ({"date": "2010-06-15"}, 2010), ({"date": "2016-01-10"}, 2015), ({"date": ""}, None)],
     returns="number")
chip("myreturn.cii", "My return: cost inflation index", ["cii", "indexation", "cost inflation index"],
     [P("date", "", "a day, YYYY-MM-DD (the year it falls in is looked up)"),
      P("table", CII, "the cost inflation index by financial year (the year it starts), CBDT notifications - base 2001-02 = 100; 2025-26 = 376 (Notification 70/2025)")],
     CHOOSE([(NOT(V("matches", text="$date", pattern=ISO)), None)],
            GET("$table", V("template", text="{y}", values=V("record", fields={"y": MX(CHIP("myreturn.fy_of", {"date": "$date"}), R("cii_base_year"))})))),
     "The cost inflation index for the financial year a day falls in; a day before 1 April 2001 takes 2001-02 (= 100, cost being the FMV on 1 April 2001).",
     [({"date": "2025-11-20"}, 376), ({"date": "2010-06-15"}, 167), ({"date": "2015-08-01"}, 254), ({"date": "1995-05-01"}, 100), ({"date": ""}, None)],
     returns="number")

# --- 2 one sale: short or long, its bucket, the value taken, the cost, the gain both ways --------------------------------------
DATED = ALL(V("matches", text="$acquired", pattern=ISO), V("matches", text="$sold", pattern=ISO))
DEEMED = ANY(EQ(A("always_short"), True),
             ALL(T("ne", left=A("aa50_bought_from"), right=""), V("matches", text="$acquired", pattern=ISO), T("ge", left="$acquired", right=A("aa50_bought_from"))),
             ALL(T("ne", left=A("aa50_sold_from"), right=""), V("matches", text="$sold", pattern=ISO), T("ge", left="$sold", right=A("aa50_sold_from"))))
LONG_BY_DATES = T("gt", left="$sold", right=V("date_shift", date="$acquired", months=A("months")))
TERM = CHOOSE([(DEEMED, "short"), (IN("$term", ["long", "short"]), "$term"), (ALL(DATED, LONG_BY_DATES), "long")], "short")
IS_LONG = EQ(TERM, "long")
S50C = ALL(EQ(A("s50c"), True), T("gt", left="$stamp", right=MUL("$sale", ADD(1, DIV(R("s50c_tolerance_pct"), 100)))))
CONS = CHOOSE([(S50C, "$stamp")], "$sale")
GF = ALL(EQ(A("grandfather"), True), IS_LONG, V("matches", text="$acquired", pattern=ISO), T("lt", left="$acquired", right=R("grandfather_before")))
COST = CHOOSE([(GF, MX("$cost", MN("$fmv", CONS)))], "$cost")
GAIN = SUB(SUB(SUB(CONS, COST), "$improve"), "$expenses")
INDEX_OK = ALL(EQ(A("index_option"), True), IS_LONG, DATED, T("lt", left="$acquired", right=R("index_before")),
               ANY(EQ("$resident", True), EQ(R("index_residents_only"), False)))
CII_SELL = CHIP("myreturn.cii", {"date": "$sold"})
I_COST = CHOOSE([(INDEX_OK, RND(DIV(MUL("$cost", CII_SELL), CHIP("myreturn.cii", {"date": "$acquired"}))))], "$cost")
IMP_ON = CHOOSE([(V("matches", text="$improve_on", pattern=ISO), "$improve_on")], "$acquired")
I_IMP = CHOOSE([(ALL(INDEX_OK, T("gt", left="$improve", right=0)), RND(DIV(MUL("$improve", CII_SELL), CHIP("myreturn.cii", {"date": IMP_ON}))))], "$improve")
ROW_PARAMS = [P("asset", "equity", "the kind of asset (chip myreturn.cg_rules assets)"), P("acquired", "", "bought on, YYYY-MM-DD"), P("sold", "", "sold / transferred on, YYYY-MM-DD"),
              P("term", "", "long / short, typed when the dates are not known"), P("sale", 0, "full value of consideration received"),
              P("cost", 0, "cost of acquisition (FMV on 1 April 2001 for an asset bought before)"), P("improve", 0, "cost of improvement"),
              P("improve_on", "", "improvement made on, YYYY-MM-DD"), P("fmv", 0, "112A: total FMV on 31 January 2018"),
              P("expenses", 0, "expenses wholly on the transfer (brokerage, stamp duty paid by the seller)"), P("stamp", 0, "s.50C: the stamp-duty value of land / building"),
              P("resident", True, "the person is resident")]
chip("myreturn.cg_row", "My return: one capital-gains sale", ["capital gain", "grandfathering", "indexation", "50c", "50aa", "112a"], ROW_PARAMS,
     V("record", fields={
         "term": TERM, "bucket": CHOOSE([(IS_LONG, A("long"))], A("short")), "deemed_50aa": CHOOSE([(DEEMED, True)], False),
         "dated": CHOOSE([(DATED, True)], False), "property": A("property"),
         "consideration": CONS, "s50c": CHOOSE([(S50C, True)], False), "grandfathered": CHOOSE([(GF, True)], False), "cost_used": COST,
         "gain": GAIN, "index_ok": CHOOSE([(INDEX_OK, True)], False),
         "cii_sell": CHOOSE([(INDEX_OK, CII_SELL)], 0), "cii_buy": CHOOSE([(INDEX_OK, CHIP("myreturn.cii", {"date": "$acquired"}))], 0),
         "cii_improve": CHOOSE([(ALL(INDEX_OK, T("gt", left="$improve", right=0)), CHIP("myreturn.cii", {"date": IMP_ON}))], 0),
         "cost_indexed": I_COST, "improve_indexed": I_IMP, "gain_indexed": SUB(SUB(SUB(CONS, I_COST), I_IMP), "$expenses")}),
     "One transfer of a capital asset (s.45 / s.48): short- or long-term by the months it was held (more than 12 / 24 months is long), s.50AA "
     "(always short-term), the bucket it is taxed in (111A 20%, 112A 12.5% over 1.25 lakh, 112 12.5%, or the slab rates), s.50C for land / building "
     "(the stamp-duty value when it is more than 110% of the price), 112A grandfathering for shares bought before 1 February 2018, and for land / "
     "building bought before 23 July 2024 by a resident the gain with indexation too (cost x CII of the year of sale / CII of the year bought).",
     [({"asset": "equity", "acquired": "2017-06-01", "sold": "2025-09-10", "sale": 300000, "cost": 100000, "fmv": 250000},
       {"term": "long", "bucket": "ltcg_112a", "grandfathered": True, "cost_used": 250000, "gain": 50000}),
      ({"asset": "equity", "acquired": "2017-06-01", "sold": "2025-09-10", "sale": 200000, "cost": 100000, "fmv": 250000}, {"cost_used": 200000, "gain": 0}),
      ({"asset": "equity", "acquired": "2019-06-01", "sold": "2025-09-10", "sale": 200000, "cost": 100000, "fmv": 250000, "expenses": 500},
       {"grandfathered": False, "cost_used": 100000, "gain": 99500}),
      ({"asset": "equity", "acquired": "2025-01-10", "sold": "2025-08-10", "sale": 150000, "cost": 120000}, {"term": "short", "bucket": "stcg_111a", "gain": 30000}),
      ({"asset": "equity", "acquired": "2024-08-10", "sold": "2025-08-10", "sale": 150000, "cost": 120000}, {"term": "short", "bucket": "stcg_111a"}),
      ({"asset": "equity", "acquired": "2024-08-10", "sold": "2025-08-11", "sale": 150000, "cost": 120000}, {"term": "long", "bucket": "ltcg_112a"}),
      ({"asset": "debt_mf", "acquired": "2023-05-01", "sold": "2025-12-01", "sale": 550000, "cost": 500000}, {"term": "short", "bucket": "stcg_app", "deemed_50aa": True, "gain": 50000}),
      ({"asset": "debt_mf", "acquired": "2022-01-10", "sold": "2025-12-01", "sale": 600000, "cost": 500000}, {"term": "long", "bucket": "ltcg_112", "index_ok": False, "gain": 100000}),
      ({"asset": "debt_mf", "acquired": "2024-01-10", "sold": "2025-12-01", "sale": 600000, "cost": 500000}, {"term": "short", "deemed_50aa": True}),
      ({"asset": "mld", "acquired": "2020-01-10", "sold": "2025-12-01", "sale": 600000, "cost": 500000}, {"term": "short", "bucket": "stcg_app"}),
      ({"asset": "unlisted_bond", "acquired": "2020-01-10", "sold": "2025-12-01", "sale": 600000, "cost": 500000}, {"term": "short", "deemed_50aa": True}),
      ({"asset": "house", "acquired": "2010-06-15", "sold": "2025-11-20", "sale": 9000000, "stamp": 10500000, "cost": 3000000, "improve": 500000, "improve_on": "2015-08-01", "expenses": 100000},
       {"term": "long", "bucket": "ltcg_112", "s50c": True, "consideration": 10500000, "gain": 6900000, "index_ok": True, "cost_indexed": 6754491,
        "improve_indexed": 740157, "gain_indexed": 2905352, "cii_sell": 376, "cii_buy": 167, "cii_improve": 254}),
      ({"asset": "land", "acquired": "2010-06-15", "sold": "2025-11-20", "sale": 9000000, "stamp": 9500000, "cost": 3000000}, {"s50c": False, "consideration": 9000000}),
      ({"asset": "land", "acquired": "2024-09-01", "sold": "2025-10-01", "sale": 5000000, "cost": 4000000}, {"term": "short", "bucket": "stcg_app", "index_ok": False}),
      ({"asset": "land", "acquired": "2024-08-01", "sold": "2026-10-01", "sale": 5000000, "cost": 4000000}, {"term": "long", "index_ok": False}),
      ({"asset": "house", "acquired": "1995-05-01", "sold": "2025-11-20", "sale": 5000000, "cost": 1000000}, {"cii_buy": 100, "cost_indexed": 3760000, "gain_indexed": 1240000}),
      ({"asset": "house", "acquired": "2010-06-15", "sold": "2025-11-20", "sale": 9000000, "cost": 3000000, "resident": False}, {"index_ok": False, "gain_indexed": 6000000}),
      ({"asset": "equity", "term": "long", "sale": 90000, "cost": 10000}, {"term": "long", "bucket": "ltcg_112a", "dated": False, "gain": 80000}),
      ({"asset": "other", "acquired": "2021-01-01", "sold": "2025-06-01", "sale": 100000, "cost": 130000}, {"term": "long", "bucket": "ltcg_112", "gain": -30000})])

# --- 3 the exemptions: 54, 54EC, 54F (with the Capital Gains Account Scheme) ----------------------------------------------------
INV = ADD("$invested", "$cgas")
ALLOWED = ALL(IN("$kind", A("ex")), EQ("$term", "long"), T("gt", left="$gain", right=0))
F_HOUSES = T("le", left="$other_houses", right=R("f54_houses_max"))
AMT = CHOOSE([
    (ALL(ALLOWED, EQ("$kind", "54")), MN("$gain", INV, R("cap_54"))),
    (ALL(ALLOWED, EQ("$kind", "54EC")), MN("$gain", "$invested", MX("$ec_room", 0))),
    (ALL(ALLOWED, EQ("$kind", "54F"), F_HOUSES, T("ge", left=MN(INV, R("cap_54")), right="$net")), "$gain"),
    (ALL(ALLOWED, EQ("$kind", "54F"), F_HOUSES, T("gt", left="$net", right=0)), MN("$gain", RND(DIV(MUL("$gain", MN(INV, R("cap_54"))), "$net"))))], 0)
chip("myreturn.cg_exempt", "My return: exemption 54 / 54EC / 54F on one sale", ["54", "54ec", "54f", "exemption", "capital gains account scheme"],
     [P("kind", "", "54 / 54EC / 54F, or blank"), P("asset", "house", "the asset sold (chip myreturn.cg_rules assets: which exemptions it may claim)"),
      P("term", "long", "long / short"), P("gain", 0, "the long-term gain"), P("net", 0, "net consideration: the value taken less transfer expenses (54F)"),
      P("invested", 0, "the new house's cost (54 / 54F) or the bonds bought (54EC)"), P("cgas", 0, "deposited in the Capital Gains Account Scheme by the return's due date (54 / 54F)"),
      P("ec_room", 5000000, "54EC: what is left of the 50 lakh in the year"), P("other_houses", 0, "54F: other residential houses owned on the day of transfer")],
     V("record", fields={"amount": AMT, "ok": CHOOSE([(T("gt", left=AMT, right=0), True)], False),
                         "why": CHOOSE([(EQ("$kind", ""), ""), (NOT(IN("$kind", A("ex"))), "ex_not_for"), (NOT(EQ("$term", "long")), "ex_short"),
                                        (ALL(EQ("$kind", "54F"), NOT(F_HOUSES)), "ex_houses"), (T("le", left="$gain", right=0), "ex_no_gain")], "")}),
     "s.54: a residential house sold, long-term - the gain up to the cost of the new house (bought 1 year before / 2 years after, or built in 3), at most "
     "10 crore counted. s.54EC: land / building, long-term - the gain up to the bonds bought within 6 months, at most 50 lakh. s.54F: any other "
     "long-term asset - the gain x the new house's cost (at most 10 crore) / the net consideration, all of it when the cost is as much; not for one "
     "who owns more than one other house. An amount deposited in the Capital Gains Account Scheme by the due date counts as the cost (54 / 54F).",
     [({"kind": "54", "gain": 6900000, "invested": 5000000, "cgas": 1000000}, {"amount": 6000000, "ok": True}),
      ({"kind": "54", "gain": 200000000, "invested": 150000000}, {"amount": 100000000}),
      ({"kind": "54EC", "asset": "land", "gain": 6900000, "invested": 6000000, "ec_room": 5000000}, {"amount": 5000000}),
      ({"kind": "54EC", "asset": "land", "gain": 6900000, "invested": 6000000, "ec_room": 1000000}, {"amount": 1000000}),
      ({"kind": "54F", "asset": "equity", "gain": 1000000, "net": 3000000, "invested": 1500000}, {"amount": 500000}),
      ({"kind": "54F", "asset": "equity", "gain": 1000000, "net": 3000000, "invested": 2000000, "cgas": 1000000}, {"amount": 1000000}),
      ({"kind": "54F", "asset": "equity", "gain": 1000000, "net": 3000000, "invested": 1500000, "other_houses": 2}, {"amount": 0, "why": "ex_houses"}),
      ({"kind": "54", "asset": "equity", "gain": 1000000, "invested": 1500000}, {"amount": 0, "why": "ex_not_for"}),
      ({"kind": "54", "term": "short", "gain": 1000000, "invested": 1500000}, {"amount": 0, "why": "ex_short"}),
      ({"kind": "54F", "asset": "house", "gain": 1000000, "net": 2000000, "invested": 2000000}, {"amount": 0, "why": "ex_not_for"}),
      ({"kind": "", "gain": 1000000}, {"amount": 0, "why": ""})])

# --- 4 the property's choice: 12.5% without indexation, or 20% with it - whichever is lower ---------------------------------------
TA = RND(MUL(MX("$gain", 0), DIV(GET(CHIP("myreturn.rates"), "rate_112"), 100)))
TB = RND(MUL(MX("$gain_indexed", 0), DIV(R("rate_indexed"), 100)))
EXCESS = CHOOSE([(EQ("$index_ok", True), MX(SUB(TA, TB), 0))], 0)
chip("myreturn.cg_choice", "My return: land / building - with or without indexation", ["indexation", "112", "23 july 2024", "excess tax"],
     [P("gain", 0, "the long-term gain without indexation, after the exemption"), P("gain_indexed", 0, "the gain with indexation, after the exemption"),
      P("index_ok", False, "the choice is open (resident, land / building bought before 23 July 2024)")],
     V("record", fields={"tax_plain": TA, "tax_indexed": CHOOSE([(EQ("$index_ok", True), TB)], 0), "excess": EXCESS,
                         "chosen": CHOOSE([(T("gt", left=EXCESS, right=0), "indexed")], "plain")}),
     "Proviso to s.112(1)(a) (Finance (No.2) Act 2024): for land / building bought before 23 July 2024 by a resident individual / HUF, the tax on the "
     "gain is the lower of 12.5% without indexation and 20% with indexation - the return shows the gain without indexation and the excess (Schedule "
     "CG B1e: TaxSec1121a - TaxSec1121aiiB, ExcessAmtSec1121a) is left out of the tax.",
     [({"gain": 6900000, "gain_indexed": 2905352, "index_ok": True}, {"tax_plain": 862500, "tax_indexed": 581070, "excess": 281430, "chosen": "indexed"}),
      ({"gain": 2000000, "gain_indexed": 1500000, "index_ok": True}, {"tax_plain": 250000, "tax_indexed": 300000, "excess": 0, "chosen": "plain"}),
      ({"gain": 2000000, "gain_indexed": -100000, "index_ok": True}, {"tax_indexed": 0, "excess": 250000}),
      ({"gain": 2000000, "gain_indexed": 1000000, "index_ok": False}, {"excess": 0, "tax_indexed": 0, "chosen": "plain"})])

# --- 5 a loss set off against gains in order ------------------------------------------------------------------------------------
G = lambda i: MX(GET("$gains", str(i)), 0)  # noqa: E731
USED = [MN(G(0), MX(0, "$loss"))] + [MN(G(i), MX(0, SUB("$loss", TOT(*[G(j) for j in range(i)])))) for i in range(1, 4)]
chip("myreturn.waterfall", "My return: a loss against gains, in order", ["set off", "loss", "cyla", "bfla"],
     [P("loss", 0, "the loss to set off"), P("gains", [0, 0, 0, 0], "the gains it may be set off against, in the order the law (or the person) takes them - up to four")],
     V("record", fields={"used": USED, "left": MX(0, SUB("$loss", TOT(G(0), G(1), G(2), G(3)))),
                         "rest": [SUB(G(i), USED[i]) for i in range(4)]}),
     "A loss set off against up to four gains, the first first: each takes what it can of what is left (s.70, s.71, s.74, s.71B - the order is "
     "chip myreturn.cg_rules stcl_order / ltcl_order). used = what each gain absorbed, left = the loss not set off, rest = each gain after.",
     [({"loss": 150, "gains": [100, 30, 50, 0]}, {"used": [100, 30, 20, 0], "left": 0, "rest": [0, 0, 30, 0]}),
      ({"loss": 300, "gains": [100, 30, 50, 0]}, {"used": [100, 30, 50, 0], "left": 120}),
      ({"loss": 0, "gains": [100, 30, 50, 0]}, {"used": [0, 0, 0, 0], "left": 0, "rest": [100, 30, 50, 0]}),
      ({"loss": 50, "gains": [0, 0, 80, 10]}, {"used": [0, 0, 50, 0], "rest": [0, 0, 30, 10]})])

# --- 6 a loss of an earlier year: can it still be set off? -----------------------------------------------------------------------
AGE = SUB(V("text_pick", text="$ay", pattern=r"^(\d{4})"), V("text_pick", text="$loss_ay", pattern=r"^(\d{4})"))
chip("myreturn.loss_age", "My return: a loss brought forward - still in time?", ["carry forward", "cfl", "8 years"],
     [P("loss_ay", "", "the assessment year the loss was first worked out in (2019-20)"), P("ay", "2026-27", "this return's assessment year"),
      P("kind", "stcl", "stcl / ltcl / hp")],
     V("record", fields={"age": AGE, "usable": CHOOSE([(ALL(T("ge", left=AGE, right=1), T("le", left=AGE, right=R("loss_years"))), True)], False)}),
     "s.74(1) / s.71B: a capital or house-property loss is carried forward to the 8 assessment years after the one it was worked out in; the 9th "
     "year on it is gone. age 1 = last year's.",
     [({"loss_ay": "2025-26"}, {"age": 1, "usable": True}), ({"loss_ay": "2018-19"}, {"age": 8, "usable": True}),
      ({"loss_ay": "2017-18"}, {"age": 9, "usable": False}), ({"loss_ay": "2026-27"}, {"age": 0, "usable": False})])

# --- 7 gifts (s.56(2)(x)) -------------------------------------------------------------------------------------------------------
RELATIVES = ["spouse", "brother", "sister", "spouse_sibling", "parent_sibling", "lineal", "spouse_lineal", "sibling_spouse", "huf_member"]
GIFT_KNOBS = [P("relatives", RELATIVES, "s.56(2)(x) Explanation (e): relatives - spouse; brother or sister; brother or sister of the spouse; brother or sister "
                "of either parent; any lineal ascendant or descendant; any lineal ascendant or descendant of the spouse; the spouse of any of these; "
                "for an HUF, any member"),
              P("exempt_occasions", ["marriage", "will", "inheritance", "death"], "s.56(2)(x) proviso: on the person's marriage, under a will or by inheritance, "
                "in contemplation of the payer's death"),
              P("threshold", 50000, "s.56(2)(x): taxable when more than this (sums and movable property in the year together, each immovable property alone)"),
              P("inadequate_pct", 10, "s.56(2)(x)(b)(B): immovable property bought for less - taxable when the stamp value beats the price by more than the "
                "higher of 50,000 and this % of the price")]
chip("myreturn.gift_rules", "My return: gifts - the rules (s.56(2)(x))", ["gift", "56(2)(x)"], GIFT_KNOBS, record_of(GIFT_KNOBS),
     "Who is a relative, which occasions are exempt and the thresholds for gifts taxed as other sources (s.56(2)(x)).", [({}, {"threshold": 50000})])
GR = CHIP("myreturn.gift_rules")
COUNTS = ALL(NOT(IN("$relation", GET(GR, "relatives"))), NOT(IN("$occasion", GET(GR, "exempt_occasions"))))
SHORTFALL = MX(SUB("$value", "$paid"), 0)
PROP_TAX = CHOOSE([(ALL(COUNTS, EQ("$kind", "property"), T("le", left="$paid", right=0), T("gt", left="$value", right=GET(GR, "threshold"))), "$value"),
                   (ALL(COUNTS, EQ("$kind", "property"), T("gt", left="$paid", right=0),
                        T("gt", left=SHORTFALL, right=MX(GET(GR, "threshold"), RND(MUL("$paid", DIV(GET(GR, "inadequate_pct"), 100)))))), SHORTFALL)], 0)
chip("myreturn.gift_row", "My return: one gift received", ["gift", "56(2)(x)"],
     [P("relation", "", "who gave it (chip myreturn.gift_rules relatives), blank for anyone else"), P("occasion", "", "marriage / will / inheritance / death, or blank"),
      P("kind", "money", "money / property (immovable: land, building) / movable (shares, jewellery, art ...)"),
      P("value", 0, "the sum, or the stamp-duty value (property), or the fair market value (movable)"), P("paid", 0, "what the person paid for it")],
     V("record", fields={"counts": CHOOSE([(COUNTS, True)], False),
                         "money": CHOOSE([(ALL(COUNTS, EQ("$kind", "money")), "$value")], 0),
                         "movable_free": CHOOSE([(ALL(COUNTS, EQ("$kind", "movable"), T("le", left="$paid", right=0)), "$value")], 0),
                         "movable_less": CHOOSE([(ALL(COUNTS, EQ("$kind", "movable"), T("gt", left="$paid", right=0)), SHORTFALL)], 0),
                         "movable_paid": CHOOSE([(ALL(COUNTS, EQ("$kind", "movable"), T("gt", left="$paid", right=0)), "$paid")], 0),
                         "property_free": CHOOSE([(ALL(EQ("$kind", "property"), T("le", left="$paid", right=0)), PROP_TAX)], 0),
                         "property_less": CHOOSE([(ALL(EQ("$kind", "property"), T("gt", left="$paid", right=0)), PROP_TAX)], 0)}),
     "One gift (s.56(2)(x)): from a relative, or on marriage, by will or inheritance, or in contemplation of death - nothing. Otherwise a sum or "
     "movable property counts towards the year's total (chip myreturn.gifts); an immovable property is taxed on its own - received free, its "
     "stamp-duty value when more than 50,000; bought for less, the shortfall when more than the higher of 50,000 and 10% of the price.",
     [({"relation": "brother", "kind": "money", "value": 500000}, {"counts": False, "money": 0}),
      ({"kind": "money", "value": 40000}, {"counts": True, "money": 40000}),
      ({"kind": "money", "value": 200000, "occasion": "marriage"}, {"counts": False, "money": 0}),
      ({"kind": "property", "value": 3000000}, {"property_free": 3000000}),
      ({"kind": "property", "value": 3000000, "paid": 2800000}, {"property_less": 0}),
      ({"kind": "property", "value": 3000000, "paid": 2500000}, {"property_less": 500000}),
      ({"kind": "property", "value": 40000}, {"property_free": 0}),
      ({"kind": "movable", "value": 80000}, {"movable_free": 80000}),
      ({"kind": "movable", "value": 80000, "paid": 20000}, {"movable_less": 60000, "movable_paid": 20000})])
TH = GET(GR, "threshold")
OVER = lambda v: CHOOSE([(T("gt", left=v, right=TH), v)], 0)  # noqa: E731
chip("myreturn.gifts", "My return: gifts taxed as other sources", ["gift", "56(2)(x)", "schedule os"],
     [P("money", 0, "sums received in the year that count"), P("movable_free", 0, "movable property received free - its FMV, in the year"),
      P("movable_less", 0, "movable property bought for less - FMV less the price, in the year"), P("property_free", 0, "immovable property received free - taxable already"),
      P("property_less", 0, "immovable property bought for less - taxable already")],
     V("record", fields={"money": OVER("$money"), "movable_free": OVER("$movable_free"), "movable_less": OVER("$movable_less"),
                         "property_free": "$property_free", "property_less": "$property_less",
                         "total": TOT(OVER("$money"), OVER("$movable_free"), OVER("$movable_less"), "$property_free", "$property_less")}),
     "s.56(2)(x): sums received without consideration in the year, more than 50,000 together - all of them; movable property received free, FMV "
     "together more than 50,000 - all of it; bought for less by more than 50,000 together - the shortfall; immovable property as chip "
     "myreturn.gift_row says. Schedule OS 1d (i) to (v).",
     [({"money": 40000}, {"money": 0, "total": 0}), ({"money": 60000}, {"money": 60000, "total": 60000}),
      ({"money": 30000, "movable_free": 30000}, {"total": 0}), ({"money": 60000, "property_free": 3000000, "movable_less": 70000}, {"total": 3130000})])

# --- 8 pre-construction interest (s.24(b)): one fifth a year for five years from the year it was finished -------------------------
FY_DONE = CHIP("myreturn.fy_of", {"date": "$completed"})
IN_TIME = ALL(V("matches", text="$completed", pattern=ISO), T("ge", left=SUB("$fy", FY_DONE), right=0), T("lt", left=SUB("$fy", FY_DONE), right="$parts"))
chip("myreturn.pre_construction", "My return: interest before construction - this year's share", ["pre-construction interest", "24(b)", "1/5"],
     [P("total", 0, "interest on the loan for the years before the house was bought / built"), P("completed", "", "the day it was bought / finished, YYYY-MM-DD"),
      P("fy", 2025, "this return's financial year (the year it starts)"), P("parts", 5, "s.24(b) Explanation: in five equal parts")],
     V("record", fields={"this_year": CHOOSE([(IN_TIME, RND(DIV("$total", "$parts")))], 0),
                         "years_left": CHOOSE([(IN_TIME, SUB(SUB("$parts", 1), SUB("$fy", FY_DONE)))], 0)}),
     "s.24(b) Explanation: interest for the period before the year a house was bought or built is allowed in five equal parts, from that year on. "
     "For a self-occupied house it sits inside the 2 lakh cap (chip myreturn.house).",
     [({"total": 250000, "completed": "2023-09-01"}, {"this_year": 50000, "years_left": 2}), ({"total": 250000, "completed": "2019-09-01"}, {"this_year": 0}),
      ({"total": 250000, "completed": "2025-04-10"}, {"this_year": 50000, "years_left": 4}), ({"total": 250000, "completed": ""}, {"this_year": 0})])

# --- 9 one house: this year's fifth of the pre-construction interest joins the interest ---------------------------------------------
h = load("myreturn.house")
if not has_param(h, "pre_total"):
    h["params"] += [P("pre_total", 0, "s.24(b): interest for the period before the house was bought / built"),
                    P("completed", "", "the day the house was bought / finished, YYYY-MM-DD"), P("fy", 2025, "this return's financial year (the year it starts)")]
    PRE = GET(CHIP("myreturn.pre_construction", {"total": "$pre_total", "completed": "$completed", "fy": "$fy"}), "this_year")
    c = [0]
    h["expr"] = swap(h["expr"], lambda n: n == "$interest", lambda n: ADD("$interest", copy.deepcopy(PRE)), c)
    print("  house: interest leaves", c[0])
    (CH / "myreturn.house.json").write_text(json.dumps(h, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for tc in h["test_cases"]:
        got = run_chip("myreturn.house", tc["args"])
        assert got == tc["expect_value"], (tc, got)
    for args, want in [({"kind": "self", "interest": 180000, "regime": "old", "pre_total": 250000, "completed": "2023-09-01"}, {"interest": 200000, "net": -200000}),
                       ({"kind": "let", "rent": 300000, "municipal_tax": 0, "interest": 100000, "regime": "new", "pre_total": 250000, "completed": "2023-09-01"},
                        {"interest": 150000, "nav": 300000, "std": 90000, "net": 60000}),
                       ({"kind": "let", "rent": 300000, "interest": 100000, "regime": "new", "pre_total": 250000, "completed": "2023-09-01", "share": 50},
                        {"interest": 75000})]:
        got = run_chip("myreturn.house", args)
        assert all(got[k2] == v for k2, v in want.items()), (args, got)
        h["test_cases"].append({"args": args, "expect_value": got})
    save(h, "pre-construction interest (s.24(b) Explanation): one fifth of it in each of five years from the year the house was bought / finished "
            "(chip myreturn.pre_construction), added to the year's interest - inside the 2 lakh cap for a self-occupied house, by the share for a co-owner.")

# --- 10 the tax: the property's excess (indexation chosen) comes off the 112 tax ------------------------------------------------------
t = load("myreturn.tax")
if not has_param(t, "excess_112"):
    t["params"].append(P("excess_112", 0, "proviso to s.112(1)(a): the tax at 12.5% without indexation less the tax at 20% with it, land / building "
                                          "bought before 23 July 2024 (chip myreturn.cg_choice) - left out of the 112 tax"))
    on112 = t["expr"]["fields"]["on_112"]["value"]
    assert on112["vop"] == "mul", on112["vop"]
    k112 = key(on112)
    c = [0]
    t["expr"] = swap(t["expr"], lambda n: isinstance(n, dict) and key(n) == k112, lambda n: MX(SUB(copy.deepcopy(n), "$excess_112"), 0), c)
    print("  tax: 112 tax less the excess, places", c[0])
    assert c[0] >= 3
    (CH / "myreturn.tax.json").write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for tc in t["test_cases"]:
        got = run_chip("myreturn.tax", tc["args"])
        assert got == tc["expect_value"], (tc["args"], {k2: (got[k2], v) for k2, v in tc["expect_value"].items() if got[k2] != v})
    adds = [({"normal": 1500000, "ltcg_112": 6900000, "excess_112": 281430, "regime": "new"}, {"on_112": 581070}),
            ({"normal": 1500000, "ltcg_112": 1000000, "excess_112": 200000}, {"on_112": 0}),
            ({"normal": 1500000, "ltcg_112": 6900000}, {"on_112": 862500})]
    for args, want in adds:
        got = run_chip("myreturn.tax", args)
        assert all(got[k2] == v for k2, v in want.items()), (args, {k2: got[k2] for k2 in want})
        t["test_cases"].append({"args": args, "expect_value": got})
    save(t, "excess_112: for land / building bought before 23 July 2024 (resident), the tax at 12.5% without indexation less the tax at 20% with it "
            "is left out of the 112 tax (never below nil) - surcharge and cess are on what is left.")

# --- 11 which form: a loss carried forward or brought forward is never ITR-1 / ITR-4 -----------------------------------------------
f = load("myreturn.form")
if not any(tc.get("args", {}).get("loss_cf") and tc.get("args", {}).get("ltcg_112a") for tc in f["test_cases"]):
    for args, want in [({"total": 900000, "ltcg_112a": 100000, "loss_cf": True}, {"form": "ITR-2"}),
                       ({"total": 900000, "ltcg_112a": 100000}, {"form": "ITR-1"}),
                       ({"total": 900000, "other_cg": True, "business": True}, {"form": "ITR-3"}),
                       ({"total": 900000, "ltcg_112a": 100000, "business": True}, {"form": "ITR-4"})]:
        got = run_chip("myreturn.form", args)
        assert all(got[k2] == v for k2, v in want.items()), (args, got)
        f["test_cases"].append({"args": args, "expect_value": got})
    save(f, "test cases for AY 2026-27 ITR-1 / ITR-4: 112A gains up to 1.25 lakh only with no capital loss brought or carried forward; any other "
            "capital gain - ITR-2 (ITR-3 with a business).")
print("done")
