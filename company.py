"""Company returns - ITR-6 for a domestic company (2026-10-11 owner: "build ITR-6 ... reuse the same machinery, no second engine").

A company is a client like any other (Clients & years: status Company, PAN 4th letter C, form ITR-6) with a company part - CIN,
date of incorporation, kind, tax option (normal / 115BA / 115BAA / 115BAB), listed or not, manufacturing, its key persons and
shareholders. Its statements go through Intake & map (SF Refs ITR6 BP <item>, ITR6 DEP <block>, ITR6 MAT <item>, ITR6 OS / CG /
80G, ITR6 BS / PL <item>), Reconcile (26AS, AIS) and Compute & close like a firm's; compute.compute() asks this module for the
heads, the total income and the tax, and keeps everything else (TDS, 234A/B/C, the balance, sign-off, filing) as it is.

Here Python only gathers: the mapped rows, the fixed-asset schedule's columns, the year's typed facts (turnover of the earlier
year, losses and MAT credit brought forward, s.79, dividends distributed) - and asks the chips: company.rate (the option),
company.dep_block (each block), company.setoff (each set-off, in the order chip company.settings names), company.loss_ok (each
brought-forward loss and credit), company.d80g / company.d80m, company.tax and company.mat. itr_facts() gives chip itr.map's
ITR-6 rows their facts, in our words; the rows say where each goes in the CBDT schema.
"""
from __future__ import annotations

import re

from fastapi import HTTPException

import clients
import recon
from core import engine

SPECIAL = ("stcg_111a", "ltcg_112a", "ltcg_112")


def settings() -> dict:
    return engine.run("company.settings")


def say(key: str, **values) -> str:
    return engine.say("ui.compute", key, **values)


def is_company(c: dict) -> bool:
    return bool((clients.status_of(c.get("status") or "") or {}).get("has_company"))


def rates(ay: str) -> tuple[dict, bool]:
    """The AY's rates (chip company.settings rates_by_ay) and whether they are this AY's own (else the verified AY's, flagged)."""
    k = settings()
    own = k["rates_by_ay"].get(ay)
    return own or k["rates_by_ay"][k["default_ay"]], bool(own)


# --- the master data (Clients & years) ------------------------------------------------------------------------------------------

def _txt(v, n: int = 150) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def _code(v) -> str:
    return re.sub(r"\s+", "", str(v or "")).upper()


def _num(v) -> float:
    try:
        return float(re.sub(r"[^\d.\-]", "", str(v if v is not None else "")) or 0)
    except ValueError:
        return 0.0


def _date(v) -> str:
    v = str(v or "").strip()[:10]
    return v if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else ""


def clean(body: dict) -> dict:
    """The company part as typed -> as kept, or a 400 naming the first thing wrong (chip company.problem)."""
    k = settings()
    b = body if isinstance(body, dict) else {}
    pan_bad = next((p for p in [_code(x.get("pan")) for x in (b.get("directors") or []) + (b.get("shareholders") or []) if isinstance(x, dict)]
                    if p and not clients.shape_ok("pan", p)), "")
    if pan_bad:
        raise HTTPException(400, clients.say("bad_pan", pan=pan_bad))
    holders = [{"name": _txt(x.get("name"), 125), "pan": _code(x.get("pan")), "pct": _num(x.get("pct")), "shares": int(_num(x.get("shares"))),
                "face": _num(x.get("face")), "issue": _num(x.get("issue")), "allotted": _date(x.get("allotted")),
                "resident": x.get("resident") not in (False, "false", "no", "N", "n"), "address": _txt(x.get("address"), 200)}
               for x in b.get("shareholders") or [] if isinstance(x, dict) and _txt(x.get("name"))]
    directors = [{"name": _txt(x.get("name"), 125), "din": re.sub(r"\D", "", str(x.get("din") or ""))[:8], "pan": _code(x.get("pan")),
                  "designation": _code(x.get("designation")) or k["designations"][1]["id"], "father": _txt(x.get("father"), 125),
                  "address": _txt(x.get("address"), 200)}
                 for x in b.get("directors") or [] if isinstance(x, dict) and _txt(x.get("name"))]
    out = {"cin": _code(b.get("cin")), "incorporated": _date(b.get("incorporated")) or str(b.get("incorporated") or "")[:10],
           "kind": str(b.get("kind") or k["kinds"][0]["id"]), "option": str(b.get("option") or k["options"][0]["id"]),
           "option_ay": _txt(b.get("option_ay"), 7), "option_ack": re.sub(r"\D", "", str(b.get("option_ack") or ""))[:15],
           "option_date": _date(b.get("option_date")), "manufacturing": bool(b.get("manufacturing")), "msme": bool(b.get("msme")),
           "indas": bool(b.get("indas")), "nature_code": re.sub(r"\D", "", str(b.get("nature_code") or ""))[:5],
           "trade_name": _txt(b.get("trade_name"), 75), "shareholders": holders, "directors": directors}
    din_shape = k["din_pattern"]
    problem = engine.run("company.problem", {
        "cin": out["cin"], "cin_pattern": k["cin_pattern"], "kind": out["kind"], "kinds": [x["id"] for x in k["kinds"]],
        "option": out["option"], "options": [x["id"] for x in k["options"]], "manufacturing": out["manufacturing"],
        "bad_din": any(d["din"] and not re.fullmatch(din_shape, d["din"]) for d in directors),
        "bad_share": any(not 0 <= h["pct"] <= 100 for h in holders), "share_total": sum(h["pct"] for h in holders),
        "incorporated": out["incorporated"]})
    if problem:
        raise HTTPException(400, clients.say(problem))
    return out


def listed(co: dict) -> bool:
    return bool(next((x for x in settings()["kinds"] if x["id"] == co.get("kind")), {}).get("listed"))


def clean_year(body: dict) -> dict:
    """The year's typed facts (Compute & close, company section)."""
    b = body if isinstance(body, dict) else {}
    years = clients.settings()["years"]
    old = lambda a: _txt(a, 7) if re.fullmatch(r"\d{4}-\d{2}", _txt(a, 7)) else ""  # noqa: E731
    return {"turnover_py": _num(b.get("turnover_py")), "s79_ok": b.get("s79_ok") not in (False, "false", "no"),
            "dividend_paid": _num(b.get("dividend_paid")), "dividend_paid_on": _date(b.get("dividend_paid_on")),
            "opt_now": bool(b.get("opt_now")), "opt_now_ack": re.sub(r"\D", "", str(b.get("opt_now_ack") or ""))[:15],
            "opt_now_date": _date(b.get("opt_now_date")), "audit_on": _date(b.get("audit_on")),
            "audit_ack": re.sub(r"\D", "", str(b.get("audit_ack") or ""))[:15],
            "bf_losses": [{"ay": old(x.get("ay")), "business": _num(x.get("business")), "dep": _num(x.get("dep")),
                           "filed_on": _date(x.get("filed_on")), "filed_ok": x.get("filed_ok") not in (False, "false", "no")}
                          for x in b.get("bf_losses") or [] if isinstance(x, dict) and old(x.get("ay")) and old(x.get("ay")) not in years[-1:]],
            "mat_credit": [{"ay": old(x.get("ay")), "amount": _num(x.get("amount"))}
                           for x in b.get("mat_credit") or [] if isinstance(x, dict) and old(x.get("ay")) and _num(x.get("amount"))]}


# --- the computation ------------------------------------------------------------------------------------------------------------

def _age(ay: str, of: str) -> int:
    return int(ay[:4]) - int(of[:4])


def _cols(x: dict, cols: dict) -> dict:
    """A fixed-asset row's figures by column (chip company.settings dep_columns): each column title read once, in the chip's order."""
    titles = [str(t or "") for t, _ in x.get("by_col") or []]
    vals = [v for _, v in x.get("by_col") or []]
    taken, out = set(), {}
    for name, pat in cols.items():
        i = next((j for j, t in enumerate(titles) if j not in taken and re.search(pat, t)), None)
        if i is not None:
            taken.add(i)
            out[name] = _num(vals[i])
    return out


def dep_rows(cid: str, ay: str) -> dict:
    """The fixed-asset schedule: rows tagged '<form> DEP <block>', added up per block."""
    import intake  # noqa: PLC0415 - intake imports clients only
    k = settings()
    ids = {b["id"] for b in k["dep_blocks"]}
    got: dict[str, dict] = {}
    for m in intake.files(cid, ay)["files"]:
        for x in intake.view(cid, ay, m["id"])["rows"]:
            if x["state"] != "tagged":
                continue
            for p in intake.parse_ref(x["ref"]) or []:
                blk = str(p.get("serial") or "").lower()
                if p["table"] == "DEP" and blk in ids:
                    one = _cols(x, k["dep_columns"])
                    if not one:
                        one = {"opening": _num(x.get("amount"))}
                    acc = got.setdefault(blk, {})
                    for f, v in one.items():
                        acc[f] = acc.get(f, 0.0) + v
    return got


def depreciation(cid: str, ay: str, co: dict, rate: dict) -> dict:
    k = settings()
    rows = dep_rows(cid, ay)
    blocks = []
    for b in k["dep_blocks"]:
        if b["id"] not in rows:
            continue
        r = rows[b["id"]]
        res = engine.run("company.dep_block", {
            "opening": r.get("opening", 0), "more": r.get("more", 0), "less": r.get("less", 0), "sales": r.get("sales", 0), "rate": b["rate"],
            "addl_ok": bool(b["addl"] and rate["addl_dep"] and co.get("manufacturing")), "addl_rate": k["addl_dep_rate"],
            "new_more": r.get("new_more", 0), "new_less": r.get("new_less", 0), "addl_bf": r.get("addl_bf", 0)})
        blocks.append({"id": b["id"], "label": b["label"], "rate": b["rate"], "sum": b["sum"], "in": r} | res)
    return {"blocks": blocks, "total": sum(x["total"] for x in blocks), "gain_50": sum(x["gain_50"] for x in blocks),
            "addl_carry": sum(x["addl_carry"] for x in blocks)}


def _sign(label: str) -> int:
    return 1 if recon.is_income(label) else -1


def _setoff(available: float, against: float) -> dict:
    return engine.run("company.setoff", {"available": available, "against": against})


def work(cid: str, ay: str, c: dict, st: dict, books: list[dict], kc: dict) -> dict:
    """The company's heads, set-offs, deductions, total income and tax. kc = chip compute.settings (the house-property 30%)."""
    k = settings()
    R, own_rates = rates(ay)
    co = c.get("company") or {}
    cy = st.get("company") or {}
    rate = engine.run("company.rate", {"option": co.get("option") or "normal", "turnover": cy.get("turnover_py") or 0, "rates": R, "via_sets": k["via_sets"]})
    warn = [] if own_rates else ["co_w_rates"]
    if rate["why"] == "why_turnover_missing":
        warn.append("co_w_turnover")

    # business income: the computation statement, item by item (chip company.settings bp_items), and depreciation u/s 32
    items, bp_lines = {}, []
    for r in (r for r in books if r["table"] == "BP"):
        it = str(r.get("serial") or "").lower()
        if it not in k["bp_items"]:
            it = "other_add" if _sign(r["label"]) > 0 else "other_less"
        sg = k["bp_items"][it]["sign"]
        items[it] = items.get(it, 0.0) + r["amount"]
        bp_lines.append({"label": r["label"], "amount": sg * r["amount"], "file": r["file"], "key": r["key"], "item": it})
    dep = depreciation(cid, ay, co, rate)
    if dep["blocks"]:
        bp_lines.append({"label": say("co_dep32_line"), "amount": -dep["total"], "file": "", "key": "DEP", "item": "dep32"})
    bp = sum(x["amount"] for x in bp_lines)

    heads = []
    if bp_lines:
        heads.append({"id": "BP", "lines": bp_lines, "gross": bp, "net": bp})
    hp_rows = [r for r in books if r["table"] == "HP" and not re.search(kc["hp_skip_pattern"], r["label"] or "")]
    hp = 0.0
    if hp_rows:
        lines = [{"label": r["label"], "amount": _sign(r["label"]) * r["amount"], "file": r["file"], "key": r["key"]} for r in hp_rows]
        nav = sum(x["amount"] for x in lines)
        h = {"id": "HP", "lines": lines, "gross": nav} | engine.run("compute.hp", {"nav": nav, "std_pct": kc["hp_std_pct"], "loss_cap": kc["hp_loss_cap"]})
        heads.append(h)
        hp = h["net"]
    os_items, os_lines = {}, []
    for r in (r for r in books if r["table"] == "OS"):
        it = str(r.get("serial") or "").lower()
        it = it if it in k["os_items"] else "other"
        v = _sign(r["label"]) * r["amount"]
        os_items[it] = os_items.get(it, 0.0) + v
        os_lines.append({"label": r["label"], "amount": v, "file": r["file"], "key": r["key"], "item": it})
    os_ = sum(os_items.values())
    if os_lines:
        heads.append({"id": "OS", "lines": os_lines, "gross": os_, "net": os_})
    cg_in, cg_lines = {x: 0.0 for x in k["cg_items"]}, []
    for r in (r for r in books if r["table"] in ("CG", "STCG", "LTCG")):
        it = str(r.get("serial") or "").lower()
        it = it if it in k["cg_items"] else ("ltcg_112" if r["table"] == "LTCG" else "stcg")
        cg_in[it] += r["amount"]                                           # a gain as the statement writes it; a loss is negative
        cg_lines.append({"label": r["label"], "amount": r["amount"], "file": r["file"], "key": r["key"], "item": it})
    if dep["gain_50"]:                                                     # a block sold beyond its WDV: short-term gain u/s 50
        cg_in["stcg"] += dep["gain_50"]
        cg_lines.append({"label": say("co_gain50_line"), "amount": dep["gain_50"], "file": "", "key": "DEP", "item": "stcg"})
    # capital losses inside the head (s.74 order: chip company.settings st_loss_order / lt_loss_order)
    gains = {x: max(0.0, v) for x, v in cg_in.items()}  # ponytail: a negative item is a loss; the set-off below is the chip's
    st_loss = -sum(v for x, v in cg_in.items() if v < 0 and k["cg_items"][x]["kind"] == "st")
    lt_loss = -sum(v for x, v in cg_in.items() if v < 0 and k["cg_items"][x]["kind"] == "lt")
    for x in k["lt_loss_order"]:
        s = _setoff(lt_loss, gains[x])
        lt_loss, gains[x] = s["loss_left"], s["income_left"]
    for x in k["st_loss_order"]:
        s = _setoff(st_loss, gains[x])
        st_loss, gains[x] = s["loss_left"], s["income_left"]
    if cg_lines:
        heads.append({"id": "CG", "lines": cg_lines, "gross": sum(cg_in.values()), "net": sum(gains.values())})

    # CYLA: a house-property loss (up to 2 lakh), then a business loss, against the other heads (s.71)
    inc = {"bp": max(0.0, bp), "hp": max(0.0, hp), "os": max(0.0, os_)} | gains
    cyla = {"hp_loss": max(0.0, -hp), "bp_loss": max(0.0, -bp), "os_loss": max(0.0, -os_), "used": {}}
    hp_cap = _setoff(cyla["hp_loss"], k["hp_setoff_cap"])["used"]
    hp_left = hp_cap
    for x in ["bp"] + [o for o in k["cyla_order"] if o != "hp"]:
        s = _setoff(hp_left, inc[x])
        hp_left, inc[x] = s["loss_left"], s["income_left"]
        cyla["used"][f"hp>{x}"] = s["used"]
    cyla["hp_used"] = hp_cap - hp_left
    cyla["hp_cf"] = cyla["hp_loss"] - cyla["hp_used"]
    bp_left = cyla["bp_loss"] + cyla["os_loss"]
    for x in k["cyla_order"]:
        s = _setoff(bp_left, inc[x])
        bp_left, inc[x] = s["loss_left"], s["income_left"]
        cyla["used"][f"bp>{x}"] = s["used"]
    cyla["bp_used"] = cyla["bp_loss"] + cyla["os_loss"] - bp_left
    ud_now = _setoff(bp_left, dep["total"])["used"]                       # the part of the loss that is depreciation: unabsorbed
    cyla["bp_cf"], cyla["ud_cf"] = bp_left - ud_now, ud_now

    # BFLA: business losses (s.72, against business income only), then unabsorbed depreciation (s.32(2), any head)
    bf_rows = []
    for x in sorted(cy.get("bf_losses") or [], key=lambda r: r["ay"]):
        for kind in ("business", "dep"):
            if not x.get(kind):
                continue
            ok = engine.run("company.loss_ok", {"kind": kind, "age": _age(ay, x["ay"]), "filed_ok": x.get("filed_ok", True),
                                                 "listed": listed(co), "s79_ok": cy.get("s79_ok", True), "years": k["loss_years"]})
            bf_rows.append({"ay": x["ay"], "kind": kind, "amount": x[kind], "filed_on": x.get("filed_on", ""), "ok": ok["ok"], "why": ok["why"], "used": 0.0})
    for r in (r for r in bf_rows if r["kind"] == "business" and r["ok"]):
        s = _setoff(r["amount"], inc["bp"])
        r["used"], inc["bp"] = s["used"], s["income_left"]
    for r in (r for r in bf_rows if r["kind"] == "dep" and r["ok"]):
        left = r["amount"]
        for x in ["bp"] + k["cyla_order"]:
            s = _setoff(left, inc[x])
            left, inc[x] = s["loss_left"], s["income_left"]
        r["used"] = r["amount"] - left
    for r in bf_rows:
        r["left"] = r["amount"] - r["used"] if r["ok"] else 0.0
    gti = sum(inc.values())
    special = sum(inc[x] for x in SPECIAL)

    # Chapter VI-A: what the option allows (chip company.rate via), s.80M, s.80G
    import compute  # noqa: PLC0415 - compute imports this module
    due = compute.dates(cid, ay)["due"]
    d80m = engine.run("company.d80m", {"dividend_in": max(0.0, os_items.get("dividend", 0.0)), "paid": cy.get("dividend_paid") or 0,
                                        "paid_on": int((cy.get("dividend_paid_on") or "0").replace("-", "")), "due": due, "months": k["d80m_months"]})
    m80 = d80m["deduction"] if "80M" in rate["via"] else 0.0
    gcat = {x: 0.0 for x in k["g80_cats"]}
    g_rows = []
    for r in (r for r in books if r["table"] == "80G"):
        cat = str(r.get("serial") or "").lower()
        cat = cat if cat in k["g80_cats"] else "50q"
        gcat[cat] += r["amount"]
        g_rows.append({"label": r["label"], "amount": r["amount"], "cat": cat, "key": r["key"], "file": r["file"], "text": r.get("text", "")})
    d80g = engine.run("company.d80g", {"d100": gcat["100"], "d50": gcat["50"], "d100q": gcat["100q"], "d50q": gcat["50q"],
                                        "adj_gti": gti - special - m80, "limit_pct": k["g80_limit_pct"], "allowed": "80G" in rate["via"]})
    asked = m80 + d80g["total"]
    capped = engine.run("compute.total_income", {"gti": gti - special, "deductions": asked, "round_to": 1})["deductions"]   # VI-A never meets special-rate gains
    ti = engine.run("compute.total_income", {"gti": gti, "deductions": capped, "round_to": R["round_to"]})
    income = ti["income"]
    normal = income - special
    if rate["split_business"]:                                              # 115BAB: the manufacturing business at its rate, the rest at 22%
        s = _setoff(inc["bp"], normal)
        main, other = s["used"], s["income_left"]
    else:
        main, other = normal, 0.0
    tax_n = engine.run("company.tax", {"main": main, "other": other, "stcg_111a": inc["stcg_111a"], "ltcg_112a": inc["ltcg_112a"], "ltcg_112": inc["ltcg_112"],
                                       "rate": rate["rate"], "other_rate": rate["other_rate"], "steps": rate["steps"], "cg": R["cg"],
                                       "cess_pct": R["cess_pct"], "round_to": R["round_to"]})

    # MAT u/s 115JB and the credit u/s 115JAA
    mat_items = {}
    for r in (r for r in books if r["table"] == "MAT"):
        it = str(r.get("serial") or "").lower()
        if it in k["mat_items"]:
            mat_items[it] = mat_items.get(it, 0.0) + r["amount"]
    book_from = "mat_rows" if mat_items else "pl"
    if not mat_items:                                                       # no Form 29B rows: the P&L's profit before tax (shown as such)
        mat_items = {"pat": items.get("profit", 0.0) + items.get("tax", 0.0)}
    book_profit = sum(k["mat_items"][x]["sign"] * v for x, v in mat_items.items())
    credits = []
    for x in sorted(cy.get("mat_credit") or [], key=lambda r: r["ay"]):
        ok = engine.run("company.loss_ok", {"kind": "mat", "age": _age(ay, x["ay"]), "years": k["loss_years"]})
        credits.append({"ay": x["ay"], "amount": x["amount"], "ok": ok["ok"], "why": ok["why"], "used": 0.0})
    m = engine.run("company.mat", {"normal_total": tax_n["total"], "book_profit": book_profit, "applies": rate["mat"], "mat_rate": R["mat_rate"],
                                   "steps": R["bands"], "cess_pct": R["cess_pct"], "round_to": R["round_to"],
                                   "credit_available": sum(x["amount"] for x in credits if x["ok"])})
    room = m["credit_used"]
    for x in (x for x in credits if x["ok"]):
        s = _setoff(x["amount"], room)
        x["used"], room = s["used"], s["income_left"]
    for x in credits:
        x["left"] = x["amount"] - x["used"] if x["ok"] else 0.0
    parts = m["parts"] if m["pays_mat"] else tax_n
    tax = {"tax": parts["tax"], "rebate": 0, "surcharge_rate": parts["surcharge_rate"], "surcharge": parts["surcharge"], "relief": parts["relief"],
           "cess": parts["cess"], "gross": m["gross"], "credit_used": m["credit_used"], "total": m["net"], "basis": "mat" if m["pays_mat"] else "normal"}
    ded_rows = ([{"label": say("co_80m_line"), "amount": m80, "table": "VIA", "file": "", "key": "80M"}] if m80 else []) + \
               ([{"label": say("co_80g_line"), "amount": d80g["total"], "table": "VIA", "file": "", "key": "80G"}] if d80g["total"] else [])
    return {"heads": heads, "gti": gti, "deductions": ti["deductions"], "deduction_rows": ded_rows, "income": income, "tax": tax,
            "company": {"option": co.get("option") or "normal", "kind": co.get("kind"), "listed": listed(co), "manufacturing": bool(co.get("manufacturing")),
                        "rate": rate, "rates_own": own_rates, "turnover_py": cy.get("turnover_py") or 0, "turnover_py_label": R["turnover_py"],
                        "turnover_limit": R["turnover_limit"], "year": cy, "warnings": warn,
                        "bp": {"items": items, "net": bp, "dep32": dep["total"] if dep["blocks"] else items.get("it_dep", 0.0)},
                        "dep": dep, "hp": hp, "os": {"items": os_items, "net": os_}, "cg": {"in": cg_in, "after": gains, "st_loss_cf": st_loss, "lt_loss_cf": lt_loss,
                                                                                           "special": special},
                        "inc": inc, "cyla": cyla, "bfla": bf_rows, "setoff_total": sum(max(0.0, h["net"]) for h in heads) - gti, "d80m": d80m | {"allowed": "80M" in rate["via"], "deduction": m80},
                        "d80g": d80g | {"rows": g_rows, "cats": gcat}, "normal": tax_n, "main": main, "other": other,
                        "mat": m, "book_profit": book_profit, "book_from": book_from, "mat_items": mat_items, "credits": credits,
                        "credit_new": m["credit_new"]}}


# --- the facts chip itr.map's ITR-6 rows point at (our words; the rows hold the schema's paths) --------------------------------

def _pin(s: str) -> str:
    return (re.findall(r"\b[1-9][0-9]{5}\b", s or "") or [""])[-1]


def _addr(s: str, state: str, fallback: dict) -> dict:
    parts = [p.strip() for p in re.sub(r"\b[1-9][0-9]{5}\b", "", s or "").split(",") if p.strip()]
    pin = _pin(s) or fallback.get("pin", "")
    return {"addr": (", ".join(parts[:-1]) if len(parts) > 1 else (parts[0] if parts else fallback.get("flat", "")))[:100] or "-",
            "city": (parts[-1] if parts else fallback.get("city", ""))[:50] or "-", "state": state, "pin": int(pin) if pin else ""}


def itr_facts(cid: str, ay: str, d: dict, f: dict) -> dict:
    """Facts 'co.*' for the ITR-6 rows of chip itr.map, from compute.compute()'s company part (d) and the facts gathered (f)."""
    k = settings()
    codes = engine.run("itr.codes")["by_form"].get("ITR-6", {})
    yn = codes.get("flags") or engine.run("itr.codes")["flags"]
    flag = lambda v: yn[str(bool(v)).lower()]  # noqa: E731
    c = clients.get(cid)
    y = clients.year_of(cid, ay)
    co_c = c.get("company") or {}
    x = d["company"]
    cy = x["year"]
    state = (c.get("gst") or "")[:2] or f["client"].get("state", "")
    here = {"pin": f["client"].get("pin", ""), "city": f["client"].get("city", ""), "flat": f["client"].get("flat", "")}
    opt = x["option"]
    earlier = opt != "normal" and not cy.get("opt_now")
    persons = [{"name": p["name"], "designation": p["designation"], "pan": p["pan"], "din": p["din"]} | _addr(p["address"] or c.get("address", ""), state, here)
               for p in co_c.get("directors") or []]
    holders = co_c.get("shareholders") or []
    big = [{"name": h["name"], "pct": h["pct"], "pan": h["pan"]} | _addr(h["address"] or "", state, here) for h in holders if h["pct"] >= k["holder_min_pct"]]
    sh = [{"name": h["name"], "res": codes.get("residential", {}).get(str(not h["resident"]).lower(), "RES"), "type": codes.get("share_type", "ES"),
           "pan": h["pan"], "allotted": h["allotted"] or co_c.get("incorporated") or "", "shares": h["shares"], "face": h["face"],
           "issue": h["issue"] or h["face"], "amount": round(h["shares"] * (h["issue"] or h["face"]))}
          for h in holders if h["pct"] >= k["sh_min_pct"]] if not x["listed"] else []
    signer = next((p for p in co_c.get("directors") or [] if p["designation"] == "MD"), None) or next(iter(co_c.get("directors") or []), {})
    bpi, dep = x["bp"]["items"], x["dep"]
    g = lambda key: round(bpi.get(key, 0.0))  # noqa: E731
    profit = g("profit") + g("tax")
    hp_in, cg_in, div_in, oth_in, exempt = g("hp_income"), g("cg_income"), g("dividend"), g("os_income"), g("exempt")
    balance = profit - hp_in - cg_in - div_in - oth_in - exempt
    dep32 = round(x["bp"]["dep32"])
    after_dep = balance + g("book_dep") - dep32
    adds = {key: g(key) for key in ("s36", "s37", "s40", "s40a", "s43b", "other_add")}
    adds["s37"] += g("csr")
    total_add = after_dep + sum(adds.values())
    less = {key: g(key) for key in ("s40_paid", "s43b_paid", "other_less")}
    net_bp = total_add - sum(less.values())
    blocks = {b["id"]: {"wdv_first": round(b["in"].get("opening", 0)), "add_more": round(b["in"].get("more", 0)), "real_full": round(b["real_full"]),
                        "full_base": round(b["full_base"]), "add_less": round(b["in"].get("less", 0)), "real_half": round(b["real_half"]),
                        "half_base": round(b["half_base"]), "dep_full": round(b["dep_full"]), "dep_half": round(b["dep_half"]),
                        "addl_more": round(b["addl_more"]) or None, "addl_less": round(b["addl_less"]) or None, "addl_bf": round(b["addl_bf"]) or None,
                        "total": round(b["total"]), "zero": 0, "net": round(b["total"]), "wdv_last": round(b["wdv_last"]), "gain_50": round(b["gain_50"])}
              for b in dep["blocks"]}
    sums = {}
    for b in dep["blocks"]:
        sums[b["sum"]] = sums.get(b["sum"], 0) + round(b["total"])
    pm = sum(sums.get(s, 0) for s in ("pm15", "pm30", "pm40", "pm45"))
    bl = sum(sums.get(s, 0) for s in ("b5", "b10", "b40"))
    depsum = {"pm15": sums.get("pm15", 0), "pm30": sums.get("pm30", 0), "pm40": sums.get("pm40", 0), "pm45": sums.get("pm45", 0), "pm_total": pm,
              "b5": sums.get("b5", 0), "b10": sums.get("b10", 0), "b40": sums.get("b40", 0), "b_total": bl, "furn": sums.get("furn", 0),
              "intang": sums.get("intang", 0), "ships": sums.get("ships", 0), "total": sum(sums.values())} if dep["blocks"] else {}
    oi = {key: round(v) for key, v in x["os"]["items"].items()}
    os_total = round(max(0.0, x["os"]["net"]))
    cgi = {key: round(v) for key, v in x["cg"]["after"].items()}
    lt = cgi.get("ltcg_112a", 0) + cgi.get("ltcg_112", 0)
    st = cgi.get("stcg_111a", 0) + cgi.get("stcg", 0)
    inc0 = {"bp": max(0, round(x["bp"]["net"])), "hp": max(0, round(x["hp"])), "os": os_total} | cgi
    cyla, inc = x["cyla"], {key: round(v) for key, v in x["inc"].items()}
    used = {key: round(v) for key, v in cyla["used"].items()}
    after_cyla = {key: inc0[key] - used.get(f"hp>{key}", 0) - used.get(f"bp>{key}", 0) for key in inc0}
    for src in (inc0, after_cyla):                                            # Schedule CYLA / BFLA put both long-term gains on one line
        src["lt"] = src.get("ltcg_112", 0) + src.get("ltcg_112a", 0)
    for w in ("hp", "bp"):
        used[f"{w}>lt"] = used.get(f"{w}>ltcg_112", 0) + used.get(f"{w}>ltcg_112a", 0)
    bf_bus = round(sum(r["used"] for r in x["bfla"] if r["kind"] == "business"))
    bf_ud = round(sum(r["used"] for r in x["bfla"] if r["kind"] == "dep"))
    inc["lt"] = inc.get("ltcg_112", 0) + inc.get("ltcg_112a", 0)
    bf_by = {key: after_cyla[key] - inc[key] for key in inc}
    ud_on = {key: v - (bf_bus if key == "bp" else 0) for key, v in bf_by.items()}
    cfl = {}
    for r in x["bfla"]:
        a = cfl.setdefault(r["ay"], {"filed_on": r["filed_on"] or "", "business": 0, "available": 0})
        if r["kind"] == "business":
            a["business"] += round(r["amount"])
            a["available"] += round(r["amount"]) if r["ok"] else 0
    ud = [{"ay": r["ay"], "bf": round(r["amount"]), "baa": 0, "used": round(r["used"]), "left": round(r["left"]), "zero": 0}
          for r in x["bfla"] if r["kind"] == "dep"]
    tn, m = x["normal"], x["mat"]
    mp = m.get("parts") or {}
    special = round(x["cg"]["special"])
    ti_total = sum(inc0.values())
    cy_loss = sum(used.values())
    via = {"s80g": round(x["d80g"]["total"]), "s80m": round(x["d80m"]["deduction"])}
    tti_gross = round(tn["total"])
    mat_rows = {key: round(v) for key, v in x["mat_items"].items()}
    madd = sum(v for key, v in mat_rows.items() if k["mat_items"][key]["sign"] > 0 and key != "pat")
    mless = sum(v for key, v in mat_rows.items() if k["mat_items"][key]["sign"] < 0)
    credit_rows = [{"ay": r["ay"], "gross": round(r["amount"]), "setoff": 0, "bf": round(r["amount"]), "used": round(r["used"]), "left": round(r["left"])}
                   for r in x["credits"] if r["ok"]]
    cg_rates = rates(ay)[0]["cg"]
    si = [{"code": k["cg_items"][key]["si"], "rate": cg_rates[key], "income": cgi.get(key, 0), "tax": round(tn["on_" + key.split("_", 1)[1]])}
          for key in SPECIAL if cgi.get(key)]
    g80 = {}
    for cat, spec in k["g80_cats"].items():
        rows = [r for r in x["d80g"]["rows"] if r["cat"] == cat]
        if not spec["path"] or not rows:
            continue
        donees = []
        for r in rows:
            p = clients.party_of(c, r["label"]) or {}
            where = _addr(p.get("address", ""), state, here)
            donees.append({"name": r["label"][:125], "pan": p.get("pan", ""), "addr": where["addr"], "city": where["city"], "pin": where["pin"], "state": state,
                           "cash": 0, "other": round(r["amount"]), "amount": round(r["amount"]),
                           "eligible": round(r["amount"] * (1 if cat in ("100", "100q") else 0.5))})
        g80[cat] = {"rows": donees, "cash": 0, "other": sum(r["amount"] for r in donees), "total": sum(r["amount"] for r in donees),
                    "eligible": sum(r["eligible"] for r in donees)}
    g80_tot = sum(v["total"] for v in g80.values())
    band = next((b["code"] for b in codes.get("turnover_bands", []) if (x["turnover_py"] or 0) <= b["upto"]), codes.get("turnover_band_top", ""))
    return {
        "gen": {"cin": co_c.get("cin", ""), "incorporated": co_c.get("incorporated") or c.get("dob") or "",
                "company_type": next((t["code"] for t in k["kinds"] if t["id"] == co_c.get("kind")), k["kinds"][0]["code"]),
                "domestic": flag(True), "opt115": opt if earlier else codes.get("no_option", "NA"),
                "opt_ay": co_c.get("option_ay") if earlier else "", "opt_ack": int(co_c["option_ack"]) if earlier and co_c.get("option_ack") else "",
                "opt_date": co_c.get("option_date") if earlier else "", "opt_now": flag(opt != "normal" and cy.get("opt_now")),
                "opt_now_sec": opt if cy.get("opt_now") and opt != "normal" else "", "opt_now_date": cy.get("opt_now_date") if cy.get("opt_now") else "",
                "opt_now_ack": int(cy["opt_now_ack"]) if cy.get("opt_now") and cy.get("opt_now_ack") else "",
                "small": flag(x["rate"]["low_turnover"]), "fs_indas": flag(co_c.get("indas")), "unlisted": flag(not x["listed"]),
                "msme": flag(co_c.get("msme")), "audit44ab": flag(y.get("audit")), "tp": flag(y.get("tp")), "audit_on": cy.get("audit_on", ""),
                "audit_ack": int(cy["audit_ack"]) if cy.get("audit_ack") else "", "turnover_band": band,
                "nature": co_c.get("nature_code") or "", "trade_name": co_c.get("trade_name") or c["name"][:75],
                "signer": signer.get("name", ""), "signer_pan": signer.get("pan", ""), "signer_father": signer.get("father", "") or c.get("father", ""),
                "capacity": k["signer_codes"].get(signer.get("designation", ""), k["signer_codes"].get("DIR", ""))},
        "persons": persons, "holders": big, "sh": sh, "has_sh": flag(bool(sh)),
        "bp": {"profit": profit, "hp_in": hp_in, "cg_in": cg_in, "os_in": div_in + oth_in, "div_in": div_in, "oth_in": oth_in, "exempt": exempt,
               "balance": balance, "book_dep": g("book_dep"), "dep32": dep32, "after_dep": after_dep, **adds, "total_add": total_add,
               **less, "total_less": sum(less.values()), "net": net_bp},
        "dep": blocks, "depsum": depsum,
        "os": {**oi, "interest_gross": oi.get("interest", 0) + oi.get("deposit", 0) + oi.get("refund", 0), "gross": round(x["os"]["net"]), "total": os_total},
        "nature": [{"code": co_c["nature_code"], "trade": co_c.get("trade_name") or c["name"][:75]}] if co_c.get("nature_code") else [],
        "cg": {"stcg_111a": cgi.get("stcg_111a", 0), "stcg": cgi.get("stcg", 0), "st": st, "ltcg": lt, "lt": lt, "total": st + lt},
        "cyla": {"hp_loss": round(cyla["hp_loss"]), "bp_loss": round(cyla["bp_loss"]), "inc": inc0, "after": after_cyla,
                 "hp_used": used, "hp_total": round(cyla["hp_used"]), "bp_total": round(cyla["bp_used"]),
                 "hp_left": round(cyla["hp_cf"]), "bp_left": round(cyla["bp_cf"] + cyla["ud_cf"])},
        "bfla": {"in": after_cyla, "by": bf_by, "ud_on": ud_on, "bus": bf_bus, "ud": bf_ud, "after": inc, "total": round(d["gti"])},
        "cfl": cfl, "cfl_total": {"available": sum(v["available"] for v in cfl.values()), "used": bf_bus, "cy": round(cyla["bp_cf"]),
                                  "all": sum(v["available"] for v in cfl.values()) - bf_bus + round(cyla["bp_cf"])},
        "ud": ud, "ud_total": {"bf": sum(r["bf"] for r in ud), "used": sum(r["used"] for r in ud), "left": sum(r["left"] for r in ud),
                               "cy": round(cyla["ud_cf"]), "ay": ay if ud or cyla["ud_cf"] else "",
                               "all": sum(r["left"] for r in ud) + round(cyla["ud_cf"])},
        "ti": {"hp": inc0["hp"], "bp": inc0["bp"], "stcg20": cgi.get("stcg_111a", 0), "st_app": cgi.get("stcg", 0), "st": st, "lt125": lt, "lt": lt,
               "cg": st + lt, "os": os_total, "total": ti_total, "cy_loss": cy_loss, "after_cyla": ti_total - cy_loss, "bf": bf_bus + bf_ud,
               "gti": round(d["gti"]), "special": special, "via_b": via["s80g"], "via_c": via["s80m"], "via": via["s80g"] + via["s80m"],
               "income": round(d["income"]), "normal": round(d["income"]) - special,
               "cf": round(cyla["bp_cf"]) + round(cyla["hp_cf"]), "deemed": max(0, round(x["book_profit"])) if x["rate"]["mat"] else None},
        "tti": {"mat_tax": round(mp.get("tax", 0)), "mat_sur": round(mp.get("surcharge", 0) - mp.get("relief", 0)), "mat_cess": round(mp.get("cess", 0)),
                "mat_total": round(m["mat"]), "at_normal": round(tn["at_normal"]), "at_special": round(tn["at_special"]), "tax": round(tn["tax"]),
                "sur": round(tn["surcharge"] - tn["relief"]), "cess": round(tn["cess"]), "liab": tti_gross, "gross": round(m["gross"]),
                "credit": round(m["credit_used"]), "after_credit": round(m["net"]), "net": round(m["net"])},
        "mat": {"pat": mat_rows.get("pat", 0), **{key: v for key, v in mat_rows.items() if key != "pat"},
                "add_total": madd, "less_total": mless, "book": round(x["book_profit"]), "tax": round(mp.get("tax", 0)),
                "sched_vi": codes.get("mat_yes", "1"), "agm": codes.get("mat_yes", "1")} if x["rate"]["mat"] else {},
        "matc": {} if not (x["rate"]["mat"] or credit_rows) else {"tax_jb": round(m["mat"]), "tax_other": tti_gross, "with_credit": max(0, tti_gross - round(m["mat"])) if x["rate"]["mat"] else 0,
                 "rows": credit_rows, "cur_ay": ay, "gross_cur": round(m["credit_new"]), "bal_cur": round(m["credit_new"]),
                 "tot_gross": sum(r["gross"] for r in credit_rows) + round(m["credit_new"]), "tot_setoff": 0,
                 "tot_bf": sum(r["bf"] for r in credit_rows), "tot_used": round(m["credit_used"]),
                 "tot_bal": sum(r["left"] for r in credit_rows) + round(m["credit_new"]), "used": round(m["credit_used"]),
                 "cf": sum(r["left"] for r in credit_rows) + round(m["credit_new"])},
        "si": si, "si_total": {"income": sum(r["income"] for r in si), "tax": sum(r["tax"] for r in si)},
        "g80": g80, "g80_total": {"cash": 0, "other": g80_tot, "total": g80_tot, "eligible": via["s80g"]},
        "via": via | {"m_os": via["s80m"], "b": via["s80g"], "c": via["s80m"], "total": via["s80g"] + via["s80m"]},
    }


if __name__ == "__main__":  # ponytail: the chips answer a company's year the way the Act does
    import store as _portal_store  # noqa: F401 - registers this portal's chips
    R, _ = rates("2026-27")
    r = engine.run("company.rate", {"option": "115BAA", "turnover": 1, "rates": R, "via_sets": settings()["via_sets"]})
    t = engine.run("company.tax", {"main": 2000000, "rate": r["rate"], "steps": r["steps"], "cg": R["cg"]})
    assert t["total"] == 503360 and not r["mat"], (t, r)                   # 22% x 1.10 x 1.04 = 25.168%
    assert engine.run("company.loss_ok", {"kind": "business", "age": 9})["why"] == "lo_lapsed"
    assert _cols({"by_col": [("WDV as on 01.04.2025", 100), ("Additions - 180 days or more", 20), ("Additions - less than 180 days", 5),
                             ("Sale", 3)]}, settings()["dep_columns"]) == {"opening": 100, "more": 20, "less": 5, "sales": 3}
    print("company self-check OK")
