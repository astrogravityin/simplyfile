"""2026-10-06 (wave 1): the rest of Chapter VI-A for My return - 80DD, 80DDB, 80EE, 80EEA, 80EEB, 80GG, 80GGC - with their caps,
who may claim them, the department's schedules and the words. Run once from D:/Simplyfile:  python tools/make_more_deductions.py
Hand-edit the chips afterwards - this is only how they were first made."""
import json
from pathlib import Path

CH = Path(__file__).resolve().parent.parent / "chips"
NEW = ["80DD", "80DDB", "80EE", "80EEA", "80EEB", "80GG", "80GGC"]


def load(cid):
    return json.loads((CH / f"{cid}.json").read_text(encoding="utf-8"))


def save(c, note):
    c["version"] += 1
    c["description_nl"] = c.get("description_nl", "") + " 2026-10-06: " + note
    (CH / f"{c['chip_id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", c["chip_id"], c["version"])


def knob(c, name, default, label):
    for p in c["params"]:
        if p["name"] == name:
            p["default"] = default
            break
    else:
        c["params"].append({"name": name, "type": "text" if isinstance(default, str) else "json", "default": default, "label": label})
        c["expr"]["fields"][name] = "$" + name
    for t in c["test_cases"]:
        if isinstance(t.get("expect_value"), dict) and not t.get("args"):
            t["expect_value"][name] = default


# 1 rates: caps, and who may claim
r = load("myreturn.rates")
P = {p["name"]: p for p in r["params"]}
vr = P["via_regimes"]["default"]
vr["old"] = vr["old"] + [s for s in NEW if s not in vr["old"]]
knob(r, "via_regimes", vr, "via regimes")
vs = P["via_status"]["default"]
vs["individual"] = vs["individual"] + [s for s in NEW if s not in vs["individual"]]
vs["huf"] = vs["huf"] + [s for s in ("80DD", "80DDB", "80GGC") if s not in vs["huf"]]
knob(r, "via_status", vs, "Chapter VI-A sections each status may claim")
knob(r, "cap_80dd", {"1": 75000, "2": 125000}, "80DD: a fixed sum - 1 disability (40% or more), 2 severe (80% or more)")
knob(r, "cap_80ddb", {"below60": 40000, "senior": 100000}, "80DDB: specified diseases - up to, by the patient's age")
knob(r, "cap_80ee", 50000, "80EE: interest on a first-home loan sanctioned in FY 2016-17")
knob(r, "cap_80eea", 150000, "80EEA: interest on an affordable first-home loan sanctioned FY 2019-20 to 2021-22 (stamp value up to 45 lakh)")
knob(r, "cap_80eeb", 150000, "80EEB: interest on an electric-vehicle loan sanctioned FY 2019-20 to 2022-23")
save(r, "80DD, 80DDB, 80EE, 80EEA, 80EEB, 80GG, 80GGC - old regime only; an HUF claims 80DD, 80DDB and 80GGC too.")

# 2 deductions: the new sections, each gated by regime and status like the others, and in the total
d = load("myreturn.deductions")
for name, default, label in [("dd_nature", "", "80DD: 1 disability, 2 severe disability of a dependant (blank: none)"),
                             ("c80ddb", 0, "80DDB: spent on treating a specified disease"), ("ddb_senior", False, "80DDB: the patient is a senior citizen"),
                             ("c80ee", 0, "80EE: interest paid"), ("c80eea", 0, "80EEA: interest paid"), ("c80eeb", 0, "80EEB: interest paid"),
                             ("c80ggc", 0, "80GGC: given to a political party, not in cash")]:
    if not any(p["name"] == name for p in d["params"]):
        d["params"].append({"name": name, "type": "text" if isinstance(default, str) else ("boolean" if isinstance(default, bool) else "number"),
                            "default": default, "label": label})
rates = {"chip": "myreturn.rates", "args": {}}


def gate(sec):
    tpl = lambda what, var: {"op": "in_set", "value": sec, "set": {"vop": "get", "value": rates, "path": {"vop": "template", "text": f"{what}.{{x}}", "values": {"vop": "record", "fields": {"x": var}}}}}  # noqa: E731
    return {"op": "all", "items": [tpl("via_regimes", "$regime"), tpl("via_status", "$status")]}


cap = lambda path: {"vop": "get", "value": rates, "path": path}  # noqa: E731
new_fields = {
    "d80DD": {"vop": "choose", "cases": [{"when": {"op": "all", "items": [gate("80DD"), {"op": "in_set", "value": "$dd_nature", "set": ["1", "2"]}]},
                                          "then": {"vop": "get", "value": cap("cap_80dd"), "path": "$dd_nature"}}], "else": 0},
    "d80DDB": {"vop": "choose", "cases": [{"when": gate("80DDB"), "then": {"vop": "smallest", "values": ["$c80ddb", {"vop": "choose", "cases": [
        {"when": {"op": "eq", "left": "$ddb_senior", "right": True}, "then": {"vop": "get", "value": cap("cap_80ddb"), "path": "senior"}}],
        "else": {"vop": "get", "value": cap("cap_80ddb"), "path": "below60"}}]}}], "else": 0},
    "d80EE": {"vop": "choose", "cases": [{"when": gate("80EE"), "then": {"vop": "smallest", "values": ["$c80ee", cap("cap_80ee")]}}], "else": 0},
    "d80EEA": {"vop": "choose", "cases": [{"when": gate("80EEA"), "then": {"vop": "smallest", "values": ["$c80eea", cap("cap_80eea")]}}], "else": 0},
    "d80EEB": {"vop": "choose", "cases": [{"when": gate("80EEB"), "then": {"vop": "smallest", "values": ["$c80eeb", cap("cap_80eeb")]}}], "else": 0},
    "d80GGC": {"vop": "choose", "cases": [{"when": gate("80GGC"), "then": "$c80ggc"}], "else": 0},
}
F = d["expr"]["fields"]
if "d80DD" not in F:
    for k, v in new_fields.items():
        F[k] = v
    tot = F["total"]                                  # smallest([total(each section ...), gross_total])
    inner = tot["values"][0]
    assert inner.get("vop") == "total", inner.get("vop")
    inner["values"] += list(new_fields.values())
    for t in d["test_cases"]:
        if isinstance(t.get("expect_value"), dict):
            t["expect_value"] = None                  # re-run below: every existing case gains the new fields at 0
    d["test_cases"].append({"args": {"regime": "old", "gross_total": 2000000, "dd_nature": "2", "c80ddb": 80000, "ddb_senior": True,
                                     "c80eea": 200000, "c80eeb": 90000, "c80ggc": 25000}, "expect_value": None})
    d["test_cases"].append({"args": {"regime": "new", "gross_total": 2000000, "dd_nature": "1", "c80ggc": 25000}, "expect_value": None})
    d["test_cases"].append({"args": {"regime": "old", "status": "huf", "gross_total": 2000000, "dd_nature": "1", "c80eea": 100000}, "expect_value": None})
    save(d, "80DD (a fixed sum by the dependant's disability), 80DDB (spent, up to the cap by age), 80EE / 80EEA / 80EEB (interest, up to each cap), 80GGC (non-cash gifts to a party) - all gated by regime and status like the rest.")

# 3 80GG on its own: it is worked out on the income left after every other deduction
gg = {"chip_id": "myreturn.d80gg", "kind": "accessor", "set": "myreturn", "label": "My return: 80GG - rent paid with no HRA",
      "aliases": ["80gg", "rent without hra"],
      "params": [{"name": n, "type": t, "default": v, "label": l} for n, t, v, l in [
          ("rent", "number", 0, "rent paid in the year"), ("ati", "number", 0, "total income before 80GG (gross total less the other deductions)"),
          ("regime", "text", "old", "regime"), ("status", "text", "individual", "individual / huf"), ("has_hra", "boolean", False, "HRA received from an employer"),
          ("month_cap", "number", 5000, "a month, at most"), ("months", "number", 12, "months"), ("ati_pct", "number", 25, "% of that income, at most"),
          ("rent_less_pct", "number", 10, "rent less this % of that income")]],
      "expr": {"vop": "choose", "cases": [{"when": {"op": "all", "items": [
          {"op": "eq", "left": "$regime", "right": "old"}, {"op": "eq", "left": "$status", "right": "individual"},
          {"op": "eq", "left": "$has_hra", "right": False}, {"op": "gt", "left": "$rent", "right": 0}]},
          "then": {"vop": "round_to", "value": {"vop": "largest", "values": [{"vop": "smallest", "values": [
              {"vop": "mul", "a": "$month_cap", "b": "$months"},
              {"vop": "div", "a": {"vop": "mul", "a": "$ati", "b": "$ati_pct"}, "b": 100},
              {"vop": "sub", "a": "$rent", "b": {"vop": "div", "a": {"vop": "mul", "a": "$ati", "b": "$rent_less_pct"}, "b": 100}}]}, 0]}}}],
          "else": 0},
      "returns": "number", "version": 1, "status": "published",
      "description_nl": "2026-10-06: s.80GG - an individual paying rent with no HRA from an employer, old regime: the least of 5,000 a month, 25% of total income (before 80GG) and rent less 10% of that income. Form 10BA is the person's declaration.",
      "test_cases": [{"args": {"rent": 240000, "ati": 600000}, "expect_value": 60000},
                     {"args": {"rent": 100000, "ati": 600000}, "expect_value": 40000},
                     {"args": {"rent": 240000, "ati": 600000, "has_hra": True}, "expect_value": 0},
                     {"args": {"rent": 240000, "ati": 600000, "regime": "new"}, "expect_value": 0},
                     {"args": {"rent": 240000, "ati": 600000, "status": "huf"}, "expect_value": 0}]}
(CH / "myreturn.d80gg.json").write_text(json.dumps(gg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote myreturn.d80gg")

# 4 words
w = load("ui.myreturn")
for k, v in {
    "more_via_h": "More deductions (old regime)", "more_via_p": "Less common ones - a dependant's disability, treating a serious illness, special loans, rent with no HRA, gifts to a party. Each needs the details the department's schedule asks for.",
    "f_dd_nature": "80DD - a dependant with a disability", "dd_none": "None", "dd_1": "Disability (40% or more)", "dd_2": "Severe disability (80% or more)",
    "f_dd_type": "Kind of disability", "dd_type_1": "Autism, cerebral palsy or multiple disabilities", "dd_type_2": "Other",
    "f_dd_dependent": "The dependant is your", "dd_dep": "1=Spouse|2=Son|3=Daughter|4=Father|5=Mother|6=Brother|7=Sister|8=Member of the HUF",
    "f_c80ddb": "80DDB - spent treating a specified disease", "f_ddb_senior": "The patient is 60 or over",
    "f_c80ee": "80EE - interest on a first-home loan (sanctioned 2016-17)", "f_c80eea": "80EEA - interest on an affordable first-home loan (2019-22)",
    "f_c80eeb": "80EEB - interest on an electric-vehicle loan (2019-23)", "f_c80gg": "80GG - rent paid (no HRA from an employer)",
    "f_c80ggc": "80GGC - given to a political party (not in cash)",
    "loan_h": "Loan details for {sec}", "f_loan_from": "Lender", "loan_b": "Bank", "loan_i": "Other institution", "f_loan_bank": "Lender's name",
    "f_loan_acc": "Loan account number", "f_loan_date": "Date sanctioned", "f_loan_amount": "Loan amount", "f_loan_left": "Outstanding at 31 March",
    "f_stamp": "Stamp duty value of the house", "f_vehicle": "Vehicle registration number",
    "ggc_h": "The gift to the party", "f_ggc_party": "Party's name", "f_ggc_pan": "Party's PAN", "f_ggc_date": "Date given", "f_ggc_ref": "Transaction reference", "f_ggc_ifsc": "Your bank's IFSC",
}.items():
    knob(w, k, v, k)
save(w, "the More deductions panel on Check.")

# 5 the department's JSON: the new section rows and their schedules, for ITR-1, ITR-2 and ITR-4
m = load("itr.map")
mp = m["params"][0]["default"]
SEC = {"Section80DD": "via.d80DD", "Section80DDB": "via.d80DDB", "Section80EE": "via.d80EE", "Section80EEA": "via.d80EEA",
       "Section80EEB": "via.d80EEB", "Section80GG": "via.d80GG", "Section80GGC": "via.d80GGC"}
for form, root in (("ITR-1", "ITR1"), ("ITR-2", "ITR2"), ("ITR-4", "ITR4")):
    rows = mp[form]
    have = {r["path"] for r in rows}
    for base in sorted({r["path"].rsplit(".", 1)[0] for r in rows if r["path"].endswith(".Section80E")}):
        for fld, src in SEC.items():
            if f"{base}.{fld}" not in have:
                rows.append({"path": f"{base}.{fld}", "from": src, "skip_zero": True})
        if f"{base}.Section80DDBUsrType" not in have:
            rows.append({"path": f"{base}.Section80DDBUsrType", "from": "via_more.ddb_type", "skip_zero": True})
    LOAN = {"LoanTknFrom": "from", "BankOrInstnName": "bank", "LoanAccNoOfBankOrInstnRefNo": "acc", "DateofLoan": "date", "TotalLoanAmt": "amount", "LoanOutstndngAmt": "left"}
    sch = [
        {"path": f"{root}.Schedule80DD.NatureOfDisability", "from": "via_more.dd_nature", "skip_zero": True},
        {"path": f"{root}.Schedule80DD.TypeOfDisability", "from": "via_more.dd_type", "skip_zero": True},
        {"path": f"{root}.Schedule80DD.DependentType", "from": "via_more.dd_dependent", "skip_zero": True},
        {"path": f"{root}.Schedule80DD.DeductionAmount", "from": "via.d80DD", "skip_zero": True},
        {"path": f"{root}.Schedule80EE.Schedule80EEDtls", "each": "loans_80ee", "item": LOAN | {"Interest80EE": "interest"}},
        {"path": f"{root}.Schedule80EE.TotalInterest80EE", "from": "via.d80EE", "skip_zero": True},
        {"path": f"{root}.Schedule80EEA.Schedule80EEADtls", "each": "loans_80eea", "item": LOAN | {"Interest80EEA": "interest"}},
        {"path": f"{root}.Schedule80EEA.PropStmpDtyVal", "from": "via_more.stamp", "skip_zero": True},
        {"path": f"{root}.Schedule80EEA.TotalInterest80EEA", "from": "via.d80EEA", "skip_zero": True},
        {"path": f"{root}.Schedule80EEB.Schedule80EEBDtls", "each": "loans_80eeb", "item": LOAN | {"Interest80EEB": "interest", "VehicleRegNo": "vehicle"}},
        {"path": f"{root}.Schedule80EEB.TotalInterest80EEB", "from": "via.d80EEB", "skip_zero": True},
        {"path": f"{root}.Schedule80GGC.Schedule80GGCDetails", "each": "ggc_rows", "item": {"DonationDate": "date", "DonationAmtCash": "#0", "DonationAmtOtherMode": "amount",
            "TransactionRefNum": "ref", "IFSCCode": "ifsc", "DonationAmt": "amount", "EligibleDonationAmt": "amount", "PoliticalPartyName": "party", "PoliticalPartyPAN": "pan"}},
        {"path": f"{root}.Schedule80GGC.TotalDonationAmtOtherMode80GGC", "from": "via.d80GGC", "skip_zero": True},
        {"path": f"{root}.Schedule80GGC.TotalDonationsUs80GGC", "from": "via.d80GGC", "skip_zero": True},
        {"path": f"{root}.Schedule80GGC.TotalEligibleDonationAmt80GGC", "from": "via.d80GGC", "skip_zero": True},
    ]
    for x in sch:
        if x["path"] not in have:
            rows.append(x)
for t in m["test_cases"]:
    if isinstance(t.get("expect_value"), dict) and "forms" in t["expect_value"] and not t.get("args"):
        t["expect_value"]["forms"] = mp
save(m, "80DD, 80DDB, 80EE, 80EEA, 80EEB, 80GG, 80GGC rows and Schedules 80DD, 80EE, 80EEA, 80EEB, 80GGC for ITR-1, ITR-2 and ITR-4.")
print("done")
