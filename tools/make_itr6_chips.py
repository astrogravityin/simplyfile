"""2026-10-11 company returns (ITR-6) - every rule, rate, threshold, schedule mapping and word for a domestic company, as chips.

Owner: "build ITR-6 ... reuse the same machinery - no second engine". The firm flow is the one ITR-3 / ITR-5 use (Clients & years,
Intake & map, Reconcile, Compute & close, Tax audit); company.py gathers the facts and asks these chips:

  company.settings   the knobs: company kinds, options, the AY's rates, depreciation blocks, SF Ref items, citations
  company.problem    a company's master data checked (CIN, DIN, PANs, shareholdings, option vs kind)
  company.rate       which rate, surcharge and Chapter VI-A follow from the option (normal 25/30%, 115BA, 115BAA, 115BAB)
  company.tax        tax at the rate and at special rates (111A / 112A / 112), surcharge with marginal relief, cess
  company.mat        s.115JB MAT against the normal tax, and the s.115JAA credit made and used
  company.dep_block  one block of assets: WDV, full / half rate, additional depreciation 32(1)(iia), s.50 gain
  company.setoff     one loss against one income (CYLA / BFLA / capital losses / MAT credit)
  company.loss_ok    may this brought-forward loss / credit be used (8 years, s.80, s.79, 15 years)?
  company.d80g       Schedule 80G: no-limit and qualifying-limit donations, the CSR proviso
  company.d80m       s.80M: dividends received, passed on a month before the due date

and changes: clients.settings (status company, form ITR-6, the company knobs), close.dates (a company files by 31 October),
intake.ref / intake.ref_part_ok (ITR6 refs, MAT / SH tables), itr.settings (the ITR-6 schema), itr.codes (ITR-6 codes),
itr.books (Schedule III balance sheet and P&L), tar.settings / tar.codes (a company's audit report is 3CA, status 5),
itr.map (ITR-6 rows), ui.compute / ui.clients (the words).

Law: Income-tax Act 1961 as it applies to AY 2026-27 (FY 2025-26). Rates: Finance Act 2026, First Schedule Part I-A
Paragraph E (unchanged from AY 2025-26 - Memorandum to the Finance Bill 2026, indiabudget.gov.in); the CBDT's ITR-6
validation rules V1.0 for AY 2026-27 (incometax.gov.in > Downloads, 04-Aug-2026) restate them in their rates table.
Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/make_itr6_chips.py   (re-runnable)"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "chips"
NOTE = "2026-10-11: "
sys.path.insert(0, str(ROOT))
SRC_RATES = "Finance Act 2026, First Schedule Part I-A Para E (rates unchanged from AY 2025-26 - Memorandum to the Finance Bill 2026, https://www.indiabudget.gov.in/doc/memo.pdf); CBDT ITR-6 validation rules V1.0 AY 2026-27 (rates table), https://www.incometax.gov.in/iec/foportal/downloads"


def load(cid):
    return json.loads((CH / f"{cid}.json").read_text(encoding="utf-8"))


def write(c):
    (CH / f"{c['chip_id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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


def PCT(a, rate):
    """a x rate %"""
    return DIV(MUL(a, rate), 100)


def RND(v, digits=0):
    return V("round_to", value=v, digits=digits)


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


def ALL(*items):
    return T("all", items=list(items))


def ANY(*items):
    return T("any", items=list(items))


def NOT(item):
    return T("not", item=item)


def IN(v, s):
    return T("in_set", value=v, set=s)


def YES(cond):
    return CHOOSE([(cond, True)], False)


def P(name, default, label, typ=None):
    typ = typ or ("boolean" if isinstance(default, bool) else "number" if isinstance(default, (int, float)) else "text" if isinstance(default, str) else "json")
    return {"name": name, "type": typ, "default": default, "label": label}


def record_of(params):
    return V("record", fields={p["name"]: "$" + p["name"] for p in params})


def chip(cid, label, params, expr, desc, cases, returns="record", cset="company"):
    c = {"chip_id": cid, "kind": "accessor", "set": cset, "label": label, "aliases": [label.lower()[:40]], "params": params, "expr": expr,
         "returns": returns, "version": 1, "status": "published", "description_nl": NOTE + desc, "test_cases": []}
    old = CH / f"{cid}.json"
    if old.exists():
        o = json.loads(old.read_text(encoding="utf-8"))
        c["version"] = o.get("version", 1) + (0 if (o.get("params"), o.get("expr")) == (params, expr) else 1)
    write(c)
    for args, want in cases:                     # every case: the answer worked out, checked against what was said by hand
        got = run_chip(cid, args)
        if isinstance(want, dict) and isinstance(got, dict):
            bad = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
        else:
            bad = {"value": (got, want)} if got != want else {}
        assert not bad, (cid, args, bad)
        c["test_cases"].append({"args": args, "expect_value": got})
    write(c)
    print("wrote", cid, f"({len(c['test_cases'])} cases)")


def save(c, note):
    """An existing chip changed: version + 1, the note once, every test case re-answered (the no-args one is what it now answers)."""
    before = load(c["chip_id"])
    a, b = dict(before), dict(c)
    for x in (a, b):
        for k in ("version", "description_nl", "test_cases"):
            x.pop(k, None)
    if a == b:
        print("same", c["chip_id"])
        return
    c["version"] = before.get("version", 1) + 1
    if note and NOTE + note not in c.get("description_nl", ""):
        c["description_nl"] = c.get("description_nl", "") + " " + NOTE + note
    write(c)
    for t in c["test_cases"]:
        got = run_chip(c["chip_id"], t["args"])
        if not t.get("args"):
            t["expect_value"] = got
        else:
            assert got == t["expect_value"], (c["chip_id"], t["args"], got, t["expect_value"])
    write(c)
    print("wrote", c["chip_id"], "v", c["version"])


def knob(c, name, default, label):
    for p in c["params"]:
        if p["name"] == name:
            p["default"] = default
            break
    else:
        c["params"].append(P(name, default, label))
    if c["expr"].get("vop") == "record":
        c["expr"]["fields"][name] = "$" + name


# =================================================================================================================================
# company.settings - every knob
# =================================================================================================================================
BANDS = [{"above": 10000000, "rate": 7}, {"above": 100000000, "rate": 12}]
FLAT10 = [{"above": 0, "rate": 10}]
RATES_2627 = {
    "turnover_limit": 4000000000, "turnover_py": "2023-24", "base_low": 25, "base_high": 30, "bands": BANDS,
    "options": {"115BA": {"rate": 25, "steps": BANDS, "mat": True, "addl_dep": False, "via": "all"},
                "115BAA": {"rate": 22, "steps": FLAT10, "mat": False, "addl_dep": False, "via": "baa"},
                "115BAB": {"rate": 15, "other_rate": 22, "steps": FLAT10, "mat": False, "addl_dep": False, "via": "baa", "split_business": True}},
    "mat_rate": 15, "cess_pct": 4, "round_to": 10,
    "cg": {"stcg_111a": 20, "ltcg_112a": 12.5, "ltcg_112": 12.5, "exempt_112a": 125000},
    "source": SRC_RATES}
VIA_SETS = {"all": ["80G", "80GGA", "80GGB", "80GGC", "80IA", "80IAB", "80IAC", "80IB", "80JJAA", "80LA", "80M"],
            "baa": ["80JJAA", "80M", "80LA(1A)"]}
DEP_BLOCKS = [
    {"id": "pm15", "label": "Plant & machinery @ 15%", "rate": 15, "addl": True, "path": "ScheduleDPM.PlantMachinery.Rate15", "sum": "pm15"},
    {"id": "pm30", "label": "Plant & machinery @ 30%", "rate": 30, "addl": True, "path": "ScheduleDPM.PlantMachinery.Rate30", "sum": "pm30"},
    {"id": "pm40", "label": "Plant & machinery @ 40% (computers, software)", "rate": 40, "addl": False, "path": "ScheduleDPM.PlantMachinery.Rate40", "sum": "pm40"},
    {"id": "pm45", "label": "Plant & machinery @ 45%", "rate": 45, "addl": False, "path": "ScheduleDPM.PlantMachinery.Rate45", "sum": "pm45"},
    {"id": "bldg5", "label": "Building (residential) @ 5%", "rate": 5, "addl": False, "path": "ScheduleDOA.Building.Rate5", "sum": "b5"},
    {"id": "bldg10", "label": "Building (other) @ 10%", "rate": 10, "addl": False, "path": "ScheduleDOA.Building.Rate10", "sum": "b10"},
    {"id": "bldg40", "label": "Building (temporary) @ 40%", "rate": 40, "addl": False, "path": "ScheduleDOA.Building.Rate40", "sum": "b40"},
    {"id": "furn10", "label": "Furniture & fittings @ 10%", "rate": 10, "addl": False, "path": "ScheduleDOA.FurnitureFittings.Rate10", "sum": "furn"},
    {"id": "intang25", "label": "Intangible assets @ 25%", "rate": 25, "addl": False, "path": "ScheduleDOA.IntangibleAssets.Rate25", "sum": "intang"},
    {"id": "ships20", "label": "Ships @ 20%", "rate": 20, "addl": False, "path": "ScheduleDOA.Ships.Rate20", "sum": "ships"}]
DEP_COLUMNS = {"opening": "(?i)opening|w\\.?\\s?d\\.?\\s?v.*(1st|first|01|as on 1)|as on 0?1[./-]0?4",
               "new_more": "(?i)new.*(180 days or more|more than 180|before)|eligible.*(more|before)",
               "new_less": "(?i)new.*(less than 180|after)|eligible.*(less|after)",
               "more": "(?i)180 days or more|more than 180|>=? ?180|before 0?3[./ -]?10|up ?to 0?2[./ -]?10|first half",
               "less": "(?i)less than 180|< ?180|after 0?2[./ -]?10|on or after 0?3[./ -]?10|second half",
               "sales": "(?i)sale|deletion|realis|disposal",
               "addl_bf": "(?i)additional.*(b/?f|brought|balance)"}
BP_ITEMS = {   # an SF Ref 'ITR6 BP <item>': its sign in business income and where it sits in Schedule BP
    "profit": {"sign": 1, "key": "ProfBfrTaxPL", "label": "Profit before tax as per the P&L", "cite": "Schedule BP line 1"},
    "tax": {"sign": 1, "key": "ProfBfrTaxPL", "label": "Income-tax provision added back (when the statement starts after tax)", "cite": "s.40(a)(ii)"},
    "book_dep": {"sign": 1, "key": "DepreciationDebPLCosAct", "label": "Depreciation as per the books (Companies Act)", "cite": "s.32 replaces it"},
    "it_dep": {"sign": -1, "key": "DepreciationAllowUs32_1_ii", "label": "Depreciation u/s 32 typed (when no Schedule DEP rows)", "cite": "s.32(1)(ii)"},
    "csr": {"sign": 1, "key": "AmtDebPLDisallowUs37", "label": "CSR expenditure (s.135 Companies Act) - not a business expense", "cite": "Explanation 2 to s.37(1)"},
    "s37": {"sign": 1, "key": "AmtDebPLDisallowUs37", "label": "Other expenditure disallowed u/s 37 (penalties, personal)", "cite": "s.37(1)"},
    "s36": {"sign": 1, "key": "AmtDebPLDisallowUs36", "label": "Disallowed u/s 36", "cite": "s.36"},
    "s40": {"sign": 1, "key": "AmtDebPLDisallowUs40", "label": "Disallowed u/s 40 (TDS not deducted / paid)", "cite": "s.40(a)(i)/(ia)"},
    "s40a": {"sign": 1, "key": "AmtDebPLDisallowUs40A", "label": "Disallowed u/s 40A (40A(2)(b), 40A(3) cash, 40A(7))", "cite": "s.40A"},
    "s43b": {"sign": 1, "key": "AmtDebPLDisallowUs43B", "label": "Unpaid by the due date - s.43B (taxes, PF employer share, bonus, bank interest, leave, MSME dues)", "cite": "s.43B incl. 43B(h)"},
    "other_add": {"sign": 1, "key": "OthItemDisallowUs28To44DA", "label": "Other additions u/s 28-44DA", "cite": "Schedule BP"},
    "dividend": {"sign": -1, "key": "IncRecCredPLOthHeadDtls.Dividend", "label": "Dividend credited to the P&L - taxed under other sources", "cite": "s.56(2)(i)"},
    "os_income": {"sign": -1, "key": "IncRecCredPLOthHeadDtls.OtherThanDividend", "label": "Other income credited to the P&L - taxed under other sources (interest ...)", "cite": "s.56"},
    "cg_income": {"sign": -1, "key": "IncRecCredPLOthHeadDtls.CapitalGains", "label": "Capital gains credited to the P&L - taxed under capital gains", "cite": "s.45"},
    "hp_income": {"sign": -1, "key": "IncRecCredPLOthHeadDtls.HouseProperty", "label": "Rent credited to the P&L - taxed under house property", "cite": "s.22"},
    "exempt": {"sign": -1, "key": "IncCredPL.OthExempInc", "label": "Exempt income credited to the P&L", "cite": "s.10"},
    "s43b_paid": {"sign": -1, "key": "AmtDisallUs43BNowAllow", "label": "Disallowed u/s 43B earlier, paid this year", "cite": "s.43B"},
    "s40_paid": {"sign": -1, "key": "AmtDisallUs40NowAllow", "label": "Disallowed u/s 40(a) earlier, TDS paid this year", "cite": "s.40(a)(ia) proviso"},
    "other_less": {"sign": -1, "key": "AnyOthAmtAllDeduct", "label": "Any other amount allowable as a deduction", "cite": "Schedule BP"}}
MAT_ITEMS = {  # an SF Ref 'ITR6 MAT <item>': the book profit u/s 115JB (Form 29B) and where it sits in Schedule MAT
    "pat": {"sign": 1, "key": "ProfAfterTaxPLAcnt", "label": "Profit after tax as per the P&L (Schedule III)", "cite": "s.115JB(2)"},
    "add_tax": {"sign": 1, "key": "Additions.ITPaidInclDefTax", "label": "Income-tax paid or payable incl. deferred tax", "cite": "Expl. 1(a) to s.115JB(2)"},
    "add_reserve": {"sign": 1, "key": "Additions.ResvrNo33AC", "label": "Amounts carried to a reserve", "cite": "Expl. 1(b)"},
    "add_provision": {"sign": 1, "key": "Additions.ProvUncertainLiab", "label": "Provision for an unascertained liability", "cite": "Expl. 1(c)"},
    "add_dividend": {"sign": 1, "key": "Additions.DividendPaidOrProposed", "label": "Dividend paid or proposed", "cite": "Expl. 1(e)"},
    "add_exempt_exp": {"sign": 1, "key": "Additions.ExpendExempIncUs10s", "label": "Expenditure on exempt income", "cite": "Expl. 1(f)"},
    "add_reval_dep": {"sign": 1, "key": "Additions.DepreciatAttribToRevalAsset", "label": "Depreciation on revaluation", "cite": "Expl. 1(i)"},
    "add_other": {"sign": 1, "key": "Additions.Others", "label": "Other additions", "cite": "Expl. 1"},
    "less_reserve": {"sign": -1, "key": "Deducts.AmtWithdrawFromResvrIfCredPL", "label": "Withdrawn from a reserve and credited to the P&L", "cite": "Expl. 1(i)"},
    "less_exempt": {"sign": -1, "key": "Deducts.IncExempIncUs10s", "label": "Exempt income credited to the P&L", "cite": "Expl. 1(ii)"},
    "less_bf": {"sign": -1, "key": "Deducts.UnAbsorbedDepreciat", "label": "Lower of brought-forward loss or unabsorbed depreciation (as per the books)", "cite": "Expl. 1(iii)"},
    "less_other": {"sign": -1, "key": "Deducts.Others", "label": "Other deductions", "cite": "Expl. 1"}}
OS_ITEMS = {"dividend": {"key": "DividendGross"}, "interest": {"key": "IntrstFrmOthers"}, "deposit": {"key": "IntrstFrmTermDeposit"},
            "refund": {"key": "IntrstFrmIncmTaxRefund"}, "rent": {"key": "RentFromMachPlantBldgs"}, "other": {"key": "AnyOtherIncome"}}
CG_ITEMS = {"stcg_111a": {"kind": "st", "special": True, "si": "1A", "label": "STCG u/s 111A (listed shares, STT paid) @ 20%"},
            "stcg": {"kind": "st", "special": False, "label": "STCG at the normal rate"},
            "ltcg_112a": {"kind": "lt", "special": True, "si": "2A", "label": "LTCG u/s 112A @ 12.5% above 1.25 lakh"},
            "ltcg_112": {"kind": "lt", "special": True, "si": "21", "label": "LTCG u/s 112 @ 12.5%"}}
G80_CATS = {"100": {"label": "100% without a limit (PM CARES, PM National Relief Fund ...)", "path": "Don100Percent"},
            "50": {"label": "50% without a limit (PM Drought Relief, Jawaharlal Nehru Memorial Fund ...)", "path": "Don50PercentNoApprReqd"},
            "100q": {"label": "100% within the qualifying limit (Govt / approved for family planning ...)", "path": "Don100PercentApprReqd"},
            "50q": {"label": "50% within the qualifying limit (approved trusts and institutions u/s 80G(5))", "path": "Don50PercentApprReqd"},
            "csr_kosh": {"label": "CSR contribution to the Swachh Bharat Kosh / Clean Ganga Fund - not deductible", "path": ""}}
CFL_PATHS = {"2018-19": "LossCFFromPrevYrToAY", "2019-20": "LossCFCurrentAssmntYear", "2020-21": "LossCFCurrentAssmntYear2021",
             "2021-22": "LossCFCurrentAssmntYear2022", "2022-23": "LossCFCurrentAssmntYear2023", "2023-24": "LossCFCurrentAssmntYear2024",
             "2024-25": "LossCFCurrentAssmntYear2025", "2025-26": "LossCFCurrentAssmntYear2026"}
SETTINGS = [
    P("kinds", [{"id": "private", "label": "Private limited", "code": "7"}, {"id": "public", "label": "Public limited (unlisted)", "code": "6"},
                {"id": "listed", "label": "Public limited (listed)", "code": "6", "listed": True}, {"id": "opc", "label": "One person company", "code": "7"}],
      "kinds of domestic company (the code is ITR-6 StatusOrCompanyType: 6 public, 7 private)"),
    P("options", [{"id": "normal", "label": "Normal provisions (25% / 30%, MAT applies)"}, {"id": "115BA", "label": "s.115BA (25%, manufacturing, opted earlier)"},
                  {"id": "115BAA", "label": "s.115BAA (22% + 10% surcharge, no MAT)"}, {"id": "115BAB", "label": "s.115BAB (15% new manufacturing + 10% surcharge, no MAT)"}],
      "the tax options a domestic company may be under"),
    P("designations", [{"id": "MD", "label": "Managing director"}, {"id": "DIR", "label": "Director"}, {"id": "CFO", "label": "CFO"}, {"id": "SEC", "label": "Company secretary"}],
      "key persons' designations (ITR-6 KeyPersons codes)"),
    P("signer_codes", {"MD": "MD", "DIR": "DR"}, "the verification capacity of a signing key person"),
    P("cin_pattern", "^[LU][0-9]{5}[A-Z]{2}[0-9]{4}(PTC|PLC|OPC|NPL|ULL|ULT|FTC|GOI|SGC|GAT|GAP)[0-9]{6}$", "CIN shape (MCA: 21 characters)"),
    P("din_pattern", "^[0-9]{8}$", "DIN shape (8 digits)"),
    P("default_ay", "2026-27", "the AY whose rates are verified; another AY uses them with a warning"),
    P("rates_by_ay", {"2026-27": RATES_2627}, "a company's rates per AY (normal by turnover, options, surcharge, MAT, cess, special-rate gains)"),
    P("via_sets", VIA_SETS, "Chapter VI-A sections a company may claim under each set (115BAA / 115BAB: only 80JJAA, 80M, 80LA(1A))"),
    P("dep_blocks", DEP_BLOCKS, "blocks of assets (Appendix I, rule 5) and their place in Schedule DPM / DOA; addl: additional depreciation 32(1)(iia) on new P&M"),
    P("dep_columns", DEP_COLUMNS, "a fixed-asset schedule's column titles -> opening WDV, additions 180 days or more / less, sales, new P&M, additional depreciation b/f"),
    P("addl_dep_rate", 20, "additional depreciation on new plant and machinery, s.32(1)(iia) (half when used under 180 days, the balance next year)"),
    P("bp_items", BP_ITEMS, "SF Ref ITR6 BP <item>: the company's computation statement, line by line"),
    P("mat_items", MAT_ITEMS, "SF Ref ITR6 MAT <item>: the book profit u/s 115JB (Form 29B)"),
    P("os_items", OS_ITEMS, "SF Ref ITR6 OS <item>: other sources by kind (Schedule OS)"),
    P("cg_items", CG_ITEMS, "SF Ref ITR6 CG <item>: capital gains by rate (si: the Schedule SI code)"),
    P("g80_cats", G80_CATS, "SF Ref ITR6 80G <category>: donations by category (Schedule 80G)"),
    P("g80_limit_pct", 10, "the qualifying limit: 10% of the adjusted gross total income, s.80G(4)"),
    P("d80m_months", 1, "s.80M: dividends distributed at least one month before the due date of the return"),
    P("hp_setoff_cap", 200000, "house-property loss set off against other heads at most, s.71(3A)"),
    P("cyla_order", ["os", "hp", "stcg", "stcg_111a", "ltcg_112", "ltcg_112a"], "a business loss is set off against these incomes in this order (normal-rate income first)"),
    P("st_loss_order", ["stcg", "stcg_111a", "ltcg_112", "ltcg_112a"], "a short-term capital loss against these gains, s.74"),
    P("lt_loss_order", ["ltcg_112", "ltcg_112a"], "a long-term capital loss against long-term gains only, s.74"),
    P("turnover_items", ["sales", "services", "professional_receipts"], "the P&L items (SF Ref ITR6 PL <item>) that are the year's turnover (Part A-GEN band)"),
    P("cfl_paths", CFL_PATHS, "Schedule CFL's block for each earlier AY"),
    P("loss_years", {"business": 8, "mat": 15}, "a business loss is carried 8 AYs (s.72(3)); MAT credit 15 AYs (s.115JAA(3A)); unabsorbed depreciation without limit (s.32(2))"),
    P("s79_pct", 51, "s.79: a closely held company keeps its losses only if 51% of the voting power stays with the same holders"),
    P("sh_min_pct", 1, "Schedule SH-1: shareholders of an unlisted company holding 1% or more"),
    P("holder_min_pct", 10, "Part A-GEN: persons holding 10% or more of the voting power"),
    P("sources", {"rates": SRC_RATES,
                  "schema": "ITR-6 JSON schema V1.0 for AY 2026-27 and validation rules V1.0 (incometax.gov.in > Downloads, 04-Aug-2026)",
                  "due": "s.139(1) Explanation 2(a): a company files by 31 October; 30 November with a Form 3CEB (s.92E)",
                  "mat": "s.115JB (15% of book profit; not for 115BAA / 115BAB - s.115JB(5A)); credit s.115JAA, 15 AYs. The Finance Bill 2026 changes MAT only from tax year 2026-27 (Income-tax Act 2025)",
                  "losses": "s.70-80: CYLA s.71 (house property loss up to 2 lakh, s.71(3A)), business loss 8 AYs s.72, unabsorbed depreciation s.32(2), s.79 (51%), return in time s.80 / s.139(3)",
                  "dep": "s.32 and rule 5 Appendix I; half rate under 180 days (2nd proviso to s.32(1)); additional 20% s.32(1)(iia); s.50 gain on a block",
                  "deductions": "s.80G (CSR proviso to 80G(2)(iiihk)/(iiihl)), s.80M, s.115BAA(2)(ii) / 115BAB(2)(ii): only 80JJAA, 80M, 80LA(1A)",
                  "csr": "Explanation 2 to s.37(1): CSR spent under s.135 of the Companies Act is not a business expense",
                  "s43b": "s.43B incl. 43B(h) (MSME dues beyond the MSMED Act 45 days)"},
      "where each rule comes from"),
]
chip("company.settings", "Company: rates, options, blocks and SF Ref items (ITR-6)", SETTINGS, record_of(SETTINGS),
     "Every knob a company's return uses (ITR-6, AY 2026-27): the kinds of company and options (normal, 115BA, 115BAA, 115BAB), "
     "the AY's rates (25% when the turnover of the PY 2023-24 is within 400 crore, else 30%; surcharge 7% above 1 crore, 12% above 10 crore; "
     "115BAA 22% / 115BAB 15% with a flat 10% surcharge; MAT 15%; cess 4%; 111A 20%, 112A / 112 12.5%, 112A exempt up to 1.25 lakh), "
     "the depreciation blocks, the SF Ref items of the computation statement, MAT, other sources, capital gains and 80G, and the sources.",
     [({}, {"default_ay": "2026-27", "addl_dep_rate": 20, "hp_setoff_cap": 200000})])
S = CHIP("company.settings")

# =================================================================================================================================
# company.problem - a company's master data
# =================================================================================================================================
PR = [P("cin", "", "CIN"), P("cin_pattern", "", "CIN shape (from company.settings)"), P("kind", "", "kind of company"),
      P("kinds", [], "the kinds' ids"), P("option", "normal", "tax option"), P("options", [], "the options' ids"),
      P("manufacturing", False, "manufacturing company"), P("bad_din", False, "a director's DIN is not 8 digits"),
      P("bad_share", False, "a shareholding % is not 0-100"), P("share_total", 0, "total of the shareholdings typed"),
      P("incorporated", "", "date of incorporation (YYYY-MM-DD)")]
chip("company.problem", "Company: what is wrong in a company's master data (empty = nothing)", PR, CHOOSE([
    (NOT(IN("$kind", "$kinds")), "co_bad_kind"),
    (NOT(IN("$option", "$options")), "co_bad_option"),
    (ALL(GT(V("text_length", text="$cin"), 0), NOT(V("matches", text="$cin", pattern="$cin_pattern"))), "co_bad_cin"),
    (ALL(GT(V("text_length", text="$incorporated"), 0), NOT(V("matches", text="$incorporated", pattern="^[12][0-9]{3}-[01][0-9]-[0-3][0-9]$"))), "co_bad_date"),
    (EQ("$bad_din", True), "co_bad_din"),
    (EQ("$bad_share", True), "co_bad_share"),
    (GT("$share_total", 100.0001), "co_share_over"),
    (ALL(EQ("$option", "115BAB"), NOT(EQ("$manufacturing", True))), "co_bab_manufacturing"),
], ""), "The company part of a client: kind and option from the lists, the CIN in the MCA's 21-character shape, an ISO date of incorporation, "
   "8-digit DINs, shareholdings 0-100% and not over 100% together, and s.115BAB only for a manufacturing company (s.115BAB(2)).",
    [({"kind": "private", "kinds": ["private"], "option": "normal", "options": ["normal"]}, ""),
     ({"kind": "x", "kinds": ["private"]}, "co_bad_kind"),
     ({"kind": "private", "kinds": ["private"], "option": "normal", "options": ["normal"], "cin": "U12345TG2015PTC000001", "cin_pattern": "^[LU][0-9]{5}[A-Z]{2}[0-9]{4}(PTC|PLC)[0-9]{6}$"}, ""),
     ({"kind": "private", "kinds": ["private"], "option": "normal", "options": ["normal"], "cin": "U1234", "cin_pattern": "^[LU][0-9]{5}[A-Z]{2}[0-9]{4}(PTC|PLC)[0-9]{6}$"}, "co_bad_cin"),
     ({"kind": "private", "kinds": ["private"], "option": "normal", "options": ["normal"], "share_total": 120}, "co_share_over"),
     ({"kind": "private", "kinds": ["private"], "option": "115BAB", "options": ["normal", "115BAB"]}, "co_bab_manufacturing"),
     ({"kind": "private", "kinds": ["private"], "option": "115BAB", "options": ["normal", "115BAB"], "manufacturing": True}, "")],
    returns="text")

# =================================================================================================================================
# company.rate - what the option means
# =================================================================================================================================
RP = [P("option", "normal", "tax option"), P("turnover", 0, "total turnover / gross receipts of the PY named by the rates (rupees)"),
      P("rates", RATES_2627, "the AY's rates (company.settings rates_by_ay)"), P("via_sets", VIA_SETS, "Chapter VI-A sets (company.settings)")]
OPT = GET("$rates", V("template", text="options.{o}", values=V("record", fields={"o": "$option"})))
NORMAL_RATE = CHOOSE([(ALL(GT("$turnover", 0), LE("$turnover", GET("$rates", "turnover_limit"))), GET("$rates", "base_low"))], GET("$rates", "base_high"))
chip("company.rate", "Company: the rate, surcharge and deductions an option brings", RP, V("record", fields={
    "rate": V("coalesce", values=[GET(OPT, "rate"), NORMAL_RATE]),
    "other_rate": V("coalesce", values=[GET(OPT, "other_rate"), GET(OPT, "rate"), NORMAL_RATE]),
    "steps": V("coalesce", values=[GET(OPT, "steps"), GET("$rates", "bands")]),
    "flat": YES(EQ(GET(V("coalesce", values=[GET(OPT, "steps"), GET("$rates", "bands")]), "0.above"), 0)),
    "mat": V("coalesce", values=[GET(OPT, "mat"), True]),
    "addl_dep": V("coalesce", values=[GET(OPT, "addl_dep"), True]),
    "split_business": V("coalesce", values=[GET(OPT, "split_business"), False]),
    "via": GET("$via_sets", V("coalesce", values=[GET(OPT, "via"), "all"])),
    "low_turnover": YES(ALL(GT("$turnover", 0), LE("$turnover", GET("$rates", "turnover_limit")))),
    "why": CHOOSE([(IN("$option", ["115BA", "115BAA", "115BAB"]), V("template", text="why_{o}", values=V("record", fields={"o": "$option"}))),
                   (LE("$turnover", 0), "why_turnover_missing"),
                   (LE("$turnover", GET("$rates", "turnover_limit")), "why_low")], "why_high"),
}), "Normal provisions: 25% when the total turnover or gross receipts of the PY 2023-24 did not exceed 400 crore, else 30% "
    "(Finance Act 2026 Part I-A Para E) - a turnover not typed counts as above the limit, and the screen says so; surcharge 7% above 1 crore, 12% above 10 crore, "
    "MAT applies, additional depreciation and every Chapter VI-A deduction allowed. s.115BA 25% (bands, MAT, no additional depreciation). "
    "s.115BAA 22% and s.115BAB 15% on the manufacturing business (22% on other income), each with a flat 10% surcharge on any income, no MAT "
    "(s.115JB(5A)), no additional depreciation, and only 80JJAA / 80M / 80LA(1A) of Chapter VI-A. " + SRC_RATES,
    [({"option": "normal", "turnover": 3000000000}, {"rate": 25, "mat": True, "flat": False, "why": "why_low", "addl_dep": True}),
     ({"option": "normal", "turnover": 4000000000}, {"rate": 25, "why": "why_low"}),
     ({"option": "normal", "turnover": 4000000001}, {"rate": 30, "why": "why_high"}),
     ({"option": "normal", "turnover": 0}, {"rate": 30, "why": "why_turnover_missing"}),
     ({"option": "115BAA", "turnover": 100000}, {"rate": 22, "flat": True, "mat": False, "addl_dep": False, "via": ["80JJAA", "80M", "80LA(1A)"], "why": "why_115BAA", "low_turnover": True}),
     ({"option": "115BAB"}, {"rate": 15, "other_rate": 22, "split_business": True, "mat": False, "flat": True}),
     ({"option": "115BA", "turnover": 9000000000}, {"rate": 25, "mat": True, "addl_dep": False, "flat": False})])

# =================================================================================================================================
# company.tax - tax on the total income (two stages, so no field repeats another)
# =================================================================================================================================
TP = [P("main", 0, "income at the option's rate (all normal-rate income; 115BAB: the manufacturing business)"),
      P("other", 0, "income at the other rate (115BAB: income other than the business)"),
      P("stcg_111a", 0, "STCG u/s 111A"), P("ltcg_112a", 0, "LTCG u/s 112A (before the exemption)"), P("ltcg_112", 0, "LTCG u/s 112"),
      P("rate", 25, "the option's rate %"), P("other_rate", 25, "the rate on 'other' %"), P("steps", BANDS, "surcharge steps"),
      P("cg", RATES_2627["cg"], "special rates (company.settings rates_by_ay cg)"), P("cess_pct", 4, "cess %"), P("round_to", 10, "tax rounded to (s.288B)")]
A = {p["name"]: "$" + p["name"] for p in TP}
X112A = MX(0, SUB("$ltcg_112a", GET("$cg", "exempt_112a")))
S1 = V("record", fields={
    "income": ADD("$main", "$other", "$stcg_111a", "$ltcg_112a", "$ltcg_112"),
    "at_normal": ADD(PCT("$main", "$rate"), PCT("$other", "$other_rate")),
    "on_111a": PCT("$stcg_111a", GET("$cg", "stcg_111a")), "on_112a": PCT(X112A, GET("$cg", "ltcg_112a")), "on_112": PCT("$ltcg_112", GET("$cg", "ltcg_112")),
    "at_special": ADD(PCT("$stcg_111a", GET("$cg", "stcg_111a")), PCT(X112A, GET("$cg", "ltcg_112a")), PCT("$ltcg_112", GET("$cg", "ltcg_112"))),
    "rate_on": OR0(V("step_rate", amount=ADD("$main", "$other", "$stcg_111a", "$ltcg_112a", "$ltcg_112"), steps="$steps")),
    "threshold": OR0(V("step_rate", amount=ADD("$main", "$other", "$stcg_111a", "$ltcg_112a", "$ltcg_112"), steps="$steps", field="above"))})
chip("company.tax_s1", "Company: the tax, stage 1 (income, tax at normal and special rates, surcharge rate, band edge)", TP, S1,
     "Part of chip company.tax: the income, the tax at the option's rate(s), at 111A / 112A (above the exemption) / 112, the surcharge rate for this income and the band's lower edge.",
     [({"main": 50000000}, {"income": 50000000, "at_normal": 12500000.0, "rate_on": 7, "threshold": 10000000})])
B = CHIP("company.tax_s1", A)
TP2 = TP + [P("b", {}, "stage 1 (chip company.tax_s1)")]
TAXSUM = ADD(GET("$b", "at_normal"), GET("$b", "at_special"))
SUR = PCT(TAXSUM, GET("$b", "rate_on"))
TAX_AT_T = MX(0, SUB(TAXSUM, PCT(SUB(GET("$b", "income"), GET("$b", "threshold")), "$rate")))     # the income above the edge at the main rate
SUR_AT_T = PCT(TAX_AT_T, OR0(V("step_rate", amount=GET("$b", "threshold"), steps="$steps")))
RELIEF = CHOOSE([(GT(GET("$b", "threshold"), 0), RND(MX(0, SUB(ADD(TAXSUM, SUR), ADD(TAX_AT_T, SUR_AT_T, SUB(GET("$b", "income"), GET("$b", "threshold"))))), 2))], 0)
CESS = RND(PCT(SUB(ADD(TAXSUM, SUR), RELIEF), "$cess_pct"), 2)
chip("company.tax_s2", "Company: the tax, stage 2 (surcharge, marginal relief, cess, total)", TP2, V("record", fields={
    "income": GET("$b", "income"), "at_normal": RND(GET("$b", "at_normal"), 2), "at_special": RND(GET("$b", "at_special"), 2),
    "on_111a": RND(GET("$b", "on_111a"), 2), "on_112a": RND(GET("$b", "on_112a"), 2), "on_112": RND(GET("$b", "on_112"), 2),
    "tax": RND(TAXSUM, 2), "surcharge_rate": GET("$b", "rate_on"), "surcharge": RND(SUR, 2), "relief": RELIEF, "cess": CESS,
    "total": MUL(RND(DIV(ADD(SUB(ADD(TAXSUM, SUR), RELIEF), CESS), "$round_to")), "$round_to")}),
    "Part of chip company.tax: surcharge on the whole tax; marginal relief - tax and surcharge above a band's edge never more than the income above it "
    "(the part above the edge taken at the main rate); cess on tax and surcharge; the total rounded to the nearest 10 (s.288B).",
    [({"main": 50000000, "b": {"income": 50000000, "at_normal": 12500000, "at_special": 0, "on_111a": 0, "on_112a": 0, "on_112": 0, "rate_on": 7, "threshold": 10000000}},
      {"total": 13910000})])
chip("company.tax", "Company: tax on total income (option rate, special rates, surcharge with marginal relief, cess)", TP,
     CHIP("company.tax_s2", A | {"b": B}),
     "A domestic company's tax for AY 2026-27: income at the option's rate (25% / 30% normal, 115BA 25%, 115BAA 22%, 115BAB 15% on the manufacturing "
     "business and 22% on the rest), STCG u/s 111A at 20%, LTCG u/s 112A at 12.5% above 1.25 lakh and u/s 112 at 12.5%; surcharge 7% / 12% above 1 / 10 crore "
     "with marginal relief, or a flat 10% under 115BAA / 115BAB; 4% Health and Education Cess; rounded to 10. " + SRC_RATES,
     [({"main": 50000000}, {"tax": 12500000.0, "surcharge": 875000.0, "relief": 0, "cess": 535000.0, "total": 13910000}),       # 25% x 1.07 x 1.04
      ({"main": 10050000}, {"tax": 2512500.0, "surcharge": 175875.0, "relief": 138375.0, "total": 2652000}),                    # = compute.tax's answer
      ({"main": 100500000, "rate": 30}, {"tax": 30150000.0, "surcharge_rate": 12, "relief": 1168000.0, "total": 33904000}),
      ({"main": 2000000, "rate": 22, "steps": FLAT10}, {"tax": 440000.0, "surcharge": 44000.0, "relief": 0, "cess": 19360.0, "total": 503360}),   # 25.168%
      ({"main": 30000000, "other": 1000000, "rate": 15, "other_rate": 22, "steps": FLAT10}, {"tax": 4720000.0, "surcharge": 472000.0, "total": 5399680}),
      ({"main": 5000000, "stcg_111a": 1000000, "ltcg_112a": 1125000, "ltcg_112": 400000}, {"at_normal": 1250000.0, "at_special": 375000.0, "tax": 1625000.0, "surcharge": 0.0, "total": 1690000}),
      ({"main": 0}, {"tax": 0, "total": 0})])

# =================================================================================================================================
# company.mat - s.115JB against the normal tax, and the s.115JAA credit
# =================================================================================================================================
MP = [P("normal_total", 0, "tax on total income under the normal provisions, incl. surcharge and cess (company.tax total)"),
      P("book_profit", 0, "book profit u/s 115JB"), P("applies", True, "MAT applies (company.rate mat)"),
      P("mat_rate", 15, "MAT %"), P("steps", BANDS, "surcharge steps on MAT"), P("cess_pct", 4, "cess %"), P("round_to", 10, "rounded to"),
      P("credit_available", 0, "MAT credit brought forward and still within 15 AYs")]
MATTAX = CHIP("compute.tax", {"income": MX(0, "$book_profit"), "status": "company", "slabs": [{"upto": None, "rate": "$mat_rate"}], "steps": "$steps",
                              "cess_pct": "$cess_pct", "round_to": "$round_to", "rebate_statuses": []})
MATT = CHOOSE([(EQ("$applies", True), GET(MATTAX, "total"))], 0)
PAYS = ALL(EQ("$applies", True), GT(MATT, "$normal_total"))
ROOM = CHOOSE([(ALL(EQ("$applies", True), GT("$normal_total", MATT)), SUB("$normal_total", MATT))], 0)
chip("company.mat", "Company: MAT u/s 115JB and the MAT credit u/s 115JAA", MP, V("record", fields={
    "mat": MATT, "parts": CHOOSE([(EQ("$applies", True), MATTAX)], {}),
    "pays_mat": YES(PAYS), "gross": CHOOSE([(PAYS, MATT)], "$normal_total"),
    "credit_new": CHOOSE([(PAYS, SUB(MATT, "$normal_total"))], 0),
    "credit_room": ROOM, "credit_used": MN("$credit_available", ROOM),
    "net": SUB(CHOOSE([(PAYS, MATT)], "$normal_total"), MN("$credit_available", ROOM))}),
    "s.115JB: when the tax on total income is less than 15% of the book profit (with surcharge 7% / 12% above 1 / 10 crore of book profit, marginal relief and 4% cess), "
    "that MAT is the tax; the excess over the normal tax becomes a credit (s.115JAA(1A)), carried 15 AYs. In a year the normal tax is more than MAT, credit is set off "
    "up to the difference (s.115JAA(4)). A company under 115BAA / 115BAB pays no MAT (s.115JB(5A)) and cannot use a credit (CBDT Circular 29/2019).",
    [({"normal_total": 1000000, "book_profit": 20000000}, {"mat": 3338400, "pays_mat": True, "gross": 3338400, "credit_new": 2338400, "credit_used": 0, "net": 3338400}),
     ({"normal_total": 5000000, "book_profit": 20000000, "credit_available": 3000000}, {"mat": 3338400, "pays_mat": False, "credit_room": 1661600, "credit_used": 1661600, "net": 3338400}),
     ({"normal_total": 5000000, "book_profit": 20000000, "credit_available": 500000}, {"credit_used": 500000, "net": 4500000}),
     ({"normal_total": 1000000, "book_profit": 20000000, "applies": False, "credit_available": 900000}, {"mat": 0, "pays_mat": False, "credit_used": 0, "net": 1000000}),
     ({"normal_total": 0, "book_profit": -500000}, {"mat": 0, "gross": 0, "net": 0})])

# =================================================================================================================================
# company.dep_block - one block of assets
# =================================================================================================================================
DP = [P("opening", 0, "WDV on the first day of the year"), P("more", 0, "additions put to use 180 days or more"), P("less", 0, "additions put to use less than 180 days"),
      P("sales", 0, "moneys received on sale / transfer during the year"), P("rate", 15, "the block's rate %"),
      P("addl_ok", False, "additional depreciation allowed (the block allows it, the option allows it, a manufacturing company)"),
      P("addl_rate", 20, "additional depreciation % (s.32(1)(iia))"), P("new_more", 0, "of the additions: new P&M used 180 days or more"),
      P("new_less", 0, "of the additions: new P&M used less than 180 days"), P("addl_bf", 0, "additional depreciation brought forward (the half held back last year)")]
FULL = MX(0, SUB(ADD("$opening", "$more"), "$sales"))
EXCESS = MX(0, SUB("$sales", ADD("$opening", "$more")))
HALF = MX(0, SUB("$less", EXCESS))
DFULL = RND(PCT(FULL, "$rate"))
DHALF = RND(PCT(HALF, DIV("$rate", 2)))
ADDL = CHOOSE([(EQ("$addl_ok", True), ADD(RND(PCT("$new_more", "$addl_rate")), RND(PCT("$new_less", DIV("$addl_rate", 2))), "$addl_bf"))], 0)
chip("company.dep_block", "Company: depreciation on one block of assets (WDV, half rate, additional depreciation, s.50)", DP, V("record", fields={
    "full_base": FULL, "real_full": MN("$sales", ADD("$opening", "$more")), "half_base": HALF, "real_half": MN(EXCESS, "$less"),
    "dep_full": DFULL, "dep_half": DHALF,
    "addl_more": CHOOSE([(EQ("$addl_ok", True), RND(PCT("$new_more", "$addl_rate")))], 0),
    "addl_less": CHOOSE([(EQ("$addl_ok", True), RND(PCT("$new_less", DIV("$addl_rate", 2))))], 0),
    "addl_bf": CHOOSE([(EQ("$addl_ok", True), "$addl_bf")], 0), "addl": ADDL,
    "addl_carry": CHOOSE([(EQ("$addl_ok", True), RND(PCT("$new_less", DIV("$addl_rate", 2))))], 0),
    "total": ADD(DFULL, DHALF, ADDL),
    "wdv_last": MX(0, SUB(ADD(FULL, HALF), ADD(DFULL, DHALF, ADDL))),
    "gain_50": MX(0, SUB("$sales", ADD("$opening", "$more", "$less")))}),
    "s.32(1)(ii) on the written-down value of the block: opening WDV + additions - moneys from sales; additions put to use for less than 180 days get half the rate "
    "(2nd proviso to s.32(1)), sales coming first out of the full-rate part. Additional depreciation u/s 32(1)(iia) - 20% of new plant and machinery of a manufacturing "
    "company, half when used under 180 days and the other half next year (the 3rd proviso) - not under 115BA / 115BAA / 115BAB. Sales above the whole block are a "
    "short-term capital gain u/s 50.",
    [({"opening": 1000000, "more": 200000, "less": 100000, "rate": 15}, {"dep_full": 180000, "dep_half": 7500, "total": 187500, "wdv_last": 1112500}),
     ({"opening": 1000000, "more": 500000, "less": 400000, "rate": 15, "addl_ok": True, "new_more": 500000, "new_less": 400000},
      {"dep_full": 225000, "dep_half": 30000, "addl": 140000, "addl_carry": 40000, "total": 395000}),
     ({"opening": 1000000, "more": 500000, "less": 400000, "rate": 15, "addl_ok": False, "new_more": 500000, "new_less": 400000, "addl_bf": 30000},
      {"addl": 0, "total": 255000}),
     ({"opening": 100000, "more": 0, "less": 50000, "sales": 120000, "rate": 15}, {"full_base": 0, "half_base": 30000, "dep_half": 2250, "gain_50": 0}),
     ({"opening": 100000, "sales": 180000, "rate": 40}, {"total": 0, "gain_50": 80000, "wdv_last": 0})])

# =================================================================================================================================
# company.setoff, company.loss_ok
# =================================================================================================================================
SO = [P("available", 0, "loss (or credit) available"), P("against", 0, "income (or room) it may be set off against")]
USED = MN(MX(0, "$available"), MX(0, "$against"))
chip("company.setoff", "Company: one loss set off against one income", SO, V("record", fields={
    "used": USED, "loss_left": SUB(MX(0, "$available"), USED), "income_left": SUB("$against", USED)}),
    "Set-off is never more than the loss, nor more than the income it meets; what is left of each goes on (s.70-74, s.115JAA(4)).",
    [({"available": 500000, "against": 300000}, {"used": 300000, "loss_left": 200000, "income_left": 0}),
     ({"available": 100000, "against": 300000}, {"used": 100000, "loss_left": 0, "income_left": 200000}),
     ({"available": 100000, "against": -5000}, {"used": 0, "loss_left": 100000})])
LO = [P("kind", "business", "business | dep (unabsorbed depreciation) | mat (MAT credit)"), P("age", 1, "AYs since the loss's AY"),
      P("filed_ok", True, "that year's return was filed by its due date (s.80 / s.139(3))"), P("listed", False, "a company in which the public are substantially interested (listed)"),
      P("s79_ok", True, "51% of the voting power with the same holders on the last day of the loss year and of this year"),
      P("years", {"business": 8, "mat": 15}, "how many AYs each may be carried (company.settings loss_years)")]
chip("company.loss_ok", "Company: may this brought-forward loss or credit be used this year?", LO, CHOOSE([
    (EQ("$kind", "dep"), {"ok": True, "why": "lo_dep"}),
    (ALL(EQ("$kind", "mat"), GT("$age", GET("$years", "mat"))), {"ok": False, "why": "lo_mat_lapsed"}),
    (EQ("$kind", "mat"), {"ok": True, "why": "lo_mat"}),
    (GT("$age", GET("$years", "business")), {"ok": False, "why": "lo_lapsed"}),
    (NOT(EQ("$filed_ok", True)), {"ok": False, "why": "lo_late"}),
    (ALL(NOT(EQ("$listed", True)), NOT(EQ("$s79_ok", True))), {"ok": False, "why": "lo_s79"}),
], {"ok": True, "why": "lo_business"}),
    "Unabsorbed depreciation goes on without limit (s.32(2)) and is not hit by s.79. A business loss: 8 AYs (s.72(3)), only when that year's return was in time "
    "(s.80 / s.139(3)), and - for a company in which the public are not substantially interested - only when 51% of the voting power stayed with the same "
    "holders (s.79(1)(a)). MAT credit: 15 AYs (s.115JAA(3A)). (The s.79 relief for eligible start-ups, s.79(1)(b), is not taken here.)",
    [({"kind": "dep", "age": 20}, {"ok": True}), ({"kind": "business", "age": 8}, {"ok": True}), ({"kind": "business", "age": 9}, {"ok": False, "why": "lo_lapsed"}),
     ({"kind": "business", "age": 2, "filed_ok": False}, {"ok": False, "why": "lo_late"}),
     ({"kind": "business", "age": 2, "s79_ok": False}, {"ok": False, "why": "lo_s79"}),
     ({"kind": "business", "age": 2, "s79_ok": False, "listed": True}, {"ok": True}),
     ({"kind": "mat", "age": 15}, {"ok": True}), ({"kind": "mat", "age": 16}, {"ok": False, "why": "lo_mat_lapsed"})])

# =================================================================================================================================
# company.d80g, company.d80m
# =================================================================================================================================
GP = [P("d100", 0, "100% without limit"), P("d50", 0, "50% without limit"), P("d100q", 0, "100% within the qualifying limit"),
      P("d50q", 0, "50% within the qualifying limit"), P("adj_gti", 0, "adjusted gross total income (GTI less special-rate gains and other VI-A deductions)"),
      P("limit_pct", 10, "qualifying limit %"), P("allowed", True, "80G may be claimed under the option (company.rate via)")]
LIM = MX(0, PCT("$adj_gti", "$limit_pct"))
Q100 = MN("$d100q", LIM)
Q50 = RND(PCT(MN("$d50q", SUB(LIM, Q100)), 50))
NOLIM = ADD("$d100", RND(PCT("$d50", 50)))
chip("company.d80g", "Company: Schedule 80G - donations, the qualifying limit", GP, CHOOSE([(EQ("$allowed", True), V("record", fields={
    "no_limit": NOLIM, "limit": LIM, "q100": Q100, "q50": Q50, "within_limit": ADD(Q100, Q50), "total": ADD(NOLIM, Q100, Q50)}))],
    {"no_limit": 0, "limit": 0, "q100": 0, "q50": 0, "within_limit": 0, "total": 0}),
    "s.80G: donations without a limit at 100% / 50%; those within the qualifying limit together at most 10% of the adjusted gross total income (s.80G(4)), "
    "the 100% ones first, then 50% of the rest. A CSR contribution to the Swachh Bharat Kosh or the Clean Ganga Fund gets nothing (proviso to s.80G(2)(iiihk)/(iiihl)); "
    "a company under 115BAA / 115BAB claims no 80G at all (s.115BAA(2)(ii)).",
    [({"d100": 100000, "d50": 200000}, {"no_limit": 200000, "total": 200000}),
     ({"d50q": 500000, "adj_gti": 2000000}, {"limit": 200000.0, "q50": 100000, "total": 100000}),
     ({"d100q": 150000, "d50q": 500000, "adj_gti": 2000000}, {"q100": 150000, "q50": 25000, "total": 175000}),
     ({"d100": 100000, "allowed": False}, {"total": 0})])
MM = [P("dividend_in", 0, "dividend from domestic / foreign companies and business trusts in the gross total income"),
      P("paid", 0, "dividend the company distributed"), P("paid_on", 0, "date distributed (yyyymmdd)"), P("due", 0, "the return's due date u/s 139(1) (yyyymmdd)"),
      P("months", 1, "at least this many months before the due date")]
IN_TIME = ALL(GT("$paid_on", 0), LE("$paid_on", SUB("$due", MUL("$months", 100))))
chip("company.d80m", "Company: s.80M - dividends received and passed on", MM, V("record", fields={
    "in_time": YES(IN_TIME), "deduction": CHOOSE([(IN_TIME, MN(MX(0, "$dividend_in"), MX(0, "$paid")))], 0)}),
    "s.80M: a domestic company's dividend income from another domestic company, a foreign company or a business trust is deducted up to the dividend it "
    "distributed itself on or before one month prior to the due date of its return (dates as yyyymmdd numbers: the due date less 100 is the same day a month "
    "earlier for the comparison). Allowed under 115BAA / 115BAB too.",
    [({"dividend_in": 500000, "paid": 300000, "paid_on": 20260915, "due": 20261031}, {"in_time": True, "deduction": 300000}),
     ({"dividend_in": 500000, "paid": 900000, "paid_on": 20260930, "due": 20261031}, {"deduction": 500000}),
     ({"dividend_in": 500000, "paid": 900000, "paid_on": 20261005, "due": 20261031}, {"in_time": False, "deduction": 0}),
     ({"dividend_in": 500000, "paid": 900000, "paid_on": 0, "due": 20261031}, {"deduction": 0})])
print("company chips done")


# =================================================================================================================================
# part 2 - the existing chips a company needs
# =================================================================================================================================

c = load("clients.settings")
sts = next(p for p in c["params"] if p["name"] == "statuses")["default"]
if not any(s["id"] == "company" for s in sts):
    sts.append({"id": "company", "label": "Company (domestic)", "pan_letter": "C", "form": "ITR-6", "has_partners": False, "has_company": True})
fs = next(p for p in c["params"] if p["name"] == "forms")["default"]
if "ITR-6" not in fs:
    fs.append("ITR-6")
save(c, "status company - a domestic company (PAN 4th letter C) files ITR-6; has_company: the client carries a company part (CIN, date of incorporation, "
        "kind, tax option, listed, manufacturing, key persons, shareholders) - company.py, chip company.settings / company.problem.")

c = load("close.dates")
if not any(p["name"] == "audit_forms" for p in c["params"]):
    v0 = c["version"]
    knob(c, "audit_forms", ["ITR-6"], "forms whose due date is the audit date whatever the 44AB flag (a company: s.139(1) Explanation 2(a))")
    c["expr"]["fields"].pop("audit_forms", None)
    s = json.dumps(c["expr"])
    AUD = json.dumps({"op": "eq", "left": "$audit", "right": True})
    assert AUD in s
    c["expr"] = json.loads(s.replace(AUD, json.dumps(ANY({"op": "eq", "left": "$audit", "right": True}, IN("$form", "$audit_forms")))))
    write(c)
    for t in c["test_cases"]:                         # the old answers stand
        got = run_chip("close.dates", t["args"])
        assert got == t["expect_value"] or not t["args"], (t["args"], got)
        t["expect_value"] = got
    a1 = {"ay_year": 2026, "form": "ITR-6", "audit": False, "filed_on": 20261015, "today": 20261015}
    g1 = run_chip("close.dates", a1)
    assert g1["due"] == 20261121 and g1["due_rule"] == 20261031, g1   # the AY 2026-27 extension of the audit date applies; the Act's date stays 31 Oct
    a2 = a1 | {"tp": True}
    g2 = run_chip("close.dates", a2)
    assert g2["due"] == 20261130, g2
    c["test_cases"] += [{"args": a1, "expect_value": g1}, {"args": a2, "expect_value": g2}]
    c["version"] = v0 + 1
    c["description_nl"] += " " + NOTE + "audit_forms: a company (ITR-6) files by the audit date - 31 October, s.139(1) Explanation 2(a) - with or without a 44AB audit; 30 November with Form 3CEB."
    write(c)
    print("wrote close.dates v", c["version"])

c = load("intake.ref")
p = next(p for p in c["params"] if p["name"] == "pattern")
p["default"] = p["default"].replace("ITR-?5)", "ITR-?5|ITR-?6)")
c["description_nl"] = c["description_nl"].replace("form 3CD, ITR3 or ITR5", "form 3CD, ITR3, ITR5 or ITR6")
save(c, "ITR6 refs for a company (ITR6 BP profit, ITR6 DEP pm15, ITR6 MAT add_tax, ITR6 BS capital ...).")

c = load("intake.ref_part_ok")
p = next(p for p in c["params"] if p["name"] == "itr_tables")
for t in ("MAT", "MATC", "SH"):
    if t not in p["default"]:
        p["default"].append(t)
save(c, "MAT (book profit u/s 115JB), MATC (MAT credit), SH (shareholding) for ITR-6.")

c = load("itr.settings")
f = next(p for p in c["params"] if p["name"] == "forms")["default"]
f["ITR-6"] = {"schema": "schemas/itr/ITR-6_2026_Main_V1.0.json", "root": "ITR6"}
save(c, "ITR-6 (companies) AY 2026-27 schema V1.0 (the department's, 04-Aug-2026: incometax.gov.in > Downloads).")

c = load("itr.codes")
bf = next(p for p in c["params"] if p["name"] == "by_form")["default"]
bf["ITR-6"] = {"statuses": {}, "substatus": {}, "capacity": {}, "default_account": "CA",
               "account_types": {"current": "CA", "ca": "CA", "cc": "CC", "cash credit": "CC", "od": "OD", "overdraft": "OD", "nro": "NRO", "cgas": "CGAS",
                                 "savings": "OTH", "saving": "OTH", "sb": "OTH"},
               "flags": {"true": "Y", "false": "N"}, "residential": {"true": "NRI", "false": "RES"}, "share_type": "ES", "no_option": "NA", "mat_yes": "1",
               "turnover_bands": [{"upto": 10000000, "code": "Upto1CR"}, {"upto": 100000000, "code": "Upto10CR"}], "turnover_band_top": "MoreThan10CR"}
save(c, "ITR-6 (from its schema): bank account types CA / CC / OD / NRO / CGAS / OTH (no savings account for a company), the default CA; "
        "Section115BA NA when no option; ScheduleMAT 1 = Yes; Part A-GEN turnover bands Upto1CR / Upto10CR / MoreThan10CR; share type ES.")

c = load("tar.settings")
next(p for p in c["params"] if p["name"] == "form_by_status")["default"]["company"] = "3CA"
save(c, "a company's accounts are audited under the Companies Act: its tax audit report is Form 3CA-3CD.")
c = load("tar.codes")
next(p for p in c["params"] if p["name"] == "statuses")["default"]["company"] = 5
save(c, "Form 3CA-3CD PartA Status 5 = Company.")
print("part 2 done")


# =================================================================================================================================
# part 3 - Schedule III balance sheet and P&L for ITR-6 (chip itr.books: form_items / form_totals / form_checks)
# =================================================================================================================================
BS = "PARTA_BSFor6FrmAY13."
EL, AS = BS + "EquityAndLiablities.", BS + "Assets."
SF, NCL, CL = EL + "ShareHolderFund.", EL + "NonCurrLiabilities.", EL + "CurrentLiabilities."
NCA, CA = AS + "NonCurrAssets.", AS + "CurrentAssets."
TA, MA, PL = "TradingAccount.", "ManufacturingAccount.", "PARTA_PL."
OI, DB = PL + "CreditsToPL.OthIncome.", PL + "DebitsToPL.DebitPlAcnt."
MO = MA + "OpeningInventory."
ITEMS6 = {
    "capital": SF + "ShareCapital.IssuedSubsPaidUp", "authorised_capital": SF + "ShareCapital.Authorised",
    "securities_premium": SF + "ResrNSurp.SecurPremResr", "general_reserve": SF + "ResrNSurp.OtherResrvTotal", "capital_reserve": SF + "ResrNSurp.CapResr",
    "reserves": SF + "ResrNSurp.PLAccount", "pl_surplus": SF + "ResrNSurp.PLAccount", "share_application": EL + "ShareAppMoneyAllot.PendingLtOneYr",
    "secured_bank": NCL + "LongTermBorrowings.TermLoans.RupeeLoans.FromBanks", "secured_other": NCL + "LongTermBorrowings.TermLoans.RupeeLoans.FromOthers",
    "director_loans": NCL + "LongTermBorrowings.LoansAndAdv", "unsecured_other": NCL + "LongTermBorrowings.OthersLoanAdv",
    "deferred_tax": NCL + "NetDefferedTaxLiability", "lt_provisions": NCL + "LongTermProvisions.ProvEmpBenefits",
    "unsecured_bank": CL + "ShortTrmBorrowings.LoansRepaybleOnDemand.FromBanks", "working_capital": CL + "ShortTrmBorrowings.LoansRepaybleOnDemand.FromBanks",
    "creditors": CL + "TradePayables.Others", "creditors_old": CL + "TradePayables.OSMoreThanOneYr",
    "current_maturities": CL + "OthCurrLiabilities.CurrMatOnLTDebt", "advances_received": CL + "OthCurrLiabilities.IncRecvdAdvance",
    "unpaid_dividend": CL + "OthCurrLiabilities.UnpaidDividend", "other_liabilities": CL + "OthCurrLiabilities.OthPayables",
    "emp_provision": CL + "ShortTermProv.EmpBenefitProv", "tax_provision": CL + "ShortTermProv.ITProvision", "provisions": CL + "ShortTermProv.OthProvision",
    "gross_block": NCA + "FixedAsset.Tangible.GrossBlock", "acc_depreciation": NCA + "FixedAsset.Tangible.Depreciation",
    "intangible_block": NCA + "FixedAsset.InTangible.GrossBlock", "amortisation": NCA + "FixedAsset.InTangible.Amortization", "cwip": NCA + "FixedAsset.CapWrkProg",
    "investments": NCA + "NonCurrInvstmnts.OtherInvstmnts", "shares": NCA + "NonCurrInvstmnts.EquityInstruments.UnListedEquities",
    "listed_shares": NCA + "NonCurrInvstmnts.EquityInstruments.ListedEquities", "deferred_tax_asset": NCA + "NetDeferredTaxAssets",
    "capital_advances": NCA + "LongTrmLoanAdv.CapitalAdv", "deposits": NCA + "LongTrmLoanAdv.SecurityDeposits", "misc_expenditure": NCA + "OthNonCurrAssets.Others",
    "mutual_funds": CA + "CurrInvstmnts.MutualFunds", "stores": CA + "Inventories.StoresConsumables", "raw_material": CA + "Inventories.RawMatl",
    "wip": CA + "Inventories.WorkInProgress", "stock": CA + "Inventories.FinOrTradGood", "debtors": CA + "TradeReceivables.Others",
    "debtors_old": CA + "TradeReceivables.OSMoreThanSixMonths", "cash": CA + "CashNCashEquivalents.CashInHand", "bank": CA + "CashNCashEquivalents.BalWithBanks",
    "advances_given": CA + "TotShortTermLoanAdv.LoanAdv", "tax_balances": CA + "TotShortTermLoanAdv.Others", "other_current": CA + "OtherCurrAssets",
    "sales": TA + "SaleOfGoods", "services": TA + "SaleOfServices", "professional_receipts": TA + "GrossRcptFromProfession",
    "closing_stock": TA + "ClsngStckOfFinishedStcks", "opening_stock": TA + "OpngStckOfFinishedStcks", "purchases": TA + "Purchases",
    "carriage": TA + "CarriageInward", "power_direct": TA + "PowerAndFuel",
    "opening_raw": MO + "OpngStckRawMat", "opening_wip": MO + "OpngStckWrkinPrgrs", "raw_purchases": MO + "Purchases", "direct_wages": MO + "DirectWages",
    "factory_power": MO + "FactoryFuelAndPower", "factory_rent": MO + "FactoryRentAndRates", "factory_exp": MO + "FactoryGeneralExpenses",
    "closing_raw": MA + "ClosingStock.ClsngStckRawMaterial", "closing_wip": MA + "ClosingStock.ClsngStckWrkInPrgrs",
    "rent_income": OI + "RentInc", "commission_income": OI + "Comissions", "dividend": OI + "Dividends", "interest_income": OI + "InterestInc",
    "profit_on_sale": OI + "ProfitOnSaleFixedAsset", "other_income": OI + "MiscOthIncome",
    "freight": DB + "Freight", "power": DB + "PowerFuel", "rent": DB + "RentExpdr", "repairs_building": DB + "RepairsBldg", "repairs_machinery": DB + "RepairMach",
    "salaries": DB + "EmployeeComp.SalsWages", "bonus": DB + "EmployeeComp.Bonus", "pf": DB + "EmployeeComp.ContToPF", "gratuity": DB + "EmployeeComp.ContToGratFund",
    "staff_welfare": DB + "StaffWelfareExp", "insurance": DB + "Insurances.OthInsur", "entertainment": DB + "Entertainment", "advertisement": DB + "Advertisement",
    "commission": DB + "CommissionExpdrDtls.Others", "professional": DB + "ProfessionalConstDtls.Others", "travel": DB + "TravelExp",
    "conveyance": DB + "ConveyanceExp", "telephone": DB + "TelephoneExp", "gift": DB + "Gift", "donation": DB + "Donation", "audit_fee": DB + "AuditFee",
    "bad_debts": DB + "BadDebtDtls.OthersAmtLt1Lakh", "other_expenses": DB + "OtherExpenses", "csr_exp": DB + "OtherExpenses", "rates_taxes": DB + "OtherExpenses",
    "interest": DB + "InterestExpdrtDtls.Others", "depreciation": DB + "DepreciationAmort",
    "tax_provision_pl": PL + "DebitsToPL.TaxProvAppr.ProvForCurrTax", "deferred_tax_pl": PL + "DebitsToPL.TaxProvAppr.ProvDefTax",
    "pl_brought_forward": PL + "DebitsToPL.TaxProvAppr.BalBFPrevYr"}


def T6(path, plus, minus=()):
    return {"path": path, "plus": list(plus)} | ({"minus": list(minus)} if minus else {})


DEBITS = [DB + x for x in ("Freight", "ConsumptionOfStores", "PowerFuel", "RentExpdr", "RepairsBldg", "RepairMach", "EmployeeComp.TotEmployeeComp",
                            "Insurances.TotInsurances", "StaffWelfareExp", "Entertainment", "Hospitality", "Conference", "SalePromoExp", "Advertisement",
                            "CommissionExpdrDtls.Total", "RoyalityDtls.Total", "ProfessionalConstDtls.Total", "HotelBoardLodge", "TravelExp", "ForeignTravelExp",
                            "ConveyanceExp", "TelephoneExp", "GuestHouseExp", "ClubExp", "FestivalCelebExp", "Scholarship", "Gift", "Donation",
                            "RatesTaxesPays.ExciseCustomsVAT.TotExciseCustomsVAT", "AuditFee", "OtherExpenses", "BadDebtDtls.BadDebt", "ProvForBadDoubtDebt",
                            "OthProvisionsExpdr")]
LTB = NCL + "LongTermBorrowings."
LRD = CL + "ShortTrmBorrowings.LoansRepaybleOnDemand."
TOTALS6 = [
    T6(MO + "OpngInvntryTotal", [MO + "OpngStckRawMat", MO + "OpngStckWrkinPrgrs"]),
    T6(MO + "DirectExpenses", [MO + "CarriageInward", MO + "PowerAndFuel", MO + "OthDirectExpenses"]),
    T6(MO + "TotalFactoryOverheads", [MO + x for x in ("IndirectWages", "FactoryRentAndRates", "FactoryInsurance", "FactoryFuelAndPower", "FactoryGeneralExpenses",
                                                       "DeprctnOfFactoryMachinery")]),
    T6(MO + "TotalDebtsManfctrngAcc", [MO + x for x in ("OpngInvntryTotal", "Purchases", "DirectWages", "DirectExpenses", "TotalFactoryOverheads")]),
    T6(MA + "ClosingStock.ClsngStckTotal", [MA + "ClosingStock.ClsngStckRawMaterial", MA + "ClosingStock.ClsngStckWrkInPrgrs"]),
    T6(MA + "CostOfGoodsPrdcd", [MO + "TotalDebtsManfctrngAcc"], [MA + "ClosingStock.ClsngStckTotal"]),
    T6(TA + "GoodsCostPrdcdFrmMA", [MA + "CostOfGoodsPrdcd"]),
    T6(TA + "SalesGrossReceiptsTotal", [TA + "SaleOfGoods", TA + "SaleOfServices", TA + "OperatingRevenueTotal"]),
    T6(TA + "TotRevenueFrmOperations", [TA + "SalesGrossReceiptsTotal", TA + "GrossRcptFromProfession"], [TA + "ExciseCustomsVAT.TotExciseCustomsVAT"]),
    T6(TA + "TardingAccTotCred", [TA + "TotRevenueFrmOperations", TA + "ClsngStckOfFinishedStcks"]),
    T6(TA + "DirectExpenses", [TA + "CarriageInward", TA + "PowerAndFuel", TA + "TotOthDirectExpenses"]),
    T6(TA + "GrossProfitFrmBusProf", [TA + "TardingAccTotCred"], [TA + "OpngStckOfFinishedStcks", TA + "Purchases", TA + "DirectExpenses",
                                                                   TA + "DutyTaxPay.ExciseCustomsVAT.TotExciseCustomsVAT", TA + "GoodsCostPrdcdFrmMA"]),
    T6(PL + "CreditsToPL.GrossProfitTrnsfFrmTrdAcc", [TA + "GrossProfitFrmBusProf"]),
    T6(OI + "TotOthIncome", [OI + x for x in ("RentInc", "Comissions", "Dividends", "InterestInc", "ProfitOnSaleFixedAsset", "ProfitOnInvChrSTT", "ProfitOnOthInv",
                                              "ProfitOnCurrFluct", "ProfitOnCnvInvntryToCapAsst", "ProfitOnAgriIncome", "MiscOthIncome")]),
    T6(PL + "CreditsToPL.TotCreditsToPL", [PL + "CreditsToPL.GrossProfitTrnsfFrmTrdAcc", OI + "TotOthIncome"]),
    T6(DB + "EmployeeComp.TotEmployeeComp", [DB + "EmployeeComp." + x for x in ("SalsWages", "Bonus", "MedExpReimb", "LeaveEncash", "LeaveTravelBenft",
                                                                                 "ContToSuperAnnFund", "ContToPF", "ContToGratFund", "ContToOthFund", "OthEmpBenftExpdr")]),
    T6(DB + "Insurances.TotInsurances", [DB + "Insurances." + x for x in ("MedInsur", "LifeInsur", "KeyManInsur", "OthInsur")]),
    T6(DB + "CommissionExpdrDtls.Total", [DB + "CommissionExpdrDtls.NonResOtherCompany", DB + "CommissionExpdrDtls.Others"]),
    T6(DB + "RoyalityDtls.Total", [DB + "RoyalityDtls.NonResOtherCompany", DB + "RoyalityDtls.Others"]),
    T6(DB + "ProfessionalConstDtls.Total", [DB + "ProfessionalConstDtls.NonResOtherCompany", DB + "ProfessionalConstDtls.Others"]),
    T6(DB + "BadDebtDtls.BadDebt", [DB + "BadDebtDtls.BadDebtAmtDtlsTotal", DB + "BadDebtDtls.OthersPANNotAvlblDtlTotal", DB + "BadDebtDtls.OthersAmtLt1Lakh"]),
    T6(DB + "PBIDTA", [PL + "CreditsToPL.TotCreditsToPL"], DEBITS),
    T6(DB + "InterestExpdrtDtls.InterestExpdr", [DB + "InterestExpdrtDtls.NonResOtherCompany", DB + "InterestExpdrtDtls.Others"]),
    T6(DB + "PBT", [DB + "PBIDTA"], [DB + "InterestExpdrtDtls.InterestExpdr", DB + "DepreciationAmort"]),
    T6(PL + "DebitsToPL.TaxProvAppr.ProfitAfterTax", [DB + "PBT"], [PL + "DebitsToPL.TaxProvAppr.ProvForCurrTax", PL + "DebitsToPL.TaxProvAppr.ProvDefTax"]),
    T6(PL + "DebitsToPL.TaxProvAppr.AmtAvlAppr", [PL + "DebitsToPL.TaxProvAppr.ProfitAfterTax", PL + "DebitsToPL.TaxProvAppr.BalBFPrevYr"]),
    T6(SF + "ShareCapital.TotShareCapital", [SF + "ShareCapital.IssuedSubsPaidUp", SF + "ShareCapital.SubscribedNotFullyPaid"]),
    T6(SF + "ResrNSurp.TotResrNSurp", [SF + "ResrNSurp." + x for x in ("CapResr", "CapRedempResr", "SecurPremResr", "DebunRedResr", "RevResr", "ShareOptOSAmount",
                                                                       "OtherResrvTotal", "PLAccount")]),
    T6(SF + "TotShareHolderFund", [SF + "ShareCapital.TotShareCapital", SF + "ResrNSurp.TotResrNSurp", SF + "MoneyRecvdAgainstShares"]),
    T6(EL + "ShareAppMoneyAllot.Total", [EL + "ShareAppMoneyAllot.PendingLtOneYr", EL + "ShareAppMoneyAllot.PendingMtOneYr"]),
    T6(LTB + "BondsDebentures.Total", [LTB + "BondsDebentures.ForeignCurrency", LTB + "BondsDebentures.Rupee"]),
    T6(LTB + "TermLoans.RupeeLoans.Total", [LTB + "TermLoans.RupeeLoans.FromBanks", LTB + "TermLoans.RupeeLoans.FromOthers"]),
    T6(LTB + "TermLoans.TotalTermLoans", [LTB + "TermLoans.ForeignCurrency", LTB + "TermLoans.RupeeLoans.Total"]),
    T6(LTB + "TotalLTBorrowings", [LTB + x for x in ("BondsDebentures.Total", "TermLoans.TotalTermLoans", "DeferredPymtLiabilities", "DepositsFrmRelatedParties",
                                                     "OtherDeposits", "LoansAndAdv", "OthersLoanAdv", "LongTermMaturities")]),
    T6(NCL + "OthLongTermLiablities.TotalOthLtLiabilities", [NCL + "OthLongTermLiablities.TradePayables", NCL + "OthLongTermLiablities.Others"]),
    T6(NCL + "LongTermProvisions.Total", [NCL + "LongTermProvisions.ProvEmpBenefits", NCL + "LongTermProvisions.Others"]),
    T6(NCL + "TotalNonCurrLiabilites", [LTB + "TotalLTBorrowings", NCL + "NetDefferedTaxLiability", NCL + "OthLongTermLiablities.TotalOthLtLiabilities",
                                        NCL + "LongTermProvisions.Total"]),
    T6(LRD + "TotLoansRepaybleOnDemand", [LRD + x for x in ("FromBanks", "FrmNonBanking", "OthFinanceInst", "Others")]),
    T6(CL + "ShortTrmBorrowings.TotShortTrmBorrowings", [LRD + "TotLoansRepaybleOnDemand"] + [CL + "ShortTrmBorrowings." + x for x in (
        "DepositsFrmRelatedParties", "LoansAndAdv", "OthLoansAndAdv", "OthDeposits")]),
    T6(CL + "TradePayables.TotalTradePayables", [CL + "TradePayables.OSMoreThanOneYr", CL + "TradePayables.Others"]),
    T6(CL + "OthCurrLiabilities.TotOthCurrLiabilities", [CL + "OthCurrLiabilities." + x for x in (
        "CurrMatOnLTDebt", "CurrMatFinanceOblg", "AccrInterestNotDue", "AccrInterest", "IncRecvdAdvance", "UnpaidDividend", "AppMonyRecvdAllotSecurities",
        "UnpaidMatDeposits", "UnpaidMatureDebenture", "OthPayables")]),
    T6(CL + "ShortTermProv.TotShortTermProvisions", [CL + "ShortTermProv." + x for x in ("EmpBenefitProv", "ITProvision", "ProposedDividend", "TaxOnDividend", "OthProvision")]),
    T6(CL + "TotCurrLiabilitiesProvision", [CL + x for x in ("ShortTrmBorrowings.TotShortTrmBorrowings", "TradePayables.TotalTradePayables",
                                                             "OthCurrLiabilities.TotOthCurrLiabilities", "ShortTermProv.TotShortTermProvisions")]),
    T6(EL + "TotEquityAndLiabilities", [SF + "TotShareHolderFund", EL + "ShareAppMoneyAllot.Total", NCL + "TotalNonCurrLiabilites", CL + "TotCurrLiabilitiesProvision"]),
    T6(NCA + "FixedAsset.Tangible.NetBlock", [NCA + "FixedAsset.Tangible.GrossBlock"], [NCA + "FixedAsset.Tangible.Depreciation", NCA + "FixedAsset.Tangible.ImpairmentLosses"]),
    T6(NCA + "FixedAsset.InTangible.NetBlock", [NCA + "FixedAsset.InTangible.GrossBlock"], [NCA + "FixedAsset.InTangible.Amortization",
                                                                                             NCA + "FixedAsset.InTangible.ImpairmentLosses"]),
    T6(NCA + "FixedAsset.TotFixedAsset", [NCA + "FixedAsset." + x for x in ("Tangible.NetBlock", "InTangible.NetBlock", "CapWrkProg", "IntangibleAssetUnDev")]),
    T6(NCA + "NonCurrInvstmnts.EquityInstruments.Total", [NCA + "NonCurrInvstmnts.EquityInstruments.ListedEquities", NCA + "NonCurrInvstmnts.EquityInstruments.UnListedEquities"]),
    T6(NCA + "NonCurrInvstmnts.TotNonCurrInvstmnts", [NCA + "NonCurrInvstmnts." + x for x in (
        "InvInProperty", "EquityInstruments.Total", "PreferenceShares", "GovtOrTrustSecurities", "DebenturesOrBonds", "MutualFunds", "InvstmntInPrtnrShipFirm",
        "OtherInvstmnts")]),
    T6(NCA + "LongTrmLoanAdv.TotLTLoanAdv", [NCA + "LongTrmLoanAdv." + x for x in ("CapitalAdv", "SecurityDeposits", "LoanAdvRelatedParties", "OthLoanAdv")]),
    T6(NCA + "OthNonCurrAssets.Total", [NCA + "OthNonCurrAssets.LTTradeReceivables.TotOthNonCurrAssets", NCA + "OthNonCurrAssets.Others"]),
    T6(NCA + "TotNonCurrAssets", [NCA + x for x in ("FixedAsset.TotFixedAsset", "NonCurrInvstmnts.TotNonCurrInvstmnts", "NetDeferredTaxAssets",
                                                    "LongTrmLoanAdv.TotLTLoanAdv", "OthNonCurrAssets.Total")]),
    T6(CA + "CurrInvstmnts.EquityInstruments.Total", [CA + "CurrInvstmnts.EquityInstruments.ListedEquities", CA + "CurrInvstmnts.EquityInstruments.UnListedEquities"]),
    T6(CA + "CurrInvstmnts.TotCurrInvstmnts", [CA + "CurrInvstmnts." + x for x in (
        "EquityInstruments.Total", "PreferenceShares", "GovtOrTrustSecurities", "DebenturesOrBonds", "MutualFunds", "InvstmntInPrtnrShipFirm", "OtherInvstmnts")]),
    T6(CA + "Inventories.TotInventries", [CA + "Inventories." + x for x in ("RawMatl", "WorkInProgress", "FinOrTradGood", "StkInTrade", "StoresConsumables",
                                                                           "LooseTools", "Others")]),
    T6(CA + "TradeReceivables.TotalTradeReceivables", [CA + "TradeReceivables.OSMoreThanSixMonths", CA + "TradeReceivables.Others"]),
    T6(CA + "CashNCashEquivalents.TotCashNCashEquivalents", [CA + "CashNCashEquivalents." + x for x in ("BalWithBanks", "ChequesDrafts", "CashInHand", "Others")]),
    T6(CA + "TotShortTermLoanAdv.TotShrtTermLoans", [CA + "TotShortTermLoanAdv.LoanAdv", CA + "TotShortTermLoanAdv.Others"]),
    T6(CA + "TotCurrAssets", [CA + x for x in ("CurrInvstmnts.TotCurrInvstmnts", "Inventories.TotInventries", "TradeReceivables.TotalTradeReceivables",
                                               "CashNCashEquivalents.TotCashNCashEquivalents", "TotShortTermLoanAdv.TotShrtTermLoans", "OtherCurrAssets")]),
    T6(BS + "TotalAssets", [NCA + "TotNonCurrAssets", CA + "TotCurrAssets"])]
CHECKS6 = {"bs_sources": EL + "TotEquityAndLiabilities", "bs_applied": BS + "TotalAssets", "pl_profit": DB + "PBT",
           "profit_pattern": "(?i)net profit|profit before tax"}
c = load("itr.books")
knob(c, "form_items", {"ITR-6": ITEMS6}, "a form with its own layout (ITR-6, Schedule III): its items' paths - used instead of items + rewrites")
knob(c, "form_totals", {"ITR-6": TOTALS6}, "that form's totals, in order")
knob(c, "form_checks", {"ITR-6": CHECKS6}, "that form's two checks (and the business-profit row's words)")
save(c, "ITR-6: a company's balance sheet and P&L in the Schedule III layout (Part A-BS For6, Trading / Manufacturing account, Part A-P&L) - its own items "
        "(the same item names as ITR-3 / ITR-5, so the same suggestions and refs work, plus share capital, securities premium, director loans, current maturities, "
        "CSR expenditure, the manufacturing account's raw material and WIP), totals in order, and the two checks: equity and liabilities = total assets; "
        "the P&L's profit before tax = the computation statement's profit-before-tax row. Rows on one path add up.")
print("part 3 done")


# =================================================================================================================================
# part 4 - the words (ui.clients: the company part of a client; ui.compute: the company section of Compute & close)
# =================================================================================================================================
W_CLIENTS = {
    "co_box": "Company (ITR-6)",
    "co_lede": "A domestic company files ITR-6 by 31 October (30 November with Form 3CEB). Its CIN, option and people go into Part A-GEN and Schedule SH.",
    "co_cin": "CIN (from the MCA)", "co_incorporated": "Date of incorporation", "co_kind": "Kind of company", "co_option": "Tax option",
    "co_option_ay": "Option first used for AY (e.g. 2021-22)", "co_option_ack": "Form 10-IB / 10-IC / 10-ID ack. no.", "co_option_date": "That form filed on",
    "co_manufacturing": "Manufacturing company (additional depreciation; needed for 115BAB)", "co_msme": "Registered under the MSMED Act",
    "co_indas": "Accounts drawn up under Ind AS", "co_nature": "Nature of business code (ITR list, 5 digits)", "co_trade": "Trade name",
    "co_directors": "Directors and key persons", "co_directors_lede": "The managing director (else the first director) signs the return: give their PAN and father's name.",
    "co_d_name": "Name", "co_d_din": "DIN", "co_d_pan": "PAN", "co_d_designation": "MD / DIR / CFO / SEC", "co_d_father": "Father's name", "co_d_address": "Address with PIN",
    "co_add_director": "Add a director",
    "co_holders": "Shareholders", "co_holders_lede": "Each holder of 1% or more (Schedule SH-1 for an unlisted company); 10% or more also goes into Part A-GEN.",
    "co_h_name": "Name", "co_h_pan": "PAN", "co_h_pct": "% held", "co_h_shares": "Shares", "co_h_face": "Face value", "co_h_issue": "Issue price",
    "co_h_allotted": "Allotted on (YYYY-MM-DD)", "co_h_address": "Address with PIN", "co_add_holder": "Add a shareholder",
    "co_bad_kind": "Pick the kind of company from the list.", "co_bad_option": "Pick the tax option from the list.",
    "co_bad_cin": "That CIN does not have the MCA's 21-character shape (e.g. U51909TG2018PTC123456).",
    "co_bad_date": "Give the date of incorporation as a date.", "co_bad_din": "A DIN has 8 digits.", "co_bad_share": "A shareholding is a % between 0 and 100.",
    "co_share_over": "The shareholdings add up to more than 100%.", "co_remove_row": "Remove this row? It goes when you save.", "co_bab_manufacturing": "s.115BAB is only for a new manufacturing company - tick Manufacturing, or pick another option."}
W_COMPUTE = {
    "regime_company": "Company (ITR-6)",
    "co_title": "Company - ITR-6", "co_lede": "The option's rate, depreciation by block, losses set off and carried, MAT and its credit, 80M / 80G.",
    "co_option": "Tax option", "co_rate": "Rate", "co_surcharge": "Surcharge", "co_sur_flat": "a flat {rate}% on any income", "co_sur_bands": "7% above 1 crore, 12% above 10 crore",
    "why_low": "25%: the turnover of the PY {py} is within 400 crore", "why_high": "30%: the turnover of the PY {py} is above 400 crore",
    "why_turnover_missing": "30% until the turnover of the PY {py} is typed below", "why_115BA": "s.115BA: 25%",
    "why_115BAA": "s.115BAA: 22% + 10% surcharge, no MAT, no additional depreciation, only 80JJAA / 80M / 80LA(1A)",
    "why_115BAB": "s.115BAB: 15% on the manufacturing business, 22% on the rest, 10% surcharge, no MAT",
    "co_year": "This year's facts", "co_turnover": "Turnover of the PY {py} (Rs)", "co_s79": "51% of the voting power stayed with the same holders (s.79)",
    "co_div_paid": "Dividend the company distributed (Rs)", "co_div_on": "Distributed on", "co_opt_now": "Option exercised this year (Form 10-IC / 10-ID)",
    "co_opt_ack": "Its ack. no.", "co_opt_date": "Filed on", "co_audit_on": "Tax audit report filed on", "co_audit_ack": "Its ack. no.",
    "co_bf": "Losses brought forward", "co_bf_ay": "AY", "co_bf_business": "Business loss", "co_bf_dep": "Unabsorbed depreciation", "co_bf_filed": "Return filed on",
    "co_bf_ok": "Filed in time", "co_add_bf": "Add a year", "co_mc": "MAT credit brought forward", "co_mc_ay": "AY", "co_mc_amount": "Credit (Rs)", "co_add_mc": "Add a year",
    "co_save": "Save the company's year", "co_saved": "Saved - the computation is worked out again",
    "co_dep": "Depreciation (Schedule DEP)", "co_dep_block": "Block", "co_dep_open": "Opening WDV", "co_dep_add": "Additions (180+ / under 180 days)",
    "co_dep_sales": "Sales", "co_dep_dep": "Depreciation", "co_dep_addl": "Additional 32(1)(iia)", "co_dep_wdv": "Closing WDV", "co_dep_total": "Depreciation u/s 32",
    "co_dep_none": "No fixed-asset schedule yet: tag its rows ITR6 DEP <block> (pm15, pm40, bldg10, furn10, intang25 ...), one row per block, with the columns opening WDV, additions 180 days or more / less, sales.",
    "co_dep32_line": "Less: depreciation u/s 32 (Schedule DEP)", "co_gain50_line": "Short-term gain u/s 50 (a block sold beyond its WDV)",
    "co_80m_line": "s.80M: dividends received and passed on", "co_80g_line": "s.80G: donations",
    "co_setoff": "Losses set off and carried", "co_setoff_line": "Less: losses set off (this year's and brought forward)", "co_cyla_hp": "House-property loss set off this year", "co_cyla_bp": "Business loss set off against other heads",
    "co_bfla": "Brought forward", "co_cf_business": "Business loss to carry forward", "co_cf_dep": "Unabsorbed depreciation to carry forward",
    "co_cf_hp": "House-property loss to carry forward", "co_cf_cg": "Capital losses to carry forward", "co_cf_note": "Carried only when the return is in time (s.80); unabsorbed depreciation always.",
    "lo_dep": "unabsorbed depreciation - no time limit (s.32(2))", "lo_business": "within 8 AYs (s.72)", "lo_lapsed": "more than 8 AYs old - lapsed (s.72(3))",
    "lo_late": "that return was late - not carried (s.80)", "lo_s79": "shareholding changed beyond 49% - lost (s.79)", "lo_mat": "within 15 AYs (s.115JAA)",
    "lo_mat_lapsed": "more than 15 AYs old - lapsed (s.115JAA)",
    "co_mat": "MAT (s.115JB) and its credit", "co_book_profit": "Book profit", "co_book_from_pl": "from the P&L's profit before tax - tag the Form 29B rows ITR6 MAT <item> for its additions and deductions",
    "co_mat_tax": "MAT at {rate}% (with surcharge and cess)", "co_normal_tax": "Tax under the normal provisions", "co_pays_mat": "MAT is higher: it is the tax, and {amount} becomes a MAT credit (s.115JAA(1A))",
    "co_pays_normal": "The normal tax is higher: it is the tax", "co_credit_used": "MAT credit set off this year (s.115JAA(4))", "co_mat_none": "No MAT under {option} (s.115JB(5A)); no MAT credit either",
    "co_credit_cf": "MAT credit to carry forward",
    "co_80m": "s.80M", "co_80m_late": "not distributed a month before the due date - no 80M", "co_80g": "s.80G", "co_80g_barred": "no 80G under 115BAA / 115BAB",
    "co_w_rates": "The rates are verified for AY 2026-27; this year uses them - check its Finance Act.",
    "co_w_turnover": "Type the turnover of the earlier year below: without it the rate is 30%.",
    "co_not_company": "Only a company has a company part.", "t_credit": "Less: MAT credit (s.115JAA)", "wf_credit": "MAT credit", "co_basis": "Tax paid as",
    "co_basis_mat": "MAT (s.115JB)", "co_basis_normal": "normal provisions", "x_mat": "MAT u/s 115JB", "x_book_profit": "Book profit u/s 115JB", "x_dep": "Depreciation u/s 32 by block"}
for cid, words in (("ui.clients", W_CLIENTS), ("ui.compute", W_COMPUTE)):
    c = load(cid)
    for k_, v_ in words.items():
        knob(c, k_, v_, k_)
    save(c, "the words of a company's return (ITR-6).")
print("part 4 done")


# =================================================================================================================================
# part 5 - chip itr.map's ITR-6 rows: a fact (our words, company.itr_facts / itr_json.facts) at each path of the CBDT schema
# =================================================================================================================================
SCH = json.loads((ROOT / "schemas/itr/ITR-6_2026_Main_V1.0.json").read_text(encoding="utf-8"))


def _ref(v):
    while "$ref" in v:
        v = SCH["definitions"][v["$ref"].split("/")[-1]]
    return v


def has(path):
    """The path is in the ITR-6 schema (ITR6.<...>; a list's items are walked into)."""
    v = SCH["definitions"]["ITR6"]
    for k in path.split(".")[1:]:
        v = _ref(v)
        if v.get("type") == "array":
            v = _ref(v["items"])
        if k not in v.get("properties", {}):
            return False
        v = v["properties"][k]
    return True


ROWS = []


def R(path, src, **kw):
    path = "ITR6." + path
    assert has(path), path
    ROWS.append({"path": path, "from": src} | kw)


def EACH(path, each, item):
    path = "ITR6." + path
    assert has(path), path
    for k in item:
        assert has(path + "." + k), (path, k)
    ROWS.append({"path": path, "each": each, "item": item})


for k_, v_ in [("SWVersionNo", "sw_version"), ("SWCreatedBy", "sw_id"), ("JSONCreatedBy", "sw_id"), ("JSONCreationDate", "today"),
               ("IntermediaryCity", "client.city"), ("Digest", "=-")]:
    R("CreationInfo." + k_, v_)
for k_, v_ in [("FormName", "form"), ("Description", "=SimplyFile"), ("AssessmentYear", "ay_code"), ("SchemaVer", "=Ver1.0"), ("FormVer", "=Ver1.0")]:
    R("Form_ITR6." + k_, v_)
G1 = "PartA_GEN1.OrgFirmInfo."
for k_, v_ in [("AssesseeName.SurNameOrOrgName", "client.name"), ("PAN", "client.pan"), ("CINissuedByMCA", "co.gen.cin"),
               ("Address.ResidenceNo", "client.flat"), ("Address.LocalityOrArea", "client.area"), ("Address.CityOrTownOrDistrict", "client.city"),
               ("Address.StateCode", "client.state"), ("Address.CountryCode", "=91"), ("Address.PinCode", "client.pin"), ("Address.CountryCodeMobile", "#91"),
               ("Address.MobileNo", "client.mobile"), ("Address.EmailAddress", "client.email"), ("DateOFFormOrIncorp", "co.gen.incorporated"),
               ("StatusOrCompanyType", "co.gen.company_type"), ("DomesticCompFlg", "co.gen.domestic")]:
    R(G1 + k_, v_)
FS = "PartA_GEN1.FilingStatus."
for k_, v_ in [("ReturnFileSec.IncomeTaxSec", "filing.section"), ("ReceiptNo", "filing.orig_ack"), ("OrigRetFiledDate", "filing.orig_date"),
               ("ResidentialStatus", "=RES"), ("Section115BA", "co.gen.opt115"), ("Section115BAAY", "co.gen.opt_ay"), ("ReceiptNo115BA", "co.gen.opt_ack"),
               ("115BAFormFiledDate", "co.gen.opt_date"), ("Section115CurrAY", "co.gen.opt_now"), ("SectionCurrAY", "co.gen.opt_now_sec"),
               ("Section115CurrAYDate", "co.gen.opt_now_date"), ("Section115CurrAYRecNo", "co.gen.opt_now_ack"), ("GrossReceipt", "co.gen.small"),
               ("FinancialStmtFlag", "co.gen.fs_indas"), ("ItrFilingDueDate", "filing.due_rule"), ("ifMSME", "co.gen.msme")]:
    R(FS + k_, v_)
G2 = "PartA_GEN2For6."
for k_, v_ in [("LiableSec44AAflg", "=Y"), ("IncDclrdUs", "=N"), ("TotalSalesExcOneCr", "co.gen.turnover_band"), ("LiableSec44ABflg", "co.gen.audit44ab"),
               ("AuditedByAccountantFlg", "co.gen.audit44ab"), ("AuditInfo.AudFrmPAN", "auditor.pan"), ("AuditInfo.AudFrmName", "auditor.name"),
               ("AuditInfo.AuditReportFurnishDate", "co.gen.audit_on"), ("AuditInfo.AckNum44AB", "co.gen.audit_ack"), ("LiableSec92Eflg", "co.gen.tp"),
               ("AccountAuditFlag", "=Y"), ("HoldingStatus.NatOfCompFlg", "=4"), ("NatureOfComp.CompanyUnlistedFlag", "co.gen.unlisted")]:
    R(G2 + k_, v_)
AD = {"AddressDetailWithZipCode.AddrDetail": "addr", "AddressDetailWithZipCode.CityOrTownOrDistrict": "city", "AddressDetailWithZipCode.StateCode": "state",
      "AddressDetailWithZipCode.CountryCode": "=91", "AddressDetailWithZipCode.PinCode": "pin"}
EACH(G2 + "KeyPersons", "co.persons", {"PersonName": "name", "Designation": "designation", **AD, "KeyPerPAN": "pan", "DirectorIdNo": "din"})
EACH(G2 + "ShareHolderInfo", "co.holders", {"ShareHolderInfoName": "name", **AD, "PercentageOfShare": "pct", "ShareHolderPAN": "pan"})
EACH(G2 + "NatOfBus.NatureOfBusiness", "co.nature", {"Code": "code", "TradeName1": "trade"})
SH = "ScheduleSH.ShrhldngUnlistedCompany."
R(SH + "SHUnlistedCompanyFlag", "co.has_sh")
EACH(SH + "DtlsSHEndPreviousYearUC", "co.sh", {"ShareholderName": "name", "ResidentialStatus": "res", "ShareType": "type", "PAN": "pan", "AllotmentDate": "allotted",
                                                "NumberOfSharesHeld": "shares", "FaceValuePerShare": "face", "IssuePricePerShare": "issue", "AmountReceived": "amount"})
B = "CorpScheduleBP.BusinessIncOthThanSpec."
for k_, v_ in [("ProfBfrTaxPL", "profit"), ("IncRecCredPLOthHeadDtls.HouseProperty", "hp_in"), ("IncRecCredPLOthHeadDtls.CapitalGains", "cg_in"),
               ("IncRecCredPLOthHeadDtls.OtherSources", "os_in"), ("IncRecCredPLOthHeadDtls.Dividend", "div_in"), ("IncRecCredPLOthHeadDtls.OtherThanDividend", "oth_in"),
               ("IncCredPL.OthExempInc", "exempt"), ("IncCredPL.TotExempInc", "exempt"), ("BalancePLOthThanSpecBus", "balance"), ("AdjustedPLOthThanSpecBus", "balance"),
               ("DepreciationDebPLCosAct", "book_dep"), ("DepreciationAllowITAct32.DepreciationAllowUs32_1_ii", "dep32"),
               ("DepreciationAllowITAct32.TotDeprAllowITAct", "dep32"), ("AdjustPLAfterDeprOthSpecInc", "after_dep"), ("AmtDebPLDisallowUs36", "s36"),
               ("AmtDebPLDisallowUs37", "s37"), ("AmtDebPLDisallowUs40", "s40"), ("AmtDebPLDisallowUs40A", "s40a"), ("AmtDebPLDisallowUs43B", "s43b"),
               ("OthItemDisallowUs28To44DA", "other_add"), ("TotAfterAddToPLDeprOthSpecInc", "total_add"), ("AmtDisallUs40NowAllow", "s40_paid"),
               ("AmtDisallUs43BNowAllow", "s43b_paid"), ("AnyOthAmtAllDeduct", "other_less"), ("TotDeductionAmts", "total_less"),
               ("PLAftAdjDedBusOthThanSpec", "net"), ("NetPLAftAdjBusOthThanSpec", "net"), ("NetPLBusOthThanSpec7A7B7C", "net"), ("IncomeOtherThanRule", "net")]:
    R(B + k_, "co.bp." + v_)
R("CorpScheduleBP.IncChrgUnHdProftGain", "co.bp.net")
DD = {"WDVFirstDay": "wdv_first", "AdditionsGrThan180Days": "add_more", "RealizationTotalPeriod": "real_full", "FullRateDeprAmt": "full_base",
      "AdditionsLessThan180Days": "add_less", "RealizationPeriodDuringYear": "real_half", "HalfRateDeprAmt": "half_base", "DepreciationAtFullRate": "dep_full",
      "DepreciationAtHalfRate": "dep_half", "AddlnDeprOnGT180DayAdditions": "addl_more", "AddlnDeprOnLessThan180DayAdditions": "addl_less",
      "AddlnDeprDuringYearAdditions": "addl_bf", "TotalDepreciation": "total", "DepDisAllowUs38_2": "zero", "NetAggregateDepreciation": "net",
      "ProportionateAggDepreciation": "net", "ExpdrOnTrforSaleAsset": "zero", "CapGainUs50": "gain_50", "WDVLastDay": "wdv_last"}
for b in DEP_BLOCKS:
    for k_, v_ in DD.items():
        if has(f"ITR6.{b['path']}.DepreciationDetail.{k_}"):
            R(f"{b['path']}.DepreciationDetail.{k_}", f"co.dep.{b['id']}.{v_}")
DS = "ScheduleDEP.SummaryFromDeprSch."
for k_, v_ in [("PlantMachinerySummary.DeprBlockTot15Percent", "pm15"), ("PlantMachinerySummary.DeprBlockTot30Percent", "pm30"),
               ("PlantMachinerySummary.DeprBlockTot40Percent", "pm40"), ("PlantMachinerySummary.DeprBlockTot45Percent", "pm45"),
               ("PlantMachinerySummary.TotPlntMach", "pm_total"), ("BuildingSummary.DeprBlockTot5Percent", "b5"), ("BuildingSummary.DeprBlockTot10Percent", "b10"),
               ("BuildingSummary.DeprBlockTot40Percent", "b40"), ("BuildingSummary.TotBuildng", "b_total"), ("FurnitureSummary", "furn"),
               ("IntangibleAssetSummary", "intang"), ("ShipsSummary", "ships")]:
    R(DS + k_, "co.depsum." + v_)
R("ScheduleDEP.SummaryFromDeprSch.TotalDepreciation", "co.depsum.total")
OS = "ScheduleOS.IncOthThanOwnRaceHorse."
for k_, v_ in [("DividendGross", "dividend"), ("DividendOthThan22e", "dividend"), ("InterestGross", "interest_gross"), ("IntrstFrmTermDeposit", "deposit"),
               ("IntrstFrmIncmTaxRefund", "refund"), ("IntrstFrmOthers", "interest"), ("RentFromMachPlantBldgs", "rent"), ("AnyOtherIncome", "other"),
               ("GrossIncChrgblTaxAtAppRate", "gross"), ("BalanceNoRaceHorse", "gross")]:
    R(OS + k_, "co.os." + v_, skip_zero=True)
R("ScheduleOS.TotOthSrcNoRaceHorse", "co.os.total", skip_zero=True)
R("ScheduleOS.IncChargeableFrmOthSrc", "co.os.total", skip_zero=True)
for k_, v_ in [("ShortTermCapGain.TotalSTCG", "st"), ("LongTermCapGain.TotalLTCG", "lt"), ("SumOfCGIncm", "total"), ("IncChargeableHeadCapGain", "total")]:
    R("ScheduleCG." + k_, "co.cg." + v_, skip_zero=True)
CY = "ScheduleCYLA."
R(CY + "TotalCurYr.TotHPlossCurYr", "co.cyla.hp_loss", skip_zero=True)
R(CY + "TotalCurYr.TotBusLoss", "co.cyla.bp_loss", skip_zero=True)
for blk, key, setoffs in [("HP", "hp", {"BusLossSetoff": "bp"}), ("BusProfExclSpecProf", "bp", {"HPlossCurYrSetoff": "hp"}),
                          ("STCG20Per", "stcg_111a", {"HPlossCurYrSetoff": "hp", "BusLossSetoff": "bp"}),
                          ("STCGAppRate", "stcg", {"HPlossCurYrSetoff": "hp", "BusLossSetoff": "bp"}),
                          ("LTCG12_5Per", "lt", {"HPlossCurYrSetoff": "hp", "BusLossSetoff": "bp"}),
                          ("OthSrcExclRaceHorseLottery", "os", {"HPlossCurYrSetoff": "hp", "BusLossSetoff": "bp"})]:
    R(f"{CY}{blk}.IncCYLA.IncOfCurYrUnderThatHead", f"co.cyla.inc.{key}", skip_zero=True)
    for k_, who in setoffs.items():
        R(f"{CY}{blk}.IncCYLA.{k_}", f"co.cyla.hp_used.{who}>{key}", skip_zero=True)
    R(f"{CY}{blk}.IncCYLA.IncOfCurYrAfterSetOff", f"co.cyla.after.{key}", skip_zero=True)
for k_, v_ in [("TotalLossSetOff.TotHPlossCurYrSetoff", "hp_total"), ("TotalLossSetOff.TotBusLossSetoff", "bp_total"),
               ("LossRemAftSetOff.BalHPlossCurYrAftSetoff", "hp_left"), ("LossRemAftSetOff.BalBusLossAftSetoff", "bp_left")]:
    R(CY + k_, "co.cyla." + v_, skip_zero=True)
BF = "ScheduleBFLA."
for blk, key in [("HP", "hp"), ("BusProfExclSpecProf", "bp"), ("STCG20Per", "stcg_111a"), ("STCGAppRate", "stcg"), ("LTCG12_5Per", "lt"),
                 ("OthSrcExclRaceHorseLottery", "os")]:
    if not has(f"ITR6.{BF}{blk}.IncBFLA.IncOfCurYrUndHeadFromCYLA"):
        continue
    R(f"{BF}{blk}.IncBFLA.IncOfCurYrUndHeadFromCYLA", f"co.bfla.in.{key}", skip_zero=True)
    if key == "bp":
        R(f"{BF}{blk}.IncBFLA.BFlossPrevYrUndSameHeadSetoff", "co.bfla.bus", skip_zero=True)
    R(f"{BF}{blk}.IncBFLA.BFUnabsorbedDeprSetoff", f"co.bfla.ud_on.{key}", skip_zero=True)
    R(f"{BF}{blk}.IncBFLA.IncOfCurYrAfterSetOffBFLosses", f"co.bfla.after.{key}", skip_zero=True)
R(BF + "TotalBFLossSetOff.TotBFLossSetoff", "co.bfla.bus", skip_zero=True)
R(BF + "TotalBFLossSetOff.TotUnabsorbedDeprSetoff", "co.bfla.ud", skip_zero=True)
R(BF + "IncomeOfCurrYrAftCYLABFLA", "co.bfla.total", skip_zero=True)
for ay_, blk in CFL_PATHS.items():
    for k_, v_ in [("DateOfFiling", "filed_on"), ("BroughtFrwrdBusLoss", "business"), ("BroughtFrwdBusLossSetOffDrYr", "available")]:
        if has(f"ITR6.ScheduleCFL.{blk}.CarryFwdLossDetail.{k_}"):
            R(f"ScheduleCFL.{blk}.CarryFwdLossDetail.{k_}", f"co.cfl.{ay_}.{v_}")
for blk, v_ in [("TotalOfBFLossesEarlierYrs", "available"), ("AdjTotBFLossInBFLA", "used"), ("CurrentAYloss", "cy"), ("CurrentYearLossCF", "cy"),
                ("TotalLossCFSummary", "all")]:
    R(f"ScheduleCFL.{blk}.LossSummaryDetail.BroughtFrwdBusLossSetOffDrYr", f"co.cfl_total.{v_}", skip_zero=True)
EACH("ITRScheduleUD.ScheduleUD", "co.ud", {"AssYr": "ay", "AmtBFUD": "bf", "AmtAdjOptTaxUs115BAA": "baa", "AmtDeprSOCY": "used", "BalCFNY": "left",
                                            "AmtBFUAllow": "zero", "AmtAllowSOCY": "zero", "AllowBalCFNY": "zero"})
for k_, v_ in [("CurrAssYr", "ay"), ("CurBalCFNY", "cy"), ("TotBFUDepritAmt", "bf"), ("TotCurYrdepritSetoffInc", "used"), ("TotDepritBalCFNY", "left"),
               ("TotalBalCFNY", "all")]:
    R("ITRScheduleUD." + k_, "co.ud_total." + v_, skip_zero=True)
TI = "PartB-TI."
for k_, v_ in [("IncomeFromHP", "hp"), ("ProfBusGain.ProfGainNoSpecBus", "bp"), ("ProfBusGain.TotProfBusGain", "bp"),
               ("CapGain.ShortTerm.ShortTerm20Per", "stcg20"), ("CapGain.ShortTerm.ShortTermAppRate", "st_app"), ("CapGain.ShortTerm.TotalShortTerm", "st"),
               ("CapGain.LongTerm.LongTerm12_5Per", "lt125"), ("CapGain.LongTerm.TotalLongTerm", "lt"), ("CapGain.ShortTermLongTermTotal", "cg"),
               ("CapGain.TotalCapGains", "cg"), ("IncFromOS.OtherSrcThanOwnRaceHorse", "os"), ("IncFromOS.TotIncFromOS", "os"), ("TotalTI", "total"),
               ("CurrentYearLoss", "cy_loss"), ("BalanceAfterSetoffLosses", "after_cyla"), ("BroughtFwdLossesSetoff", "bf"), ("GrossTotalIncome", "gti"),
               ("IncChargeTaxSplRate111A112", "special"), ("DeductionsUndSchVIADtl.PartBchapterVIA", "via_b"), ("DeductionsUndSchVIADtl.PartCchapterVIA", "via_c"),
               ("DeductionsUndSchVIADtl.TotDeductUndSchVIA", "via"), ("TotalIncome", "income"), ("IncChargeableTaxSplRates", "special"),
               ("IncChargeableTaxNormalRates", "normal"), ("LossesOfCurrentYearCarriedFwd", "cf"), ("DeemedTotIncSec115JB", "deemed")]:
    R(TI + k_, "co.ti." + v_)
TT = "PartB_TTI.ComputationOfTaxLiability."
for k_, v_ in [("TaxPayableOnDeemedTI.TaxDeemedTISec115JB", "co.tti.mat_tax"), ("TaxPayableOnDeemedTI.Surcharge", "co.tti.mat_sur"),
               ("TaxPayableOnDeemedTI.EducationCess", "co.tti.mat_cess"), ("TaxPayableOnDeemedTI.TotalTax", "co.tti.mat_total"),
               ("TaxPayableOnTI.TaxAtNormalRates", "co.tti.at_normal"), ("TaxPayableOnTI.TaxAtSpecialRates", "co.tti.at_special"),
               ("TaxPayableOnTI.TaxPayableOnTotInc", "co.tti.tax"), ("TaxPayableOnTI.SurchargeOnTaxPayable", "co.tti.sur"),
               ("TaxPayableOnTI.TotalSurcharge", "co.tti.sur"), ("TaxPayableOnTI.EducationCess", "co.tti.cess"), ("TaxPayableOnTI.GrossTaxLiability", "co.tti.liab"),
               ("GrossTaxPayable", "co.tti.gross"), ("CredUs115JAATaxPaid", "co.tti.credit"), ("TaxPayableAfterCredUs115JAA", "co.tti.after_credit"),
               ("NetTaxLiability", "co.tti.net"), ("IntrstPay.IntrstPayUs234A", "tax.i234a"), ("IntrstPay.IntrstPayUs234B", "tax.i234b"),
               ("IntrstPay.IntrstPayUs234C", "tax.i234c"), ("IntrstPay.TotalIntrstPay", "tax.interest"), ("AggregateTaxInterestLiability", "tax.aggregate")]:
    R(TT + k_, v_)
for k_, v_ in [("TaxPaid.TaxesPaid.AdvanceTax", "tax.advance"), ("TaxPaid.TaxesPaid.TDS", "tax.tds"), ("TaxPaid.TaxesPaid.SelfAssessmentTax", "tax.sat"),
               ("TaxPaid.TaxesPaid.TotalTaxesPaid", "tax.paid"), ("TaxPaid.BalTaxPayable", "tax.payable"), ("Refund.RefundDue", "tax.refund"),
               ("Refund.BankAccountDtls.BankDtlsFlag", "has_banks"), ("AssetOutsideIndiaFlg", "=NO")]:
    R("PartB_TTI." + k_, v_)
EACH("PartB_TTI.Refund.BankAccountDtls.AddtnlBankDetails", "banks", {"IFSCCode": "ifsc", "BankName": "bank", "BankAccountNo": "account", "AccountType": "type",
                                                                      "UseForRefund": "refund"})
MT = "ScheduleMAT."
R(MT + "PLAcntPrepSchedVICompAct", "co.mat.sched_vi")
R(MT + "PLAcntPrepAsperAGM", "co.mat.agm")
R(MT + "ProfAfterTaxPLAcnt", "co.mat.pat")
for item, spec in MAT_ITEMS.items():
    if item != "pat":
        R(MT + spec["key"], "co.mat." + item)
for k_, v_ in [("Additions.TotAdditions", "add_total"), ("Deducts.TotDeducts", "less_total"), ("BookProfUs115JB", "book"), ("DeemedTotalIncUs115JB", "book"),
               ("DeemedTotalIncUs115JBOther", "book"), ("TaxPayableUs115JB", "tax")]:
    R(MT + k_, "co.mat." + v_)
MC = "ScheduleMATC."
for k_, v_ in [("TaxUs115JBCurrAssYr", "tax_jb"), ("TaxOthProvCurrAssYr", "tax_other"), ("AmtOfTaxWithCred", "with_credit"), ("CurAssYr", "cur_ay"),
               ("MATCredGrossCurAY", "gross_cur"), ("BalMATCredCFCurAY", "bal_cur"), ("TotMatCredGross", "tot_gross"), ("TotMatCredSetOff", "tot_setoff"),
               ("TotMatCredBF", "tot_bf"), ("TotMatCredUtilCurrYr", "tot_used"), ("TotBalMATCredCF", "tot_bal"), ("AmtTaxCredUs115JAA", "used"),
               ("AmtMATLiabAllAssYrAvailSubseqYr", "cf")]:
    R(MC + k_, "co.matc." + v_)
EACH(MC + "UtilMATCredAvl", "co.matc.rows", {"AssYr": "ay", "MATCredGross": "gross", "MATCredSetOff": "setoff", "MATCredBF": "bf", "MATCredUtilCurrYr": "used",
                                              "BalMATCredCF": "left"})
EACH("ScheduleSI.SplCodeRateTax", "co.si", {"SecCode": "code", "SplRatePercent": "rate", "SplRateInc": "income", "SplRateIncTax": "tax"})
R("ScheduleSI.TotSplRateInc", "co.si_total.income", skip_zero=True)
R("ScheduleSI.TotSplRateIncTax", "co.si_total.tax", skip_zero=True)
G80T = {"100": ("Don100Percent", ["TotDon100PercentCash", "TotDon100PercentOtherMode", "TotDon100Percent", "TotElgDon100Percent"]),
        "50": ("Don50PercentNoApprReqd", ["TotDon50PercentNoApprReqdCash", "TotDon50PercentNoApprReqdOtherMode", "TotDon50PercentNoApprReqd", "TotElgDon50PercentNoApprReqd"]),
        "100q": ("Don100PercentApprReqd", ["TotDon100PercentApprReqdCash", "TotDon100PercentApprReqdOtherMode", "TotDon100Percent", "TotElgDon100Percent"]),
        "50q": ("Don50PercentApprReqd", ["TotDon50PercentApprReqdCash", "TotDon50PercentApprReqdOtherMode", "TotDon50PercentApprReqd", "TotElgDon50PercentApprReqd"])}
for cat, (blk, tots) in G80T.items():
    EACH(f"Schedule80G.{blk}.DoneeDetail", f"co.g80.{cat}.rows", {"DoneeName": "name", "DoneePAN": "pan", "AddressDetail.AddrDetail": "addr",
                                                                  "AddressDetail.CityOrTownOrDistrict": "city", "AddressDetail.StateCode": "state", "AddressDetail.PinCode": "pin",
                                                                  "DonationAmtCash": "cash", "DonationAmtOtherMode": "other", "DonationAmt": "amount",
                                                                  "DonationElgAmt": "eligible"})
    for k_, v_ in zip(tots, ("cash", "other", "total", "eligible")):
        R(f"Schedule80G.{blk}.{k_}", f"co.g80.{cat}.{v_}", skip_zero=True)
for k_, v_ in [("TotalDonationsUs80GCash", "cash"), ("TotalDonationsUs80GOtherMode", "other"), ("TotalDonationsUs80G", "total"), ("TotalEligibleDonationsUs80G", "eligible")]:
    R("Schedule80G." + k_, "co.g80_total." + v_, skip_zero=True)
for blk in ("UsrDeductUndChapVIA", "DeductUndChapVIA"):
    for k_, v_ in [("Section80G", "s80g"), ("Section80M", "s80m"), ("Section80M_OS", "m_os"), ("TotPartBchapterVIA", "b"), ("TotPartCchapterVIA", "c"),
                   ("TotalChapVIADeductions", "total")]:
        R(f"ScheduleVIA.{blk}.{k_}", "co.via." + v_, skip_zero=True)
EACH("ScheduleTDS2.TDSOthThanSalaryDtls", "tds", {"TDSCreditName": "=S", "TANOfDeductor": "tan", "TDSSection": "section", "TaxDeductCreditDtls.TaxDeductedOwnHands": "tax",
                                                  "TaxDeductCreditDtls.TaxClaimedOwnHands": "tax", "GrossAmount": "gross", "HeadOfIncome": "head", "AmtCarriedFwd": "#0"})
R("ScheduleTDS2.TotalTDSonOthThanSals", "tax.tds")
EACH("ScheduleIT.TaxPayment", "challans", {"BSRCode": "bsr", "DateDep": "date", "SrlNoOfChaln": "serial", "Amt": "amount"})
R("ScheduleIT.TotalTaxPayments", "tax.challans")
for k_, v_ in [("AssesseeVerName", "co.gen.signer"), ("FatherName", "co.gen.signer_father"), ("AssesseeVerPAN", "co.gen.signer_pan"), ("Capacity", "co.gen.capacity"),
               ("Place", "client.city"), ("Date", "today")]:
    R("Verification.Declaration." + k_, v_)
c = load("itr.map")
forms = next(p for p in c["params"] if p["name"] == "forms")["default"]
forms["ITR-6"] = ROWS
save(c, f"ITR-6 for a company ({len(ROWS)} rows, built by tools/make_itr6_chips.py and checked against the schema's paths): Part A-GEN 1 and 2 (CIN, "
        "kind, the 115BA / 115BAA / 115BAB option and its Form 10-IB/IC/ID, turnover band, audit, 92E, key persons, holders of 10%+, nature of business), "
        "Schedule SH-1, Schedule BP (the company's computation statement), DPM / DOA / DEP (each block), OS, CG totals, CYLA, BFLA, CFL, UD, Part B-TI and TTI "
        "(MAT on deemed income, credit u/s 115JAA), MAT, MATC, SI, 80G (each donee), VI-A (80G, 80M), TDS2, IT, bank and verification by the signing director. "
        "The balance sheet and P&L come from chip itr.books (ITR-6 form_items). Left to the utility: Schedule CG's asset-wise rows, AL, OI, QD, GST, FA, TPSA.")
print("part 5 done", len(ROWS), "rows")


# =================================================================================================================================
# part 6 - the rule book (chip rulebook.sections) and the Compute & close walk (chip guide.compute)
# =================================================================================================================================
RULES6 = [
    {"chip": "company.rate", "area": "ca", "law": "Finance Act 2026, First Schedule Part I-A Para E (AY 2026-27); ss.115BA, 115BAA, 115BAB; s.115JB(5A)",
     "plain": "A domestic company's rate from its option: normal provisions 25% when the total turnover or gross receipts of the PY 2023-24 did not exceed 400 crore, "
              "else 30% (a turnover not typed counts as above, and the screen says so); 115BA 25%; 115BAA 22%; 115BAB 15% on the manufacturing business and 22% on other "
              "income. Under 115BAA / 115BAB: a flat 10% surcharge, no MAT, no additional depreciation, only 80JJAA / 80M / 80LA(1A) of Chapter VI-A.",
     "gaps": "115BAB's 15% is applied to the whole business income (the Act: income derived from or incidental to manufacturing); short-term gains on non-depreciable assets at 22% are not split out."},
    {"chip": "company.tax", "area": "ca", "law": "First Schedule Part I-A Paras E and F (surcharge, marginal relief); ss.111A, 112, 112A; Health and Education Cess; s.288B",
     "plain": "Tax on the total income: the option's rate on normal income, 20% on STCG u/s 111A, 12.5% on LTCG u/s 112A above 1.25 lakh and u/s 112; surcharge 7% above 1 crore "
              "and 12% above 10 crore with marginal relief (or a flat 10% under 115BAA / 115BAB); 4% cess; rounded to 10.",
     "gaps": "Marginal relief takes the income above the band's edge at the main rate (the usual case); a company whose special-rate gains straddle the edge should be checked by hand."},
    {"chip": "company.mat", "area": "ca", "law": "s.115JB (15% of book profit; Explanation 1 adjustments, Form 29B); s.115JAA (credit, 15 AYs); CBDT Circular 29/2019",
     "plain": "When the normal tax is below 15% of the book profit (with its own surcharge and cess), that MAT is the tax and the excess becomes a MAT credit; in a year the normal "
              "tax is higher, brought-forward credit is set off up to the difference, oldest first. No MAT and no credit under 115BAA / 115BAB. Book profit comes from rows "
              "tagged ITR6 MAT <item> (Form 29B); without them, from the P&L's profit before tax - and the screen says so.",
     "gaps": "Form 29B itself (the CA's report) is not produced; Ind AS transition adjustments (s.115JB(2A)-(2C)) are not worked out. The Finance Bill 2026's MAT changes (14%, MAT as final tax) apply from tax year 2026-27 under the Income-tax Act 2025, not to AY 2026-27."},
    {"chip": "company.dep_block", "area": "ca", "law": "s.32(1)(ii) and rule 5 / Appendix I; 2nd proviso to s.32(1) (under 180 days); s.32(1)(iia) and its 3rd proviso; s.50",
     "plain": "Each block from the fixed-asset schedule (rows tagged ITR6 DEP <block>): opening WDV + additions - sales; half rate on additions used under 180 days; additional 20% "
              "on new plant and machinery of a manufacturing company (half now, half next year); sales above the block are a short-term gain u/s 50.",
     "gaps": "Additional depreciation for the specified backward areas (35%, s.32(1)(iia) proviso), SLM for power units (s.32(1)(i)) and s.43(6)(c) adjustments for a block that ceases are not worked out."},
    {"chip": "company.loss_ok", "area": "ca", "law": "ss.72(3), 32(2), 79(1)(a), 80 / 139(3), 115JAA(3A)",
     "plain": "A brought-forward business loss is used only within 8 AYs, only when that year's return was in time, and - for a closely held company - only when 51% of the voting power "
              "stayed with the same holders; unabsorbed depreciation without limit; MAT credit within 15 AYs.",
     "gaps": "s.79(1)(b) (an eligible start-up whose original holders stay) and the s.79(2) exceptions (death, gift to a relative, amalgamation of a foreign company) are not taken; type s.79 as held when they apply."},
    {"chip": "company.setoff", "area": "ca", "law": "ss.70-74, 71(3A)",
     "plain": "One loss against one income, never more than either: a house-property loss up to 2 lakh, a business loss against other heads (normal-rate income first), brought-forward "
              "business loss against business income only, unabsorbed depreciation against any head, short-term capital loss against any gain, long-term loss against long-term gains.", "gaps": ""},
    {"chip": "company.d80g", "area": "ca", "law": "s.80G (incl. the 10% qualifying limit, s.80G(4)); proviso to s.80G(2)(iiihk)/(iiihl); s.115BAA(2)(ii)",
     "plain": "Donations without a limit at 100% / 50%; those within the qualifying limit together at most 10% of the adjusted gross total income; CSR contributions to the Swachh "
              "Bharat Kosh / Clean Ganga Fund get nothing; none under 115BAA / 115BAB.",
     "gaps": "Whether other CSR donations get 80G is contested; the category chosen on the row (ITR6 80G <category>) is the CA's call."},
    {"chip": "company.d80m", "area": "ca", "law": "s.80M",
     "plain": "Dividend received from another domestic company, a foreign company or a business trust is deducted up to the dividend the company itself distributed on or before one month "
              "prior to the due date of its return. Allowed under 115BAA / 115BAB too.", "gaps": ""},
    {"chip": "company.problem", "area": "ca", "law": "Companies Act 2013 (CIN, DIN); s.115BAB(2)",
     "plain": "A company client's master data is checked: the CIN in the MCA's 21-character shape, 8-digit DINs, shareholdings 0-100% and not over 100% together, and 115BAB only for a "
              "manufacturing company.", "gaps": ""}]
c = load("rulebook.sections")
rules = next(p for p in c["params"] if p["name"] == "rules")["default"]
have = {r["chip"] for r in rules}
for r in RULES6:
    if r["chip"] not in have:
        at = max(i for i, x in enumerate(rules) if x["area"] == "ca") + 1
        rules.insert(at, r)
    else:
        rules[[x["chip"] for x in rules].index(r["chip"])] = r
for r in rules:                                                   # close.dates now names the company's date
    if r["chip"] == "close.dates" and "a company" not in r["plain"]:
        r["plain"] = r["plain"].replace("audit 31 October;", "audit 31 October - and always for a company (ITR-6);")
save(c, "nine rules for a company's return (ITR-6): company.rate, company.tax, company.mat, company.dep_block, company.loss_ok, company.setoff, "
        "company.d80g, company.d80m, company.problem - each with what it does not cover yet.")

c = load("guide.compute")
steps = next(p for p in c["params"] if p["name"] == "steps")["default"]
STEP = {"title": "A company (ITR-6)", "say": "For a company, its own section: the option's rate and surcharge, depreciation block by block, losses set off and carried "
        "(8 years, s.79, unabsorbed depreciation), MAT against the normal tax and the MAT credit, 80M and 80G - and below, the year's facts to type: the earlier "
        "year's turnover, losses and credit brought forward, dividends paid.", "target": "#co-card|.cc-comp"}
if not any(s["title"] == STEP["title"] for s in steps):
    steps.insert(next(i for i, s in enumerate(steps) if s["title"] == "The computation") + 1, STEP)
c["params"][[p["name"] for p in c["params"]].index("steps")]["default"] = steps
save(c, "a company's section (ITR-6).")
print("part 6 done")


# =================================================================================================================================
# part 7 - Chip Chat's answers (chip chat.faq) and the Clients & years walk (chip guide.clients)
# =================================================================================================================================
CO_ROLES = []
FAQ6 = [
    {"id": "company_how", "q": "How do I file a company's return (ITR-6)?",
     "words": "company return itr-6 itr6 private limited pvt ltd domestic company corporate file a company how to file company",
     "a": "Clients & years > New client, status Company (the PAN's fourth letter is C): CIN, date of incorporation, kind, tax option (normal, 115BA, 115BAA, 115BAB), "
          "directors and shareholders. Then Intake & map (final accounts, computation of income, fixed-asset schedule - refs ITR6 PL / BS / BP / DEP / MAT), "
          "Reconcile (26AS) and Compute & close: its company section works out depreciation, losses, MAT and its credit, and the ITR-6 JSON comes out checked "
          "against the CBDT schema.", "roles": CO_ROLES, "go": "#/clients", "live": ""},
    {"id": "company_rate", "q": "What is the tax rate for a company?",
     "words": "company tax rate corporate tax rate 25 30 percent 22 15 115baa 115bab 115ba surcharge 7 12 percent 400 crore turnover",
     "a": "AY {ay}, a domestic company: 25% when the turnover of the year 2023-24 was within 400 crore, else 30%; surcharge 7% above 1 crore and 12% above 10 crore "
          "(with marginal relief); 4% cess. Under 115BAA 22%, under 115BAB 15% - each with a flat 10% surcharge, no MAT and only 80JJAA / 80M / 80LA(1A).",
     "roles": CO_ROLES, "go": "#/compute", "live": ""},
    {"id": "company_mat", "q": "How is MAT worked out for a company?",
     "words": "mat minimum alternate tax 115jb book profit mat credit 115jaa form 29b 15 percent",
     "a": "When the normal tax is less than 15% of the book profit (plus surcharge and cess), that MAT is the tax and the difference becomes a MAT credit for 15 years; "
          "in a year the normal tax is higher, the credit is set off up to the difference. Tag the Form 29B rows ITR6 MAT pat / add_tax / less_bf ...; without them "
          "the P&L profit before tax is used and the screen says so. No MAT under 115BAA / 115BAB.", "roles": CO_ROLES, "go": "#/compute", "live": ""},
    {"id": "company_losses", "q": "Does a company keep its losses when the shareholding changes?",
     "words": "section 79 shareholding change 51 percent voting power company loss carry forward lost unabsorbed depreciation lapse 8 years",
     "a": "A closely held company keeps a brought-forward business loss only if 51% of the voting power stayed with the same holders (s.79), the loss is within 8 years "
          "and that year's return was in time. Unabsorbed depreciation is not hit by s.79 and has no time limit. Tick or untick the s.79 box in the company's year "
          "on Compute & close.", "roles": CO_ROLES, "go": "#/compute", "live": ""},
    {"id": "company_due", "q": "When is a company's return due?",
     "words": "company due date itr-6 deadline last date company return 31 october 30 november 3ceb transfer pricing",
     "a": "31 October for every company, audited under 44AB or not (s.139(1)); 30 November when a Form 3CEB is due. A CBDT extension of the audit date for the year "
          "applies to companies too; the ITR-6 JSON still names the Act's date.", "roles": CO_ROLES, "go": "#/compute", "live": ""},
    {"id": "company_csr", "q": "Is CSR expenditure deductible?",
     "words": "csr corporate social responsibility deduction deductible disallowed added back 37 80g kosh ganga",
     "a": "No as a business expense: CSR spent under s.135 of the Companies Act is added back (Explanation 2 to s.37(1)) - tag it ITR6 BP csr. A CSR contribution to "
          "the Swachh Bharat Kosh or the Clean Ganga Fund gets no 80G either (ITR6 80G csr_kosh).", "roles": CO_ROLES, "go": "#/compute", "live": ""}]
c = load("chat.faq")
rows = next(p for p in c["params"] if p["name"] == "rows")["default"]
ids = [r["id"] for r in rows]
for r in FAQ6:
    if r["id"] in ids:
        rows[ids.index(r["id"])] = r
    else:
        rows.append(r)
for r in rows:
    if r["id"] == "other_forms":
        r["a"] = ("ITR-1, ITR-2, ITR-3 and ITR-4 (My return, and ITR-3 on the CA side too), ITR-5 (firms, LLPs, AOPs) and ITR-6 (companies), plus Form "
                  "3CA/3CB-3CD for a tax audit. ITR-7 (trusts) is not prepared here.")
    if r["id"] == "wizard_company":            # New filing still shows a company as not yet; Clients & years files it
        r["q"] = "Can I file a trust's return?"
        r["words"] = "trust itr-7 itr7 charitable trust religious trust society institution section 11 not yet new filing"
        r["a"] = ("A trust (ITR-7): not yet - New filing shows it as Not yet; meanwhile file the trustees' own returns, the card offers that in one press. "
                  "A company (ITR-6) is filed from Clients & years: status Company, then Intake & map, Reconcile and Compute & close.")
save(c, "six questions about a company's return (ITR-6): how, the rate, MAT, losses and s.79, the due date, CSR; which forms are prepared now includes ITR-6; "
        "the not-yet row is about trusts (a company is filed from Clients & years).")

c = load("guide.clients")
steps = next(p for p in c["params"] if p["name"] == "steps")["default"]
STEP = {"title": "A company", "say": "Status Company - the PAN's fourth letter C - opens its own box: CIN, date of incorporation, kind and tax option (normal, 115BA, "
        "115BAA or 115BAB), the directors who sign and the shareholders of 1% or more. ITR-6's Part A-GEN and Schedule SH come from here.", "target": "#cl-new"}
if not any(s["title"] == STEP["title"] for s in steps):
    steps.insert(next(i for i, s in enumerate(steps) if s["title"] == "A new client") + 1, STEP)
save(c, "a company's box (ITR-6).")
print("part 7 done")
