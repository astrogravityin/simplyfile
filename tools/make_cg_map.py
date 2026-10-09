"""2026-10-07 My return, wave 3 (second half): the knobs, words and department-JSON places for capital gains in full - Schedule 112A,
Schedule CG (A / B / D / E / F), CYLA / BFLA, Schedule CFL, Schedule TDS3 (194IA), gifts in Schedule OS; the capital-gains
statement reader (CAMS / KFintech / a broker's tax P&L), the AIS's 194IA / SFT-012 lines, last year's return (Schedule CFL).
Re-runnable: knobs and words are set to these values each run; the ITR-2 rows it owns are replaced each run.
Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/make_cg_map.py"""
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
    if note and note not in c.get("description_nl", ""):
        c["description_nl"] = c.get("description_nl", "") + " " + NOTE + note
    (CH / f"{c['chip_id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", c["chip_id"], "v", c["version"])


def knob(c, name, default, label):
    """A knob on a record chip that hands its params back: param, field, and the no-args test."""
    for p in c["params"]:
        if p["name"] == name:
            p["default"] = default
            break
    else:
        c["params"].append({"name": name, "type": "text" if isinstance(default, str) else "number" if isinstance(default, (int, float)) and not isinstance(default, bool)
                            else "boolean" if isinstance(default, bool) else "json", "default": default, "label": label})
        if c["expr"].get("vop") == "record" and all(isinstance(v, str) and v.startswith("$") for v in c["expr"]["fields"].values()):
            c["expr"]["fields"][name] = "$" + name
    for t in c["test_cases"]:
        if isinstance(t.get("expect_value"), dict) and not t.get("args") and name in c["expr"].get("fields", {}):
            t["expect_value"][name] = default


# --- 1 myreturn.json: the department's codes and the places Schedule CFL keeps --------------------------------------------------
js = load("myreturn.json")
for k2, v, lbl in [
    ("gift_code", "OTH", "ITR-1 / ITR-4 Schedule OS: gifts (s.56(2)(x)) go in as any other income"),
    ("gift_words", "Gifts taxable u/s 56(2)(x)", "ITR-1 / ITR-4 Schedule OS: the words beside the gifts"),
    ("tds3_sections", ["4IA", "4-IA", "4IB", "4-IB", "94M", "94S"], "TDS a buyer or tenant deducts on Form 26QB / 26QC / 26QD / 26QE - Schedule TDS3, not TDS2"),
    ("tds3_head", "CG", "Schedule TDS3: 194IA (property sold) is capital gains"),
    ("mf_111a_code", "1A", "Schedule CG A2: 111A (shares / equity fund units, STT paid)"),
    ("share_before", {"true": "BE", "false": "AE"}, "Schedule 112A: bought on or before 31 January 2018 (BE) or after (AE)"),
    ("isin_none", "INNOTREQUIRD", "Schedule 112A: the department's ISIN for a line with none"),
    ("typed_name", "Total of 112A gains typed on Review", "Schedule 112A: the line for a total typed without the scrips"),
    ("country_india", "91", "Schedule CG: the buyer's country (India)"),
    ("cfl_blocks", ["LossCFFromPrevYrToAY", "LossCFFromPrev2ndYearFromAY", "LossCFFromPrev3rdYearFromAY", "LossCFFromPrev4thYearFromAY",
                    "LossCFFromPrev5thYearFromAY", "LossCFFromPrev6thYearFromAY", "LossCFFromPrev7thYearFromAY", "LossCFFromPrev8thYearFromAY"],
     "Schedule CFL: the eight earlier years, last year first"),
    ("cfl_fields", {"stcl": "TotalSTCGPTILossCF", "ltcl": "TotalLTCGPTILossCF", "hp": "TotalHPPTILossCF"}, "Schedule CFL: short-term, long-term and house-property loss"),
    ("cfl_detail", "CarryFwdLossDetail", "Schedule CFL: a year's block"), ("cfl_date", "DateOfFiling", "Schedule CFL: the date that year's return was filed"),
    ("cfl_date_default", "07-31", "Schedule CFL: a year's filing date when none is typed - that year's 31 July"),
    ("cfl_summary", "LossSummaryDetail", "Schedule CFL: a total's block"), ("cfl_bf_total", "TotalOfBFLossesEarlierYrs", "Schedule CFL: brought forward"),
    ("cfl_adjusted", "AdjTotBFLossInBFLA", "Schedule CFL: set off this year (Schedule BFLA)"), ("cfl_current", "CurrentAYloss", "Schedule CFL: this year's loss"),
    ("cfl_total", "TotalLossCFSummary", "Schedule CFL: carried forward to next year")]:
    knob(js, k2, v, lbl)
save(js, "capital gains: Schedule 112A (BE / AE, INNOTREQUIRD), 111A code, Schedule CFL's blocks and fields, Schedule TDS3 sections (26QB ...), gifts in ITR-1 / ITR-4.")

# --- 2 myreturn.settings: how many rows, last year's Schedule CFL ------------------------------------------------------------------
st = load("myreturn.settings")
knob(st, "cg_max", 300, "sales typed on Review, at most")
knob(st, "losses_max", 40, "losses brought forward typed, at most")
knob(st, "gifts_max", 40, "gifts typed, at most")
opk = next(p for p in st["params"] if p["name"] == "one_per_kind")["default"]
knob(st, "one_per_kind", opk + [x for x in ["filed_prev"] if x not in opk], "one document of these kinds")
knob(st, "from_prev", {"cfl": "ScheduleCFL", "detail": "CarryFwdLossDetail", "summary": "LossSummaryDetail", "filed": "DateOfFiling",
                       "adjusted": "AdjTotBFLossInBFLA", "current": "CurrentAYloss",
                       "fields": {"stcl": "TotalSTCGPTILossCF", "ltcl": "TotalLTCGPTILossCF", "hp": "TotalHPPTILossCF"},
                       "date": ["Verification.Date", "PartA_GEN1.FilingStatus.OrigRetFiledDate"]},
     "last year's filed return: where its Schedule CFL keeps each year's loss, what it set off, its own loss, and the day it was filed")
save(st, "cg_max / losses_max / gifts_max; filed_prev (last year's return) is one document; from_prev - its Schedule CFL.")

# --- 3 myreturn.checks: the AIS's sales beside the rows ---------------------------------------------------------------------------
ck = load("myreturn.checks")
tol = next(p for p in ck["params"] if p["name"] == "tolerance")
tol["default"] = tol["default"] | {"cg_sales": 1000, "property": 1000}
save(ck, "cg_sales (AIS SFT-017 / 018 sales of shares and fund units against the rows) and property (194IA / SFT-012 against the property sold), 1,000 apart is the same.")

# --- 4 myreturn.read: the capital-gains statement; the AIS's property lines ------------------------------------------------------
rd = load("myreturn.read")
codes = next(p for p in rd["params"] if p["name"] == "ais_codes")["default"]
codes = [c for c in codes if c.get("field") not in ("property_tds", "property_sft")]
codes = [{"code": "TDS-194IA.*", "field": "property_tds"}, {"code": "SFT-012.*", "field": "property_sft"},
         {"title": "transfer of (certain )?immovable property", "field": "property_tds"}] + codes
knob(rd, "ais_codes", codes, "AIS information codes -> the return's fields")
knob(rd, "cg_statement", {
    "words": ["isin", "capital gain", "scheme name", "scrip", "redemption", "sale value", "sell value", "long term", "short term", "tax p&l", "realised"],
    "cols": {"isin": ["isin"],
             "fmv": ["fair market value", "fmv", "market value as on 31", "nav as on 31", "price as on 31", "grandfathered", "31/01/2018", "31-01-2018", "31.01.2018"],
             "sold": ["sale date", "sell date", "redemption date", "date of sale", "date of transfer", "transfer date", "date of redemption", "sold on"],
             "acquired": ["purchase date", "buy date", "date of acquisition", "acquisition date", "date of purchase", "bought on"],
             "sale": ["sale value", "sell value", "redemption amount", "redemption value", "sale consideration", "full value of consideration", "sale amount",
                      "sell amount", "sales value", "consideration"],
             "cost": ["purchase value", "buy value", "cost of acquisition", "purchase amount", "acquisition cost", "buy amount", "purchase cost", "cost"],
             "units": ["units", "quantity", "qty", "no. of shares", "shares"],
             "expenses": ["expenses", "brokerage", "charges", "transfer cost"],
             "category": ["asset class", "category", "scheme type", "fund type", "asset type", "type"],
             "name": ["scheme name", "scrip name", "security name", "stock name", "company name", "scheme", "scrip", "security", "symbol", "stock", "name", "description"]},
    "need": ["sale", "cost"], "need_one": ["isin", "name"],
    "per_unit_words": ["nav", "per unit", "price", "rate"],
    "skip_words": ["total", "grand total", "sub total", "subtotal"],
    "isin_pattern": "IN[0-9A-Z]{10}",
    "asset_words": {"debt_mf": ["debt", "liquid", "gilt", "money market", "overnight", "bond fund", "income fund", "corporate bond", "banking & psu", "short duration"],
                    "equity": ["equity", "elss", "index fund", "etf", "shares"]},
    "default_asset": "equity",
    "months": {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12},
    "two_digit_base": 2000, "two_digit_pivot": 50},
    "a broker's / registrar's capital-gains statement: the words that tell one, each column's heading words (the first column whose heading has "
    "one), which are needed, a debt fund by its words, the FMV on 31-01-2018 per unit when its heading says so, dates written dd-mm-yy")
save(rd, "AIS TDS-194IA (the buyer's TDS on a property sold: amount, TDS, the buyer's PAN) and SFT-012 (the sub-registrar's report); "
         "cg_statement - a CAMS / KFintech consolidated capital-gains statement or a broker's tax P&L (CSV / Excel), one row per sale.")

# --- 5 the words ----------------------------------------------------------------------------------------------------------------------
w = load("ui.myreturn")
WORDS = {
    "rv_cg_p2": "Each sale, from your broker's / CAMS / KFintech statement (drop it on Gather) or typed here. Anything other than 112A gains up to "
                "1.25 lakh - or any loss - makes it an ITR-2.",
    "cg_rows_h": "Sales you type", "cg_none": "None typed.", "cg_add": "Add a sale", "cg_remove": "Remove this sale",
    "cg_read_h": "{n} sales read from your statements", "cg_bucket": "Taxed as", "cg_gain_h": "Gain",
    "cg_assets": "equity=Listed shares / equity fund units (STT paid)|listed=Other listed securities (bonds, debentures)|debt_mf=Debt / other mutual fund units"
                 "|mld=Market-linked debentures|unlisted_bond=Unlisted bonds / debentures|land=Land or a plot|house=A house or flat|other=Anything else (unlisted shares, gold, art)",
    "f_cg_asset": "What was sold", "f_cg_name": "Name", "f_cg_isin": "ISIN", "f_cg_units": "Units / shares", "f_cg_acquired": "Bought on", "f_cg_sold": "Sold on",
    "f_cg_term": "Held", "cg_term_auto": "From the dates", "cg_term_long": "Long-term", "cg_term_short": "Short-term",
    "f_cg_sale": "Sale value", "f_cg_cost": "Cost (FMV on 1-4-2001 if bought before)", "f_cg_fmv": "FMV on 31-01-2018 (all units)", "f_cg_expenses": "Transfer expenses",
    "f_cg_stamp": "Stamp-duty value (s.50C)", "f_cg_improve": "Cost of improvement", "f_cg_improve_on": "Improved on", "f_cg_buyer": "Buyer",
    "f_cg_buyer_pan": "Buyer's PAN", "f_cg_address": "Property address", "f_cg_pin": "PIN", "f_cg_tds": "TDS by the buyer (194IA)",
    "f_cg_ex_kind": "Exemption", "ex_none": "None", "ex_54": "54 - a new house", "ex_54EC": "54EC - bonds (6 months, 50 lakh)", "ex_54F": "54F - a house, from another asset",
    "f_cg_ex_amount": "Invested (new house / bonds)", "f_cg_ex_on": "Invested on", "f_cg_cgas": "Capital Gains Account Scheme deposit", "f_cg_cgas_on": "Deposited on",
    "f_cg_cgas_acc": "CGAS account no.", "f_cg_cgas_ifsc": "CGAS bank IFSC", "f_cg_other_houses": "Other houses you own (54F)",
    "b_stcg_111a": "Short-term, 111A (20%)", "b_stcg_app": "Short-term, slab rates", "b_ltcg_112": "Long-term, 112 (12.5%)", "b_ltcg_112a": "Long-term, 112A (12.5% over 1.25 lakh)",
    "cg_gain": "gain {gain}", "cg_res_50aa": "short-term whatever the holding (s.50AA)", "cg_res_gf": "grandfathered: cost taken {cost}",
    "cg_res_50c": "stamp-duty value taken (s.50C): {value}", "cg_res_ex": "exempt {amount} (s.{kind})",
    "cg_res_choice": "tax without indexation at 12.5%: {plain}; with indexation at 20%: {indexed} - the lower, {chosen}, is used",
    "cg_chosen_plain": "without indexation", "cg_chosen_indexed": "with indexation",
    "ex_not_for": "This exemption is not for this kind of asset", "ex_short": "Exemptions are for long-term gains only", "ex_houses": "54F: not when you own more than one other house",
    "ex_no_gain": "No gain to exempt",
    "cg_sum_h": "The year's gains after losses are set off", "cg_sum_nil": "Nothing taxable after losses.",
    "cg_excess": "Indexation saves {amount} on the land / building (left out of the 112 tax)",
    "cg_cf": "Carried forward to next year: short-term loss {stcl}, long-term loss {ltcl} (8 years).",
    "cg_cf_late": "Filed after the due date: this year's capital loss ({stcl} short-term, {ltcl} long-term) cannot be carried forward (s.80).",
    "cg_totals_h": "Only totals, no detail (from a statement already added up)",
    "loss_h": "Losses brought forward", "loss_p": "Capital and house-property losses of the last 8 years not yet set off - from last year's return (its Schedule CFL). "
                                               "A short-term loss is set off against any capital gain, a long-term loss only against long-term gains, a house loss only against house income.",
    "f_loss_ay": "Year of the loss (AY)", "f_loss_kind": "Kind", "loss_stcl": "Short-term capital loss", "loss_ltcl": "Long-term capital loss", "loss_hp": "House-property loss",
    "f_loss_amount": "Amount still to set off", "f_loss_filed_on": "That year's return filed on", "loss_add": "Add a loss", "loss_none": "None typed.",
    "loss_prev": "Fill from last year's return", "loss_prev_how": "Drop last year's filed return (JSON) on Gather to fill these from its Schedule CFL.",
    "loss_gone": "AY {ay}: more than 8 years ago - it cannot be set off any more", "loss_used": "Set off this year: {amount}",
    "no_prev_losses": "Last year's filed return holds no loss to carry forward - or it is not on Gather yet.",
    "gift_h": "Gifts received", "gift_p": "Sums, property or valuables received free or for less (s.56(2)(x)). From a relative, on your marriage, by will or "
                                          "inheritance - not taxed. Others: sums and valuables over 50,000 in the year together, each property over 50,000.",
    "f_gift_from": "From", "f_gift_relation": "Relation", "f_gift_occasion": "Occasion", "f_gift_kind": "What", "f_gift_value": "Value (sum / stamp value / FMV)",
    "f_gift_paid": "You paid", "f_gift_on": "Received on", "gift_add": "Add a gift", "gift_none": "None typed.", "gift_total": "Taxed as other sources: {amount}",
    "gift_relations": "=Not a relative|spouse=Spouse|brother=Brother|sister=Sister|spouse_sibling=Spouse's brother / sister|parent_sibling=Parent's brother / sister"
                      "|lineal=Parent, grandparent, child, grandchild|spouse_lineal=Spouse's parent, grandparent, child|sibling_spouse=Spouse of any of these|huf_member=Member of the HUF",
    "gift_occasions": "=None|marriage=On your marriage|will=Under a will|inheritance=By inheritance|death=In contemplation of the giver's death",
    "gift_kinds": "money=A sum of money|property=Land or a building|movable=Shares, jewellery, art, other valuables",
    "f_pre_total": "Interest before it was finished (total)", "f_completed": "Bought / finished on",
    "c_cg_sales": "Shares and funds sold: your rows against the AIS", "c_property": "Property sold: your row against the AIS (194IA / SFT-012)",
    "k_cg": "Capital-gains statement", "k_cg_why": "Each sale of shares or fund units: dates, sale value, cost and the 31-01-2018 value - read into Schedule 112A and Schedule CG.",
    "k_cg_how": "Broker: back office > Reports > Tax P&L / Capital gains (Excel or CSV)|Mutual funds: CAMS (camsonline.com) or KFintech (mfs.kfintech.com) > "
                "Capital gains statement for FY 2025-26 (Excel)|Drop each one here",
    "k_filed_prev": "Last year's return", "k_filed_prev_why": "Its Schedule CFL: the losses still to carry forward into this year.",
    "k_filed_prev_how": "Sign in at incometax.gov.in|e-File > Income Tax Returns > View Filed Returns|Pick the AY before {ay} and download the JSON|Drop it here",
    "fd_cg_rows": "Sales read", "fd_cg_sale": "Total sale value", "no_cg_rows": "The statement's table was found, but no sale in it.",
    "fd_property_seen": "Property sold (194IA)", "fd_tds_194ia": "TDS by the buyer (194IA)", "fd_property_sft": "Property sold (SFT-012)",
}
for k2 in ("k_cg_how", "loss_prev_how"):   # 2026-10-08: wave 4 says these now (make_wave4_chips.py)
    WORDS.pop(k2, None)
for k2, v in WORDS.items():
    knob(w, k2, v, k2)
save(w, "capital gains in full: each sale, exemptions, the indexation choice, losses brought forward, gifts, pre-construction interest, the statements.")

# --- 6 the department's JSON: ITR-2 places ------------------------------------------------------------------------------------------
m = load("itr.map")
mp = m["params"][0]["default"]
OWN = "cg3"                                                    # the rows this script owns carry "by": "cg3"
old = mp["ITR-2"]
drop = lambda r: r.get("by") == OWN or (r["path"].startswith("ITR2.ScheduleCGFor23.") and "VDA" not in r["path"]) or any(r["path"].startswith(f"ITR2.{x}") for x in (  # noqa: E731
    "ScheduleCYLA.STCG20Per", "ScheduleCYLA.STCGAppRate", "ScheduleCYLA.LTCG12_5Per", "ScheduleBFLA.STCG20Per", "ScheduleBFLA.STCGAppRate",
    "ScheduleBFLA.LTCG12_5Per", "ScheduleBFLA.HP.", "PartB-TI.CapGain.ShortTerm", "PartB-TI.CapGain.LongTerm", "PartB-TI.CapGain.TotalCapGains",
    "PartB-TI.BalanceAfterSetoffLosses"))
keep = [r for r in old if not drop(r)]
print("  ITR-2 rows: kept", len(keep), "of", len(old))
sz = lambda path, src: {"path": path, "from": src, "skip_zero": True, "by": OWN}  # noqa: E731
fr = lambda path, src: {"path": path, "from": src, "by": OWN}  # noqa: E731
same = lambda fields: {f: f for f in fields}  # noqa: E731
CG = "ITR2.ScheduleCGFor23."
S112A = ["SaleValue112A", "CostAcqWithoutIndx112A", "AcquisitionCost112A", "LTCGBeforelowerB1B2112A", "FairMktValueCapAst112A", "ExpExclCnctTransfer112A",
         "Deductions112A", "Balance112A", "TotalBalance112A"]
ROWS112A = ["ShareOnOrBefore", "ISINCode", "ShareUnitName", "NumSharesUnits", "SalePricePerShareUnit", "TotSaleValue", "CostAcqWithoutIndx", "AcquisitionCost",
            "LTCGBeforelowerB1B2", "FairMktValuePerShareunit", "TotFairMktValueCapAst", "ExpExclCnctTransfer", "TotalDeductions", "Balance"]
ST_PROP = ["DateofPurchase", "DateofSale", "FullConsideration", "PropertyValuation", "FullConsideration50C", "AquisitCost", "ImproveCost", "ExpOnTrans", "TotalDedn",
           "Balance", "DeductionUs54B", "STCGonImmvblPrprty", "TrnsfImmblPrprty"]
LT_PROP = ["FullConsideration", "DateofPurchase", "DateofSale", "PropertyValuation", "FullConsideration50C", "AquisitCost", "AquisitCostIndex", "CostOfImprovements",
           "ExpOnTrans", "TotalDedn", "TotalDednForEiB", "Balance", "BalanceForEiB", "ExemptionOrDednUs54", "LTCGonImmvblPrprty", "LTCGonImmvblPrprtyBE",
           "TaxSec1121aiiB", "TaxSec1121a", "ExcessAmtSec1121a", "TrnsfImmblPrprty"]
C54 = ["DateofTransfer", "CostofNewResHouse", "DateofPurchase", "AmtDeposited", "DepositDate", "AccountNo", "IFSC", "AmtDeducted"]
new = [
    {"path": "ITR2.Schedule112A.Schedule112ADtls", "each": "cg112a_rows", "item": same(ROWS112A), "by": OWN},
    *[sz(f"ITR2.Schedule112A.{f}", f"s112a.{f}") for f in S112A],
    {"path": CG + "ShortTermCapGainFor23.SaleofLandBuild.SaleofLandBuildDtls", "each": "cg_st_prop", "item": same(ST_PROP), "by": OWN},
    {"path": CG + "ShortTermCapGainFor23.EquityMFonSTT", "each": "cg_mf111a", "item": {"MFSectionCode": "code", "EquityMFonSTTDtls": "dtls"}, "by": OWN},
    fr(CG + "ShortTermCapGainFor23.SaleOnOtherAssets", "cg_st_other"),
    sz(CG + "ShortTermCapGainFor23.TotalSTCG", "cgx.total_st"),
    {"path": CG + "LongTermCapGain23.SaleofLandBuild.SaleofLandBuildDtls", "each": "cg_lt_prop", "item": same(LT_PROP), "by": OWN},
    sz(CG + "LongTermCapGain23.SaleofLandBuild.TotalLTCGImmblPrprty", "cgx.lt_prop"),
    sz(CG + "LongTermCapGain23.SaleofLandBuild.TotalExcessTax", "cgx.excess"),
    fr(CG + "LongTermCapGain23.SaleOfEquityShareUs112A", "cg_eq112a"),
    fr(CG + "LongTermCapGain23.SaleofAssetNADtls.SaleofAssetNA", "cg_na"),
    sz(CG + "LongTermCapGain23.TotalLTCG", "cgx.total_lt"),
    sz(CG + "SumOfCGIncm", "cgx.sum_pre"),
    sz(CG + "TotScheduleCGFor23", "cgx.with_vda_pre"),
    {"path": CG + "DeducClaimInfo.DeducClaimDtlsUs54", "each": "cg_claims54", "item": same(C54), "by": OWN},
    {"path": CG + "DeducClaimInfo.DeducClaimDtlsUs54EC", "each": "cg_claims54ec", "item": same(["DateofTransfer", "AmtInvested", "DateofInvestment", "AmtDeducted"]), "by": OWN},
    {"path": CG + "DeducClaimInfo.DeducClaimDtlsUs54F", "each": "cg_claims54f", "item": same(C54), "by": OWN},
    sz(CG + "DeducClaimInfo.TotDeductClaim", "cgx.claims"),
    fr(CG + "CurrYrLosses", "cg_table_e"),
    fr(CG + "AccruOrRecOfCG.ShortTermUnder20Per", "cg_q20"),
    fr(CG + "AccruOrRecOfCG.ShortTermUnderAppRate", "cg_qapp"),
    fr(CG + "AccruOrRecOfCG.LongTermUnder12_5Per", "cg_qlt"),
    *[fr(f"ITR2.ScheduleCYLA.{b}.IncCYLA.{f}", src) for b, src in (("STCG20Per", "cgx.s20_pre"), ("STCGAppRate", "cgx.app_pre"), ("LTCG12_5Per", "cgx.lt_pre"))
      for f in ("IncOfCurYrUnderThatHead", "IncOfCurYrAfterSetOff")],
    *[fr(f"ITR2.ScheduleBFLA.{b}.IncBFLA.{f}", f"cgx.{src}") for b, pre, bf, post in (("STCG20Per", "s20_pre", "bf_s20", "s20"), ("STCGAppRate", "app_pre", "bf_app", "app"),
                                                                                      ("LTCG12_5Per", "lt_pre", "bf_lt", "lt"), ("HP", "hp_pos", "hp_bf", "hp_after"))
      for f, src in (("IncOfCurYrUndHeadFromCYLA", pre), ("BFlossPrevYrUndSameHeadSetoff", bf), ("IncOfCurYrAfterSetOffBFLosses", post))],
    fr("ITR2.ScheduleBFLA.TotalBFLossSetOff.TotBFLossSetoff", "cgx.bf_all"),
    fr("ITR2.PartB-TI.CapGain.ShortTerm.ShortTerm20Per", "cgx.s20_pre"),
    fr("ITR2.PartB-TI.CapGain.ShortTerm.ShortTermAppRate", "cgx.app_pre"),
    fr("ITR2.PartB-TI.CapGain.ShortTerm.TotalShortTerm", "cgx.short_pre"),
    fr("ITR2.PartB-TI.CapGain.LongTerm.LongTerm12_5Per", "cgx.lt_pre"),
    fr("ITR2.PartB-TI.CapGain.LongTerm.TotalLongTerm", "cgx.lt_pre"),
    fr("ITR2.PartB-TI.CapGain.ShortTermLongTermTotal", "cgx.sum_pre"),
    fr("ITR2.PartB-TI.CapGain.TotalCapGains", "cgx.with_vda_pre"),
    fr("ITR2.PartB-TI.BalanceAfterSetoffLosses", "gti_pre_bf"),
    fr("ITR2.PartB-TI.BroughtFwdLossesSetoff", "cgx.bf_all"),
    fr("ITR2.PartB-TI.LossesOfCurrentYearCarriedFwd", "cgx.cf_now"),
    fr("ITR2.ScheduleCFL", "cfl"),
    {"path": "ITR2.ScheduleTDS3.TDS3onOthThanSalDtls", "each": "tds3_rows", "by": OWN,
     "item": {"TDSCreditName": "=S", "PANOfBuyerTenant": "pan", "TDSSection": "section", "TaxDeductCreditDtls.TaxDeductedOwnHands": "tds",
              "TaxDeductCreditDtls.TaxClaimedOwnHands": "tds", "GrossAmount": "income", "HeadOfIncome": "head", "AmtCarriedFwd": "#0"}},
    sz("ITR2.ScheduleTDS3.TotalTDS3OnOthThanSal", "tds3.total"),
    *[sz(f"ITR2.ScheduleOS.IncOthThanOwnRaceHorse.{f}", f"os.gifts.{src}") for f, src in (
        ("Tot562x", "total"), ("Aggrtvaluewithoutcons562x", "money"), ("Immovpropwithoutcons562x", "property_free"), ("Immovpropinadeqcons562x", "property_less"),
        ("Anyotherpropwithoutcons562x", "movable_free"), ("Anyotherpropinadeqcons562x", "movable_less"))],
]
mp["ITR-2"] = keep + new
for tc in m["test_cases"]:
    if isinstance(tc.get("expect_value"), dict) and "forms" in tc["expect_value"] and not tc.get("args"):
        tc["expect_value"]["forms"] = mp
save(m, "ITR-2 capital gains in full: Schedule 112A per scrip; Schedule CG A1 / A2 / A5 (land / building, 111A, other assets) and B1 / 112A / others "
        "(land / building with both computations and the excess tax), Table D (54 / 54EC / 54F with the CGAS deposit), Table E (this year's losses "
        "set off across rates), Table F (when the gains were made); CYLA / BFLA capital-gain and house rows, Part B-TI (losses brought forward, "
        "carried forward), Schedule CFL, Schedule TDS3 (194IA), gifts in Schedule OS (56(2)(x)).")
print("done")
