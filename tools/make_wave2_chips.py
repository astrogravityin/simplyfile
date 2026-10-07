"""2026-10-07 My return, wave 2: co-owned house property (s.26), special-rate income (115BB lottery / races / gambling,
115BBJ online games, 115BBH virtual digital assets), agricultural income (partial integration), 44AE goods carriages,
the 80EE / 80EEA check, the employer's and the person's address. Writes / updates the chips once - each step looks first
and leaves a chip already done alone. Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/make_wave2_chips.py
Hand-edit the chips afterwards if you like - this is only how they were first made (AY 2026-27, Finance Act 2025)."""
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


def new_chip(c):
    (CH / f"{c['chip_id']}.json").write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", c["chip_id"], "(new)")


def has_param(c, name):
    return any(p["name"] == name for p in c["params"])


def param(c, name, default, label, typ=None):
    if has_param(c, name):
        return
    typ = typ or ("boolean" if isinstance(default, bool) else "number" if isinstance(default, (int, float)) else "text" if isinstance(default, str) else "json")
    c["params"].append({"name": name, "type": typ, "default": default, "label": label})


def knob(c, name, default, label):
    """A knob on a record chip that hands its params back (rates, settings, words): param, field, and the no-args test."""
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


def key(n):
    return json.dumps(n, sort_keys=True)


def swap(node, match, make, count):
    """Every subtree `match(node)` says yes to becomes make(node) - not looked into again."""
    if match(node):
        count[0] += 1
        return make(node)
    if isinstance(node, dict):
        return {k: swap(v, match, make, count) for k, v in node.items()}
    if isinstance(node, list):
        return [swap(v, match, make, count) for v in node]
    return node


def same(target):
    t = key(target)
    return lambda n: isinstance(n, (dict, list)) and key(n) == t


R = {"chip": "myreturn.rates", "args": {}}


def rget(path):
    return {"vop": "get", "value": R, "path": path}


def run_chip(cid, args):
    from core import engine  # noqa: PLC0415
    import store  # noqa: F401,PLC0415 - registers the portal's chips
    engine.refresh()
    return engine.run(cid, args)


# --- 1 rates: the special rates and the agricultural-income threshold ------------------------------------------------------
r = load("myreturn.rates")
if not has_param(r, "rate_115bb"):
    knob(r, "rate_115bb", 30, "115BB: winnings from lottery, crossword puzzle, races (horse races), card games, gambling, betting - flat rate")
    knob(r, "rate_115bbj", 30, "115BBJ: net winnings from online games - flat rate")
    knob(r, "rate_115bbh", 30, "115BBH: income from transfer of virtual digital assets (crypto, NFT) - flat rate")
    knob(r, "agri_integrate_above", 5000, "net agricultural income above this is added for rate purposes (Finance Act, Part I - partial integration)")
    save(r, "rate_115bb / rate_115bbj / rate_115bbh (30%, both regimes, no basic exemption, no 87A, no Chapter VI-A against them) and agri_integrate_above 5,000 (partial integration, both regimes).")

# --- 2 the tax: special-rate income and partial integration of agricultural income ------------------------------------------
t = load("myreturn.tax")
if not has_param(t, "lottery"):
    F = t["expr"]["fields"]
    old_cases = copy.deepcopy(t["test_cases"])
    for n, lbl in (("lottery", "115BB winnings (lottery, crossword, races, gambling, betting)"), ("online_games", "115BBJ net winnings from online games"),
                   ("vda", "115BBH income from virtual digital assets"), ("agri", "net agricultural income (exempt, but counts for the rate)")):
        param(t, n, 0, lbl)
    TOTAL, SPEC_OLD = F["total"], F["on_special"]["value"]
    assert TOTAL["vop"] == "total" and SPEC_OLD["vop"] == "total" and len(SPEC_OLD["values"]) == 3, (TOTAL["vop"], SPEC_OLD["vop"])
    TOTAL2 = {"vop": "total", "values": TOTAL["values"] + ["$lottery", "$online_games", "$vda"]}
    c = [0]
    t["expr"] = swap(t["expr"], same(TOTAL), lambda n: copy.deepcopy(TOTAL2), c)
    print("  total income replaced", c[0])
    F = t["expr"]["fields"]
    SR2 = F["surcharge_rate"]
    m30 = lambda v, k: {"vop": "mul", "a": v, "b": {"vop": "div", "a": rget(k), "b": 100}}  # noqa: E731
    S30 = {"vop": "total", "values": [m30("$lottery", "rate_115bb"), m30("$online_games", "rate_115bbj"), m30("$vda", "rate_115bbh")]}
    SPEC_NEW = {"vop": "total", "values": SPEC_OLD["values"] + [S30]}
    c = [0]
    t["expr"] = swap(t["expr"], same(SPEC_OLD), lambda n: copy.deepcopy(SPEC_NEW), c)
    print("  special-rate tax replaced", c[0])
    # the surcharge on special-rate tax is capped at 15% - for 111A / 112 / 112A only; on 115BB / BBJ / BBH it is the full rate
    spec_new_key = key(SPEC_NEW)
    capped = lambda n: (isinstance(n, dict) and n.get("vop") == "mul" and key(n.get("a")) == spec_new_key and isinstance(n.get("b"), dict)  # noqa: E731
                        and n["b"].get("vop") == "div" and isinstance(n["b"].get("a"), dict) and n["b"]["a"].get("vop") == "smallest")
    c = [0]
    t["expr"] = swap(t["expr"], capped, lambda n: {"vop": "total", "values": [
        {"vop": "mul", "a": copy.deepcopy(SPEC_OLD), "b": n["b"]}, {"vop": "mul", "a": copy.deepcopy(S30), "b": {"vop": "div", "a": copy.deepcopy(SR2), "b": 100}}]}, c)
    print("  capped surcharge split", c[0])
    assert c[0] > 0
    F = t["expr"]["fields"]
    BASIC = rget({"vop": "template", "text": "basic.{a}.{b}", "values": {"vop": "record", "fields": {"a": "$regime", "b": "$band"}}})
    SL = rget({"vop": "template", "text": "slabs.{a}.{b}", "values": {"vop": "record", "fields": {"a": "$regime", "b": "$band"}}})
    INTEG = {"op": "all", "items": [{"op": "gt", "left": "$agri", "right": rget("agri_integrate_above")}, {"op": "gt", "left": "$total", "right": BASIC}]}
    slab = lambda amount: {"vop": "slab_tax", "amount": amount, "slabs": copy.deepcopy(SL)}  # noqa: E731
    sn = {"chip_id": "myreturn.slab_normal", "kind": "accessor", "set": "myreturn", "label": "My return: slab tax on normal income, agricultural income integrated",
          "aliases": ["partial integration", "agricultural income rate"],
          "params": [{"name": n, "type": "text" if isinstance(d0, str) else "number", "default": d0, "label": lbl} for n, d0, lbl in [
              ("normal", 0, "income charged at the slab rates"), ("agri", 0, "net agricultural income"), ("total", 0, "total income (every head, special rates too)"),
              ("regime", "new", "regime"), ("band", "below60", "age band")]],
          "expr": {"vop": "record", "fields": {
              "tax": {"vop": "choose", "cases": [{"when": INTEG, "then": {"vop": "largest", "values": [
                  {"vop": "sub", "a": slab({"vop": "add", "a": "$normal", "b": "$agri"}), "b": slab({"vop": "add", "a": copy.deepcopy(BASIC), "b": "$agri"})}, 0]}}], "else": slab("$normal")},
              "aggregate": {"vop": "choose", "cases": [{"when": INTEG, "then": slab({"vop": "add", "a": "$normal", "b": "$agri"})}], "else": slab("$normal")},
              "rebate": {"vop": "choose", "cases": [{"when": INTEG, "then": slab({"vop": "add", "a": copy.deepcopy(BASIC), "b": "$agri"})}], "else": 0}}},
          "returns": "record", "version": 1, "status": "published",
          "description_nl": NOTE + "Finance Act 2025, Part I (both regimes - s.115BAC keeps the integration): net agricultural income above 5,000 with total "
          "income above the basic exemption - tax on (normal income + agricultural income) less tax on (basic exemption + agricultural income). "
          "Otherwise the slab tax on normal income. aggregate / rebate are what Part B-TTI shows (tax on the aggregate, rebate on agricultural income).",
          "test_cases": [{"args": {"normal": 600000, "agri": 100000, "total": 600000, "regime": "old"}, "expect_value": {"tax": 47500, "aggregate": 52500, "rebate": 5000}},
                         {"args": {"normal": 600000, "agri": 4000, "total": 600000, "regime": "old"}, "expect_value": {"tax": 32500, "aggregate": 32500, "rebate": 0}},
                         {"args": {"normal": 200000, "agri": 100000, "total": 200000, "regime": "old"}, "expect_value": {"tax": 0, "aggregate": 0, "rebate": 0}},
                         {"args": {"normal": 1000000, "agri": 300000, "total": 1000000}, "expect_value": {"tax": 60000, "aggregate": 75000, "rebate": 15000}}]}
    new_chip(sn)
    call = lambda part: {"vop": "get", "value": {"chip": "myreturn.slab_normal", "args": {"normal": "$normal", "agri": "$agri", "total": copy.deepcopy(TOTAL2),  # noqa: E731
                                                                                       "regime": "$regime", "band": "$band"}}, "path": part}
    is_slab = lambda n: isinstance(n, dict) and n.get("vop") == "slab_tax" and n.get("amount") == "$normal"  # noqa: E731
    c = [0]
    t["expr"] = swap(t["expr"], is_slab, lambda n: call("tax"), c)
    print("  slab tax integrated", c[0])
    F = t["expr"]["fields"]
    new_fields = {
        "on_aggregate": {"vop": "round_to", "value": call("aggregate")},
        "agri_rebate": {"vop": "round_to", "value": call("rebate")},
        "on_111a": {"vop": "round_to", "value": copy.deepcopy(SPEC_OLD["values"][0])},
        "on_112a": {"vop": "round_to", "value": copy.deepcopy(SPEC_OLD["values"][1])},
        "on_112": {"vop": "round_to", "value": copy.deepcopy(SPEC_OLD["values"][2])},
        "on_115bb": {"vop": "round_to", "value": m30("$lottery", "rate_115bb")},
        "on_115bbj": {"vop": "round_to", "value": m30("$online_games", "rate_115bbj")},
        "on_115bbh": {"vop": "round_to", "value": m30("$vda", "rate_115bbh")},
    }
    fields = {}
    for k2, v in F.items():
        fields[k2] = v
        if k2 == "on_special":
            fields |= new_fields
    t["expr"]["fields"] = fields
    (CH / "myreturn.tax.json").write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # every old case keeps its answers; the new fields join them
    for tc in t["test_cases"]:
        got = run_chip("myreturn.tax", tc["args"])
        for k2, v in tc["expect_value"].items():
            assert got[k2] == v, (tc["args"], k2, got[k2], v)
        tc["expect_value"] = got
    adds = [
        ({"normal": 600000, "lottery": 100000}, {"on_normal": 10000, "on_special": 30000, "rebate": 10000, "cess": 1200, "tax": 31200, "on_115bb": 30000}),
        ({"normal": 400000, "lottery": 200000, "regime": "old"}, {"on_normal": 7500, "on_special": 60000, "rebate": 0, "cess": 2700, "tax": 70200}),
        ({"online_games": 200000}, {"basic_left": 400000, "on_special": 60000, "rebate": 0, "tax": 62400, "on_115bbj": 60000}),
        ({"vda": 25000000}, {"surcharge_rate": 25, "on_special": 7500000, "surcharge": 1875000, "cess": 375000, "tax": 9750000}),
        ({"stcg_111a": 25000000}, {"surcharge_rate": 25, "surcharge": 738000}),
        ({"normal": 600000, "agri": 100000, "regime": "old"}, {"on_aggregate": 52500, "agri_rebate": 5000, "on_normal": 47500, "rebate": 0, "cess": 1900, "tax": 49400}),
        ({"normal": 1000000, "agri": 300000}, {"on_aggregate": 75000, "agri_rebate": 15000, "on_normal": 60000, "rebate": 60000, "tax": 0}),
        ({"normal": 600000, "agri": 4000, "regime": "old"}, {"on_aggregate": 32500, "agri_rebate": 0, "on_normal": 32500, "tax": 33800}),
        ({"normal": 200000, "agri": 100000, "regime": "old"}, {"on_normal": 0, "agri_rebate": 0, "tax": 0}),
    ]
    for args, want in adds:
        got = run_chip("myreturn.tax", args)
        bad = {k2: (got[k2], v) for k2, v in want.items() if got[k2] != v}
        assert not bad, (args, bad)
        t["test_cases"].append({"args": args, "expect_value": got})
    save(t, "special-rate income: 115BB (lottery, crossword, races, card games, gambling, betting), 115BBJ (online games) and 115BBH "
            "(virtual digital assets) at 30% each, in both regimes - no basic exemption against them, no 87A rebate on their tax (they still count "
            "in total income for the 87A limit), surcharge on them at the full rate (the 15% cap is for 111A / 112 / 112A only). Agricultural "
            "income above 5,000 with total income above the basic exemption: partial integration in both regimes - tax on (normal + agri) "
            "less tax on (basic exemption + agri); on_aggregate / agri_rebate are the two figures Part B-TTI shows.")

# --- 3 one house: the person's share (s.26 co-owners) -------------------------------------------------------------------------
h = load("myreturn.house")
if not has_param(h, "share"):
    param(h, "share", 100, "the person's share of the property, percent (s.26: each co-owner is assessed on their share)")
    pct = lambda v: {"vop": "round_to", "value": {"vop": "div", "a": {"vop": "mul", "a": v, "b": "$share"}, "b": 100}}  # noqa: E731
    leaves = {"$rent": pct("$rent"), "$municipal_tax": pct("$municipal_tax"), "$interest": pct("$interest")}

    def leaf(n):
        if isinstance(n, str) and n in leaves:
            return copy.deepcopy(leaves[n])
        if isinstance(n, dict):
            return {k2: leaf(v) for k2, v in n.items()}
        if isinstance(n, list):
            return [leaf(v) for v in n]
        return n
    h["expr"] = leaf(h["expr"])
    h["expr"]["fields"] = {"share": "$share", "balance": {"vop": "choose", "cases": [{"when": {"op": "eq", "left": "$kind", "right": "self"}, "then": 0}],
                                                          "else": {"vop": "largest", "values": [{"vop": "sub", "a": "$rent", "b": "$municipal_tax"}, 0]}}} | h["expr"]["fields"]
    for tc in h["test_cases"]:
        tc["expect_value"] = {"share": 100, "balance": tc["expect_value"]["nav"]} | tc["expect_value"]
    h["test_cases"] += [
        {"args": {"kind": "self", "interest": 500000, "regime": "old", "share": 50}, "expect_value": {"share": 50, "balance": 0, "nav": 0, "std": 0, "interest": 200000, "net": -200000}},
        {"args": {"kind": "let", "rent": 300000, "municipal_tax": 20000, "interest": 100000, "regime": "old", "share": 50},
         "expect_value": {"share": 50, "balance": 280000, "nav": 140000, "std": 42000, "interest": 50000, "net": 48000}}]
    save(h, "co-owned (s.26): rent, municipal tax and loan interest each by the person's share; the 30% is on the share's annual value; "
            "a self-occupied house's 2 lakh cap applies to each co-owner on their share. balance is the whole property's annual value (Schedule HP BalanceALV), nav the share.")

# --- 4 the person's virtual digital assets: gain per transfer, a loss counts for nothing (115BBH(2)) ---------------------------
vda = {"chip_id": "myreturn.vda", "kind": "accessor", "set": "myreturn", "label": "My return: virtual digital assets (115BBH)",
       "aliases": ["crypto", "vda", "115bbh"],
       "params": [{"name": "rows", "type": "json", "default": [], "label": "each transfer: {cost, sale} (plus dates, kept as they are)"}],
       "expr": {"vop": "record", "fields": {
           "rows": {"vop": "rows_math", "rows": {"vop": "rows_math", "rows": "$rows", "out": "gain", "how": "sub", "a": "sale", "b": "cost"}, "out": "income", "how": "max", "a": "gain", "b": 0},
           "income": {"vop": "coalesce", "values": [{"vop": "rows_aggregate", "rows": {"vop": "rows_math", "rows": {"vop": "rows_math", "rows": "$rows", "out": "gain", "how": "sub", "a": "sale", "b": "cost"},
                                                                                       "out": "income", "how": "max", "a": "gain", "b": 0}, "agg": "sum", "key": "income"}, 0]},
           "loss_ignored": {"vop": "coalesce", "values": [{"vop": "sub", "a": {"vop": "rows_aggregate", "rows": {"vop": "rows_math", "rows": {"vop": "rows_math", "rows": "$rows", "out": "gain", "how": "sub", "a": "sale", "b": "cost"},
                                                                                                                   "out": "income", "how": "max", "a": "gain", "b": 0}, "agg": "sum", "key": "income"},
                                                          "b": {"vop": "rows_aggregate", "rows": {"vop": "rows_math", "rows": "$rows", "out": "gain", "how": "sub", "a": "sale", "b": "cost"}, "agg": "sum", "key": "gain"}}, 0]}}},
       "returns": "record", "version": 1, "status": "published",
       "description_nl": NOTE + "s.115BBH: income from transferring a virtual digital asset is the sale value less the cost of acquisition - no other "
       "deduction or allowance; a loss on one transfer is not set off against any income (not even another VDA's gain) and is not carried forward. "
       "Each row: {cost, sale}; income is the sum of the gains.",
       "test_cases": [
           {"args": {"rows": [{"cost": 100000, "sale": 250000}, {"cost": 80000, "sale": 50000}]},
            "expect_value": {"rows": [{"cost": 100000, "sale": 250000, "gain": 150000, "income": 150000}, {"cost": 80000, "sale": 50000, "gain": -30000, "income": 0}],
                             "income": 150000, "loss_ignored": 30000}},
           {"args": {}, "expect_value": {"rows": [], "income": 0, "loss_ignored": 0}}]}
if not (CH / "myreturn.vda.json").exists():
    new_chip(vda)

# --- 5 one goods carriage under 44AE ------------------------------------------------------------------------------------------
heavy = {"op": "gt", "left": "$weight_kg", "right": "$heavy_above_kg"}
ae = {"chip_id": "myreturn.vehicle_44ae", "kind": "accessor", "set": "myreturn", "label": "My return: one goods carriage, 44AE",
      "aliases": ["44ae", "goods carriage", "truck"],
      "params": [{"name": n, "type": "number", "default": d, "label": lbl} for n, d, lbl in [
          ("weight_kg", 0, "gross vehicle weight, kg"), ("months", 12, "months (or part of a month) owned or hired in the year"),
          ("heavy_above_kg", 12000, "a heavy goods vehicle: gross vehicle weight above this"),
          ("per_ton", 1000, "heavy goods vehicle: a month, per ton of gross vehicle weight"),
          ("per_vehicle", 7500, "any other goods carriage: a month")]],
      "expr": {"vop": "record", "fields": {
          "heavy": {"vop": "choose", "cases": [{"when": heavy, "then": True}], "else": False},
          "tons": {"vop": "round_to", "value": {"vop": "div", "a": "$weight_kg", "b": 1000}},
          "income": {"vop": "round_to", "value": {"vop": "choose", "cases": [{"when": heavy, "then": {"vop": "mul", "a": {"vop": "mul", "a": "$per_ton", "b": {"vop": "div", "a": "$weight_kg", "b": 1000}}, "b": "$months"}}],
                                                  "else": {"vop": "mul", "a": "$per_vehicle", "b": "$months"}}}}},
      "returns": "record", "version": 1, "status": "published",
      "description_nl": NOTE + "s.44AE: a goods carriage's presumptive income - a heavy goods vehicle (gross vehicle weight above 12,000 kg) 1,000 a "
      "month per ton of gross vehicle weight, any other 7,500 a month, for each month or part of a month it was owned or hired.",
      "test_cases": [{"args": {"weight_kg": 16000, "months": 12}, "expect_value": {"heavy": True, "tons": 16, "income": 192000}},
                     {"args": {"weight_kg": 7500, "months": 10}, "expect_value": {"heavy": False, "tons": 8, "income": 75000}},
                     {"args": {"weight_kg": 12000, "months": 12}, "expect_value": {"heavy": False, "tons": 12, "income": 90000}}]}
if not (CH / "myreturn.vehicle_44ae.json").exists():
    new_chip(ae)

# --- 6 presumptive business: 44AE beside 44ADA / 44AD -----------------------------------------------------------------------
b = load("myreturn.business")
if not has_param(b, "ae_income"):
    param(b, "ae_income", 0, "44AE: the goods carriages' presumptive income (each chip myreturn.vehicle_44ae)")
    param(b, "vehicles", 0, "44AE: goods carriages owned at any time in the year")
    param(b, "ae_max_vehicles", 10, "44AE: at most this many goods carriages at any time in the year")
    is_ae = {"op": "eq", "left": "$kind", "right": "44AE"}
    kind_choose = lambda n: (isinstance(n, dict) and n.get("vop") == "choose" and any(  # noqa: E731
        isinstance(cs.get("when"), dict) and cs["when"].get("left") == "$kind" and cs["when"].get("right") == "44AD" for cs in n.get("cases") or []))
    F = b["expr"]["fields"]
    c = [0]
    F["deemed"] = swap(F["deemed"], kind_choose, lambda n: n | {"cases": n["cases"] + [{"when": is_ae, "then": "$ae_income"}]}, c)
    F["income"] = swap(F["income"], kind_choose, lambda n: n | {"cases": n["cases"] + [{"when": is_ae, "then": "$ae_income"}]}, c)
    print("  44AE deemed cases", c[0])
    F["limit"] = F["limit"] | {"cases": F["limit"]["cases"] + [{"when": is_ae, "then": "$ae_max_vehicles"}]}
    F["over_limit"] = {"vop": "choose", "cases": [{"when": {"op": "all", "items": [is_ae, {"op": "gt", "left": "$vehicles", "right": "$ae_max_vehicles"}]}, "then": True},
                                                  {"when": is_ae, "then": False}], "else": F["over_limit"]}
    (CH / "myreturn.business.json").write_text(json.dumps(b, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for args, want in [({"kind": "44AE", "ae_income": 282000, "vehicles": 2}, {"deemed": 282000, "income": 282000, "limit": 10, "over_limit": False}),
                       ({"kind": "44AE", "ae_income": 282000, "vehicles": 2, "declared": 300000}, {"deemed": 282000, "income": 300000, "over_limit": False}),
                       ({"kind": "44AE", "ae_income": 900000, "vehicles": 11}, {"income": 900000, "over_limit": True})]:
        got = run_chip("myreturn.business", args)
        assert all(got[k2] == v for k2, v in want.items()), (args, got)
        b["test_cases"].append({"args": args, "expect_value": got})
    save(b, "44AE (goods carriages): the income is the vehicles' presumptive income (chip myreturn.vehicle_44ae) or more if declared; more than 10 goods carriages at any time in the year closes 44AE - books and ITR-3.")

# --- 7 which form: special-rate income is never ITR-1 / ITR-4 ---------------------------------------------------------------
f = load("myreturn.form")
if not has_param(f, "special"):
    param(f, "special", False, "winnings (115BB / 115BBJ) or virtual digital assets (115BBH)")
    has_cg = lambda n: (isinstance(n, dict) and n.get("vop") == "choose" and any(  # noqa: E731
        isinstance(cs.get("then"), dict) and (cs["then"].get("fields") or {}).get("why") == "why_cg" for cs in n.get("cases") or []))

    def add_case(n):
        cases, out = n["cases"], []
        for cs in cases:
            out.append(cs)
            if (cs["then"].get("fields") or {}).get("why") == "why_cg":
                out.append({"when": {"op": "eq", "left": "$special", "right": True}, "then": {"vop": "record", "fields": {"form": "ITR-2", "why": "why_special"}}})
        return n | {"cases": out}
    c = [0]
    f["expr"] = swap(f["expr"], has_cg, add_case, c)
    print("  form choosers", c[0])
    f["test_cases"] += [{"args": {"total": 900000, "special": True}, "expect_value": {"form": "ITR-2", "why": "why_special"}},
                        {"args": {"total": 900000, "special": True, "business": True}, "expect_value": {"form": "ITR-3", "why": "why_biz_more"}},
                        {"args": {"total": 900000, "agri": 60000}, "expect_value": {"form": "ITR-2", "why": "why_agri"}}]
    save(f, "winnings from lottery / races / gambling / online games, or a virtual digital asset transferred: ITR-1 and ITR-4 cannot hold them - ITR-2 (ITR-3 with business income).")

# --- 8 80EEA is not for one who claims 80EE (s.80EEA(4)(b)) ------------------------------------------------------------------
d = load("myreturn.deductions")
if "80EE claimed" not in d.get("description_nl", ""):
    old = d["expr"]["fields"]["d80EEA"]
    c = [0]
    d["expr"] = swap(d["expr"], same(old), lambda n: {"vop": "choose", "cases": [{"when": {"op": "gt", "left": "$c80ee", "right": 0}, "then": 0}], "else": n}, c)
    print("  80EEA gated", c[0])
    (CH / "myreturn.deductions.json").write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for tc in d["test_cases"]:
        tc["expect_value"] = run_chip("myreturn.deductions", tc["args"])
    args = {"regime": "old", "gross_total": 2000000, "c80ee": 40000, "c80eea": 150000}
    got = run_chip("myreturn.deductions", args)
    assert got["d80EE"] == 40000 and got["d80EEA"] == 0, got
    d["test_cases"].append({"args": args, "expect_value": got})
    save(d, "80EE claimed: no 80EEA (s.80EEA(4)(b) - not for one who claims 80EE); chip myreturn.check_80ee says so on Check.")

ck = {"chip_id": "myreturn.check_80ee", "kind": "accessor", "set": "myreturn", "label": "My return: 80EE and 80EEA both claimed",
      "aliases": ["80ee 80eea"],
      "params": [{"name": "c80ee", "type": "number", "default": 0, "label": "80EE claimed"}, {"name": "c80eea", "type": "number", "default": 0, "label": "80EEA claimed"}],
      "expr": {"vop": "record", "fields": {"what": "ee_both", "a": "$c80ee", "b": "$c80eea", "gap": "$c80eea", "word": "lv_ee_both",
                                           "level": {"vop": "choose", "cases": [{"when": {"op": "all", "items": [{"op": "gt", "left": "$c80ee", "right": 0},
                                                                                                            {"op": "gt", "left": "$c80eea", "right": 0}]}, "then": "red"}], "else": "ok"}}},
      "returns": "record", "version": 1, "status": "published",
      "description_nl": NOTE + "s.80EEA(4)(b): 80EEA is for one not eligible under 80EE - both claimed is a red check (the return keeps 80EE and drops 80EEA, chip myreturn.deductions).",
      "test_cases": [{"args": {"c80ee": 40000, "c80eea": 150000}, "expect_value": {"what": "ee_both", "a": 40000, "b": 150000, "gap": 150000, "word": "lv_ee_both", "level": "red"}},
                     {"args": {"c80eea": 150000}, "expect_value": {"what": "ee_both", "a": 0, "b": 150000, "gap": 150000, "word": "lv_ee_both", "level": "ok"}}]}
if not (CH / "myreturn.check_80ee.json").exists():
    new_chip(ck)

# --- 9 settings: the person's address and contact, typed on Review when no document has them --------------------------------
s = load("myreturn.settings")
P = {p["name"]: p for p in s["params"]}
if "email" not in P["questions"]["default"]:
    qs = P["questions"]["default"] + ["address", "city", "pin", "email", "mobile", "lottery_on", "games_on"]
    ad = P["answer_defaults"]["default"] | {"address": "", "city": "", "pin": "", "email": "", "mobile": "", "lottery_on": "", "games_on": ""}
    knob(s, "questions", qs, "questions")
    knob(s, "answer_defaults", ad, "answer defaults")
    knob(s, "vda_max", 50, "virtual digital asset transfers typed, at most")
    knob(s, "vehicles_max", 20, "goods carriages typed, at most (44AE allows 10; more is shown, and closes 44AE)")
    save(s, "the person's address, city, PIN, e-mail and mobile (typed on Review when no document has them - a typed answer wins), the dates of winnings (lottery_on, games_on), vda_max, vehicles_max.")

# --- 10 reading: AIS winnings / VDA, the AIS header, the employer's address in Form 16 ----------------------------------------
STATES = dict(x.split("=", 1) for x in next(p["default"] for p in load("ui.myreturn")["params"] if p["name"] == "states").split("|"))
rd = load("myreturn.read")
RP = {p["name"]: p for p in rd["params"]}
if not any(row.get("field") == "lottery" for row in RP["ais_codes"]["default"]):
    rows = [{"code": "TDS-194BB.*", "field": "lottery"}, {"code": "TDS-194BA.*", "field": "online_games"}, {"code": "TDS-194B", "field": "lottery"},
            {"code": "TDS-194S.*", "field": "vda_sale"},
            {"title": "winnings? from (lotter|crossword|horse race|card game|gambling|betting)", "field": "lottery"},
            {"title": "winnings? from online game", "field": "online_games"}, {"title": "virtual digital asset", "field": "vda_sale"}]
    knob(rd, "ais_codes", rows + RP["ais_codes"]["default"], "AIS information code / title -> field")
    knob(rd, "income_of", RP["income_of"]["default"] | {"194B": "lottery", "194BB": "lottery", "194BA": "online_games"}, "26AS section -> the income it shows")
    knob(rd, "ais_header", {"start_words": ["part a", "general information", "annual information statement"], "end": "(?i)\\bPART\\s*B\\b",
                            "mobile": "(?i)mobile(?:\\s*(?:number|no\\.?))?\\s*:?\\s*(?:\\+?91[\\s-]*)?([6-9]\\d{9})\\b",
                            "email": "(?i)e-?\\s*mail(?:\\s*(?:address|id))?\\s*:?\\s*([\\w.+-]+@[\\w-]+(?:\\.[\\w-]+)+)",
                            "address": "(?i)\\baddress\\s*:?\\s*(.+?)(?=\\s+(?:mobile|e-?\\s*mail|date of birth|pan|aadhaar)\\b|$)",
                            "json": {"mobile": ["mobileNo", "mobileNumber", "mobile"], "email": ["emailId", "emailAddress", "email"], "address": ["address", "addressLine"]}},
         "the taxpayer's mobile, e-mail and address in the AIS's general information (Part A) - fills what the pre-filled JSON lacks")
    knob(rd, "employer_block", {"stop": "(?i)PAN of the Deductor|TAN of the Deductor|Name and address of the Employee|Certificate No|Period with the Employer",
                                "column_gap": "\\s{3,}", "email": "[\\w.+-]+@[\\w-]+(?:\\.[\\w-]+)+", "phone": "^\\+?\\(?\\d[\\d()\\s-]{6,}$",
                                "pin": "\\b[1-9][0-9]{5}\\b", "city": "([A-Za-z][A-Za-z .]+?)\\s*[-,]?\\s*[1-9][0-9]{5}"},
         "Form 16 Part A: the employer's address block (the lines under 'Name and address of the Employer', left column) - address, city, PIN, state")
    knob(rd, "state_names", [{"pattern": "(?i)\\b" + n.replace(" and ", " (?:and|&) ") + "\\b", "code": c2} for c2, n in sorted(STATES.items(), key=lambda kv: -len(kv[1]))]
         + [{"pattern": "(?i)\\bOrissa\\b", "code": "24"}, {"pattern": "(?i)\\bPondicherry\\b", "code": "25"}, {"pattern": "(?i)\\bNew Delhi\\b", "code": "09"},
            {"pattern": "(?i)\\bBombay\\b", "code": "19"}],
         "a state named in an address -> the department's state code")
    pins = [("160", "06"), ("194", "37"), ("403", "10"), ("605", "25"), ("68255", "17"), ("737", "28"), ("744", "01"), ("79[0-2]", "03"), ("79[34]", "21"),
            ("795", "20"), ("796", "22"), ("79[78]", "23"), ("799", "30"), ("24[6-9]", "34"), ("263", "34"), ("396", "08"),
            ("11", "09"), ("1[23]", "12"), ("1[456]", "26"), ("17", "13"), ("1[89]", "14"), ("2[0-8]", "31"), ("3[0-4]", "27"), ("3[6-9]", "11"),
            ("4[0-4]", "19"), ("4[5-8]", "18"), ("49", "33"), ("50", "36"), ("5[1-3]", "02"), ("5[6-9]", "15"), ("6[0-4]", "29"), ("6[7-9]", "16"),
            ("7[0-4]", "32"), ("7[5-7]", "24"), ("78", "04"), ("83", "35"), ("8[0-2]|8[45]", "05")]
    knob(rd, "pin_states", [{"pattern": f"^(?:{p})", "code": c2} for p, c2 in pins],
         "a guess of the state from the PIN when the address names none (postal circles; the person can correct it)")
    save(rd, "AIS TDS-194B / 194BB (winnings - 115BB), 194BA (online games - 115BBJ), 194S (a VDA transferred - the sale value, shown beside the rows typed); "
             "26AS 194B / 194BB / 194BA; the AIS header's mobile, e-mail and address; Form 16's employer address block, a state from its name or PIN.")

# --- 11 the JSON's codes ----------------------------------------------------------------------------------------------------
j = load("myreturn.json")
if not has_param(j, "si_codes"):
    knob(j, "si_codes", {"stcg_111a": ["1A", 20], "ltcg_112a": ["2A", 12.5], "ltcg_112": ["21", 12.5], "lottery": ["5BB", 30], "online_games": ["5BBJ", 30], "vda": ["5BBH", 30]},
         "Schedule SI: a figure -> [section code, rate]")
    knob(j, "quarters", [["Upto15Of6", "0615"], ["Upto15Of9", "0915"], ["Up16Of9To15Of12", "1215"], ["Up16Of12To15Of3", "0315"], ["Up16Of3To31Of3", "0331"]],
         "the advance-tax periods a special income is shown by (Schedule OS / CG date ranges): [field, up to MMDD]")
    knob(j, "quarter_default", "Upto15Of6", "a winning with no date: the first period (no 234C relief claimed for it)")
    knob(j, "agri_category", "AGRI", "exempt income: agricultural (ITR-1 Category)")
    knob(j, "co_owned", {"true": "YES", "false": "NO"}, "Schedule HP: co-owned flag")
    knob(j, "vda_head", "CG", "Schedule VDA: head the income is taxed under (an investor's - capital gains)")
    knob(j, "vehicle_own", {"own": "OWN", "lease": "LEASE", "hired": "HIRED"}, "44AE: owned / leased / hired")
    save(j, "Schedule SI codes and rates, the special-income date ranges, agricultural (AGRI), co-owned YES/NO, VDA head CG, 44AE owned / leased / hired.")

# --- 12 words ----------------------------------------------------------------------------------------------------------------
w = load("ui.myreturn")
if not any(p["name"] == "why_special" for p in w["params"]):
    for k2, v in {
        "why_special": "ITR-2, because of winnings (lottery, races, gambling, online games) or virtual digital assets - ITR-1 and ITR-4 cannot take them.",
        "f_lottery": "Winnings - lottery, crossword, races, card games, betting (115BB)", "f_online_games": "Net winnings from online games (115BBJ)",
        "rv_special_h": "Winnings and crypto (taxed at 30%)", "rv_special_p": "Winnings from a lottery, crossword, race, card game or betting (115BB) and online games (115BBJ) are taxed at 30% with no basic exemption, no 87A rebate and no deduction against them. Crypto and other virtual digital assets (115BBH): 30% on the gain - cost is the only deduction, and a loss counts for nothing. The AIS shows them as TDS-194B, 194BB, 194BA and 194S.",
        "vda_h": "Virtual digital assets transferred", "vda_add": "Add a transfer", "vda_none": "No crypto or other virtual digital asset sold in the year.",
        "f_vda_acquired": "Bought on", "f_vda_transferred": "Sold on", "f_vda_cost": "Cost", "f_vda_sale": "Sold for", "f_vda_name": "Asset (coin / token)",
        "vda_total": "Income from virtual digital assets {income} (a loss of {loss} counts for nothing)", "vda_seen": "The AIS shows {amount} received for virtual digital assets transferred (194S).",
        "f_lottery_on": "Winnings received on", "f_games_on": "Online-game winnings received on",
        "f_agri": "Net agricultural income", "agri_p": "Exempt, but above 5,000 it raises the rate on your other income (partial integration) and needs ITR-2.",
        "f_share": "Your share %", "f_co_name": "Co-owner's name", "f_co_pan": "Co-owner's PAN", "h_co_p": "Co-owned: the rent, municipal tax and loan interest are taken by your share; a self-occupied house's 2 lakh interest limit applies to your share.",
        "biz_ae": "Goods carriages - 44AE", "ae_h": "Goods carriages", "ae_add": "Add a vehicle", "f_ae_reg": "Registration no.", "f_ae_weight": "Gross vehicle weight (kg)",
        "f_ae_months": "Months held", "f_ae_own": "Owned / leased / hired", "ae_own": "own=Owned|lease=Leased|hired=Hired",
        "ae_income": "44AE income {income} on {n} vehicles (heavy: 1,000 a ton a month; others 7,500 a month)", "ae_over": "More than 10 goods carriages - 44AE is not open; this needs books and ITR-3.",
        "c_ee_both": "80EE and 80EEA both claimed", "lv_ee_both": "80EEA is not allowed to one who claims 80EE (s.80EEA(4)) - only the 80EE of {a} counts; drop 80EE to claim 80EEA instead.",
        "q_address": "Your address (house, street, area)", "q_city": "City / town", "q_pin": "PIN code", "q_email": "E-mail", "q_mobile": "Mobile",
        "q_contact_p": "From your pre-filled JSON or AIS when they have it; type here to change what goes into the return.",
    }.items():
        knob(w, k2, v, k2)
    save(w, "co-owned houses, winnings and virtual digital assets, agricultural income, 44AE vehicles, the 80EE / 80EEA check, and the address and contact fields.")

# --- 13 the department's JSON: where the new figures go ----------------------------------------------------------------------
m = load("itr.map")
mp = m["params"][0]["default"]
if not any(r["path"] == "ITR2.ScheduleVDA.ScheduleVDADtls" for r in mp["ITR-2"]):
    def rows_of(form):
        return mp[form]

    def set_item(form, path, changes, drop=()):
        row = next(r for r in mp[form] if r["path"] == path)
        for k2 in drop:
            row["item"].pop(k2, None)
        row["item"].update(changes)

    def set_from(form, path, src):
        row = next(r for r in mp[form] if r["path"] == path)
        row["from"] = src

    hp_more = {"PropCoOwnedFlg": "co_flag", "AsseseeShareProperty": "share", "CoOwners": "co_owners", "Rentdetails.BalanceALV": "balance"}
    set_item("ITR-1", "ITR1.ITR1_IncomeDeductions.PropertyDetails", hp_more)
    set_item("ITR-4", "ITR4.IncomeDeductions.PropertyDetails", hp_more)
    set_item("ITR-2", "ITR2.ScheduleHP.PropertyDetails", hp_more)
    set_item("ITR-2", "ITR2.ScheduleS.Salaries", {"AddressDetail.PinCode": "pin"})
    for p in ("ITR2.ScheduleOS.IncChargeable", "ITR2.ScheduleOS.IncOthThanOwnRaceHorse.BalanceNoRaceHorse", "ITR2.ScheduleOS.TotOthSrcNoRaceHorse", "ITR2.PartB-TI.IncFromOS.TotIncFromOS"):
        set_from("ITR-2", p, "os.all")
    set_from("ITR-2", "ITR2.PartB-TI.CapGain.TotalCapGains", "cg.with_vda")
    set_from("ITR-2", "ITR2.ScheduleCGFor23.TotScheduleCGFor23", "cg.with_vda")
    set_from("ITR-2", "ITR2.PartB-TI.IncChargeableTaxSplRates", "cg.special_all")
    set_from("ITR-2", "ITR2.PartB_TTI.ComputationOfTaxLiability.TaxPayableOnTI.TaxAtNormalRatesOnAggrInc", "tax2.on_aggregate")
    sz = lambda path, src: {"path": path, "from": src, "skip_zero": True}  # noqa: E731
    Q = ["Upto15Of6", "Upto15Of9", "Up16Of9To15Of12", "Up16Of12To15Of3", "Up16Of3To31Of3"]
    mp["ITR-2"] += [
        sz("ITR2.ScheduleOS.IncOthThanOwnRaceHorse.IncChargeableSpecialRates", "os.special"),
        sz("ITR2.ScheduleOS.IncOthThanOwnRaceHorse.LtryPzzlChrgblUs115BB", "os.lottery"),
        sz("ITR2.ScheduleOS.IncOthThanOwnRaceHorse.IncChrgblUs115BBJ", "os.online_games"),
        *[sz(f"ITR2.ScheduleOS.IncFrmLottery.DateRange.{q}", f"lottery_q.{q}") for q in Q],
        *[sz(f"ITR2.ScheduleOS.IncFrmOnGames.DateRange.{q}", f"games_q.{q}") for q in Q],
        sz("ITR2.PartB-TI.IncFromOS.IncChargblSplRate", "os.special"),
        sz("ITR2.PartB-TI.CapGain.CapGains30Per115BBH", "vda.income"),
        sz("ITR2.ScheduleCGFor23.IncmFromVDATrnsf", "vda.income"),
        *[sz(f"ITR2.ScheduleCGFor23.AccruOrRecOfCG.VDATrnsfGainsUnder30Per.DateRange.{q}", f"vda_q.{q}") for q in Q],
        {"path": "ITR2.ScheduleVDA.ScheduleVDADtls", "each": "vda_rows", "item": {"DateofAcquisition": "acquired", "DateofTransfer": "transferred", "HeadUndIncTaxed": "head",
                                                                                  "AcquisitionCost": "cost", "ConsidReceived": "sale", "IncomeFromVDA": "income"}},
        sz("ITR2.ScheduleVDA.TotIncCapGain", "vda.income"),
        {"path": "ITR2.ScheduleSI.SplCodeRateTax", "each": "si_rows", "item": {"SecCode": "code", "SplRatePercent": "rate", "SplRateInc": "income", "SplRateIncTax": "tax"}},
        sz("ITR2.ScheduleSI.TotSplRateInc", "si.income"),
        sz("ITR2.ScheduleSI.TotSplRateIncTax", "si.tax"),
        sz("ITR2.ScheduleEI.GrossAgriRecpt", "agri.gross"),
        sz("ITR2.ScheduleEI.NetAgriIncOrOthrIncRule7", "agri.net"),
        sz("ITR2.ScheduleEI.TotalExemptInc", "agri.net"),
        sz("ITR2.PartB-TI.NetAgricultureIncomeOrOtherIncomeForRate", "agri.net"),
        sz("ITR2.PartB_TTI.ComputationOfTaxLiability.TaxPayableOnTI.RebateOnAgriInc", "tax2.agri_rebate"),
    ]
    mp["ITR-1"] += [
        {"path": "ITR1.ITR1_IncomeDeductions.ExemptIncAgriOthUs10.ExemptIncAgriOthUs10Dtls", "each": "agri_rows", "item": {"Category": "category", "OthAmount": "amount"}},
        sz("ITR1.ITR1_IncomeDeductions.ExemptIncAgriOthUs10.ExemptIncAgriOthUs10Total", "agri.itr1"),
    ]
    mp["ITR-4"] += [
        {"path": "ITR4.ScheduleBP.NatOfBus44AE", "from": "biz.nature_ae"},
        {"path": "ITR4.ScheduleBP.GoodsDtlsUs44AE", "each": "ae_rows", "item": {"RegNumberGoodsCarriage": "reg", "OwnedLeasedHiredFlag": "own", "TonnageCapacity": "tons",
                                                                               "HoldingPeriod": "months", "PresumptiveIncome": "income"}},
        sz("ITR4.ScheduleBP.PersumptiveInc44AE.TotPersumInc44AE", "biz.ae_income"),
        sz("ITR4.ScheduleBP.PersumptiveInc44AE.TotalPersumptiveInc", "biz.ae_income"),
        sz("ITR4.ScheduleBP.PersumptiveInc44AE.IncChargeableUnderBus", "biz.ae_income"),
    ]
    for tc in m["test_cases"]:
        if isinstance(tc.get("expect_value"), dict) and "forms" in tc["expect_value"] and not tc.get("args"):
            tc["expect_value"]["forms"] = mp
    save(m, "co-owners and the person's share in every Schedule HP; the employer's PIN; ITR-2 winnings (Schedule OS 115BB / 115BBJ and their date ranges), "
            "Schedule VDA and the 115BBH gain in Schedule CG / Part B-TI, Schedule SI (every special rate), Schedule EI and partial integration "
            "(Part B-TTI tax on the aggregate and the rebate on agricultural income); ITR-1 agricultural income up to 5,000; ITR-4 44AE (nature, each goods carriage, income).")
# --- 14 the readers' last knobs and words -------------------------------------------------------------------------------------
rd = load("myreturn.read")
eb = next(p["default"] for p in rd["params"] if p["name"] == "employer_block")
if "employee_anchor" not in eb:
    eb = {k2: v for k2, v in eb.items() if k2 != "city"} | {"employee_anchor": "Name and address of the Employee", "lines_max": 8}
    knob(rd, "employer_block", eb, "Form 16 Part A: the employer's address block")
    save(rd, "employer_block: the employee's column (left of it is the employer's), at most 8 lines.")
w = load("ui.myreturn")
if not any(p["name"] == "fd_vda_seen" for p in w["params"]):
    for k2, v in {"fd_vda_seen": "Virtual digital assets sold (194S)", "fd_address": "Your address", "fd_employer_at": "Employer's address"}.items():
        knob(w, k2, v, k2)
    save(w, "what the readers found: a VDA sold, the person's address (AIS), the employer's address (Form 16).")
print("done")
