"""2026-10-07: the rule book gets every rule chip added overnight (wave 1 rest, capital gains, ITR-3 from My return, residence,
foreign income, clubbing, s.89, ITR-U, s.234A in an extended year). Re-runnable: a chip already listed is skipped; the old
'not built' notes these waves closed are cleared. Run from D:/Simplyfile."""
import json
from pathlib import Path

p = Path("chips/rulebook.sections.json")
c = json.loads(p.read_text(encoding="utf-8"))
P = {x["name"]: x for x in c["params"]}
areas, rules = P["areas"]["default"], P["rules"]["default"]
for a in ({"id": "cg", "label": "Capital gains and losses"}, {"id": "abroad", "label": "Residence, foreign income and clubbing"},
          {"id": "past", "label": "Earlier years: arrears and updated returns"}):
    if not any(x["id"] == a["id"] for x in areas):
        areas.insert(next(i for i, x in enumerate(areas) if x["id"] == "huf"), a)
R = lambda chip, area, law, plain, gaps="": {"chip": chip, "area": area, "law": law, "plain": plain, "gaps": gaps}  # noqa: E731
NEW = [
    R("compute.due_234a", "interest", "s.234A, Explanation 1; CBDT extension orders (e.g. 9/2021, 17/2021)",
      "When CBDT extends a due date by circular, interest under s.234A still runs from the original date if the tax owed after advance tax, TDS/TCS and reliefs is over one lakh; otherwise from the extended date. Circular 07/2026 is silent on interest, so the safer reading is used.",
      "Ask a CA if the circular for a year says otherwise."),
    R("myreturn.house", "house", "ss.22-27, s.26 (co-owners), s.24(b) (interest, pre-construction one-fifth)",
      "Each co-owner is taxed on their share: rent, municipal tax and loan interest by share; the 30% on the share's annual value; the self-occupied interest cap per co-owner. Interest paid before the year of completion is allowed one fifth a year for five years, inside the self-occupied cap."),
    R("myreturn.vda", "other", "s.115BBH (virtual digital assets)",
      "Each transfer's gain is the sale less cost only, at 30%; a loss counts for nothing, is not set off even against another VDA's gain and is not carried forward."),
    R("myreturn.tax", "tax", "ss.115BB, 115BBJ, 115BBH (30%), s.87A, First Schedule",
      "Lottery, races, online games and VDA gains are taxed at 30% in both regimes, with no basic exemption, no 87A rebate and no Chapter VI-A deduction against them."),
    R("myreturn.slab_normal", "tax", "Finance Act, First Schedule Part I (partial integration of agricultural income)",
      "Agricultural income over 5,000, when other income is above the basic exemption: tax on (normal + agricultural) less tax on (basic exemption + agricultural), in both regimes; 87A then applies."),
    R("myreturn.vehicle_44ae", "business", "s.44AE",
      "Goods carriages, up to ten at any time: 1,000 per ton of gross weight per month for a vehicle over 12,000 kg, 7,500 per month for others; a part month counts as a month; higher income may be declared. More than ten vehicles: books, ITR-3."),
    R("myreturn.check_80ee", "via", "s.80EEA(4)(b)", "80EEA is not allowed when 80EE is claimed: the return keeps 80EE and the check is red."),
    R("myreturn.business_pl", "business", "s.44AA, ss.44AD/44ADA/44AE (beyond the limits)",
      "When the presumptive limits are passed, or the business is not presumptive, the profit typed from the person's own P&L is the income and the books flag is set; ITR-3 is written with the no-books P&L and balance sheet.",
      "A business loss, depreciation and disallowances need a CA."),
    R("myreturn.audit_44ab", "business", "s.44AB(a), (b), (e)",
      "Tax audit needed when business turnover is over 1 crore (10 crore with cash at 5% or less), professional receipts over 50 lakh (75 lakh), or presumptive income is declared lower than allowed with income above the basic exemption. My return then says: get a CA."),
    R("myreturn.cg_rules", "cg", "ss.2(42A), 111A, 112, 112A, 50AA, 70-74; Finance (No.2) Act 2024",
      "Holding periods (12 months listed, 24 months others), rates after 23 July 2024 (111A 20%, 112A 12.5% over 1.25 lakh, 112 12.5%), s.50AA debt funds and market-linked debentures always short-term at slab rates, and the set-off order: short-term loss against any gain, long-term loss only against long-term gain."),
    R("myreturn.cg_row", "cg", "ss.48, 49, 50C, 55(2)(ac) (grandfathering)",
      "One sale's gain: price (or stamp value when over 110% of it), less cost, improvement and expenses; shares bought before 1 Feb 2018 use the higher of cost and the lower of the 31 Jan 2018 value and the price."),
    R("myreturn.cii", "cg", "s.48 Explanation (v); CBDT CII notifications", "The cost inflation index from 2001-02 (100) to 2025-26 (376); an asset bought before 2001 uses its value on 1 April 2001."),
    R("myreturn.cg_choice", "cg", "s.112(1) proviso (Finance (No.2) Act 2024)",
      "Land or building bought before 23 July 2024 sold by a resident individual or HUF: tax at 12.5% without indexation or 20% with it, whichever is lower; both are shown."),
    R("myreturn.cg_exempt", "cg", "ss.54, 54EC, 54F",
      "54: house to house, cost up to 10 crore; 54EC: up to 50 lakh of bonds within six months; 54F: other asset to house in proportion, not with more than one other house; Capital Gains Account Scheme deposits count.",
      "Time limits are not checked; one exemption per sale row."),
    R("myreturn.waterfall", "cg", "ss.70-72, 74 (set-off order)", "Losses net within each rate first, then a short-term loss against slab gains first and 112A last; a long-term loss against 112 before 112A."),
    R("myreturn.loss_age", "cg", "ss.71B, 74, 80 (carry forward)",
      "Capital and house losses carry forward eight years; a capital loss only from a return filed on time; a brought-forward house loss is set off only against house income."),
    R("myreturn.gifts", "other", "s.56(2)(x)",
      "Gifts from relatives, on marriage, by will or inheritance are not taxed; money and valuables over 50,000 together in a year are; each property is tested on its own (stamp value, or shortfall over the higher of 50,000 and 10%)."),
    R("myreturn.residence", "abroad", "s.6(1), 6(1A), 6(6)",
      "Resident on 182 days, or 60 days and 365 in the four years before (182 for a citizen leaving for work or a visiting citizen/PIO; 120 when Indian income is over 15 lakh); deemed resident; RNOR by 9 of 10 years, 729 days in 7, the 120-day visitor and the deemed resident. A non-resident: no 87A, 80TTB, 80DD/DDB/U or senior limits; ITR-2/3 only."),
    R("myreturn.dtaa_relief", "abroad", "ss.90, 90A, 91; Rule 128 (Form 67)",
      "For a resident and ordinarily resident: foreign income is taxed here, and relief per country and head is the lower of the tax paid abroad and the Indian tax at the average rate. Form 67 by 31 March of the assessment year."),
    R("myreturn.check_fa", "abroad", "Schedule FA; Black Money Act s.42-43", "A resident and ordinarily resident with any foreign asset or foreign income must list the assets in Schedule FA: red check otherwise.",
      "Tables D-F (signing authority, trusts, other) are not asked."),
    R("myreturn.club_row", "abroad", "s.64(1)(iv), 64(1)(vi), 64(1A), s.10(32)",
      "A minor child's income (not from their own work or skill, nor a child with an 80U disability) is added to the parent's, less 1,500 per child; income from assets given to a spouse or son's wife without consideration is added under its head; Schedule SPI."),
    R("myreturn.relief_89", "past", "s.89, Rule 21A (Form 10E)",
      "Salary arrears: tax this year with arrears less without, less the same difference for each earlier year at that year's slabs; never below nil; available in the new regime too.",
      "An earlier year with surcharge is flagged, not relieved."),
    R("myreturn.itru", "past", "s.139(8A), s.140B, ss.234A(1A)/234B(1A) (Finance Act 2025: 48 months)",
      "An updated return within 48 months: not a loss or lower-tax return, not after search, survey or assessment; the further tax plus interest plus 25/50/60/70% by the year since.",
      "No ITR-U JSON until its schema is added; 234C, surcharge and special rates of the earlier year are not computed."),
]
have = {r["chip"] for r in rules}
add = [r for r in NEW if r["chip"] not in have]
for r in add:
    rules.append(r)
for r in rules:                # the gaps the waves closed
    if r["chip"] == "myreturn.form":
        r["gaps"] = ""
c["test_cases"] = [{"args": {}, "expect_value": {"areas": areas, "rules": rules}}] if c.get("test_cases") else c.get("test_cases", [])
c["version"] += 1
c["description_nl"] += f" 2026-10-07: {len(add)} rules added (capital gains, residence and foreign income, clubbing, s.89, ITR-U, s.234A in an extended year, 44AE, agri, special rates)."
p.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("added", len(add), "missing chips:", [r["chip"] for r in add if not Path(f"chips/{r['chip']}.json").exists()])
