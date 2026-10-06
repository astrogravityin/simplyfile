"""My return - an individual files their own ITR-1 or ITR-2 (2026-10-06 owner: "Can I use SimplyFile for individual filing
help ... Form 16 integration and bank statements ... the most intuitive and sophisticated experience").

One journey, five steps (chip myreturn.settings steps): Gather (drop the pre-filled JSON from the e-filing portal, the AIS,
Form 16 from each employer, 26AS - myreturn_read.py reads each one and says what it found), Check (the same figure from two
documents, compared: Form 16's TDS against 26AS, salary against AIS, interest against what is claimed - chip
myreturn.checks), Choose (both regimes worked out side by side, the cheaper one marked - chips myreturn.salary / house /
deductions / tax / better), Review (every figure, where it came from, and an edit box), File (ITR-1 or ITR-2 - chip
myreturn.form - as the department's own JSON, checked against its schema by itr_json.assemble).

A figure comes from the documents (chip myreturn.sources says which document wins for which part) unless the person typed
their own (state["edits"]): a typed figure always wins, and says so. Python reads, merges and adds up; every rate, limit,
rule and word is a chip (myreturn.*, ui.myreturn).
"""
from __future__ import annotations

import copy
import datetime
import re
import threading
from pathlib import Path

from fastapi import HTTPException

import clients
import compute
from core import engine, store
from core.ops import template

_LOCK = threading.Lock()   # ponytail: one lock for every return; per-return locks if many people save at once
SECTIONS = ("person", "employers", "other", "cg", "via", "tds", "paid", "banks", "houses")
OTHER = ("savings", "deposits", "dividend", "family_pension", "refund_interest", "other")
CG = ("stcg_111a", "ltcg_112a", "ltcg_112", "stcg_other")
VIA = ("c80c", "c80ccc", "c80ccd1", "c80ccd1b", "c80ccd2", "c80d_self", "c80d_parents", "c80e", "c80g")
EMPLOYER = ("name", "tan", "gross_17_1", "perq_17_2", "profit_17_3", "exempt_all", "exempt_new", "hra", "prof_tax", "tds", "basic_da")


def settings() -> dict:
    return engine.run("myreturn.settings")


def say(key: str, **values) -> str:
    return template(engine.run("ui.myreturn")[key], values)


def _bad(key: str, code: int = 400, **values):
    raise HTTPException(code, say(key, **values))


def _num(v) -> float:
    try:
        return round(float(str(v).replace(",", "").strip() or 0), 2)
    except (TypeError, ValueError):
        return 0.0


# --- where things live --------------------------------------------------------------------------------------------------

def _name(cid: str, ay: str) -> str:
    clients.get(cid)                                        # 404 for a client not in the register
    if ay not in clients.settings()["years"]:
        raise HTTPException(400, clients.say("bad_ay", ay=ay))
    return f"sf_myreturn/{cid}/{ay}.json"


def folder(cid: str, ay: str) -> Path:
    _name(cid, ay)
    p = store.DATA / "sf_myreturn" / cid / ay
    p.mkdir(parents=True, exist_ok=True)
    return p


def state(cid: str, ay: str) -> dict:
    return store.read(_name(cid, ay), {}) or {}


def _save(cid: str, ay: str, st: dict) -> None:
    st["updated_at"] = store.now()
    store.write(_name(cid, ay), st)


# --- the documents ------------------------------------------------------------------------------------------------------

def add_doc(user: dict, cid: str, ay: str, filename: str, data: bytes, password: str = "") -> dict:
    """Keep the file, read it (myreturn_read.read), and add what it said to the return."""
    import myreturn_read  # noqa: PLC0415 - the readers import nothing of ours
    clients.guard_open(cid, ay)
    k = settings()
    ext = Path(filename).suffix.lower()
    if ext not in k["exts"]:
        _bad("bad_ext", exts=", ".join(k["exts"]))
    if len(data) > int(k["max_mb"]) * 1024 * 1024:
        _bad("too_big", mb=k["max_mb"])
    st0 = state(cid, ay)
    c = clients.get(cid)
    dob = c.get("dob") or next((d["facts"]["person"].get("dob") for d in st0.get("docs") or [] if (d.get("facts") or {}).get("person", {}).get("dob")), "")
    got = myreturn_read.read(filename, data, password=password, user=user, ay=ay, pan=c.get("pan", ""), dob=dob,
                             ai_ok=bool((st0.get("answers") or {}).get("ai_ok")))
    fid = store.new_id()
    (folder(cid, ay) / f"{fid}{ext}").write_bytes(data)
    doc = {"id": fid, "name": Path(filename).name[:120], "ext": ext, "size": len(data), "kind": got["kind"], "method": got["method"],
           "facts": got["facts"], "found": got.get("found", []), "problems": got.get("problems", []),
           "added_at": store.now(), "added_by": user["id"]}
    with _LOCK:
        st = state(cid, ay)
        st.setdefault("docs", []).append(doc)
        _save(cid, ay, st)
    return work(cid, ay) | {"added": {k2: doc[k2] for k2 in ("id", "name", "kind", "method", "found", "problems")}}


def remove_doc(user: dict, cid: str, ay: str, fid: str) -> dict:
    clients.guard_open(cid, ay)
    with _LOCK:
        st = state(cid, ay)
        docs = st.get("docs") or []
        d = next((x for x in docs if x["id"] == fid), None)
        if not d:
            _bad("no_doc", 404)
        st["docs"] = [x for x in docs if x["id"] != fid]
        _save(cid, ay, st)
    f = folder(cid, ay) / f"{fid}{d['ext']}"
    f.unlink(missing_ok=True)
    return work(cid, ay)


def doc_file(cid: str, ay: str, fid: str) -> tuple[Path, str]:
    d = next((x for x in state(cid, ay).get("docs") or [] if x["id"] == fid), None)
    if not d or not re.fullmatch(r"[0-9a-f]+", fid):
        _bad("no_doc", 404)
    return folder(cid, ay) / f"{fid}{d['ext']}", d["name"]


# --- the person's own answers and figures --------------------------------------------------------------------------------

def answer(user: dict, cid: str, ay: str, body: dict) -> dict:
    """answers (yes/no questions and small facts), edits (a figure typed over the documents'), houses, regime."""
    clients.guard_open(cid, ay)
    k = settings()
    with _LOCK:
        st = state(cid, ay)
        for q, v in (body.get("answers") or {}).items():
            if q not in k["questions"]:
                _bad("bad_field", field=q)
            st.setdefault("answers", {})[q] = v if isinstance(v, bool) else str(v)[:80]
        for sec, vals in (body.get("edits") or {}).items():
            if sec not in ("other", "cg", "via"):
                _bad("bad_field", field=sec)
            ok = {"other": OTHER, "cg": CG, "via": VIA}[sec]
            for f, v in (vals or {}).items():
                if f not in ok:
                    _bad("bad_field", field=f)
                e = st.setdefault("edits", {}).setdefault(sec, {})
                if v in (None, ""):
                    e.pop(f, None)                  # blank = back to what the documents say
                else:
                    e[f] = _num(v)
        for i, vals in (body.get("employers") or {}).items():
            e = st.setdefault("edits", {}).setdefault("employers", {}).setdefault(str(i), {})
            for f, v in (vals or {}).items():
                if f not in EMPLOYER:
                    _bad("bad_field", field=f)
                if v in (None, ""):
                    e.pop(f, None)
                else:
                    e[f] = str(v)[:120] if f in ("name", "tan") else _num(v)
        if "houses" in body:
            hs = []
            for h in (body["houses"] or [])[: int(k["houses_max"])]:
                kind = str(h.get("kind") or "self")
                if kind not in ("self", "let"):
                    _bad("bad_field", field="kind")
                hs.append({"kind": kind, "rent": _num(h.get("rent")), "municipal_tax": _num(h.get("municipal_tax")),
                           "interest": _num(h.get("interest")), "address": str(h.get("address") or "")[:200]})
            st["houses"] = hs
        if "regime" in body:
            if body["regime"] not in ("", "new", "old"):
                _bad("bad_field", field="regime")
            if body["regime"] == "old" and not work(cid, ay)["old_ok"]:
                _bad("old_closed")
            st["regime"] = body["regime"]
        if body.get("step"):
            st["step"] = str(body["step"])[:20]
        for flag in ("reviewed", "regime_seen"):           # the person has looked: the step counts as done
            if flag in body:
                st[flag] = bool(body[flag])
        if "ready" in body:                                # the "Before you start" list: what the person has to hand
            ok_ids = {x["id"] for x in engine.run("myreturn.checklist")["rows"]}
            st["ready"] = sorted({str(x) for x in body["ready"] or [] if str(x) in ok_ids})
        if body.get("accept"):                             # "I have checked this one" - a gap the person stands behind
            st["accepted"] = sorted(set(st.get("accepted") or []) | {str(body["accept"])[:40]})
        st["by"] = user["id"]
        _save(cid, ay, st)
    return work(cid, ay)


# --- one return from many documents --------------------------------------------------------------------------------------

def merged(cid: str, ay: str) -> dict:
    """Every part of the return, from the document chip myreturn.sources puts first for it, then the person's own figures over
    it. Each part says where it came from: {"from": doc id / "you" / ""}."""
    st = state(cid, ay)
    order = engine.run("myreturn.sources")
    docs = st.get("docs") or []
    out: dict = {"from": {}}
    for sec in SECTIONS:
        if sec == "houses":
            continue
        for kind in order.get(sec, []):
            have = [d for d in docs if d["kind"] == kind and (d["facts"] or {}).get(sec)]
            if not have:
                continue
            if sec in ("employers", "tds", "paid"):             # lists: every document of the winning kind adds its rows
                out[sec] = [dict(r, doc=d["id"]) for d in have for r in d["facts"][sec]]
            else:
                out[sec] = copy.deepcopy(have[0]["facts"][sec])
            out["from"][sec] = {"kind": kind, "doc": have[0]["id"]}
            break
    for sec, keys in (("other", OTHER), ("cg", CG), ("via", VIA)):
        base = {k: _num((out.get(sec) or {}).get(k)) for k in keys}
        mine = (st.get("edits") or {}).get(sec) or {}
        out[sec] = base | {k: v for k, v in mine.items() if k in keys}
        out.setdefault("typed", {})[sec] = sorted(mine)
    emps = out.get("employers") or []
    for i, e in (((st.get("edits") or {}).get("employers")) or {}).items():
        i = int(i)
        while len(emps) <= i:
            emps.append({})
        emps[i] = emps[i] | e | {"typed": sorted(e)}
    out["employers"] = [{k: (e.get(k) if k in ("name", "tan") else _num(e.get(k))) for k in EMPLOYER}
                        | {"doc": e.get("doc", ""), "typed": e.get("typed", []), "exempt_rows": e.get("exempt_rows") or []} for e in emps]
    out["houses"] = st.get("houses") or []
    out["person"] = out.get("person") or {}
    out["tds"] = out.get("tds") or []
    out["paid"] = out.get("paid") or []
    out["banks"] = out.get("banks") or []
    return out


def _age(dob: str, ay: str) -> int:
    """Age on the last day of the financial year (31 March of the AY's first year)."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(dob or ""))
    if not m:
        return 0
    end = datetime.date(int(ay[:4]), 3, 31)
    born = datetime.date(int(m[1]), int(m[2]), int(m[3]))
    return end.year - born.year - ((end.month, end.day) < (born.month, born.day))


def one_regime(r: dict, regime: str, band: str, ans: dict) -> dict:
    """The whole computation under one regime - every step a chip."""
    emps = r["employers"]
    gross = sum(e["gross_17_1"] + e["perq_17_2"] + e["profit_17_3"] for e in emps)
    sal = engine.run("myreturn.salary", {"gross": gross, "exempt_all": sum(e["exempt_all"] for e in emps),
                                         "exempt_new": sum(e["exempt_new"] for e in emps), "prof_tax": sum(e["prof_tax"] for e in emps),
                                         "regime": regime}) if emps else {"exempt": 0, "std": 0, "prof_tax": 0, "income": 0}
    houses = [engine.run("myreturn.house", h | {"regime": regime}) for h in r["houses"]]
    hp = engine.run("myreturn.hp_total", {"nets": [h["net"] for h in houses], "regime": regime}) if houses else {"loss": 0, "net": 0}
    o = r["other"]
    fp = engine.run("myreturn.family_pension", {"pension": o["family_pension"], "regime": regime})
    os_ = o["savings"] + o["deposits"] + o["dividend"] + o["refund_interest"] + o["other"] + fp["net"]
    cg = r["cg"]
    gti_normal = sal["income"] + hp["net"] + os_ + cg["stcg_other"]
    via = engine.run("myreturn.deductions", {f: r["via"][f] for f in VIA} | {
        "regime": regime, "band": band, "gross_total": gti_normal, "basic_da": sum(e["basic_da"] for e in emps) or gross,   # ponytail: Form 16 rarely shows basic + DA; the employer kept 80CCD(2) inside it, so the salary stands in
        "parents_senior": bool(ans.get("parents_senior")), "savings_interest": o["savings"], "deposit_interest": o["deposits"],
        "disability": ans.get("disability") or ""})
    k = engine.run("myreturn.rates")
    normal = engine.run("compute.total_income", {"gti": gti_normal, "deductions": via["total"], "round_to": k["round_to"]})["income"]
    tax = engine.run("myreturn.tax", {"normal": max(normal, 0), "stcg_111a": cg["stcg_111a"], "ltcg_112a": cg["ltcg_112a"],
                                      "ltcg_112": cg["ltcg_112"], "regime": regime, "band": band, "resident": ans.get("resident", True) is not False})
    return {"regime": regime, "salary": sal | {"gross": gross}, "houses": houses, "hp": hp, "family_pension": fp, "other": os_,
            "gti": gti_normal + cg["stcg_111a"] + cg["ltcg_112a"] + cg["ltcg_112"], "gti_normal": gti_normal, "via": via,
            "normal": normal, "tax": tax}


def work(cid: str, ay: str) -> dict:
    """The journey as it stands: documents, the merged return, both regimes, the checks, the form, the balance, the steps."""
    st = state(cid, ay)
    c = clients.get(cid)
    k = settings()
    r = merged(cid, ay)
    ans = (k["answer_defaults"] | (st.get("answers") or {}))
    dob = r["person"].get("dob") or c.get("dob") or ""
    band = engine.run("myreturn.age_band", {"age": _age(dob, ay)}) if dob else "below60"
    both = {g: one_regime(r, g, band, ans) for g in ("new", "old")}
    tds = sum(_num(x.get("tds")) for x in r["tds"])
    paid = sum(_num(x.get("amount")) for x in r["paid"])
    cg = r["cg"]
    # the form first (it needs no dates): eligibility on the new regime's figures - ITR-1's 50 lakh leaves 112A gains out
    form = engine.run("myreturn.form", {
        "resident": ans.get("resident", True) is not False, "total": both["new"]["normal"] + cg["stcg_111a"] + cg["ltcg_112"], "houses": len(r["houses"]),
        "ltcg_112a": cg["ltcg_112a"], "other_cg": bool(cg["stcg_111a"] or cg["ltcg_112"] or cg["stcg_other"]),
        "agri": _num(ans.get("agri")), "director": bool(ans.get("director")), "unlisted": bool(ans.get("unlisted")),
        "foreign": bool(ans.get("foreign")), "loss_cf": bool(ans.get("loss_cf")), "other": False})
    # then the dates for THAT form, as of the day it was filed (the person says so) or today (chip close.dates)
    filed_on = str(ans.get("filed_on") or "")[:10]
    today = datetime.date.today().isoformat()
    dd = engine.run("close.dates", {"ay_year": int(ay[:4]), "audit": False, "tp": False, "form": form["form"],
                                    "filed_on": compute._ymd(filed_on or today), "today": compute._ymd(today),  # noqa: SLF001
                                    "has_current": False, "has_updated": False})
    late = dd["kind"] in k["late_kinds"]
    born = int(str(dob or "0").replace("-", "") or 0)
    exempt = engine.run("compute.no_advance", {"status": c["status"], "nri": ans.get("resident") is False, "born": born,
                                               "fy_end": compute.year_day(ay, "end"), "has_business": False}) is True
    challans = [{"date": x.get("date", ""), "tax": _num(x.get("amount")), "gross": _num(x.get("amount")), "minor": str(x.get("minor") or "")}
                for x in r["paid"]]
    for g in both.values():
        fee = engine.run("chat.fee_234f", {"income": g["tax"]["total"]}) if late else 0
        g["fee_234f"] = fee if isinstance(fee, (int, float)) else 0
        g["interest"] = compute.interest_234(cid, ay, compute.settings(), g["tax"]["tax"] - tds, challans, exempt,
                                             filed_on=compute._ymd(filed_on or today), due=dd["due"])  # noqa: SLF001
        g["tds"], g["paid"] = tds, paid
        g["balance"] = round(g["tax"]["tax"] + g["fee_234f"] + g["interest"]["total"] - tds - paid)
    best = engine.run("myreturn.better", {g: both[g]["tax"]["tax"] + both[g]["fee_234f"] + both[g]["interest"]["total"] for g in both})
    old_ok = dd["kind"] in k["old_regime_kinds"]          # 115BAC(6): the old regime is chosen in a return filed by the due date
    if not old_ok:
        best = {"better": "new", "saving": best["saving"] if best["better"] == "new" else 0, "old_closed": True}
    chosen = (st.get("regime") if old_ok or st.get("regime") == "new" else "") or best["better"]
    g = both[chosen]
    checks = checks_of(st, r)
    docs = [{k2: d[k2] for k2 in ("id", "name", "kind", "method", "found", "problems", "added_at", "size")} for d in st.get("docs") or []]
    have = {d["kind"] for d in docs}
    for x in checks:
        x["key"] = f"{x['what']}:{x.get('tan') or x.get('field') or ''}"
        x["accepted"] = x["key"] in (st.get("accepted") or [])
    steps = engine.run("myreturn.steps", {"has_docs": bool(docs), "has_income": bool(g["gti"]),
                                          "open_checks": sum(1 for x in checks if x["level"] == "red" and not x["accepted"]),
                                          "regime_seen": bool(st.get("regime_seen") or st.get("regime")), "reviewed": bool(st.get("reviewed"))})
    return {"client": clients.row(c, ay), "ay": ay, "docs": docs, "have": sorted(have), "return": r, "answers": ans, "band": band,
            "regimes": both, "better": best, "regime": chosen, "old_ok": old_ok, "chosen_by": "you" if st.get("regime") else "best",
            "form": form, "checks": checks, "steps": steps, "step": st.get("step") or steps["now"], "dates": dd, "late": late,
            "filed_on": filed_on, "has_filed": any(d["kind"] == "filed" for d in st.get("docs") or []), "ready": st.get("ready") or [],
            "checklist": engine.run("myreturn.checklist"),
            "locked": clients.locked(cid, ay)}


def checks_of(st: dict, r: dict) -> list[dict]:
    """The same figure in two documents, side by side (chip myreturn.checks decides when a gap matters)."""
    docs = st.get("docs") or []
    by_kind = lambda kind: [d for d in docs if d["kind"] == kind]  # noqa: E731
    out = []
    credit = {}
    for kind in engine.run("myreturn.sources").get("tds", []):
        for d in by_kind(kind):
            for t in d["facts"].get("tds") or []:
                credit.setdefault(kind, {}).setdefault(str(t.get("tan") or "").upper(), 0.0)
                credit[kind][str(t.get("tan") or "").upper()] += _num(t.get("tds"))
    f16 = credit.get("form16", {})
    other = next((credit[x] for x in ("26as", "ais", "prefill") if x in credit), {})
    for tan, amt in f16.items():
        if other:
            out.append(engine.run("myreturn.checks", {"what": "tds", "a": amt, "b": other.get(tan, 0)}) | {"tan": tan, "a": amt, "b": other.get(tan, 0)})
    ais = next((d for d in by_kind("ais")), None)
    if ais:
        a = ais["facts"].get("other") or {}
        for f in ("savings", "deposits", "dividend"):
            if _num(a.get(f)) or _num(r["other"].get(f)):
                out.append(engine.run("myreturn.checks", {"what": f, "a": r["other"].get(f), "b": a.get(f)}) | {"field": f, "a": r["other"].get(f), "b": _num(a.get(f))})
        s = _num((ais["facts"].get("salary") or {}).get("gross"))
        mine = sum(e["gross_17_1"] + e["perq_17_2"] + e["profit_17_3"] for e in r["employers"])
        if s or mine:
            out.append(engine.run("myreturn.checks", {"what": "salary", "a": mine, "b": s}) | {"field": "salary", "a": mine, "b": s})
    return out


# --- the department's JSON --------------------------------------------------------------------------------------------------

def facts(cid: str, ay: str) -> dict:
    """What chip itr.map's ITR-1 / ITR-2 rows point at - plain values; the codes (sections, account types, filing kinds) are
    chip itr.codes, the rest chip myreturn.json."""
    w = work(cid, ay)
    g = w["regimes"][w["regime"]]
    c = clients.get(cid)
    r = w["return"]
    p = r["person"]
    ans = w["answers"]
    codes = engine.run("itr.codes")
    js = engine.run("myreturn.json")
    i = lambda v: int(round(_num(v)))  # noqa: E731
    words = (p.get("name") or c["name"]).split()
    pin = str(p.get("pin") or (re.findall(r"[1-9][0-9]{5}", c.get("address") or "") or [""])[-1])
    parts = [x.strip() for x in re.split(r",", re.sub(r"[1-9][0-9]{5}", "", c.get("address") or "")) if x.strip()]
    cur = (w["dates"] or {})
    kind = cur["kind"]
    sal = g["salary"]
    rates = engine.run("myreturn.rates")
    keep_new = set(rates["exempt_in_new"])
    ex = {}
    for e in r["employers"]:
        for x in e.get("exempt_rows") or []:
            if w["regime"] == "old" or x["code"] in keep_new:
                ex[x["code"]] = ex.get(x["code"], 0) + i(x["amount"])
    exempt_rows = [{"code": k2, "amount": v} for k2, v in ex.items() if v]
    o = r["other"]
    os_rows = [{"code": code, "amount": i(o[f]), "what": js["os_words"].get(code, "")} for f, code in js["os_codes"].items() if i(o[f])]
    if i(o["family_pension"]):
        os_rows.append({"code": js["family_pension_code"], "amount": i(o["family_pension"]), "what": ""})
    hp_rows = []
    for n, (h, x) in enumerate(zip(r["houses"], g["houses"]), 1):
        hp_rows.append({"n": n, "address": (h.get("address") or (parts[0] if parts else ""))[:200] or "-", "city": p.get("city") or (parts[-1] if parts else ""),
                        "state": str(p.get("state") or ans.get("state") or ""), "pin": int(pin) if pin.isdigit() else "",
                        "let": "S" if h["kind"] == "self" else "L", "rent": i(h["rent"]), "municipal_tax": i(h["municipal_tax"]),
                        "nav": i(x["nav"]), "std": i(x["std"]), "interest": i(x["interest"]), "deduct": i(x["std"] + x["interest"]), "net": i(x["net"])})
    sec = lambda v: codes["sections"].get(re.sub(r"\s+", "", str(v or "")).upper(), codes["sections"].get(str(v or "")[:4].upper(), ""))  # noqa: E731
    tds_sal = [{"tan": x.get("tan", ""), "name": x.get("name", "") or x.get("tan", ""), "income": i(x.get("income")), "tds": i(x.get("tds"))}
               for x in r["tds"] if x.get("kind") == "salary"]
    tds_oth = [{"tan": x.get("tan", ""), "name": x.get("name", "") or x.get("tan", ""), "income": i(x.get("income")), "tds": i(x.get("tds")),
                "section": sec(x.get("section")), "year": str(int(ay[:4]) - 1), "year_n": int(ay[:4]) - 1} for x in r["tds"] if x.get("kind") != "salary"]
    adv = sum(_num(x.get("amount")) for x in r["paid"] if engine.run("compute.paid_kind", {
        "minor": str(x.get("minor") or ""), "paid_on": compute._day(x.get("date")), "fy_end": compute.year_day(ay, "end")}) == "advance")  # noqa: SLF001
    t = g["tax"]
    slab = i(t["on_normal"] + t["on_special"])
    rebate = i(t["rebate"] + t["relief_87a"])
    gross = i(slab - rebate + t["surcharge"] + t["cess"])
    interest = i(g["interest"]["total"] + g["fee_234f"])
    v = g["via"]
    banks = [{"ifsc": b.get("ifsc", ""), "bank": b.get("bank", ""), "account": b.get("account", ""),
              "type": codes["account_types"].get(str(b.get("type") or "").lower(), codes["default_account"]), "refund": "true" if n == 0 else "false"}
             for n, b in enumerate(r["banks"])]
    mobile = re.sub(r"\D", "", str(p.get("mobile") or c.get("phone") or ""))[-10:]
    return {
        "today": datetime.date.today().isoformat(), "ay_code": ay[:4], "form": w["form"]["form"],
        "sw_id": engine.run("itr.settings")["sw_id"], "sw_version": engine.run("itr.settings")["sw_version"],
        "client": {"name": p.get("name") or c["name"], "first": p.get("first") or " ".join(words[:-1]), "middle": p.get("middle") or "",
                   "surname": p.get("surname") or (words[-1] if words else ""), "pan": (p.get("pan") or c["pan"]).upper(),
                   "dob": p.get("dob") or c.get("dob") or "", "flat": (p.get("flat") or (parts[0] if parts else ""))[:50],
                   "building": p.get("building", ""), "road": p.get("road", ""), "area": (p.get("area") or (parts[1] if len(parts) > 1 else ""))[:50],
                   "city": (p.get("city") or (parts[-1] if len(parts) > 2 else ""))[:50], "state": str(p.get("state") or ans.get("state") or ""),
                   "pin": int(pin) if pin.isdigit() else "", "mobile": int(mobile) if mobile else "", "email": p.get("email") or c.get("email") or "",
                   "father": ans.get("father") or ""},
        "filing": {"section": codes["return_sec"].get(kind, 11), "due": _iso(w["dates"]["due"]),
                   "orig_ack": "", "orig_date": "", "residential": "RES" if ans.get("resident", True) is not False else "NRI", "employer_category": ans.get("employer_category") or (js["employer_default"] if r["employers"] else "NA")},
        "regime_opt_out": "Y" if w["regime"] == "old" else "N",
        "salary": {"gross": i(sal["gross"]), "s17_1": sum(i(e["gross_17_1"]) for e in r["employers"]), "s17_2": sum(i(e["perq_17_2"]) for e in r["employers"]),
                   "s17_3": sum(i(e["profit_17_3"]) for e in r["employers"]), "exempt": sum(x["amount"] for x in exempt_rows),
                   "net": i(sal["gross"]) - sum(x["amount"] for x in exempt_rows), "std": i(sal["std"]), "prof_tax": i(sal["prof_tax"]),
                   "d16": i(sal["std"] + sal["prof_tax"]), "income": i(sal["income"])},
        "exempt_rows": exempt_rows, "hp_rows": hp_rows, "hp": {"net": i(g["hp"]["net"])},
        "salary_rows": [{"name": e["name"] or "-", "category": ans.get("employer_category") or js["employer_default"], "tan": e["tan"],
                         "address": (parts[0] if parts else "-"), "city": p.get("city") or (parts[-1] if parts else "-"),
                         "state": str(p.get("state") or ans.get("state") or ""), "gross": i(e["gross_17_1"] + e["perq_17_2"] + e["profit_17_3"]),
                         "s17_1": i(e["gross_17_1"]), "s17_2": i(e["perq_17_2"]), "s17_3": i(e["profit_17_3"])} for e in r["employers"]],
        "os": {"total": i(g["other"]), "fp_deduction": i(g["family_pension"]["deduction"]), "dividend": i(o["dividend"]),
               "interest": i(o["savings"] + o["deposits"] + o["refund_interest"]), "savings": i(o["savings"]), "deposits": i(o["deposits"]),
               "refund_interest": i(o["refund_interest"]), "family_pension": i(o["family_pension"]), "other": i(o["other"]),
               "gross": i(o["savings"] + o["deposits"] + o["refund_interest"] + o["dividend"] + o["family_pension"] + o["other"])}, "os_rows": os_rows,
        "gti_normal": i(g["gti_normal"]), "gti": i(g["gti"]),
        "cg": {k2: i(r["cg"][k2]) for k2 in CG} | {"ltcg_all": i(r["cg"]["ltcg_112a"] + r["cg"]["ltcg_112"]), "short": i(r["cg"]["stcg_111a"] + r["cg"]["stcg_other"]),
                                                    "total": i(sum(r["cg"][k2] for k2 in CG)), "special": i(r["cg"]["stcg_111a"] + r["cg"]["ltcg_112a"] + r["cg"]["ltcg_112"])},
        "total_gross": i(g["gti"] - v["total"]),
        "flags": {"unlisted": "Y" if ans.get("unlisted") else "N", "director": "Y" if ans.get("director") else "N",
                  "banks": "Y" if r["banks"] else "N", "foreign_word": "YES" if ans.get("foreign") else "NO"},
        "via": {k2: i(v[k2]) for k2 in v}, "total_income": i(t["total"]),
        "cyla": (cy := {k2: i(x) for k2, x in engine.run("myreturn.cyla", {"hp": g["hp"]["net"], "salary": sal["income"], "os": g["other"]}).items()}),
        "heads": i(g["gti"]) + cy["loss"],   # PartB-TI TotalTI: the heads before the house loss is set off
        "cg_111a_rows": [{"gain": i(r["cg"]["stcg_111a"])}] if i(r["cg"]["stcg_111a"]) else [],
        "d80d": {"total": i(v["d80D"]), "self": i(v["d80D_self"]) if w["band"] == "below60" else 0, "self_sr": 0 if w["band"] == "below60" else i(v["d80D_self"]),
                 "parents": 0 if ans.get("parents_senior") else i(v["d80D_parents"]), "parents_sr": i(v["d80D_parents"]) if ans.get("parents_senior") else 0,
                 "self_flag": ("N" if w["band"] == "below60" else "Y") if v["d80D"] else "", "parents_flag": ("Y" if ans.get("parents_senior") else "N") if v["d80D"] else ""},
        "tax2": {"slab": slab, "on_normal": i(t["on_normal"]), "on_special": i(t["on_special"]), "rebate_all": rebate, "after_rebate": slab - rebate, "surcharge": i(t["surcharge"]), "cess": i(t["cess"]),
                 "gross": gross, "i234a": i(g["interest"]["a"]), "i234b": i(g["interest"]["b"]), "i234c": i(g["interest"]["c"]),
                 "fee_234f": i(g["fee_234f"]), "interest_fee": interest, "aggregate": gross + interest,
                 "tds": i(g["tds"]), "advance": i(adv), "sat": i(g["paid"] - adv), "paid": i(g["paid"]), "paid_all": i(g["tds"] + g["paid"]),
                 "tds_salary": sum(x["tds"] for x in tds_sal), "tds_other": sum(x["tds"] for x in tds_oth),
                 "payable": max(gross + interest - i(g["tds"] + g["paid"]), 0), "refund": max(i(g["tds"] + g["paid"]) - gross - interest, 0)},
        "tds_salary": tds_sal, "tds_other": tds_oth,
        "paid_rows": [{"bsr": x.get("bsr", ""), "date": _iso(x.get("date")), "serial": int(re.sub(r"\D", "", str(x.get("challan") or "")) or 0),
                       "amount": i(x.get("amount"))} for x in r["paid"]],
        "bank_rows": banks}


def _iso(v) -> str:
    """26AS 15-Jun-2025 / 15/06/2025 / 2025-06-15 -> 2025-06-15."""
    m = re.fullmatch(r"(\d{2})[/-](\d{2})[/-](\d{4})", str(v or "").strip())
    n = str(int(m[3] + m[2] + m[1]) if m else compute._day(v))  # noqa: SLF001
    return f"{n[:4]}-{n[4:6]}-{n[6:8]}" if len(n) == 8 else ""


def compare(cid: str, ay: str) -> dict:
    """The return as filed (its JSON dropped in) beside the return as SimplyFile makes it, figure by figure. A figure's place in
    the filed JSON is where chip itr.map puts it - no second list of paths; which figures, and how close is close, are chip
    myreturn.compare."""
    import itr_json  # noqa: PLC0415
    st = state(cid, ay)
    d = next((x for x in reversed(st.get("docs") or []) if x["kind"] == "filed"), None)
    if not d:
        _bad("no_filed", 404)
    filed, their_form = d["facts"].get("filed_json") or {}, d["facts"].get("form") or ""
    f = facts(cid, ay)
    k = engine.run("myreturn.compare")
    rows_map = [r for r in engine.run("itr.map")["forms"].get(their_form) or [] if "from" in r]
    out = []
    for row in k["rows"]:
        path = next((r["path"] for r in rows_map if r["from"] == row["key"]), "")
        cur = filed.get("ITR", filed)
        for part in path.split(".") if path else []:
            cur = cur.get(part) if isinstance(cur, dict) else None
        theirs = cur if isinstance(cur, (int, float)) else (_num(cur) if cur not in (None, "") else None)
        ours = itr_json._get(f, row["key"])  # noqa: SLF001
        if theirs is None and not ours:
            continue
        chk = engine.run("myreturn.checks", {"what": "compare", "a": _num(ours), "b": theirs or 0, "tolerance": {"compare": k["tolerance"]}})
        out.append({"key": row["key"], "word": row["word"], "ours": _num(ours), "theirs": theirs, "gap": chk["gap"],
                    "level": "missing" if theirs is None else chk["level"]})
    return {"form_filed": their_form, "form_ours": f["form"], "rows": out, "same": all(x["level"] == "ok" for x in out),
            "regime_filed": "old" if str(itr_json._get(filed.get("ITR", {}), next((r["path"] for r in rows_map if r["from"] == "regime_opt_out"), "-")) or "") == "Y" else "new",  # noqa: SLF001
            "file": d["name"]}


def export(cid: str, ay: str) -> tuple[str, bytes, dict]:
    import json  # noqa: PLC0415
    import itr_json  # noqa: PLC0415
    f = facts(cid, ay)
    doc, rep = itr_json.assemble(f, f["form"])
    c = clients.get(cid)
    return f"{f['form']} {c['pan']} AY {ay}.json", json.dumps(doc, indent=1, ensure_ascii=False).encode("utf-8"), rep


def report(cid: str, ay: str) -> dict:
    import itr_json  # noqa: PLC0415
    f = facts(cid, ay)
    return itr_json.assemble(f, f["form"])[1]


if __name__ == "__main__":  # ponytail: both regimes from a hand-made return - the chips' arithmetic joined up as the screen uses it
    import store as _portal_store  # noqa: F401 - registers this portal's chips, as the app does
    assert _age("1966-04-01", "2026-27") == 59 and _age("1966-03-31", "2026-27") == 60 and _age("", "2026-27") == 0
    one = {"employers": [{k: 0.0 for k in EMPLOYER if k not in ("name", "tan")} | {"name": "x", "tan": "", "gross_17_1": 1440000.0}],
           "houses": [], "other": {k: 0.0 for k in OTHER} | {"savings": 18400.0}, "cg": {k: 0.0 for k in CG},
           "via": {k: 0.0 for k in VIA} | {"c80c": 150000.0}}
    new, old = one_regime(one, "new", "below60", {}), one_regime(one, "old", "below60", {})
    assert new["salary"]["income"] == 1365000 and new["via"]["total"] == 0 and new["normal"] == 1383400, new
    assert old["salary"]["income"] == 1390000 and old["via"]["total"] == 160000 and old["normal"] == 1248400, old
    assert new["tax"]["tax"] < old["tax"]["tax"], (new["tax"], old["tax"])
    print("myreturn self-check OK")
