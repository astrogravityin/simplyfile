"""2026-10-07 My return, wave 3 (second half): the knobs, words and department-JSON places for residential status (FilingStatus),
foreign income (Schedule FSI / TR, Part B-TTI relief u/s 90 / 91), foreign assets (Schedule FA), clubbing (Schedule SPI, Schedule EI
10(32)), relief u/s 89 (Part B-TTI / ITR-1 / ITR-4 Section89) and the updated return card. Re-runnable: knobs and words are set to these
values each run; the rows this script owns (by "w3") are replaced each run, the rows it changes are changed to the same each run.
Then re-run tools/make_itr3_myreturn.py (ITR-3's My-return rows are made from the ITR-2 rows).
Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/make_wave3_map.py"""
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
    path = CH / f"{c['chip_id']}.json"
    before = json.loads(path.read_text(encoding="utf-8"))
    a, b = dict(before), dict(c)
    for x in (a, b):
        x.pop("version", None)
        x.pop("description_nl", None)
    if a == b:
        print("same", c["chip_id"])
        return
    c["version"] = before["version"] + 1
    if note and note not in c.get("description_nl", ""):
        c["description_nl"] = c.get("description_nl", "") + " " + NOTE + note
    path.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", c["chip_id"], "v", c["version"])


def knob(c, name, default, label):
    """A knob on a record chip that hands its params back: param, field, and the no-args test."""
    changed = True
    for p in c["params"]:
        if p["name"] == name:
            changed = p["default"] != default        # 2026-10-08: an unchanged word keeps its test's answer ({product} is filled there)
            p["default"] = default
            break
    else:
        c["params"].append({"name": name, "type": "text" if isinstance(default, str) else "number" if isinstance(default, (int, float)) and not isinstance(default, bool)
                            else "boolean" if isinstance(default, bool) else "json", "default": default, "label": label})
        if c["expr"].get("vop") == "record" and all(isinstance(v, str) and v.startswith("$") for v in c["expr"]["fields"].values()):
            c["expr"]["fields"][name] = "$" + name
    for t in c["test_cases"]:
        if isinstance(t.get("expect_value"), dict) and not t.get("args") and name in c["expr"].get("fields", {}) and changed:
            t["expect_value"][name] = default


# --- 1 myreturn.settings: the questions of residential status, how many rows ---------------------------------------------------
st = load("myreturn.settings")
NEWQ = {"days_fy": "", "days_4y": "", "citizen": False, "pio": False, "visiting": False, "left_for_job": False, "indian_income": "",
        "taxed_elsewhere": False, "nr_years": "", "days_7y": "", "res_country": "", "res_tin": ""}
qs = next(p for p in st["params"] if p["name"] == "questions")["default"]
knob(st, "questions", qs + [q for q in NEWQ if q not in qs], "questions")
ad = next(p for p in st["params"] if p["name"] == "answer_defaults")["default"]
knob(st, "answer_defaults", ad | {q: v for q, v in NEWQ.items() if q not in ad}, "answer defaults")
knob(st, "foreign_max", 40, "foreign income rows typed, at most")
knob(st, "fa_max", 60, "foreign assets typed, at most")
knob(st, "club_max", 20, "clubbed income rows typed, at most")
knob(st, "arrears_max", 15, "years of salary arrears typed (Form 10E), at most")
knob(st, "countries_from", "CountryCodeExcludingIndia", "the department's country list: the ITR-2 schema definition that holds it (code: name)")
save(st, "wave 3: residential-status questions (days in India this year / the 4 and 7 years before, years as a non-resident, citizen / person "
         "of Indian origin, visiting, left for a job, taxed elsewhere, income other than from foreign sources, country of residence and TIN); "
         "foreign_max / fa_max / club_max / arrears_max; countries_from.")

# --- 2 myreturn.json: the department's codes ---------------------------------------------------------------------------------------
js = load("myreturn.json")
FA_KINDS = {
    "bank": {"list": "DetailsForiegnBank", "map": {"Bankname": "name", "AddressOfBank": "address", "ZipCode": "zip", "ForeignAccountNumber": "account",
                                                    "OwnerStatus": "status", "AccOpenDate": "opened", "PeakBalanceDuringYear": "peak", "ClosingBalance": "closing",
                                                    "IntrstAccured": "income"}, "defaults": {"status": "OWNER"}, "values": {"status": {"DIRECT": "OWNER"}}},
    "custodial": {"list": "DtlsForeignCustodialAcc", "map": {"FinancialInstName": "name", "FinancialInstAddress": "address", "ZipCode": "zip", "AccountNumber": "account",
                                                            "Status": "status", "AccOpenDate": "opened", "PeakBalanceDuringPeriod": "peak", "ClosingBalance": "closing",
                                                            "GrossAmtPaidCredited": "income", "NatureOfAmount": "nature"}, "defaults": {"status": "OWNER", "nature": "N"},
                  "values": {"status": {"DIRECT": "OWNER"}}},
    "equity": {"list": "DtlsForeignEquityDebtInterest", "map": {"NameOfEntity": "name", "AddressOfEntity": "address", "ZipCode": "zip", "NatureOfEntity": "nature",
                                                               "InterestAcquiringDate": "opened", "InitialValOfInvstmnt": "cost", "PeakBalanceDuringPeriod": "peak",
                                                               "ClosingBalance": "closing", "TotGrossAmtPaidCredited": "income", "TotGrossProceeds": "proceeds"},
               "defaults": {"nature": "Company"}},
    "insurance": {"list": "DtlsForeignCashValueInsurance", "map": {"FinancialInstName": "name", "FinancialInstAddress": "address", "ZipCode": "zip",
                                                                  "ContractDate": "opened", "CashValOrSurrenderVal": "closing", "TotGrossAmtPaidCredited": "income"}},
    # 2026-10-10: Schedule FA table B - a financial interest in an entity abroad (a company, firm, LLP, partnership): the department's
    # DetailsFinancialInterest - nature of the entity, the interest (direct / beneficial owner / beneficiary), held since, investment, income from it
    "financial": {"list": "DetailsFinancialInterest", "map": {"ZipCode": "zip", "NatureOfEntity": "nature", "NameOfEntity": "name", "AddressOfEntity": "address",
                                                             "NatureOfInt": "status", "DateHeld": "opened", "TotalInvestment": "cost", "IncFromInt": "income",
                                                             "NatureOfInc": "inc_nature", "IncTaxAmt": "taxed", "IncTaxSch": "sch", "IncTaxSchNo": "sch_no"},
                  "defaults": {"status": "DIRECT", "nature": "Company", "inc_nature": "None", "sch": "NI"}, "values": {"status": {"OWNER": "DIRECT"}}},
    "property": {"list": "DetailsImmovableProperty", "map": {"ZipCode": "zip", "AddressOfProperty": "address", "Ownership": "status", "DateOfAcq": "opened",
                                                            "TotalInvestment": "cost", "IncDrvProperty": "income", "NatureOfInc": "nature", "IncTaxAmt": "taxed",
                                                            "IncTaxSch": "sch", "IncTaxSchNo": "sch_no"}, "defaults": {"status": "DIRECT", "nature": "Rent", "sch": "NI"},
                 "values": {"status": {"OWNER": "DIRECT"}}},
    "other": {"list": "DetailsOthAssets", "map": {"ZipCode": "zip", "NatureOfAsset": "name", "Ownership": "status", "DateOfAcq": "opened", "TotalInvestment": "cost",
                                                  "IncDrvAsset": "income", "NatureOfInc": "nature", "IncTaxAmt": "taxed", "IncTaxSch": "sch", "IncTaxSchNo": "sch_no"},
              "defaults": {"status": "DIRECT", "nature": "None", "sch": "NI"}, "values": {"status": {"OWNER": "DIRECT"}}},
    # 2026-10-08 wave 4: Schedule FA D-F as the person knows them - accounts with signing authority, trusts abroad, other income from outside India
    # ("flag" - is the income taxable and offered in this return: Y when an amount offered is typed - myreturn.wave3_facts)
    "signing": {"list": "DetailsOfAccntsHvngSigningAuth", "map": {"NameOfInstitution": "name", "AddressOfInstitution": "address", "ZipCode": "zip",
                                                                 "NameMentionedInAccnt": "holder", "InstitutionAccountNumber": "account",
                                                                 "PeakBalanceOrInvestment": "peak", "IncAccuredTaxFlag": "flag", "IncAccuredInAcc": "income",
                                                                 "IncOfferedAmt": "taxed", "IncOfferedSch": "sch", "IncOfferedSchNo": "sch_no"}, "defaults": {"sch": "NI"}},
    "trust": {"list": "DetailsOfTrustOutIndiaTrustee", "map": {"NameOfTrust": "name", "AddressOfTrust": "address", "ZipCode": "zip",
                                                              "NameOfOtherTrustees": "trustees", "AddressOfOtherTrustees": "trustees_addr",
                                                              "NameOfSettlor": "settlor", "AddressOfSettlor": "settlor_addr",
                                                              "NameOfBeneficiaries": "beneficiaries", "AddressOfBeneficiaries": "beneficiaries_addr",
                                                              "DateHeld": "opened", "IncDrvTaxFlag": "flag", "IncDrvFromTrust": "income",
                                                              "IncOfferedAmt": "taxed", "IncOfferedSch": "sch", "IncOfferedSchNo": "sch_no"}, "defaults": {"sch": "NI"}},
    "income": {"list": "DetailsOfOthSourcesIncOutsideIndia", "map": {"NameOfPerson": "name", "AddressOfPerson": "address", "ZipCode": "zip",
                                                                    "IncDerived": "income", "NatureOfInc": "nature", "IncDrvTaxFlag": "flag",
                                                                    "IncOfferedAmt": "taxed", "IncOfferedSch": "sch", "IncOfferedSchNo": "sch_no"},
               "defaults": {"nature": "Other", "sch": "NI"}},
}
for k2, v, lbl in [
    ("foreign_state", "99", "Schedule S / HP: the state code of a place outside India (99 - Foreign)"),
    ("foreign_category", "OTH", "Schedule S: a foreign employer's nature of employment (Others)"),
    ("owner_self", "SE", "Schedule HP PropertyOwner: the person's own (SE); a minor's MI, a spouse's SP, another's OT (chip myreturn.club_rules)"),
    ("tin_none", "NA", "Schedule FSI / TR / FilingStatus: the foreign TIN when the person has none to give"),
    ("h115_no", "N", "FilingStatus.BenefitUs115HFlg: a resident (ROR / RNOR) answers whether 115H is claimed - N (ITR-2 validation rule 83)"),
    ("fsi_blocks", ["IncFromSal", "IncFromHP", "IncCapGain", "IncOthSrc"], "ITR-2 Schedule FSI: the heads of a country's row"),
    ("fsi_blocks_itr3", ["IncFromSal", "IncFromHP", "IncFromBusiness", "IncCapGain", "IncOthSrc"], "ITR-3 Schedule FSI: the heads of a country's row"),
    ("tr_refunded_no", "NO", "Schedule TR: tax paid abroad on which relief was allowed has since been refunded - NO"),
    ("fa_kinds", FA_KINDS, "Schedule FA: each kind of foreign asset - the department's table (A1 bank accounts, A2 custodial accounts, A3 equity and debt "
                           "interests, A4 cash-value insurance, B a financial interest in an entity, C immovable property, D other capital assets, E accounts "
                           "with signing authority, F trusts, G other income from outside India), which of the row's fields goes in each column, and "
                           "(values) a status typed that the table does not take, said its way"),
    ("fa_defaults", {"text": "-", "zip": "NA", "country": "", "sch_no": "-"}, "Schedule FA: what a blank text column says"),
    ("club_words", {"minor_child": "Minor child", "spouse": "Spouse", "son_wife": "Son's wife"}, "Schedule SPI: the relationship"),
]:
    knob(js, k2, v, lbl)
save(js, "wave 3: foreign state / employer codes, Schedule FSI blocks (ITR-2 / ITR-3), Schedule TR flag, Schedule FA tables, Schedule SPI words, 115H.")

# --- 3 the department's JSON ---------------------------------------------------------------------------------------------------------
m = load("itr.map")
mp = m["params"][0]["default"]
OWN = "w3"
same = lambda fields: {f: f for f in fields}  # noqa: E731
sz = lambda path, src: {"path": path, "from": src, "skip_zero": True, "by": OWN}  # noqa: E731
fr = lambda path, src: {"path": path, "from": src, "by": OWN}  # noqa: E731


def change(form, path, **kw):
    rows = [r for r in mp[form] if r["path"] == path]
    assert rows, (form, path)
    for r in rows:
        for k2, v in kw.items():
            if k2 == "item_set":
                r["item"] |= v
            else:
                r[k2] = v


old = [r for r in mp["ITR-2"] if r.get("by") != OWN]
mp["ITR-2"] = old
FS, CTL = "ITR2.PartA_GEN1.FilingStatus.", "ITR2.PartB_TTI.ComputationOfTaxLiability."
change("ITR-2", CTL + "NetTaxLiability", **{"from": "tax2.net"})
change("ITR-2", "ITR2.ScheduleEI.TotalExemptInc", **{"from": "ei.total"})
change("ITR-2", "ITR2.ScheduleHP.PropertyDetails", item_set={"AddressDetailWithZipCode.CountryCode": "country", "AddressDetailWithZipCode.ZipCode": "zip",
                                                             "PropertyOwner": "owner"})
change("ITR-2", "ITR2.ScheduleS.Salaries", item_set={"AddressDetail.ZipCode": "zip"})
FSI = ["CountryName", "CountryCodeExcludingIndia", "TaxIdentificationNo", "IncFromSal", "IncFromHP", "IncCapGain", "IncOthSrc", "TotalCountryWise"]
TR = ["CountryName", "CountryCodeExcludingIndia", "TaxIdentificationNo", "TaxPaidOutsideIndia", "TaxReliefOutsideIndia", "ReliefClaimedUsSection"]
new = [
    fr(FS + "ConditionsResStatus", "res.condition"),
    {"path": FS + "JurisdictionResPrevYr.JurisdictionResPrevYrDtls", "each": "res_juris", "item": {"JurisdictionResidence": "code", "TIN": "tin"}, "by": OWN},
    fr(FS + "TotalPrStayIndiaPrevYr", "res.days_fy"),
    fr(FS + "TotalPrStayIndia4PrecYr", "res.days_4y"),
    fr(FS + "BenefitUs115HFlg", "res.h115"),
    {"path": "ITR2.ScheduleFSI.ScheduleFSIDtls", "each": "fsi_rows", "item": same(FSI), "by": OWN},
    {"path": "ITR2.ScheduleTR1.ScheduleTR", "each": "tr_rows", "item": same(TR), "by": OWN},
    sz("ITR2.ScheduleTR1.TotalTaxPaidOutsideIndia", "tr.paid"),
    sz("ITR2.ScheduleTR1.TotalTaxReliefOutsideIndia", "tr.relief"),
    sz("ITR2.ScheduleTR1.TaxReliefOutsideIndiaDTAA", "tr.dtaa"),
    sz("ITR2.ScheduleTR1.TaxReliefOutsideIndiaNotDTAA", "tr.not_dtaa"),
    fr("ITR2.ScheduleTR1.TaxPaidOutsideIndFlg", "tr.flag"),
    *[{"path": f"ITR2.ScheduleFA.{spec['list']}", "each": f"fa_{kind}", "item": same(["CountryName", "CountryCodeExcludingIndia"] + list(spec["map"])), "by": OWN}
      for kind, spec in FA_KINDS.items()],
    {"path": "ITR2.ScheduleSPI.SpecifiedPerson", "each": "spi_rows", "item": same(["SpecifiedPersonName", "PANofSpecPerson", "ReltnShip", "AmtIncluded", "HeadIncIncluded"]), "by": OWN},
    {"path": "ITR2.ScheduleEI.OthersInc.OthersIncDtls", "each": "ei_rows", "item": same(["Category", "SubCategory", "OthAmount"]), "by": OWN},
    sz("ITR2.ScheduleEI.Others", "ei.others"),
    sz(CTL + "TaxRelief.Section89", "tax2.s89"),
    sz(CTL + "TaxRelief.Section90", "tax2.s90"),
    sz(CTL + "TaxRelief.Section91", "tax2.s91"),
    sz(CTL + "TaxRelief.TotTaxRelief", "tax2.relief"),
    sz("ITR2.ScheduleOS.IncOthThanOwnRaceHorse.IntrstFrmOthers", "os.interest_other"),
]
mp["ITR-2"] = old + new
change("ITR-1", "ITR1.ITR1_TaxComputation.NetTaxLiability", **{"from": "tax2.net"})
change("ITR-4", "ITR4.TaxComputation.NetTaxLiability", **{"from": "tax2.net"})
for form, path in (("ITR-1", "ITR1.ITR1_TaxComputation.Section89"), ("ITR-4", "ITR4.TaxComputation.Section89")):
    mp[form] = [r for r in mp[form] if r["path"] != path] + [{"path": path, "from": "tax2.s89", "by": OWN}]
for tc in m["test_cases"]:
    if isinstance(tc.get("expect_value"), dict) and "forms" in tc["expect_value"] and not tc.get("args"):
        tc["expect_value"]["forms"] = mp
save(m, "wave 3 (ITR-2): FilingStatus - the condition of the residential status, the days in India, a non-resident's country of residence and TIN, "
        "115H; Schedule FSI (per country: salary, house, capital gains, other sources - income, tax paid abroad, Indian tax, relief, DTAA article), "
        "Schedule TR (relief u/s 90 / 90A / 91), Schedule FA (A1-A4, B, C), Schedule SPI (clubbed income), Schedule EI 10(32); Part B-TTI TaxRelief "
        "(89 / 90 / 91) and NetTaxLiability after it; a foreign employer's / house's ZIP code and country, the owner of a clubbed house. "
        "ITR-1 / ITR-4: Section89 and NetTaxLiability after it.")

# --- 4 the words -----------------------------------------------------------------------------------------------------------------------
w = load("ui.myreturn")
WORDS = {
    # residential status
    "rs_h": "Residential status", "rs_p": "Where you lived in FY 2025-26 decides what India taxes. Type the days you were in India (the day you arrive "
                                        "and the day you leave both count) - or leave them blank if you lived in India all year.",
    "f_days_fy": "Days in India, FY 2025-26", "f_days_4y": "Days in India, FY 2021-22 to 2024-25", "f_nr_years": "Of the 10 years before, years as a non-resident",
    "f_days_7y": "Days in India in the 7 years before", "f_indian_income": "Income other than from foreign sources (blank: worked out)",
    "q_citizen": "I am a citizen of India", "q_pio": "I am a person of Indian origin (not a citizen)", "q_visiting": "I live abroad and came to India on a visit",
    "q_left_for_job": "I left India this year for a job abroad, or as crew of an Indian ship", "q_taxed_elsewhere": "I am liable to tax in another country as its resident",
    "f_res_country": "Country of residence", "f_res_tin": "Tax identification number there",
    "rs_ROR": "Resident and ordinarily resident", "rs_RNOR": "Resident but not ordinarily resident (RNOR)", "rs_NR": "Non-resident",
    "res_why_1": "In India 182 days or more this year (s.6(1)(a)).", "res_why_2": "In India 60 days or more this year and 365 days or more in the 4 years before (s.6(1)(c)).",
    "res_why_3": "Resident, but a non-resident in 9 of the 10 years before - not ordinarily resident (s.6(6)(a)).",
    "res_why_4": "Resident, but in India 729 days or less in the 7 years before - not ordinarily resident (s.6(6)(a)).",
    "res_why_5": "Not resident: fewer days in India than s.6(1) asks for this year.",
    "res_why_6": "A citizen / person of Indian origin on a visit, with income other than from foreign sources over 15 lakh, in India 120 days or more "
                 "and 365 in the 4 years before - resident but not ordinarily resident (s.6(1) Explanation 1(b), s.6(6)(c)).",
    "res_why_7": "A citizen with income other than from foreign sources over 15 lakh, not liable to tax in any other country - deemed resident, "
                 "not ordinarily resident (s.6(1A), s.6(6)(d)).",
    "rs_nr_note": "As a non-resident only income received or arising in India is taxed. No 87A rebate, no 80TTB, 80DD / 80DDB / 80U; the old regime's "
                  "basic exemption is 2.5 lakh at any age; advance tax is due even at 60+. You file ITR-2 (ITR-3 with a business). Investment income "
                  "and gains on foreign-exchange assets may instead be taxed at the special rates of s.115E (Chapter XII-A, s.115A for others) - My return "
                  "taxes them at the normal rates; ask a CA if that suits you better. Tax treaty rates (DTAA) need a Tax Residency Certificate and Form 10F.",
    "rs_rnor_note": "As not ordinarily resident, income earned abroad is not taxed in India - unless it comes from a business controlled in, or a profession "
                    "set up in, India. Foreign assets need not be listed (Schedule FA). ITR-2 (ITR-3 with a business).",
    "rs_unknown": "Days not typed: the 'resident' answer decides (resident and ordinarily resident unless you untick it).",
    "why_nonres": "Not resident and ordinarily resident (a non-resident or RNOR): ITR-1 and ITR-4 are for residents only - ITR-2.",
    # foreign income
    "fi_h": "Income from outside India", "fi_p": "Each item of foreign income, in rupees: convert at the SBI telegraphic-transfer buying rate on the last "
                                               "day of the month before the month it was received (rule 115). Taxed in India only for a resident and ordinarily resident.",
    "f_fi_country": "Country", "f_fi_head": "Kind", "f_fi_amount": "Income (rupees)", "f_fi_tax_paid": "Tax paid there (rupees)", "f_fi_sec": "Relief under",
    "f_fi_article": "DTAA article", "f_fi_tin": "Your TIN there", "f_fi_controlled": "From a business controlled / profession set up in India",
    "f_fi_employer": "Employer", "f_fi_address": "Address", "f_fi_city": "City", "f_fi_zip": "ZIP code", "f_fi_municipal_tax": "Local taxes paid", "f_fi_interest": "Loan interest",
    "fi_heads": "salary=Salary|house=Rent from a house|interest=Interest|dividend=Dividend|other=Other income|stcg=Short-term capital gain|ltcg=Long-term capital gain"
                "|business=Business / profession income",
    "fi_secs": "90=s.90 - a tax treaty (DTAA)|90A=s.90A - an agreement of specified associations|91=s.91 - no treaty",
    "fi_add": "Add foreign income", "fi_none": "None typed.", "fi_not": "Not taxed in India for you ({status}).",
    "fi_relief": "Relief for tax paid abroad: {amount} (s.90 / 90A {dtaa}, s.91 {other}) - the lower of the foreign tax and the Indian tax on it at your average rate.",
    "fi_form67": "File Form 67 (with proof of the tax paid abroad) on the e-filing portal before 31 March 2027 - without it the relief is refused (rule 128(9)).",
    "ca_foreign_business": "Income from a business or profession abroad needs books of account and ITR-3 Schedule BP - My return does not file it. Get a CA "
                           "({product}'s CA-firm side handles books and business income).",
    # foreign assets
    "fa_h": "Foreign assets (Schedule FA)", "fa_p": "As a resident and ordinarily resident, list everything held abroad at any time in the calendar year "
                                                    "1 January - 31 December 2025: bank and custodial accounts, shares and debt, insurance, property, other assets - "
                                                    "even with no income from it. Rupee values at the SBI TT buying rate. Leaving it out can cost 10 lakh (Black Money Act).",
    "fa_kinds": "bank=Bank account (A1)|custodial=Custodial / brokerage account (A2)|equity=Shares, ESOPs, debt (A3)|insurance=Cash-value insurance (A4)"
                "|financial=Interest in a foreign company, firm or other entity (B)"
                "|property=Immovable property (C)|other=Other capital asset (D)|signing=Account you can sign for (E)|trust=Trust abroad - trustee, "
                "beneficiary or settlor (F)|income=Other income from outside India (G)",
    "f_fa_inc_nature": "Nature of the income from it",
    "f_fa_holder": "Name in the account", "f_fa_trustees": "Other trustees", "f_fa_trustees_addr": "Their address", "f_fa_settlor": "Settlor",
    "f_fa_settlor_addr": "Settlor's address", "f_fa_beneficiaries": "Beneficiaries", "f_fa_beneficiaries_addr": "Beneficiaries' address",
    "f_fa_kind": "Asset", "f_fa_country": "Country", "f_fa_name": "Name (bank / entity / asset)", "f_fa_address": "Address", "f_fa_zip": "ZIP code",
    "f_fa_account": "Account number", "f_fa_status": "You are", "f_fa_opened": "Opened / acquired on", "f_fa_peak": "Peak value in 2025", "f_fa_closing": "Value on 31 Dec 2025",
    "f_fa_income": "Income from it in 2025", "f_fa_cost": "Cost / initial value", "f_fa_proceeds": "Sale proceeds in 2025", "f_fa_nature": "Nature (entity / income)",
    "f_fa_taxed": "Income taxed in this return", "f_fa_sch": "Shown in schedule", "f_fa_sch_no": "Item no.",
    "fa_statuses": "OWNER=Owner|BENEFICIAL_OWNER=Beneficial owner|BENIFICIARY=Beneficiary|DIRECT=Direct owner",
    "fa_schs": "NI=Not in this return|SA=Salary|HP=House property|CG=Capital gains|OS=Other sources|EI=Exempt income",
    "fa_add": "Add a foreign asset", "fa_none": "None typed.", "fa_not_needed": "Schedule FA is for a resident and ordinarily resident - not needed for you ({status}).",
    "c_fa_missing": "Foreign assets not listed (Schedule FA)", "lv_fa_missing": "You have foreign income or assets: list every foreign account and asset held in 2025 in Schedule FA.",
    # clubbing
    "cl_h": "Income of your spouse or child (clubbing)", "cl_p": "A minor child's income joins the income of the parent whose income is the greater (s.64(1A)) - "
                                                               "1,500 a child is exempt (s.10(32)); not what the child earns by work, skill or talent. The income from "
                                                               "money or property you gave your spouse (or son's wife) without adequate consideration joins yours (s.64(1)(iv), (vi)).",
    "cl_relations": "minor_child=Minor child|spouse=Spouse|son_wife=Son's wife", "cl_heads": "interest=Interest|dividend=Dividend|other=Other income|house=Rent from a house"
                    "|stcg_111a=Short-term gain, listed shares (111A)|stcg=Short-term gain, other|ltcg_112a=Long-term gain, listed shares (112A)|ltcg_112=Long-term gain, other (112)",
    "f_cl_name": "Name", "f_cl_pan": "PAN (if any)", "f_cl_relation": "Relation", "f_cl_head": "Kind of income", "f_cl_amount": "Income (rent for a house)",
    "f_cl_skill": "Earned by the child's own work / skill", "f_cl_disabled": "The child has a disability (s.80U)", "f_cl_address": "House address",
    "cl_add": "Add clubbed income", "cl_none": "None typed.", "cl_in": "Added to your income: {amount}", "cl_exempt": "s.10(32): {amount} exempt",
    "cl_not": "Not clubbed (s.64(1A) proviso).", "why_club": "Income of a spouse or child is clubbed with yours (s.64) - ITR-2 shows whose it is (Schedule SPI).",
    # salary arrears, s.89
    "ar_h": "Salary arrears - relief u/s 89 (Form 10E)", "ar_p": "Arrears (or advance salary) received this year for earlier years push this year's tax up. "
                                                             "Type each year the arrears belong to, with that year's income: the relief is the extra tax now less the "
                                                             "extra tax then. Available in the new regime too. File Form 10E on the e-filing portal before the return.",
    "f_ar_fy": "Year (FY, e.g. 2019-20)", "f_ar_amount": "Arrears of that year", "f_ar_income": "That year's total income", "f_ar_regime": "That year's regime",
    "ar_regimes": "=As then (old before 2023-24)|old=Old|new=New", "ar_add": "Add a year", "ar_none": "None typed.",
    "ar_relief": "Relief u/s 89: {amount} (extra tax now {now}, extra tax in those years {past}).", "ar_form10e": "File Form 10E (e-File > Income Tax Forms) before you file the return.",
    "ar_unknown": "A year cannot be worked out (before FY 2015-16, the new regime before 2020-21, or income over 50 lakh) - no relief is claimed; ask a CA.",
    "ar_nil": "No relief: the arrears would have cost as much or more in their own years.", "d_relief": "Relief u/s 89 / 90 / 91",
    # the updated return (ITR-U)
    "iu_h": "Updated return (ITR-U) for an earlier year", "iu_p": "Missed income in an earlier year? Within 48 months of the end of that AY you may file an "
                                                                 "updated return (s.139(8A)) - paying the tax, interest and an additional tax of 25% / 50% / 60% / 70% "
                                                                 "of it (s.140B). Not to lower tax or raise a refund or a loss.",
    "f_iu_ay": "Assessment year", "f_iu_filed": "Return filed for it", "iu_filed": "none=None|original=Original|belated=Belated|revised=Revised",
    "f_iu_orig_income": "Total income in that return (nil if none)", "f_iu_added": "Income left out", "f_iu_tds_added": "TDS on the income left out",
    "f_iu_tds": "That year's TDS in all", "f_iu_advance": "Advance tax paid that year", "f_iu_regime": "That year's regime", "f_iu_reason": "Why you update",
    "f_iu_on": "Filing on", "iu_bars_h": "Does any of these apply to that year?",
    "iu_bar_search": "A search (s.132) or requisition started", "iu_bar_survey": "A survey (s.133A)", "iu_bar_requisition": "Books requisitioned (s.132A)",
    "iu_bar_assessment": "An assessment / reassessment pending or made", "iu_bar_prosecution": "Prosecution started",
    "iu_bar_other_law": "Information held under another law (PMLA, Black Money, Benami)", "iu_bar_already_updated": "An updated return already filed for it",
    "iu_bar_loss_return": "It would be a return of loss", "iu_bar_lower_tax": "It would lower the tax or raise the refund",
    "itru_late": "Too late: 48 months from the end of that AY have passed (s.139(8A)).", "itru_not_more": "An updated return must add tax - this adds none.",
    "itru_bar_search": "Not allowed: a search or requisition was started (s.139(8A) proviso).", "itru_bar_survey": "Not allowed: a survey was made (s.139(8A) proviso).",
    "itru_bar_requisition": "Not allowed: books were requisitioned.", "itru_bar_assessment": "Not allowed: an assessment / reassessment is pending or made for the year.",
    "itru_bar_prosecution": "Not allowed: prosecution has started.", "itru_bar_other_law": "Not allowed: information is held under another law.",
    "itru_bar_already_updated": "Not allowed: only one updated return a year.", "itru_bar_loss_return": "Not allowed: a return of loss cannot be updated this way.",
    "itru_bar_lower_tax": "Not allowed: it may not lower the tax or raise a refund.",
    "itru_bar_year_unknown": "That year's tax cannot be worked out here (the new regime before FY 2020-21, or income over 50 lakh) - ask a CA.",
    "iu_lines": "Tax on the income before|Tax on the updated income|Further tax (less TDS on the income added)|Interest u/s 234A|Interest u/s 234B|"
                "Additional tax u/s 140B ({pct}%)|Late fee u/s 234F|To pay",
    "iu_ok": "Allowed: file it by {by}.",
    "iu_steps": "Pay the amount above first: incometax.gov.in > e-File > e-Pay Tax > Income Tax, AY {ay}, Self-Assessment Tax|"
                "e-File > Income Tax Returns > File Income Tax Return > AY {ay} > Online, filing section 139(8A) - Updated return|"
                "Part A ITR-U: the reason for updating, the previous return's acknowledgement and date (if any)|"
                "Part B-ATI: the income added, the tax, the interest, the additional tax and the challan|Verify (Aadhaar OTP / EVC) within 30 days",
    "iu_no_schema": "{product} does not make the ITR-U JSON: the department's ITR-U schema (and AY {ay}'s ITR schemas) is not in schemas/itr. "
                    "The computation and the steps are above - file it on the portal, or add the schema to have the JSON made.",
    "iu_none": "Pick a year to work one out.", "iu_reasons_h": "Reason",
}
for k2 in ("ar_unknown", "f_iu_orig_income", "f_iu_added", "itru_bar_year_unknown", "iu_lines"):   # 2026-10-08: wave 4 says these now (make_wave4_chips.py)
    WORDS.pop(k2, None)
for k2, v in WORDS.items():
    knob(w, k2, v, k2)
ir = load("myreturn.itru_rules")
reasons = next(p for p in ir["params"] if p["name"] == "reasons")["default"]
knob(w, "iu_reasons", "|".join(f"{c}={t}" for c, t in reasons.items()), "iu_reasons")
save(w, "wave 3: residential status, foreign income and assets, clubbing, salary arrears (s.89), the updated return (ITR-U).")
print("done")
