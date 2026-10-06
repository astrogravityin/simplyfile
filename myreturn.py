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
from functools import lru_cache
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
VIA = ("c80c", "c80ccc", "c80ccd1", "c80ccd1b", "c80ccd2", "c80d_self", "c80d_parents", "c80e", "c80g",
       "c80ddb", "c80ee", "c80eea", "c80eeb", "c80ggc", "c80gg")      # 2026-10-06: the rest of Chapter VI-A (c80gg = rent, for 80GG)
VIA_MORE = ("dd_nature", "dd_type", "dd_dependent", "ddb_senior", "stamp", "vehicle", "ggc_party", "ggc_pan", "ggc_date", "ggc_ref", "ggc_ifsc")
LOAN = ("from", "bank", "acc", "date", "amount", "left")
BIZ = ("kind", "code", "name", "digital", "cash", "declared", "gstin", "gst_turnover")   # 2026-10-06 presumptive business / profession
BIZ_TEXT = ("kind", "code", "name", "gstin")
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
    folder(cid, ay)                                         # a return typed with no document yet still has its folder
    store.write(_name(cid, ay), st)


# --- the documents ------------------------------------------------------------------------------------------------------

def add_doc(user: dict, cid: str, ay: str, filename: str, data: bytes, password: str = "", on_same: str = "") -> dict:
    """Keep the file, read it (myreturn_read.read), and add what it said to the return. A second AIS / 26AS / ... (chip
    myreturn.settings one_per_kind) is not added until the person says: on_same "replace" (the old kept for History) or "keep"."""
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
    dob = c.get("dob") or next((w["dob"] for d in st0.get("docs") or [] if (w := who(d)).get("dob")), "")
    got = myreturn_read.read(filename, data, password=password, user=user, ay=ay, pan=c.get("pan", ""), dob=dob,
                             ai_ok=bool((st0.get("answers") or {}).get("ai_ok")))
    w = who(got)                                            # a document naming this person fills what the client lacks
    if w.get("pan") == c.get("pan") and (w.get("dob") and not c.get("dob") or w.get("name") and c.get("name") == c.get("pan")):
        clients.save(user, c | {"dob": c.get("dob") or w["dob"], "name": w["name"] if c.get("name") == c.get("pan") and w.get("name") else c["name"]}, cid)
    name = Path(filename).name[:120]
    same = [x for x in st0.get("docs") or [] if got["kind"] in k["one_per_kind"] and x["kind"] == got["kind"] and x["name"] != name]
    if same and on_same not in ("replace", "keep"):
        return work(cid, ay) | {"ask": {"why": "same", "kind": got["kind"], "new": name, "have": [{"name": x["name"], "at": x["added_at"]} for x in same]}}
    for x in same if on_same == "replace" else []:
        remove_doc(user, cid, ay, x["id"])
    with _LOCK:
        st = state(cid, ay)
        old = next((x for x in st.get("docs") or [] if x["name"] == name), None)   # the same file again replaces it, the old one kept
        fid, v = (old["id"], int(old.get("version", 1)) + 1) if old else (store.new_id(), 1)
        d = folder(cid, ay)
        if old and (d / f"{fid}{old['ext']}").exists():
            (d / f"{fid}{old['ext']}").replace(d / f"{fid}.v{v - 1}{old['ext']}")
        (d / f"{fid}{ext}").write_bytes(data)
        doc = {"id": fid, "name": name, "ext": ext, "size": len(data), "kind": got["kind"], "method": got["method"], "version": v,
               "facts": got["facts"], "found": got.get("found", []), "problems": got.get("problems", []),
               "added_at": store.now(), "added_by": user["id"]}
        st["docs"] = [x for x in st.get("docs") or [] if x["id"] != fid] + [doc]
        _save(cid, ay, st)
    return work(cid, ay) | {"added": {k2: doc[k2] for k2 in ("id", "name", "kind", "method", "found", "problems")}}


def who(got: dict) -> dict:
    """The person a read document names: the pre-filled JSON's, else a filed return's PersonalInfo (chip myreturn.settings who)."""
    import itr_json  # noqa: PLC0415
    p = (got.get("facts") or {}).get("person") or {}
    if p.get("pan"):
        return {"pan": p["pan"], "name": p.get("name") or "", "dob": p.get("dob") or ""}
    k, stack = settings()["who"], [(got.get("facts") or {}).get("filed_json")]
    while stack:                                            # PersonalInfo sits at a different depth in ITR-1 and ITR-2
        x = stack.pop()
        if isinstance(x, dict):
            pi = x.get(k["block"])
            if isinstance(pi, dict) and pi.get(k["pan"]):
                name = " ".join(str(v) for v in (itr_json._get(pi, n) for n in k["name"]) if v)  # noqa: SLF001
                return {"pan": str(pi[k["pan"]]).upper(), "name": name, "dob": str(pi.get(k["dob"]) or "")}
            stack += list(x.values())
    return {}


def start(user: dict, ay: str, filename: str, data: bytes, password: str = "", on_old: str = "", on_same: str = "") -> dict:
    """A return begun from a document, no client added first: the person it names becomes the client (or is found by PAN).
    A return already holding documents for the year is not touched until the person says: on_old "continue" or "fresh"."""
    import myreturn_read  # noqa: PLC0415
    w = who(myreturn_read.read(filename, data, password=password, user=user, ay=ay))
    if not w:
        _bad("no_who")
    c = next((c for c in clients._mine(user) if c["pan"] == w["pan"] and not c.get("archived_at")), None)  # noqa: SLF001
    old = bool(c)
    if not c:
        st = next((s for s in clients.settings()["statuses"] if s["pan_letter"] == w["pan"][3:4]), None)
        c = clients.save(user, {"name": w["name"] or w["pan"], "pan": w["pan"], "dob": w["dob"], "status": (st or {}).get("id", ""), "ay": ay})
    have = (state(c["id"], ay).get("docs") or []) if old else []
    if have and on_old not in ("continue", "fresh"):
        return {"ask": {"why": "start", "cid": c["id"], "name": c["name"], "ay": ay,
                        "have": [{"kind": d["kind"], "name": d["name"], "at": d["added_at"]} for d in have]}}
    if have and on_old == "fresh":
        start_over(user, c["id"], ay)
    got = add_doc(user, c["id"], ay, filename, data, password, on_same)
    if got.get("ask"):
        return got | {"cid": c["id"]}
    added = got["added"]
    return answer(user, c["id"], ay, {"step": "gather"}) | {        # open where the rest of the documents go
        "added": added, "cid": c["id"], "said": say("found_old" if old else "made", name=c["name"], file=Path(filename).name)}


def start_over(user: dict, cid: str, ay: str) -> None:
    """An empty return for the year: every document removed (each kept for History), the rest of the return saved beside it."""
    import json  # noqa: PLC0415
    for d in state(cid, ay).get("docs") or []:
        remove_doc(user, cid, ay, d["id"])
    with _LOCK:
        (folder(cid, ay) / f"before-{store.new_id()}.json").write_text(json.dumps(state(cid, ay)), encoding="utf-8")
        _save(cid, ay, {"docs": [], "started_over_at": store.now(), "started_over_by": user["id"]})


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
    if f.exists():                                          # kept for History (<fid>.v<n><ext>), never deleted
        f.replace(f.with_name(f"{fid}.v{d.get('version', 1)}{d['ext']}"))
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
            if q == "karta_pan" and v and not re.fullmatch(r"[A-Z]{3}P[A-Z][0-9]{4}[A-Z]", str(v).strip().upper()):
                _bad("bad_karta_pan")
            st.setdefault("answers", {})[q] = v if isinstance(v, bool) else (str(v).strip().upper() if q == "karta_pan" else str(v)[:80])
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
        if "business" in body:                              # presumptive business / profession, typed on Check
            b = body["business"] or {}
            if str(b.get("kind") or "") not in ("", "44ADA", "44AD"):
                _bad("bad_field", field="kind")
            st["business"] = {f: (str(b.get(f) or "").strip()[:120] if f in BIZ_TEXT else _num(b.get(f))) for f in BIZ}
        if "via_more" in body:                              # the details the department's deduction schedules ask for
            vm = body["via_more"] or {}
            keep = st.setdefault("via_more", {})
            for f, v in vm.items():
                if f in VIA_MORE:
                    keep[f] = v if isinstance(v, bool) else str(v or "").strip()[:80]
                elif f in ("loan_80ee", "loan_80eea", "loan_80eeb") and isinstance(v, dict):
                    keep[f] = {x: (_num(v.get(x)) if x in ("amount", "left") else str(v.get(x) or "").strip()[:60]) for x in LOAN}
                else:
                    _bad("bad_field", field=f)
        if "paid" in body:                                  # tax the person paid themselves, typed (the AIS may predate it)
            minor = k["paid_minor"]
            ps = []
            for x in (body["paid"] or [])[:20]:
                if str(x.get("kind") or "self") not in minor:
                    _bad("bad_field", field="kind")
                ps.append({"kind": str(x.get("kind") or "self"), "date": str(x.get("date") or "")[:10], "amount": _num(x.get("amount")),
                           "bsr": re.sub(r"\D", "", str(x.get("bsr") or ""))[:7], "challan": re.sub(r"\D", "", str(x.get("challan") or ""))[:5]})
            st["paid_typed"] = ps
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

@lru_cache(maxsize=1)
def biz_codes() -> dict:
    """The nature-of-work codes the department lists in the ITR-4 schema (CodeADA / CodeAD, "14001 - Software development, ..."):
    {"44ADA": [[code, words], ...], "44AD": [...]} - the department's list, so never a copy of ours to go stale."""
    import itr_json  # noqa: PLC0415
    d = itr_json.schema("ITR-4")["definitions"]
    out = {}
    for kind, node, field in (("44ADA", "NatOfBus44ADA", "CodeADA"), ("44AD", "NatOfBus44AD", "CodeAD")):
        f = d[node]["properties"][field]
        words = dict(re.findall(r"(\d{5}(?:_\d)?)\s*-\s*(.+?)\s*(?=,\s*\d{5}|$)", f.get("description") or ""))
        out[kind] = [[x, words.get(x, x)] for x in f["enum"]]
    return out


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
    out["via_more"] = st.get("via_more") or {}
    secs = set(settings()["business_sections"])          # what the department saw paid to the person for work (194J, 194C ...)
    seen = sum(_num(x.get("income")) for x in out.get("tds") or [] if re.sub(r"\s+", "", str(x.get("section") or "")).upper() in secs)
    biz = st.get("business") or {}
    bk = [d["facts"]["bank"] for d in st.get("docs") or [] if d["kind"] == "bank" and (d.get("facts") or {}).get("bank")]
    out["bank"] = {f: round(sum(_num(x.get(f)) for x in bk), 2) for f in ("credits", "receipts", "cash", "interest")} | {"statements": len(bk)}
    out["business"] = {f: (str(biz.get(f) or "") if f in BIZ_TEXT else _num(biz.get(f))) for f in BIZ} | {"seen": seen}
    out["person"] = out.get("person") or {}
    out["tds"] = out.get("tds") or []
    minor = settings()["paid_minor"]
    out["paid_typed"] = st.get("paid_typed") or []
    out["paid"] = (out.get("paid") or []) + [{"date": x["date"], "amount": x["amount"], "minor": minor[x["kind"]], "bsr": x.get("bsr", ""), "challan": x.get("challan", ""), "typed": True}
                                             for x in out["paid_typed"] if x["amount"]]
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


def one_regime(r: dict, regime: str, band: str, ans: dict, status: str = "individual") -> dict:
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
    b = r.get("business") or {}
    biz = engine.run("myreturn.business", {f: b.get(f) or (0 if f != "kind" else "") for f in ("kind", "digital", "cash", "declared", "seen")})
    gti_normal = sal["income"] + hp["net"] + os_ + cg["stcg_other"] + biz["income"]   # ponytail: a house loss sets off against salary and other sources (cyla), not business yet
    vm = r.get("via_more") or {}
    via = engine.run("myreturn.deductions", {f: r["via"][f] for f in VIA if f != "c80gg"} | {
        "dd_nature": str(vm.get("dd_nature") or ""), "ddb_senior": vm.get("ddb_senior") is True,
        "regime": regime, "band": band, "gross_total": gti_normal, "basic_da": sum(e["basic_da"] for e in emps) or gross,   # ponytail: Form 16 rarely shows basic + DA; the employer kept 80CCD(2) inside it, so the salary stands in
        "parents_senior": bool(ans.get("parents_senior")), "savings_interest": o["savings"], "deposit_interest": o["deposits"],
        "disability": ans.get("disability") or "", "status": status})
    # 80GG is worked out on the income left after every other deduction (chip myreturn.d80gg)
    gg = engine.run("myreturn.d80gg", {"rent": r["via"]["c80gg"], "ati": max(gti_normal - via["total"], 0), "regime": regime, "status": status,
                                       "has_hra": any(e.get("hra") for e in emps)})
    via = via | {"d80GG": gg, "total": min(via["total"] + gg, max(gti_normal, 0))}
    k = engine.run("myreturn.rates")
    normal = engine.run("compute.total_income", {"gti": gti_normal, "deductions": via["total"], "round_to": k["round_to"]})["income"]
    tax = engine.run("myreturn.tax", {"normal": max(normal, 0), "stcg_111a": cg["stcg_111a"], "ltcg_112a": cg["ltcg_112a"],
                                      "ltcg_112": cg["ltcg_112"], "regime": regime, "band": band, "resident": ans.get("resident", True) is not False,
                                      "status": status})
    return {"regime": regime, "salary": sal | {"gross": gross}, "houses": houses, "hp": hp, "family_pension": fp, "other": os_,
            "gti": gti_normal + cg["stcg_111a"] + cg["ltcg_112a"] + cg["ltcg_112"], "gti_normal": gti_normal, "via": via,
            "normal": normal, "tax": tax, "business": biz}


def work(cid: str, ay: str) -> dict:
    """The journey as it stands: documents, the merged return, both regimes, the checks, the form, the balance, the steps."""
    st = state(cid, ay)
    c = clients.get(cid)
    k = settings()
    r = merged(cid, ay)
    ans = (k["answer_defaults"] | (st.get("answers") or {}))
    dob = r["person"].get("dob") or c.get("dob") or ""
    status = "huf" if c.get("status") == "huf" else "individual"
    band = engine.run("myreturn.age_band", {"age": _age(dob, ay), "status": status}) if dob else "below60"
    both = {g: one_regime(r, g, band, ans, status) for g in ("new", "old")}
    tds = sum(_num(x.get("tds")) for x in r["tds"])
    paid = sum(_num(x.get("amount")) for x in r["paid"])
    cg = r["cg"]
    # the form first (it needs no dates): eligibility on the new regime's figures - ITR-1's 50 lakh leaves 112A gains out
    form = engine.run("myreturn.form", {
        "resident": ans.get("resident", True) is not False, "total": both["new"]["normal"] + cg["stcg_111a"] + cg["ltcg_112"], "houses": len(r["houses"]),
        "ltcg_112a": cg["ltcg_112a"], "other_cg": bool(cg["stcg_111a"] or cg["ltcg_112"] or cg["stcg_other"]),
        "agri": _num(ans.get("agri")), "director": bool(ans.get("director")), "unlisted": bool(ans.get("unlisted")),
        "foreign": bool(ans.get("foreign")), "loss_cf": bool(ans.get("loss_cf")), "other": False,
        "business": bool(r["business"]["kind"]), "over_limit": both["new"]["business"]["over_limit"] is True, "huf": status == "huf"})
    # then the dates for THAT form, as of the day it was filed (the person says so) or today (chip close.dates)
    filed_on = str(ans.get("filed_on") or "")[:10]
    today = datetime.date.today().isoformat()
    dd = engine.run("close.dates", {"ay_year": int(ay[:4]), "audit": False, "tp": False, "form": form["form"],
                                    "filed_on": compute._ymd(filed_on or today), "today": compute._ymd(today),  # noqa: SLF001
                                    "has_current": False, "has_updated": False})
    late = dd["kind"] in k["late_kinds"]
    born = int(str(dob or "0").replace("-", "") or 0)
    exempt = engine.run("compute.no_advance", {"status": c["status"], "nri": ans.get("resident") is False, "born": born,
                                               "fy_end": compute.year_day(ay, "end"), "has_business": bool(r["business"]["kind"])}) is True
    challans = [{"date": x.get("date", ""), "tax": _num(x.get("amount")), "gross": _num(x.get("amount")), "minor": str(x.get("minor") or "")}
                for x in r["paid"]]
    for g in both.values():
        fee = engine.run("chat.fee_234f", {"income": g["tax"]["total"]}) if late else 0
        g["fee_234f"] = fee if isinstance(fee, (int, float)) else 0
        g["interest"] = compute.interest_234(cid, ay, compute.settings(), g["tax"]["tax"] - tds, challans, exempt,
                                             filed_on=compute._ymd(filed_on or today), due=dd["due"],  # noqa: SLF001
                                             presumptive=bool(r["business"]["kind"]))   # 44AD / 44ADA: one instalment by 15 March (234C)
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
    return {"client": clients.row(c, ay) | {"status_id": c.get("status", "")}, "ay": ay, "docs": docs, "have": sorted(have), "return": r, "answers": ans, "band": band,
            "regimes": both, "better": best, "regime": chosen, "old_ok": old_ok, "chosen_by": "you" if st.get("regime") else "best",
            "form": form, "checks": checks, "steps": steps, "step": st.get("step") or steps["now"], "dates": dd, "late": late,
            "filed_on": filed_on, "has_filed": any(d["kind"] == "filed" for d in st.get("docs") or []), "ready": st.get("ready") or [],
            "checklist": engine.run("myreturn.checklist"),
            "locked": clients.locked(cid, ay), "biz_codes": biz_codes() if r["business"]["kind"] else {}}


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
    b, gb, kb = r["business"], g["business"], engine.knobs("myreturn.business")
    ada, ad = b["kind"] == "44ADA", b["kind"] == "44AD"
    nature = [{"NameOfBusiness": b["name"] or c["name"], ("CodeADA" if ada else "CodeAD"): b["code"], "Description": dict(biz_codes().get(b["kind"], [])).get(b["code"], "")}] if b["kind"] else []
    biz = {"income": i(gb["income"]), "nature_ada": nature if ada else [], "nature_ad": nature if ad else [],
           "ada_receipts": i(gb["receipts"]) if ada else 0, "ada_digital": i(b["digital"]) if ada else 0, "ada_cash": i(b["cash"]) if ada else 0,
           "ada_income": i(gb["income"]) if ada else 0, "ad_receipts": i(gb["receipts"]) if ad else 0, "ad_digital": i(b["digital"]) if ad else 0,
           "ad_cash": i(b["cash"]) if ad else 0, "ad_6": i(b["digital"] * kb["ad_digital_pct"] / 100) if ad else 0, "ad_8": i(b["cash"] * kb["ad_cash_pct"] / 100) if ad else 0,
           "ad_income": i(gb["income"]) if ad else 0, "gst_turnover": i(b["gst_turnover"]),
           "gst_rows": [{"GSTINNo": b["gstin"].upper(), "AmtTurnGrossRcptGSTIN": i(b["gst_turnover"])}] if b["gstin"] else []}
    vm, gv = r.get("via_more") or {}, g["via"]                    # the deduction schedules, only for what is claimed
    via_more = {"dd_nature": vm.get("dd_nature", "") if gv.get("d80DD") else "", "dd_type": (vm.get("dd_type") or "2") if gv.get("d80DD") else "",
                "dd_dependent": (vm.get("dd_dependent") or "1") if gv.get("d80DD") else "",
                "ddb_type": ("2" if vm.get("ddb_senior") else "1") if gv.get("d80DDB") else "", "stamp": i(vm.get("stamp")) if gv.get("d80EEA") else 0}
    loan = lambda sec, extra: ([{**{x: (i((vm.get(f"loan_{sec}") or {}).get(x)) if x in ("amount", "left") else (vm.get(f"loan_{sec}") or {}).get(x)) for x in LOAN}, "from": (vm.get(f"loan_{sec}") or {}).get("from") or "B",  # noqa: E731
                                 "interest": i(gv.get(f"d{sec.upper()}")), **extra}] if gv.get(f"d{sec.upper()}") else [])
    ggc_rows = [{"date": vm.get("ggc_date", ""), "amount": i(gv["d80GGC"]), "ref": vm.get("ggc_ref", ""), "ifsc": vm.get("ggc_ifsc", "").upper(),
                 "party": vm.get("ggc_party", ""), "pan": vm.get("ggc_pan", "").upper()}] if gv.get("d80GGC") else []
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
        "client": {"status_code": js["status_codes"].get(c.get("status"), "I"), "capacity": js["capacity"].get(c.get("status"), "S"),
                   "signer_name": (ans.get("karta_name") if c.get("status") == "huf" else "") or p.get("name") or c["name"],
                   "signer_pan": (ans.get("karta_pan") or c.get("signer_pan") if c.get("status") == "huf" else "") or c["pan"], "name": p.get("name") or c["name"], "first": p.get("first") or " ".join(words[:-1]), "middle": p.get("middle") or "",
                   "surname": p.get("surname") or (words[-1] if words else ""), "pan": (p.get("pan") or c["pan"]).upper(),
                   "dob": p.get("dob") or c.get("dob") or ans.get("formed_on") or "", "flat": (p.get("flat") or (parts[0] if parts else ""))[:50],
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
        "exempt_rows": exempt_rows, "hp_rows": hp_rows, "hp": {"net": i(g["hp"]["net"])}, "biz": biz,
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
        "total_gross": i(engine.run("compute.total_income", {"gti": g["gti"], "deductions": v["total"],    # rounded to 10 (section 288A)
                                                             "round_to": engine.run("myreturn.rates")["round_to"]})["income"]),
        "flags": {"unlisted": "Y" if ans.get("unlisted") else "N", "director": "Y" if ans.get("director") else "N",
                  "banks": "Y" if r["banks"] else "N", "foreign_word": "YES" if ans.get("foreign") else "NO"},
        "via": {k2: i(v[k2]) for k2 in v}, "via_more": via_more, "loans_80ee": loan("80ee", {}), "loans_80eea": loan("80eea", {}),
        "loans_80eeb": loan("80eeb", {"vehicle": vm.get("vehicle", "")}), "ggc_rows": ggc_rows, "total_income": i(t["total"]),
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
        # the figure where this form keeps it - ITR-2 fills TotalIncome from total_gross, so a row may name others (also)
        key, path = next(((x, r["path"]) for x in [row["key"]] + list(row.get("also") or []) for r in rows_map if r["from"] == x), (row["key"], ""))
        cur = filed.get("ITR", filed) if path else None
        for part in path.split(".") if path else []:
            cur = cur.get(part) if isinstance(cur, dict) else None
        theirs = cur if isinstance(cur, (int, float)) else (_num(cur) if isinstance(cur, str) and cur else None)
        ours = itr_json._get(f, key)  # noqa: SLF001
        if theirs is None and not ours:
            continue
        chk = engine.run("myreturn.checks", {"what": "compare", "a": _num(ours), "b": theirs or 0, "tolerance": {"compare": k["tolerance"]}})
        out.append({"key": row["key"], "word": row["word"], "ours": _num(ours), "theirs": theirs, "gap": chk["gap"],
                    "level": "missing" if theirs is None else chk["level"]})
    return {"form_filed": their_form, "form_ours": f["form"], "rows": out, "same": all(x["level"] == "ok" for x in out),
            "regime_filed": "old" if str(itr_json._get(filed.get("ITR", {}), next((r["path"] for r in rows_map if r["from"] == "regime_opt_out"), "-")) or "") == "Y" else "new",  # noqa: SLF001
            "file": d["name"]}


def from_filed(user: dict, cid: str, ay: str) -> dict:
    """This year's filed return (its JSON dropped in) fills "Already filed?" - the date it was verified and its acknowledgement
    (the portal names the file by it) - and each challan it lists that the documents do not already show (chip
    myreturn.settings from_filed)."""
    import itr_json  # noqa: PLC0415
    k = settings()["from_filed"]
    st = state(cid, ay)
    d = next((x for x in reversed(st.get("docs") or []) if x["kind"] == "filed"), None)
    if not d:
        _bad("from_filed_none", 404, ay=ay)
    itr = (d["facts"].get("filed_json") or {}).get("ITR") or {}
    body = next(iter(itr.values()), {}) if itr else {}
    date = next((str(v)[:10] for p in k["date"] if (v := itr_json._get(body, p))), "")  # noqa: SLF001
    stem = Path(d["name"]).stem
    ack = stem if stem.isdigit() and len(stem) == int(k["ack_digits"]) else (st.get("answers") or {}).get("ack_no", "")
    fy_end = compute.year_day(ay, "end")
    have = {(str(x.get("challan") or ""), round(_num(x.get("amount")))) for x in merged(cid, ay)["paid"] if not x.get("typed")}
    typed = []
    for x in itr_json._get(body, k["challans"]) or []:  # noqa: SLF001
        no, amt, on = str(x.get(k["no"]) or ""), _num(x.get(k["amount"])), str(x.get(k["on"]) or "")[:10]
        if (no, round(amt)) in have or not amt:
            continue
        typed.append({"kind": "self" if compute._ymd(on) > fy_end else "advance", "date": on, "amount": amt,  # noqa: SLF001
                      "bsr": str(x.get(k["bsr"]) or ""), "challan": no})
    w = answer(user, cid, ay, {"answers": {"filed_on": date, "ack_no": ack}, "paid": typed})
    return w | {"said": say("from_filed_done", date=date or "-", ack=ack or "-", n=len(typed))}


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
