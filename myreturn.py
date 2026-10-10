"""My return - an individual files their own ITR-1 or ITR-2 (2026-10-06 owner: "Can I use SimplyFile for individual filing
help ... Form 16 integration and bank statements ... the most intuitive and sophisticated experience").

One journey, five steps (chip myreturn.settings steps): Gather (drop the pre-filled JSON from the e-filing portal, the AIS,
Form 16 from each employer, 26AS - myreturn_read.py reads each one and says what it found), Check (the same figure from two
documents, compared: Form 16's TDS against 26AS, salary against AIS, interest against what is claimed - chip
myreturn.checks), Choose (both regimes worked out side by side, the cheaper one marked - chips myreturn.salary / house /
deductions / tax / better), Review (every figure, where it came from, and an edit box), File (ITR-1, 2, 3 or 4 - chip
myreturn.form - as the department's own JSON, checked against its schema by itr_json.assemble; a tax audit or a business
loss is a CA's job - no JSON, the person is told so).

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
OTHER = ("savings", "deposits", "dividend", "family_pension", "refund_interest", "other",
         "lottery", "online_games")                                     # 2026-10-07: winnings at the 115BB / 115BBJ rate, not the slabs
SPECIAL_OS = ("lottery", "online_games")
VDA = ("name", "acquired", "transferred", "cost", "sale")              # 2026-10-07: one transfer of a virtual digital asset (115BBH)
VEHICLE = ("reg", "weight_kg", "months", "own")                        # 2026-10-07: one goods carriage (44AE)
CG = ("stcg_111a", "ltcg_112a", "ltcg_112", "stcg_other")
VIA = ("c80c", "c80ccc", "c80ccd1", "c80ccd1b", "c80ccd2", "c80d_self", "c80d_parents", "c80e", "c80g",
       "c80ddb", "c80ee", "c80eea", "c80eeb", "c80ggc", "c80gg")      # 2026-10-06: the rest of Chapter VI-A (c80gg = rent, for 80GG)
VIA_MORE = ("dd_nature", "dd_type", "dd_dependent", "ddb_senior", "stamp", "vehicle", "ggc_party", "ggc_pan", "ggc_date", "ggc_ref", "ggc_ifsc")
LOAN = ("from", "bank", "acc", "date", "amount", "left")
BIZ = ("kind", "code", "name", "digital", "cash", "declared", "gstin", "gst_turnover",   # 2026-10-06 presumptive business / profession
       "gp", "expenses", "np", "debtors", "creditors", "stock", "cash_in_hand",         # 2026-10-07 ITR-3: own profit and loss, no regular books
       "ad_left")                                                                        # 2026-10-08: s.44AD(4) - left 44AD within five years ("yes")
BIZ_TEXT = ("kind", "code", "name", "gstin", "ad_left")
BIZ_OPT = ("pay_total", "pay_cash")       # 2026-10-08 s.44AB provisos: payments in all / in cash - "" until typed (the receipts' share stands in)
GSTIN = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]")
EX = ("ex_kind", "ex_amount", "ex_on", "ex_build", "cgas", "cgas_on", "cgas_acc", "cgas_ifsc")   # 2026-10-08: one exemption claim on a sale
EMPLOYER = ("name", "tan", "gross_17_1", "perq_17_2", "profit_17_3", "exempt_all", "exempt_new", "hra", "prof_tax", "tds", "basic_da",
            "address", "city", "state", "pin")
EMP_TEXT = ("name", "tan", "address", "city", "state", "pin")            # 2026-10-07: the employer's address from Form 16 Part A
# 2026-10-07 wave 3: one sale of a capital asset (typed, or read from a broker / CAMS / KFintech statement), with its exemption claim
CG_ROW = ("asset", "name", "isin", "units", "acquired", "sold", "term", "sale", "cost", "improve", "improve_on", "fmv", "expenses", "stamp",
          "ex_kind", "ex_amount", "ex_on", "ex_build", "cgas", "cgas_on", "cgas_acc", "cgas_ifsc", "other_houses",
          "buyer", "buyer_pan", "buyer_share", "address", "state", "pin", "tds")
CG_NUM = ("units", "sale", "cost", "improve", "fmv", "expenses", "stamp", "ex_amount", "cgas", "other_houses", "buyer_share", "tds")
CG_DAY = ("acquired", "sold", "improve_on", "ex_on", "cgas_on")
LOSS = ("ay", "kind", "amount", "filed_on")                              # a loss brought forward (Schedule CFL)
GIFT = ("from", "relation", "occasion", "kind", "value", "paid", "on")   # a gift received (s.56(2)(x))
BUCKETS = ("stcg_111a", "stcg_app", "ltcg_112", "ltcg_112a")
# 2026-10-07 wave 3: foreign income (Schedule FSI / TR), foreign assets (Schedule FA), clubbing (s.64, Schedule SPI), salary arrears
# (s.89, Form 10E) and the updated return of an earlier year (ITR-U)
FOREIGN = ("country", "head", "amount", "tax_paid", "sec", "article", "tin", "controlled", "employer", "address", "city", "zip", "municipal_tax", "interest")
FOREIGN_NUM = ("amount", "tax_paid", "municipal_tax", "interest")
FA = ("kind", "country", "name", "address", "zip", "account", "status", "opened", "peak", "closing", "income", "nature", "cost", "proceeds",
      "taxed", "sch", "sch_no", "holder", "trustees", "trustees_addr", "settlor", "settlor_addr", "beneficiaries", "beneficiaries_addr",   # 2026-10-08: D-F
      "inc_nature")                                                                    # 2026-10-10: table B (a financial interest) - the income's nature
FA_NUM = ("peak", "closing", "income", "cost", "proceeds", "taxed")
CLUB = ("name", "pan", "relation", "head", "amount", "skill", "disabled", "municipal_tax", "interest", "address")
ARREAR = ("fy", "amount", "income", "regime")
ITRU = ("ay", "filed", "orig_income", "added", "tds_added", "tds", "advance", "regime", "reason", "on", "form",
        # 2026-10-08: that year's special-rate income (in the return before / added) and the advance tax by instalment (234C)
        "orig_111a", "orig_112a", "orig_112", "orig_30", "add_111a", "add_112a", "add_112", "add_30", "early", "adv_q1", "adv_q2", "adv_q3", "adv_q4")
ITRU_NUM = ("orig_income", "added", "tds_added", "tds", "advance", "orig_111a", "orig_112a", "orig_112", "orig_30", "add_111a", "add_112a", "add_112",
            "add_30", "adv_q1", "adv_q2", "adv_q3", "adv_q4")
ITRU_SPECIAL = {"111a": "stcg_111a", "112a": "ltcg_112a", "112": "ltcg_112", "30": "special"}



def _ai_allowed(user: dict | None) -> bool:
    """2026-10-09 owner: only the portal admin fetches with AI (chip ai.features form16_ai_read who)."""
    import firms  # noqa: PLC0415
    from core import engine  # noqa: PLC0415
    row = next((f for f in engine.knobs("ai.features").get("features") or [] if f.get("id") == "form16_ai_read"), None)
    return bool(row) and (row.get("who") != "owner" or firms.is_owner(user))

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
                             ai_ok=bool((st0.get("answers") or {}).get("ai_ok")) and _ai_allowed(user))
    w = who(got)                                            # a document naming this person fills what the client lacks
    if w.get("pan") == c.get("pan") and (w.get("dob") and not c.get("dob") or w.get("name") and c.get("name") == c.get("pan")):
        clients.save(user, c | {"dob": c.get("dob") or w["dob"], "name": w["name"] if c.get("name") == c.get("pan") and w.get("name") else c["name"]}, cid)
    name = Path(filename).name[:120]
    # 2026-10-08: a second AIS / 26AS ..., or a second Form 16 from the same employer (TAN) - asked first (chip myreturn.doc_clash)
    others = [x for x in st0.get("docs") or [] if x["kind"] == got["kind"] and x["name"] != name]
    tans = {str(e.get("tan") or "").upper() for e in (got.get("facts") or {}).get("employers") or [] if e.get("tan")}
    by_tan = [x for x in others if tans & {str(e.get("tan") or "").upper() for e in (x.get("facts") or {}).get("employers") or []}]
    why = engine.run("myreturn.doc_clash", {"kind": got["kind"], "one_per_kind": k["one_per_kind"], "same_kind": len(others),
                                            "tan_kinds": k["tan_kinds"], "same_tan": len(by_tan)})["why"]
    same = others if why == "same" else by_tan if why == "same_tan" else []
    if same and on_same not in ("replace", "keep"):
        emp = next((e for e in (got.get("facts") or {}).get("employers") or [] if e.get("tan")), {})
        return work(cid, ay) | {"ask": {"why": why, "kind": got["kind"], "new": name, "tan": emp.get("tan", ""), "employer": emp.get("name", ""),
                                        "have": [{"name": x["name"], "at": x["added_at"]} for x in same]}}
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
        before = copy.deepcopy(st)
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
                    e[f] = str(v)[:120] if f in EMP_TEXT else _num(v)
        if "houses" in body:
            hs = []
            for h in (body["houses"] or [])[: int(k["houses_max"])]:
                kind = str(h.get("kind") or "self")
                if kind not in ("self", "let"):
                    _bad("bad_field", field="kind")
                share = _num(h.get("share")) or 100.0              # s.26: the person's share of a co-owned house, percent
                if not 0 < share <= 100:
                    _bad("bad_field", field="share")
                cos = [x for x in (h.get("co_owners") or []) if isinstance(x, dict)]
                if not cos and str(h.get("co_name") or "").strip():  # the page's one co-owner row
                    cos = [{"name": h.get("co_name"), "pan": h.get("co_pan"), "share": 100 - share}]
                co = []
                for x in cos[:10]:
                    pan = re.sub(r"\s", "", str(x.get("pan") or "")).upper()[:10]
                    if pan and not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan):
                        _bad("bad_field", field="co_pan")
                    co.append({"name": str(x.get("name") or "").strip()[:125], "pan": pan, "share": _num(x.get("share"))})
                hs.append({"kind": kind, "rent": _num(h.get("rent")), "municipal_tax": _num(h.get("municipal_tax")),
                           "interest": _num(h.get("interest")), "address": str(h.get("address") or "")[:200],
                           "share": share, "co_owners": [x for x in co if x["name"]],
                           "pre_total": _num(h.get("pre_total")), "completed": _iso(h.get("completed"))})   # 2026-10-07: s.24(b) pre-construction interest
            st["houses"] = hs
        if "cg_rows" in body:                               # 2026-10-07: each sale of a capital asset, typed on Review
            rules = engine.run("myreturn.cg_rules")
            rows = []
            for x in (body["cg_rows"] or [])[: int(k["cg_max"])]:
                if not isinstance(x, dict):
                    continue
                one = {f: (_num(x.get(f)) if f in CG_NUM else _iso(x.get(f)) if f in CG_DAY else str(x.get(f) or "").strip()[:125]) for f in CG_ROW}
                one["asset"] = one["asset"] or "equity"
                if one["asset"] not in rules["assets"]:
                    _bad("bad_field", field="asset")
                # 2026-10-08: several exemptions on one sale (54 + 54EC ...) - a list, or the page's flat fields (ex_kind, ex_kind_1 ...)
                claims = []
                flat = [{f: x.get(f + ("" if n == 0 else f"_{n}")) for f in EX} for n in range(int(rules["ex_max"]))]
                for c in (x["ex_rows"] if isinstance(x.get("ex_rows"), list) else flat)[: int(rules["ex_max"])]:
                    if not isinstance(c, dict) or not str(c.get("ex_kind") or "").strip():
                        continue
                    c = {"ex_kind": str(c.get("ex_kind")).strip(), "ex_amount": _num(c.get("ex_amount")), "ex_on": _iso(c.get("ex_on")),
                         "ex_build": "build" if str(c.get("ex_build") or "") in ("build", "true", "True", "1", "on") else "",
                         "cgas": _num(c.get("cgas")), "cgas_on": _iso(c.get("cgas_on")), "cgas_acc": str(c.get("cgas_acc") or "").strip()[:20],
                         "cgas_ifsc": str(c.get("cgas_ifsc") or "").strip().upper()[:11]}
                    if c["ex_kind"] not in ("54", "54EC", "54F"):
                        _bad("bad_field", field="ex_kind")
                    claims.append(c)
                one["ex_rows"] = claims
                one |= claims[0] if claims else {f: (0.0 if f in ("ex_amount", "cgas") else "") for f in EX}
                if one["term"] not in ("", "long", "short"):
                    _bad("bad_field", field="term")
                one["isin"] = re.sub(r"\s", "", one["isin"]).upper()[:12]
                one["buyer_pan"] = re.sub(r"\s", "", one["buyer_pan"]).upper()[:10]
                if one["buyer_pan"] and not re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", one["buyer_pan"]):
                    _bad("bad_field", field="buyer_pan")
                one["cgas_ifsc"] = one["cgas_ifsc"].upper()[:11]
                rows.append(one)
            st["cg_rows"] = rows
        if "losses_bf" in body:                             # losses of earlier years brought forward (Schedule CFL)
            ls = []
            for x in (body["losses_bf"] or [])[: int(k["losses_max"])]:
                if not isinstance(x, dict):
                    continue
                kind, lay = str(x.get("kind") or "stcl"), str(x.get("ay") or "").strip()
                if kind not in ("stcl", "ltcl", "hp") or (lay and not re.fullmatch(r"\d{4}-\d{2}", lay)):
                    _bad("bad_field", field="kind" if kind not in ("stcl", "ltcl", "hp") else "ay")
                ls.append({"ay": lay, "kind": kind, "amount": abs(_num(x.get("amount"))), "filed_on": _iso(x.get("filed_on"))})
            st["losses_bf"] = ls
        if "gifts" in body:                                 # gifts received (s.56(2)(x))
            gr = engine.run("myreturn.gift_rules")
            gs = []
            for x in (body["gifts"] or [])[: int(k["gifts_max"])]:
                if not isinstance(x, dict):
                    continue
                one = {f: (_num(x.get(f)) if f in ("value", "paid") else _iso(x.get(f)) if f == "on" else str(x.get(f) or "").strip()[:80]) for f in GIFT}
                one["kind"] = one["kind"] or "money"
                if one["kind"] not in ("money", "property", "movable") or (one["relation"] and one["relation"] not in gr["relatives"]) \
                        or (one["occasion"] and one["occasion"] not in gr["exempt_occasions"]):
                    _bad("bad_field", field="gift")
                gs.append(one)
            st["gifts"] = gs
        _wave3(body, st, k, ay)
        if body.get("losses_from_prev"):                    # last year's filed return: its Schedule CFL, carried a year on
            got = prev_losses(st, ay)
            if not got:
                _bad("no_prev_losses", 404)
            st["losses_bf"] = [x for x in got if x["kind"] in ("stcl", "ltcl", "hp")]
            st["losses_bf_other"] = [x for x in got if x["kind"] not in ("stcl", "ltcl", "hp")]   # 2026-10-08: a business loss (ITR-3) - a CA's job
        if "business" in body:                              # presumptive business / profession, typed on Check
            b = body["business"] or {}
            if str(b.get("kind") or "") not in k["biz_kinds"]:
                _bad("bad_field", field="kind")
            vs = b["vehicles"] if "vehicles" in b else (st.get("business") or {}).get("vehicles") or []
            own = engine.run("myreturn.json")["vehicle_own"]
            vehicles = []
            for x in (vs or [])[: int(k["vehicles_max"])]:            # 44AE goods carriages, each typed on Check
                o = str(x.get("own") or "own").lower()
                if o not in own:
                    _bad("bad_field", field="own")
                vehicles.append({"reg": re.sub(r"[^A-Z0-9]", "", str(x.get("reg") or "").upper())[:11], "weight_kg": _num(x.get("weight_kg")),
                                 "months": min(max(int(_num(x.get("months")) or 12), 1), 12), "own": o})
            # 2026-10-08: the GST schedule - turnover per GSTIN (typed rows; the old single gstin / gst_turnover is the first row)
            gs = b["gst_rows"] if "gst_rows" in b else (st.get("business") or {}).get("gst_rows") or []
            gst_rows = []
            for x in (gs or [])[: int(k["gst_max"])]:
                g = re.sub(r"\s", "", str((x or {}).get("gstin") or "")).upper()[:15]
                if g and not GSTIN.fullmatch(g) or not g and _num((x or {}).get("turnover")):
                    _bad("bad_gstin", gstin=g or "-")       # a blank row (just added) is kept to be typed in; the JSON takes only GSTINs
                gst_rows.append({"gstin": g, "turnover": _num(x.get("turnover"))})
            opt = {f: ("" if str(b.get(f) if b.get(f) is not None else "").strip() == "" else _num(b.get(f))) for f in BIZ_OPT}
            st["business"] = {f: (str(b.get(f) or "").strip()[:120] if f in BIZ_TEXT else _num(b.get(f))) for f in BIZ} | {"vehicles": vehicles, "gst_rows": gst_rows} | opt
            if "gst_rows" in b:                              # the rows say it all now: the single GSTIN of before goes
                st["business"] |= {"gstin": "", "gst_turnover": 0.0}
            if st["business"]["ad_left"] not in ("", "yes"):
                _bad("bad_field", field="ad_left")
        if "vda" in body:                                   # virtual digital assets transferred in the year (115BBH)
            st["vda"] = [{f: (_num(x.get(f)) if f in ("cost", "sale") else str(x.get(f) or "").strip()[:60]) for f in VDA}
                         for x in (body["vda"] or [])[: int(k["vda_max"])] if isinstance(x, dict)]
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
            st["regime"] = body["regime"]       # checked below, on the return with the rest of this save in it
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
        # 2026-10-08: 115BAC(6) - the old regime is open when THIS return (with the business, the dates ... of this same save) is filed by
        # its form's due date (chip myreturn.settings old_regime_kinds on close.dates): asked after the save, the save undone when it is not
        if body.get("regime") == "old" and not work(cid, ay)["old_ok"]:
            _save(cid, ay, before)
            _bad("old_closed")
    return work(cid, ay)


def _wave3(body: dict, st: dict, k: dict, ay: str) -> None:
    """2026-10-07 wave 3: foreign income rows, foreign assets, clubbed income, salary arrears (s.89) and an updated return (ITR-U) -
    each typed on Review / File; what is allowed is chip myreturn.foreign_rules / club_rules / json / itru_rules."""
    pan_ok = lambda v: not v or re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", v)  # noqa: E731
    cc = {c for c, _ in countries()}
    if "foreign_rows" in body:
        fr = engine.run("myreturn.foreign_rules")
        rows = []
        for x in (body["foreign_rows"] or [])[: int(k["foreign_max"])]:
            if not isinstance(x, dict):
                continue
            one = {f: (_num(x.get(f)) if f in FOREIGN_NUM else bool(x.get(f) in (True, "true", "on", "1")) if f == "controlled"
                       else str(x.get(f) or "").strip()[:75]) for f in FOREIGN}
            one["head"] = one["head"] or "other"
            if one["head"] not in fr["heads"] or (one["sec"] and one["sec"] not in fr["relief_secs"]) or (one["country"] and one["country"] not in cc):
                _bad("bad_field", field="foreign")
            one["article"] = one["article"][:16]
            rows.append(one)
        st["foreign_rows"] = rows
    if "fa_rows" in body:
        kinds = engine.run("myreturn.json")["fa_kinds"]
        rows = []
        for x in (body["fa_rows"] or [])[: int(k["fa_max"])]:
            if not isinstance(x, dict):
                continue
            one = {f: (_num(x.get(f)) if f in FA_NUM else _iso(x.get(f)) if f == "opened" else str(x.get(f) or "").strip()[:100]) for f in FA}
            one["kind"] = one["kind"] or "bank"
            if one["kind"] not in kinds or (one["country"] and one["country"] not in cc):
                _bad("bad_field", field="fa")
            rows.append(one)
        st["fa_rows"] = rows
    if "club_rows" in body:
        cr = engine.run("myreturn.club_rules")
        rows = []
        for x in (body["club_rows"] or [])[: int(k["club_max"])]:
            if not isinstance(x, dict):
                continue
            one = {f: (_num(x.get(f)) if f in ("amount", "municipal_tax", "interest") else bool(x.get(f) in (True, "true", "on", "1")) if f in ("skill", "disabled")
                       else str(x.get(f) or "").strip()[:125]) for f in CLUB}
            one["relation"], one["head"] = one["relation"] or "minor_child", one["head"] or "interest"
            one["pan"] = re.sub(r"\s", "", one["pan"]).upper()[:10]
            if one["relation"] not in cr["relations"] or one["head"] not in cr["heads"] or not pan_ok(one["pan"]):
                _bad("bad_field", field="club")
            rows.append(one)
        st["club_rows"] = rows
    if "arrears" in body:
        rows = []
        for x in (body["arrears"] or [])[: int(k["arrears_max"])]:
            if not isinstance(x, dict):
                continue
            one = {"fy": str(x.get("fy") or "").strip()[:7], "amount": _num(x.get("amount")), "income": _num(x.get("income")), "regime": str(x.get("regime") or "")}
            if (one["fy"] and not re.fullmatch(r"\d{4}-\d{2}", one["fy"])) or one["regime"] not in ("", "old", "new"):
                _bad("bad_field", field="arrears")
            rows.append(one)
        st["arrears"] = rows
    if "itru" in body:
        u = body["itru"] or {}
        ir = engine.run("myreturn.itru_rules")
        one = {f: (_num(u.get(f)) if f in ITRU_NUM else _iso(u.get(f)) if f == "on" else str(u.get(f) or "").strip()[:20]) for f in ITRU}
        one["bars"] = [b for b in ir["bars"] if b in (u.get("bars") or [])]
        if one["ay"] and (one["ay"] not in clients.settings()["years"] or one["ay"] >= ay) or one["regime"] not in ("", "old", "new") \
                or (one["reason"] and one["reason"] not in ir["reasons"]) or one["filed"] not in ("", "none", "original", "belated", "revised"):
            _bad("bad_field", field="itru")
        st["itru"] = one if one["ay"] else {}


@lru_cache(maxsize=1)
def countries() -> list:
    """[[code, name], ...] - the department's own country list (ITR-2 schema CountryCodeExcludingIndia: "93:AFGHANISTAN; ...")."""
    import itr_json  # noqa: PLC0415
    s = itr_json.schema("ITR-2")
    v = itr_json._ref(s, s["definitions"][settings()["countries_from"]])  # noqa: SLF001
    names = dict(re.findall(r"(\d+)\s*:\s*([^;]+)", v.get("description") or ""))
    return [[c, names.get(c, c).strip().title()] for c in v["enum"]]


@lru_cache(maxsize=1)
def cfl3_years() -> dict:
    """{block name: AY} of ITR-3's Schedule CFL - "LossCFCurrentAssmntYear2025" ... read from the ITR-3 schema's own descriptions ("Carry
    forward losses for AY2024-25"; chip myreturn.settings itr3_cfl block_ay): the names stay year to year, so last year's file reads by them."""
    import itr_json  # noqa: PLC0415
    k3 = settings()["itr3_cfl"]
    s = itr_json.schema(k3["form"])
    cfl = itr_json._ref(s, s["definitions"][settings()["from_prev"]["cfl"]])  # noqa: SLF001
    out = {}
    for b, v in cfl["properties"].items():
        if m := re.search(k3["block_ay"], str(v.get("description") or "")):
            out[b] = m.group(1)
    return out


# --- one return from many documents --------------------------------------------------------------------------------------

@lru_cache(maxsize=1)
def biz_codes() -> dict:
    """The nature-of-work codes the department lists in the ITR-4 schema (CodeADA / CodeAD, "14001 - Software development, ..."):
    {"44ADA": [[code, words], ...], "44AD": [...]} - the department's list, so never a copy of ours to go stale."""
    import itr_json  # noqa: PLC0415
    d = itr_json.schema("ITR-4")["definitions"]
    out = {}
    for kind, node, field in (("44ADA", "NatOfBus44ADA", "CodeADA"), ("44AD", "NatOfBus44AD", "CodeAD"), ("44AE", "NatOfBus44AE", "CodeAE")):
        out[kind] = _codes_of(d[node]["properties"][field])
    for kind, (form, path, field) in settings()["pl_codes"].items():   # 2026-10-07: own P&L - ITR-3's nature-of-business list
        s = itr_json.schema(form)
        v = s["definitions"][itr_json.settings()["forms"][form]["root"]]
        for part in path.split("."):
            v = itr_json._ref(s, itr_json._ref(s, v)["properties"][part])  # noqa: SLF001
        v = itr_json._ref(s, v["items"] if v.get("type") == "array" else v)  # noqa: SLF001
        out[kind] = _codes_of(itr_json._ref(s, v["properties"][field]))  # noqa: SLF001
    return out


def _codes_of(f: dict) -> list:
    words = dict(re.findall(r"(\d{5}(?:_\d)?)\s*-\s*(.+?)\s*(?=[,;]\s*\d{5}|$)", f.get("description") or ""))
    return [[x, words.get(x, x).strip(" ;,")] for x in f["enum"]]


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
            elif sec == "via" and kind == "form16":            # 2026-10-08: two employers' Form 16s - each one's deductions, added up
                out[sec] = {f: round(sum(_num(d["facts"][sec].get(f)) for d in have), 2) for f in VIA}   # (the caps apply once; check two_emp_80c)
            else:
                out[sec] = copy.deepcopy(have[0]["facts"][sec])
            out["from"][sec] = {"kind": kind, "doc": have[0]["id"]}
            break
    # 2026-10-07: who the person is - each detail from the first document that has it (the AIS header has the address,
    # e-mail and mobile when the pre-filled JSON is missing)
    pp: dict = {}
    for kind in order.get("person", []):
        for d in docs:
            if d["kind"] == kind:
                pp |= {f: v for f, v in ((d["facts"] or {}).get("person") or {}).items() if v not in (None, "") and f not in pp}
    out["person"] = pp
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
    out["employers"] = [{k: (str(e.get(k) or "") if k in EMP_TEXT else _num(e.get(k))) for k in EMPLOYER}
                        | {"doc": e.get("doc", ""), "typed": e.get("typed", []), "exempt_rows": e.get("exempt_rows") or []} for e in emps]
    out["houses"] = [{"share": 100.0, "co_owners": []} | h for h in st.get("houses") or []]
    out["vda"] = st.get("vda") or []
    out["vda_seen"] = round(sum(_num((d.get("facts") or {}).get("vda_seen")) for d in docs if d["kind"] == "ais"), 2)
    out["via_more"] = st.get("via_more") or {}
    secs = set(settings()["business_sections"])          # what the department saw paid to the person for work (194J, 194C ...)
    seen = sum(_num(x.get("income")) for x in out.get("tds") or [] if re.sub(r"\s+", "", str(x.get("section") or "")).upper() in secs)
    biz = st.get("business") or {}
    bk = [d["facts"]["bank"] for d in st.get("docs") or [] if d["kind"] == "bank" and (d.get("facts") or {}).get("bank")]
    out["bank"] = {f: round(sum(_num(x.get(f)) for x in bk), 2) for f in ("credits", "receipts", "cash", "interest")} | {"statements": len(bk)}
    out["business"] = {f: (str(biz.get(f) or "") if f in BIZ_TEXT else _num(biz.get(f))) for f in BIZ} | {"seen": seen, "vehicles": biz.get("vehicles") or []}
    out["business"] |= {f: biz.get(f, "") for f in BIZ_OPT}
    # 2026-10-08: the GST schedule - the rows typed, else what each GSTR-3B summary read gives (a GSTIN's months added up), else the one GSTIN typed
    gst_read: dict = {}
    for d in docs:
        for x in (d.get("facts") or {}).get("gst_rows") or [] if d["kind"] == "gst" else []:
            gst_read[x["gstin"]] = round(gst_read.get(x["gstin"], 0.0) + _num(x.get("turnover")), 2)
    typed_gst = [x for x in biz.get("gst_rows") or [] if x.get("gstin")] or ([{"gstin": biz["gstin"].upper(), "turnover": _num(biz.get("gst_turnover"))}] if biz.get("gstin") else [])
    out["business"]["gst_rows"] = typed_gst or [{"gstin": g, "turnover": v, "doc": True} for g, v in gst_read.items()]
    out["business"]["gst_typed"] = biz.get("gst_rows") or typed_gst                # what the page shows to type over (a blank row too)
    out["business"]["gst_read"] = [{"gstin": g, "turnover": v} for g, v in gst_read.items()]
    out["business"]["gst_turnover"] = round(sum(_num(x.get("turnover")) for x in out["business"]["gst_rows"]), 2)
    out["person"] = out.get("person") or {}
    out["tds"] = out.get("tds") or []
    minor = settings()["paid_minor"]
    out["paid_typed"] = st.get("paid_typed") or []
    out["paid"] = (out.get("paid") or []) + [{"date": x["date"], "amount": x["amount"], "minor": minor[x["kind"]], "bsr": x.get("bsr", ""), "challan": x.get("challan", ""), "typed": True}
                                             for x in out["paid_typed"] if x["amount"]]
    out["banks"] = out.get("banks") or []
    # 2026-10-07 wave 3: sales typed, then every statement's rows (CAMS, KFintech, a broker's tax P&L); losses brought forward; gifts
    out["cg_rows"] = [dict(x, doc="") for x in st.get("cg_rows") or []] + [
        {f: x.get(f, 0.0 if f in CG_NUM else "") for f in CG_ROW} | {"asset": x.get("asset") or "equity", "doc": d["id"]}
        for d in docs if d["kind"] == "cg" for x in (d.get("facts") or {}).get("cg_rows") or []]
    out["losses_bf"] = st.get("losses_bf") or []
    out["gifts"] = st.get("gifts") or []
    for f in ("foreign_rows", "fa_rows", "club_rows", "arrears"):     # 2026-10-07 wave 3, typed on Review
        out[f] = st.get(f) or []
    out["extra"] = {}                                       # what they add to the return - apply_status(), once the status is known
    seen = [dict(x, doc=d["id"]) for d in docs if d["kind"] == "26as" for x in (d.get("facts") or {}).get("tds_194ia") or []]   # 2026-10-08: 26AS Part A2
    by26 = {x["pan"] for x in seen if x.get("pan")}                    # the same buyer in the AIS and 26AS: 26AS (the tax credit statement) only
    seen += [dict(x, doc=d["id"]) for d in docs if d["kind"] == "ais" for x in (d.get("facts") or {}).get("tds_194ia") or [] if x.get("pan") not in by26]
    pans = {x["pan"] for x in seen if x.get("pan")}
    out["tds_194ia"] = seen + [{"pan": x["buyer_pan"], "name": x["buyer"], "income": x["sale"], "tds": x["tds"], "section": "194IA", "doc": ""}
                               for x in out["cg_rows"] if x.get("tds") and x.get("buyer_pan") and x["buyer_pan"] not in pans]
    out["property_seen"] = round(max(sum(_num((d.get("facts") or {}).get("property_seen")) for d in docs if d["kind"] == "ais"),
                                     sum(_num((d.get("facts") or {}).get("property_sft")) for d in docs if d["kind"] == "ais"),
                                     sum(_num(x.get("income")) for x in seen if x.get("doc") in {d["id"] for d in docs if d["kind"] == "26as"})), 2)  # 2026-10-08: 26AS Part A2
    out["losses_bf_other"] = st.get("losses_bf_other") or []
    out["sales_seen"] = round(sum(_num((d.get("facts") or {}).get("sales")) for d in docs if d["kind"] == "ais"), 2)
    out["fy"] = int(ay[:4]) - 1
    return out


def _age(dob: str, ay: str) -> int:
    """Age on the last day of the financial year (31 March of the AY's first year)."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(dob or ""))
    if not m:
        return 0
    end = datetime.date(int(ay[:4]), 3, 31)
    born = datetime.date(int(m[1]), int(m[2]), int(m[3]))
    return end.year - born.year - ((end.month, end.day) < (born.month, born.day))


def _wf(loss: float, gains: list) -> dict:
    """A loss against up to four gains in order (chip myreturn.waterfall)."""
    return engine.run("myreturn.waterfall", {"loss": round(loss, 2), "gains": (list(gains) + [0, 0, 0, 0])[:4]})


def cg_work(r: dict, resident: bool = True, ay: str = "") -> dict:
    """Capital gains, regime by regime the same (2026-10-07 wave 3): each sale (chip myreturn.cg_row - its term, bucket, the value
    taken, grandfathering, indexation), its exemption both ways (chip myreturn.cg_exempt), the property's choice (chip
    myreturn.cg_choice), then the losses: netted inside each rate (111A 20%, slab, 12.5% LTCG), a short-term loss of one rate
    against the other gains and a long-term loss against long-term gains only (s.70 - the order is chip myreturn.cg_rules), then
    the losses brought forward (s.74, still in time by chip myreturn.loss_age). The totals typed on Review join their bucket."""
    k = engine.run("myreturn.cg_rules")
    ay = ay or f"{int(r.get('fy') or 2025) + 1}-{(int(r.get('fy') or 2025) + 2) % 100:02d}"
    rows, ec_room = [], float(k["cap_54ec"])
    gain = {b: 0.0 for b in BUCKETS}
    loss = {b: 0.0 for b in BUCKETS}
    for x in r.get("cg_rows") or []:
        c = engine.run("myreturn.cg_row", {f: x.get(f) or (0 if f in CG_NUM else "") for f in
                                           ("asset", "acquired", "sold", "term", "sale", "cost", "improve", "improve_on", "fmv", "expenses", "stamp")}
                       | {"resident": resident})
        # 2026-10-08: each exemption claimed on the sale (54 + 54EC ...): in time? (chip myreturn.cg_window - an investment out of time is not
        # counted), its amount (chip myreturn.cg_exempt, each against the gain), then each in order up to the gain still left (chip myreturn.waterfall)
        claims = x.get("ex_rows") or ([{f: x.get(f) for f in EX}] if x.get("ex_kind") else [])
        outs, plain, indexed, why = [], [], [], ""
        for cl in claims[: int(k["ex_max"])]:
            win = engine.run("myreturn.cg_window", {"kind": cl.get("ex_kind") or "", "sold": x.get("sold") or "", "on": cl.get("ex_on") or "",
                                                     "build": cl.get("ex_build") == "build", "invested": _num(cl.get("ex_amount")), "cgas": _num(cl.get("cgas")),
                                                     "cgas_on": cl.get("cgas_on") or "", "ay_year": int(ay[:4])})
            args = {"kind": cl.get("ex_kind") or "", "asset": x["asset"], "term": c["term"], "net": c["consideration"] - _num(x.get("expenses")),
                    "invested": _num(cl.get("ex_amount")) if win["invest_ok"] else 0, "cgas": _num(cl.get("cgas")) if win["cgas_ok"] else 0,
                    "ec_room": ec_room, "other_houses": _num(x.get("other_houses"))}
            ex = engine.run("myreturn.cg_exempt", args | {"gain": c["gain"]})
            exi = engine.run("myreturn.cg_exempt", args | {"gain": c["gain_indexed"]}) if c["index_ok"] else ex
            if args["kind"] == "54EC":
                ec_room -= ex["amount"]
            plain.append(ex["amount"])
            indexed.append(exi["amount"])
            outs.append(dict(cl) | {"why": win["why"] or ex["why"], "win_why": win["why"], "from": win["from"], "to": win["to"]})
            why = why or win["why"] or ex["why"]
        sp, spi = _wf(max(c["gain"], 0), plain), _wf(max(c["gain_indexed"], 0), indexed)
        for n, o in enumerate(outs):
            o["amount"], o["amount_indexed"] = sp["used"][n], spi["used"][n]
            if o.get("ex_kind") == "54EC":
                ec_room += plain[n] - o["amount"]                # what the gain left unused of the 54EC room goes back to it
        ex_amt, exi_amt = round(sum(o["amount"] for o in outs), 2), round(sum(o["amount_indexed"] for o in outs), 2)
        by = {kd: round(sum(o["amount"] for o in outs if o.get("ex_kind") == kd), 2) for kd in ("54", "54EC", "54F")}
        final, final_i = c["gain"] - ex_amt, c["gain_indexed"] - exi_amt
        ch = engine.run("myreturn.cg_choice", {"gain": final, "gain_indexed": final_i, "index_ok": c["index_ok"]})
        rows.append(dict(x) | c | {"exempt": ex_amt, "exempt_indexed": exi_amt, "ex_why": why, "claims": outs, "ex_by": by,
                                   "final": final, "final_indexed": final_i} | ch)
        (gain if final >= 0 else loss)[c["bucket"]] += abs(final)
    typed = typed_cg(r)
    for f, b in (("stcg_111a", "stcg_111a"), ("stcg_other", "stcg_app"), ("ltcg_112", "ltcg_112"), ("ltcg_112a", "ltcg_112a")):
        v = _num(typed.get(f))
        (gain if v >= 0 else loss)[b] += abs(v)
    # inside each rate first (Schedule CG A / B: a sale's loss nets against the same rate's gains)
    after = {b: max(gain[b] - loss[b], 0.0) for b in ("stcg_111a", "stcg_app")}
    lt = _wf(loss["ltcg_112"] + loss["ltcg_112a"], [gain[b] for b in k["ltcl_order"]])
    after |= {b: lt["rest"][i] for i, b in enumerate(k["ltcl_order"])}
    within = dict(after)
    left = {"stcg_111a": max(loss["stcg_111a"] - gain["stcg_111a"], 0.0), "stcg_app": max(loss["stcg_app"] - gain["stcg_app"], 0.0)}
    ltcl = lt["left"]
    # Schedule CG Table E: a short-term loss of one rate against the other gains (s.70(2))
    cross = {}
    for cls in ("stcg_111a", "stcg_app"):
        order = [b for b in k["stcl_order"] if b != cls]
        wf = _wf(left[cls], [after[b] for b in order])
        for i, b in enumerate(order):
            after[b] = wf["rest"][i]
            cross[f"{cls}>{b}"] = wf["used"][i]
        cross[f"{cls}>used"] = left[cls] - wf["left"]
        left[cls] = wf["left"]
    pre_bf = dict(after)
    # losses brought forward (s.74): a short-term one against any gain, a long-term one against long-term gains
    life = [dict(x) | engine.run("myreturn.loss_age", {"loss_ay": x.get("ay") or "", "ay": ay, "kind": x.get("kind")}) for x in r.get("losses_bf") or []]
    avail = {kd: round(sum(_num(x.get("amount")) for x in life if x["usable"] and x.get("kind") == kd), 2) for kd in ("stcl", "ltcl", "hp")}
    used = {b: 0.0 for b in BUCKETS}
    bf_left = {}
    for kd, order in (("stcl", k["stcl_order"]), ("ltcl", k["ltcl_order"])):
        wf = _wf(avail[kd], [after[b] for b in order])
        for i, b in enumerate(order):
            after[b], used[b] = wf["rest"][i], used[b] + wf["used"][i]
        bf_left[kd] = wf["left"]
    excess = sum(x["excess"] for x in rows if x["bucket"] == "ltcg_112" and x["final"] > 0)
    return {"rows": rows, "gain": gain, "loss": loss, "within": within, "pre_bf": pre_bf, "final": after, "cross": cross,
            "left": left, "ltcl": ltcl, "bf_avail": avail, "bf_used": used, "bf_used_total": round(sum(used.values()), 2), "bf_left": bf_left,
            "life": life, "excess": excess, "cf": {"stcl": round(left["stcg_111a"] + left["stcg_app"], 2), "ltcl": round(ltcl, 2)},
            "any": bool(rows) or any(gain.values()) or any(loss.values())}


def gifts_of(r: dict) -> dict:
    """Gifts received (s.56(2)(x)): each one by chip myreturn.gift_row, the year's sums by chip myreturn.gifts."""
    rows = [engine.run("myreturn.gift_row", {f: x.get(f) or (0 if f in ("value", "paid") else "") for f in ("relation", "occasion", "kind", "value", "paid")})
            for x in r.get("gifts") or []]
    parts = ("money", "movable_free", "movable_less", "property_free", "property_less")
    return engine.run("myreturn.gifts", {p: round(sum(y[p] for y in rows), 2) for p in parts}) | {"rows": rows}


def typed_cg(r: dict) -> dict:
    """The capital-gain totals typed on Review, with the foreign / clubbed gains that join them (2026-10-07 wave 3)."""
    ex = (r.get("extra") or {}).get("cg") or {}
    return {k2: _num((r.get("cg") or {}).get(k2)) + _num(ex.get(k2)) for k2 in CG}


def residence_of(ans: dict, status: str, indian_income: float | None = None) -> dict:
    """Resident / RNOR / non-resident (chip myreturn.residence) from the answers - the days in India when typed, else the yes / no."""
    n = lambda q, blank=-1: _num(ans.get(q)) if str(ans.get(q) if ans.get(q) is not None else "").strip() != "" else blank  # noqa: E731
    return engine.run("myreturn.residence", {
        "days_fy": n("days_fy"), "days_4y": max(n("days_4y"), 0), "nr_years": max(n("nr_years"), 0), "days_7y": n("days_7y"),
        "citizen": ans.get("citizen") is True, "pio": ans.get("pio") is True, "visiting": ans.get("visiting") is True,
        "left_for_job": ans.get("left_for_job") is True, "taxed_elsewhere": ans.get("taxed_elsewhere") is True,
        "indian_income": n("indian_income", 0) if indian_income is None else indian_income,
        "resident_flag": ans.get("resident", True) is not False, "huf": status == "huf"})


def apply_status(r: dict, res: dict) -> dict:
    """2026-10-07 wave 3: what the foreign income and the clubbed income add to the return, for this residential status - each row
    by chip myreturn.foreign_row / club_row (does it count, under which head), a minor child's 1,500 by chip myreturn.minor_exempt.
    Salary joins as one more employer (Schedule S, state 99), a house as one more house (Schedule HP: the 30%, the interest), interest /
    dividend / other to Schedule OS, a gain to the capital-gain totals. Python only routes the amounts."""
    ex = {"employers": [], "houses": [], "interest": 0.0, "dividend": 0.0, "other": 0.0, "cg": {k2: 0.0 for k2 in CG}, "foreign": [], "club": [],
          "ca": False, "exempt_10_32": 0.0}
    names = dict(countries())
    js = engine.run("myreturn.json")

    def put(to: str, amount: float, x: dict, owner: str, country: str) -> int | None:
        if to == "salary":
            ex["employers"].append({k2: (str(x.get(k2) or "") if k2 in EMP_TEXT else 0.0) for k2 in EMPLOYER}
                                   | {"name": x.get("employer") or names.get(country, country) or "-", "gross_17_1": amount, "state": js["foreign_state"],
                                      "pin": "", "zip": x.get("zip") or "", "city": x.get("city") or names.get(country, ""), "address": x.get("address") or "",
                                      "doc": "", "typed": [], "exempt_rows": [], "foreign": True, "category": js["foreign_category"]})
        elif to == "house":
            ex["houses"].append({"kind": "let", "rent": amount, "municipal_tax": _num(x.get("municipal_tax")), "interest": _num(x.get("interest")),
                                 "address": x.get("address") or names.get(country, "") or "-", "share": 100.0, "co_owners": [], "pre_total": 0.0, "completed": "",
                                 "country": country or js["country_india"], "zip": x.get("zip") or "", "owner": owner,
                                 "city": (x.get("city") or names.get(country, "")) if country else "",
                                 "state": js["foreign_state"] if country else ""})
            return len(r.get("houses") or []) + len(ex["houses"]) - 1
        elif to in ("interest", "dividend", "other"):
            ex[to] += amount
        elif to in CG:
            ex["cg"][to] += amount
        elif to == "business":
            ex["ca"] = True
        return None
    for x in r.get("foreign_rows") or []:
        f = engine.run("myreturn.foreign_row", {"status": res["status"], "head": x.get("head") or "other", "amount": _num(x.get("amount")),
                                                "controlled": x.get("controlled") is True})
        row = dict(x) | f
        if f["counts"]:
            row["house_i"] = put(f["to"], f["amount"], x, js["owner_self"], x.get("country") or "")
        ex["foreign"].append(row)
    rows = []
    for x in r.get("club_rows") or []:
        c = engine.run("myreturn.club_row", {f: x.get(f) for f in ("relation", "head", "amount", "skill", "disabled")})
        rows.append(dict(x) | c | {"included": c["amount"], "exempt": 0.0})
    kids = {}
    for x in rows:                                          # s.10(32): 1,500 a child, off the child's income other than a house
        if x["counts"] and x["relation"] == "minor_child" and x["to"] != "house":
            kids.setdefault((x.get("name") or "").strip().upper() or "-", []).append(x)
    for xs in kids.values():
        left = engine.run("myreturn.minor_exempt", {"income": sum(x["amount"] for x in xs)})["exempt"]
        ex["exempt_10_32"] += left
        for x in xs:
            cut = min(left, x["amount"])
            x["exempt"], x["included"], left = cut, x["amount"] - cut, left - cut
    for x in rows:
        if x["counts"]:
            x["house_i"] = put(x["to"], x["included"], x, x["owner"], "")
        ex["club"].append(x)
    r["extra"] = ex
    return ex


def reliefs(r: dict, g: dict, tax: dict, sal_income: float, status: str, band_of, targs: dict) -> dict:
    """2026-10-07 wave 3: relief u/s 89 (salary arrears - chips myreturn.arrear_row, relief_89: this year's tax with and without the
    arrears, each earlier year's at its own slabs) and u/s 90 / 90A / 91 (tax paid abroad - chip myreturn.dtaa_relief, per country and
    head: the lower of the foreign tax and the Indian tax at the average rate). Python sums the rows."""
    out = {"s89": 0, "s90": 0, "s91": 0, "rows89": [], "fsi": [], "form10e": False, "unknown89": False}
    ar = [x for x in r.get("arrears") or [] if _num(x.get("amount")) and re.fullmatch(r"\d{4}-\d{2}", str(x.get("fy") or ""))]
    if ar:
        rows = [engine.run("myreturn.arrear_row", {"fy": int(x["fy"][:4]), "regime": x.get("regime") or "", "band": band_of(int(x["fy"][:4])),
                                                   "income": _num(x.get("income")), "amount": _num(x.get("amount"))}) | {"fy": x["fy"], "amount": _num(x.get("amount"))}
                for x in ar]
        without = engine.run("myreturn.tax", targs | {"normal": max(targs["normal"] - sum(x["amount"] for x in rows), 0)})["tax"]
        unknown = any(not x["known"] or x["over"] for x in rows)
        rel = engine.run("myreturn.relief_89", {"now_with": tax["tax"], "now_without": without, "past": sum(x["extra"] for x in rows),
                                                "unknown": unknown, "huf": status == "huf", "salary": sal_income})
        out |= {"s89": rel["relief"], "rows89": rows, "now_with": tax["tax"], "now_without": without, "now_extra": rel["now_extra"],
                "past": sum(x["extra"] for x in rows), "form10e": rel["form10e"], "unknown89": unknown}
    ex = r.get("extra") or {}
    by: dict = {}
    for x in ex.get("foreign") or []:
        if not x.get("counts") or not x.get("fsi"):
            continue
        inc = g["houses"][x["house_i"]]["net"] if x.get("house_i") is not None else _num(x.get("amount"))
        c = by.setdefault(x.get("country") or "", {"tin": x.get("tin") or "", "sec": x.get("sec") or "", "blocks": {}})
        b = c["blocks"].setdefault(x["fsi"], {"income": 0.0, "paid": 0.0, "article": ""})
        b["income"] += inc
        b["paid"] += _num(x.get("tax_paid"))
        b["article"] = b["article"] or (x.get("article") or "")
        c["sec"] = c["sec"] or (x.get("sec") or "")
    for code, c in by.items():
        for b in c["blocks"].values():
            d = engine.run("myreturn.dtaa_relief", {"income": b["income"], "tax_paid": b["paid"], "tax_total": tax["tax"], "income_total": tax["total"],
                                                    "sec": c["sec"] or engine.run("myreturn.foreign_rules")["relief_secs"][0]})
            b |= {"indian": d["indian_tax"], "relief": d["relief"]}
            out["s90" if d["dtaa"] else "s91"] += d["relief"]
        out["fsi"].append({"country": code} | c)
    out["total"] = min(out["s89"] + out["s90"] + out["s91"], max(tax["tax"], 0))
    return out


def prev_losses(st: dict, ay: str) -> list[dict]:
    """Last year's filed return (its JSON dropped in): each loss its Schedule CFL carries, a year older now, less what it set off
    last year (AdjTotBFLossInBFLA, oldest first), and last year's own loss (CurrentAYloss) - the paths are chip myreturn.settings
    from_prev, the years chip myreturn.json cfl_blocks."""
    import itr_json  # noqa: PLC0415
    k, blocks = settings()["from_prev"], engine.run("myreturn.json")["cfl_blocks"]
    d = next((x for x in reversed(st.get("docs") or []) if x["kind"] == "filed_prev"), None)
    if not d:
        return []
    itr = (d["facts"].get("filed_json") or {}).get("ITR") or {}
    body = next(iter(itr.values()), {}) if itr else {}
    cfl = itr_json._get(body, k["cfl"]) or {}  # noqa: SLF001
    y0 = int(ay[:4]) - 1                                       # last year's AY starts the year before this one's
    when = next((str(v)[:10] for p in k["date"] if (v := itr_json._get(body, p))), "")  # noqa: SLF001
    rows = []
    k3 = settings()["itr3_cfl"]
    fields = k["fields"] | (k3["other_fields"] if d["facts"].get("form") == k3["form"] else {})
    if d["facts"].get("form") == k3["form"]:                  # 2026-10-08: ITR-3 names each block by its AY (the schema says which)
        named = [(b, ay_) for b, ay_ in cfl3_years().items() if b in cfl]
    else:                                                      # ITR-2: their n-th earlier year is our (n+1)-th; their 8th is gone
        named = [(b, f"{y0 - n}-{(y0 - n + 1) % 100:02d}") for n, b in enumerate(blocks[:-1], 1)]
    for b, lay in named:
        x = itr_json._get(cfl, f"{b}.{k['detail']}") or {}  # noqa: SLF001
        for kd, field in fields.items():
            if _num(x.get(field)):
                rows.append({"ay": lay, "kind": kd, "amount": _num(x.get(field)), "filed_on": str(x.get(k["filed"]) or "")[:10]})
    adj = itr_json._get(cfl, f"{k['adjusted']}.{k['summary']}") or {}  # noqa: SLF001
    for kd, field in fields.items():                           # what set off last year came from the oldest first
        take = _num(adj.get(field))
        for x in sorted((x for x in rows if x["kind"] == kd), key=lambda x: x["ay"]):
            cut = min(take, x["amount"])
            x["amount"], take = round(x["amount"] - cut, 2), take - cut
    cur = itr_json._get(cfl, f"{k['current']}.{k['summary']}") or {}  # noqa: SLF001
    for kd, field in fields.items():
        if _num(cur.get(field)):
            rows.append({"ay": f"{y0}-{(y0 + 1) % 100:02d}", "kind": kd, "amount": _num(cur.get(field)), "filed_on": when})
    return sorted((x for x in rows if x["amount"]), key=lambda x: (x["ay"], x["kind"]))


def one_regime(r: dict, regime: str, band: str, ans: dict, status: str = "individual") -> dict:
    """The whole computation under one regime - every step a chip."""
    ex = r.get("extra") or {}                                # 2026-10-07 wave 3: foreign / clubbed income joins its head
    emps = r["employers"] + (ex.get("employers") or [])
    resident = (r.get("res") or {}).get("resident", ans.get("resident", True) is not False)
    gross = sum(e["gross_17_1"] + e["perq_17_2"] + e["profit_17_3"] for e in emps)
    sal = engine.run("myreturn.salary", {"gross": gross, "exempt_all": sum(e["exempt_all"] for e in emps),
                                         "exempt_new": sum(e["exempt_new"] for e in emps), "prof_tax": sum(e["prof_tax"] for e in emps),
                                         "regime": regime}) if emps else {"exempt": 0, "std": 0, "prof_tax": 0, "income": 0}
    fy = {"fy": r["fy"]} if r.get("fy") else {}
    houses = [engine.run("myreturn.house", {f: h.get(f) for f in ("kind", "rent", "municipal_tax", "interest", "share")}
                         | {"pre_total": _num(h.get("pre_total")), "completed": h.get("completed") or "", "regime": regime} | fy)
              for h in r["houses"] + (ex.get("houses") or [])]
    hp = engine.run("myreturn.hp_total", {"nets": [h["net"] for h in houses], "regime": regime}) if houses else {"loss": 0, "net": 0}
    cgw = r.get("cgw") or cg_work(r)                         # 2026-10-07: capital gains after every set-off (regime-free)
    hp_bf = _wf(cgw["bf_avail"]["hp"], [max(hp["net"], 0)])["used"][0]   # s.71B: a house loss brought forward, against house income only
    hp_now = hp["net"] - hp_bf
    o = r["other"]
    fp = engine.run("myreturn.family_pension", {"pension": o["family_pension"], "regime": regime})
    gifts = gifts_of(r)                                      # s.56(2)(x)
    os_ = o["savings"] + o["deposits"] + o["dividend"] + o["refund_interest"] + o["other"] + fp["net"] + gifts["total"] \
        + _num(ex.get("interest")) + _num(ex.get("dividend")) + _num(ex.get("other"))
    fin = cgw["final"]
    cg = {"stcg_111a": fin["stcg_111a"], "ltcg_112a": fin["ltcg_112a"], "ltcg_112": fin["ltcg_112"], "stcg_other": fin["stcg_app"]}
    b = r.get("business") or {}
    kind = b.get("kind") or ""
    ae = [engine.run("myreturn.vehicle_44ae", {"weight_kg": v["weight_kg"], "months": v["months"]}) | v for v in b.get("vehicles") or []] if kind == "44AE" else []
    # 2026-10-07: a business on its own profit and loss is asked of the presumptive section it would have had (limits, s.44AB(e))
    as_kind = settings()["pl_as"].get(kind, kind)
    pres = engine.run("myreturn.business", {f: b.get(f) or (0 if f != "kind" else "") for f in ("digital", "cash", "declared", "seen")}
                      | {"kind": as_kind, "ae_income": sum(x["income"] for x in ae), "vehicles": len(ae)})
    own = engine.run("myreturn.business_pl", {"kind": kind, "over_limit": pres["over_limit"] is True, "presumptive_income": pres["income"]}
                     | {f: _num(b.get(f)) for f in ("digital", "cash", "gp", "expenses", "np")})
    biz = pres | own | {"vehicles": ae, "presumptive_income": pres["income"],
                        "presumptive_open": kind in settings()["pl_as"] and pres["over_limit"] is not True}
    vda = engine.run("myreturn.vda", {"rows": [{"cost": x["cost"], "sale": x["sale"]} for x in r.get("vda") or []]})
    gti_normal = sal["income"] + hp_now + os_ + cg["stcg_other"] + biz["income"]   # ponytail: a house loss sets off against salary and other sources (cyla), not business yet
    vm = r.get("via_more") or {}
    via = engine.run("myreturn.deductions", {f: r["via"][f] for f in VIA if f != "c80gg"} | {
        "dd_nature": str(vm.get("dd_nature") or ""), "ddb_senior": vm.get("ddb_senior") is True,
        "regime": regime, "band": band, "gross_total": gti_normal, "basic_da": sum(e["basic_da"] for e in emps) or gross,   # ponytail: Form 16 rarely shows basic + DA; the employer kept 80CCD(2) inside it, so the salary stands in
        "parents_senior": bool(ans.get("parents_senior")), "savings_interest": o["savings"], "deposit_interest": o["deposits"],
        "disability": ans.get("disability") or "", "status": status, "resident": resident})
    # 80GG is worked out on the income left after every other deduction (chip myreturn.d80gg)
    gg = engine.run("myreturn.d80gg", {"rent": r["via"]["c80gg"], "ati": max(gti_normal - via["total"], 0), "regime": regime, "status": status,
                                       "has_hra": any(e.get("hra") for e in emps)})
    via = via | {"d80GG": gg, "total": min(via["total"] + gg, max(gti_normal, 0))}
    k = engine.run("myreturn.rates")
    normal = engine.run("compute.total_income", {"gti": gti_normal, "deductions": via["total"], "round_to": k["round_to"]})["income"]
    targs = {"normal": max(normal, 0), "stcg_111a": cg["stcg_111a"], "ltcg_112a": cg["ltcg_112a"],
             "ltcg_112": cg["ltcg_112"], "regime": regime, "band": band, "resident": resident,
             "status": status, "lottery": o["lottery"], "online_games": o["online_games"], "vda": vda["income"],
             "agri": _num(ans.get("agri")), "excess_112": cgw["excess"]}   # 2026-10-07: 30% winnings / VDA; agri for the rate; 112 indexation
    tax = engine.run("myreturn.tax", targs)
    # 2026-10-07: a tax audit (s.44AB) - out of My return (a CA's job); "above the basic exemption" on this regime's total income
    au = engine.run("myreturn.audit_44ab", {"pl": biz["pl"] is True, "profession": biz["profession"] is True, "turnover": biz["turnover"],
                                            "cash": _num(b.get("cash")), "net": biz["net"], "deemed": pres["deemed"],
                                            "presumptive_open": biz["presumptive_open"],
                                            "above_exemption": normal > _num((k["basic"].get(regime) or {}).get(band)),
                                            # 2026-10-08: the payments' cash share (both sides of the provisos) and s.44AD(4) / (5)
                                            "pay_total": _num(b.get("pay_total")), "pay_cash": -1 if b.get("pay_cash") in ("", None) else _num(b.get("pay_cash")),
                                            "ad_left": b.get("ad_left") == "yes", "ad_business": kind in ("44AD", "business"), "kind_44ad": kind == "44AD"})
    biz |= {"audit": au["audit"] is True, "audit_why": au["why"], "audit_limit": au["limit"], "ask_pay": au["ask_pay"] is True,
            "ad_closed": au["ad_closed"] is True}
    gti = gti_normal + cg["stcg_111a"] + cg["ltcg_112a"] + cg["ltcg_112"] + o["lottery"] + o["online_games"] + vda["income"]
    cy = engine.run("myreturn.cyla", {"hp": hp["net"], "salary": sal["income"], "os": os_})
    hp_cf = max(-_num(hp["loss"]), 0) - cy["used"]          # s.71(3A) / s.71B: a house loss not set off this year goes forward
    band_of = lambda y: engine.run("myreturn.age_band", {"age": _age(r["dob"], str(y + 1)), "status": status, "resident": resident}) if r.get("dob") else band  # noqa: E731
    rel = reliefs(r, {"houses": houses}, tax, sal["income"], status, band_of, targs)   # 2026-10-07: s.89 and s.90 / 90A / 91
    return {"regime": regime, "salary": sal | {"gross": gross}, "houses": houses, "hp": hp | {"bf": hp_bf, "after_bf": hp_now, "cf": max(hp_cf, 0)},
            "relief": rel, "net_tax": max(tax["tax"] - rel["total"], 0),
            "family_pension": fp, "other": os_, "gifts": gifts, "cg": cg, "cyla": cy,
            "gti": gti, "gti_pre_bf": gti + cgw["bf_used_total"] + hp_bf, "bf_used": cgw["bf_used_total"] + hp_bf,
            "gti_normal": gti_normal, "via": via, "normal": normal, "tax": tax, "business": biz, "vda": vda,
            "special": o["lottery"] + o["online_games"] + vda["income"]}


def work(cid: str, ay: str) -> dict:
    """The journey as it stands: documents, the merged return, both regimes, the checks, the form, the balance, the steps."""
    st = state(cid, ay)
    c = clients.get(cid)
    k = settings()
    r = merged(cid, ay)
    ans = (k["answer_defaults"] | (st.get("answers") or {}))
    dob = r["person"].get("dob") or c.get("dob") or ""
    status = "huf" if c.get("status") == "huf" else "individual"
    r["dob"] = dob
    # 2026-10-07 wave 3: the residential status first (s.6) - it decides which foreign income counts, the band, the rebate and the form;
    # a visitor's / citizen's 15 lakh test is on the income other than from foreign sources, worked out here when not typed
    res = residence_of(ans, status)
    if str(ans.get("indian_income") or "").strip() == "" and (ans.get("citizen") is True or ans.get("pio") is True) and res["known"]:
        apply_status(r, {"status": "NR"})
        b0 = engine.run("myreturn.age_band", {"age": _age(dob, ay), "status": status, "resident": False}) if dob else "below60"
        r["cgw"] = cg_work(r, False, ay)
        res = residence_of(ans, status, one_regime(r | {"res": {"resident": False}}, "new", b0, ans, status)["tax"]["total"])
    r["res"] = res
    apply_status(r, res)
    band = engine.run("myreturn.age_band", {"age": _age(dob, ay), "status": status, "resident": res["resident"]}) if dob else "below60"
    r["cgw"] = cgw = cg_work(r, res["resident"], ay)   # 2026-10-07: every sale, exemption and set-off, once
    both = {g: one_regime(r, g, band, ans, status) for g in ("new", "old")}
    tds = sum(_num(x.get("tds")) for x in r["tds"]) + sum(_num(x.get("tds")) for x in r["tds_194ia"])
    paid = sum(_num(x.get("amount")) for x in r["paid"])
    cg = both["new"]["cg"]
    gw = cgw["gain"]
    # the form first (it needs no dates): eligibility on the new regime's figures - ITR-1's 50 lakh leaves 112A gains out;
    # 112A gains up to 1.25 lakh stay in ITR-1 / ITR-4 only with no capital loss and no loss brought or carried forward
    losses = bool(ans.get("loss_cf") or any(_num(x.get("amount")) for x in r["losses_bf"]) or any(cgw["loss"].values())
                  or both["new"]["hp"]["cf"] > 0)
    ex = r["extra"]
    rr = engine.run("myreturn.res_rules")
    fa_on = res["status"] in rr["fa_for"] and bool(r["fa_rows"])
    form = engine.run("myreturn.form", {
        "resident": res["ordinary"] is True, "total": both["new"]["normal"] + cg["stcg_111a"] + cg["ltcg_112"], "houses": len(r["houses"]),
        "ltcg_112a": gw["ltcg_112a"], "other_cg": bool(gw["stcg_111a"] or gw["ltcg_112"] or gw["stcg_app"]),
        "agri": _num(ans.get("agri")), "director": bool(ans.get("director")), "unlisted": bool(ans.get("unlisted")),
        "foreign": bool(ans.get("foreign")) or fa_on or any(x["counts"] for x in ex["foreign"]),
        "clubbing": any(x["counts"] for x in ex["club"]), "loss_cf": losses, "other": False,
        "business": bool(r["business"]["kind"]), "over_limit": both["new"]["business"]["over_limit"] is True, "huf": status == "huf",
        "books": r["business"]["kind"] in k["pl_as"],
        "special": bool(both["new"]["special"])})
    # then the dates for THAT form, as of the day it was filed (the person says so) or today (chip close.dates)
    filed_on = str(ans.get("filed_on") or "")[:10]
    today = datetime.date.today().isoformat()
    dd = engine.run("close.dates", {"ay_year": int(ay[:4]), "audit": False, "tp": False, "form": form["form"],
                                    "filed_on": compute._ymd(filed_on or today), "today": compute._ymd(today),  # noqa: SLF001
                                    "has_current": False, "has_updated": False})
    late = dd["kind"] in k["late_kinds"]
    born = int(str(dob or "0").replace("-", "") or 0)
    exempt = engine.run("compute.no_advance", {"status": c["status"], "nri": res["resident"] is not True, "born": born,
                                               "fy_end": compute.year_day(ay, "end"), "has_business": bool(r["business"]["kind"])}) is True
    challans = [{"date": x.get("date", ""), "tax": _num(x.get("amount")), "gross": _num(x.get("amount")), "minor": str(x.get("minor") or "")}
                for x in r["paid"]]
    for g in both.values():
        fee = engine.run("chat.fee_234f", {"income": g["tax"]["total"]}) if late else 0
        g["fee_234f"] = fee if isinstance(fee, (int, float)) else 0
        g["interest"] = compute.interest_234(cid, ay, compute.settings(), g["net_tax"] - tds, challans, exempt,
                                             filed_on=compute._ymd(filed_on or today), due=dd["due"], due_rule=dd.get("due_rule", 0),  # noqa: SLF001
                                             presumptive=g["business"]["presumptive"] is True)   # 44AD / 44ADA: one instalment by 15 March (234C)
        g["tds"], g["paid"] = tds, paid
        g["balance"] = round(g["net_tax"] + g["fee_234f"] + g["interest"]["total"] - tds - paid)
    best = engine.run("myreturn.better", {g: both[g]["net_tax"] + both[g]["fee_234f"] + both[g]["interest"]["total"] for g in both})
    old_ok = dd["kind"] in k["old_regime_kinds"]          # 115BAC(6): the old regime is chosen in a return filed by the due date
    cgr = engine.run("myreturn.cg_rules")                  # s.80: a capital loss goes forward only from a return filed in time
    cgw["cf_ok"] = dd["kind"] in cgr["cf_kinds"]
    cgw["hp_cf_ok"] = cgw["cf_ok"] or cgr["hp_cf_any"] is True
    if not old_ok:
        best = {"better": "new", "saving": best["saving"] if best["better"] == "new" else 0, "old_closed": True}
    chosen = (st.get("regime") if old_ok or st.get("regime") == "new" else "") or best["better"]
    g = both[chosen]
    # 2026-10-07: a tax audit (s.44AB) or a business loss - not filed from My return; a CA (the CA-firm side) does it
    gb = g["business"]
    # 2026-10-08: 44AD chosen while s.44AD(4) keeps it closed; a business loss brought forward (from last year's ITR-3) - also a CA's job
    bl = round(sum(_num(x.get("amount")) for x in r.get("losses_bf_other") or []), 2)
    why_ca = gb["audit_why"] if gb.get("audit") else ("ca_loss" if gb.get("loss") is True else "ca_foreign_business" if ex["ca"]
                                                      else "ca_44ad_closed" if gb.get("ad_closed") else "ca_bf_business_loss" if bl else "")
    ca = {"why": why_ca, "receipts": gb["turnover"], "limit": gb.get("audit_limit", 0), "net": gb["net"], "deemed": gb["deemed"], "loss": bl} if why_ca else None
    checks = checks_of(st, r, chosen)
    fa_chk = engine.run("myreturn.check_fa", {"status": res["status"], "foreign_income": any(x["counts"] for x in ex["foreign"]),
                                              "flag": bool(ans.get("foreign")), "fa_rows": len(r["fa_rows"])})
    if fa_chk["level"] != "ok":                                # 2026-10-07: a resident with foreign income / assets lists them (Schedule FA)
        checks.append(fa_chk)
    if r["business"]["kind"] and r["business"]["gst_rows"]:    # 2026-10-08: the GST turnover beside the receipts of the return
        a, b = gb["turnover"] or gb.get("receipts", 0), r["business"]["gst_turnover"]
        checks.append(engine.run("myreturn.checks", {"what": "gst", "a": a, "b": b}) | {"field": "gst", "a": a, "b": b})
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
            "form": form, "checks": checks, "steps": steps, "step": st.get("step") or steps["now"], "dates": dd, "late": late, "ca_needed": ca,
            "filed_on": filed_on, "has_filed": any(d["kind"] == "filed" for d in st.get("docs") or []), "ready": st.get("ready") or [],
            "checklist": engine.run("myreturn.checklist"),
            "locked": clients.locked(cid, ay), "biz_codes": biz_codes() if r["business"]["kind"] else {},
            "res": res, "countries": countries(), "itru": itru_work(cid, ay, st, dob, status),
            "itru_years": [y for y in clients.settings()["years"] if y < ay], "itru_bars": engine.run("myreturn.itru_rules")["bars"]}


def itru_work(cid: str, ay: str, st: dict, dob: str, status: str) -> dict | None:
    """2026-10-07 wave 3: an updated return (s.139(8A)) for an earlier AY, from My return - that year's tax at that year's slabs (chip
    myreturn.arrear_row / tax_of_year: the income of the return before, then with the income added), the last day (chip close.dates
    updated_by), the bars, the interest and the additional tax (chip myreturn.itru, which asks chip close.itr_u for 140B's %), the late
    fee when no return was filed (chip chat.fee_234f). The department's ITR-U schema is not here: the computation and the steps only."""
    from core.ops import months_part  # noqa: PLC0415
    u = st.get("itru") or {}
    if not u.get("ay"):
        return None
    ayu, fy = u["ay"], int(u["ay"][:4]) - 1
    on = compute._ymd(u.get("on") or datetime.date.today().isoformat())  # noqa: SLF001
    band = engine.run("myreturn.age_band", {"age": _age(dob, ayu), "status": status}) if dob else "below60"
    reg = engine.run("myreturn.arrear_row", {"fy": fy, "regime": u.get("regime") or "", "band": band})["regime"]
    # 2026-10-08: that year's tax in full (chip myreturn.year_tax): slabs, its special rates, 87A, surcharge with marginal relief, cess -
    # the return before, then with the income added (normal and special-rate)
    sp0 = {v: _num(u.get(f"orig_{k2}")) for k2, v in ITRU_SPECIAL.items()}
    sp1 = {v: sp0[v] + _num(u.get(f"add_{k2}")) for k2, v in ITRU_SPECIAL.items()}
    yt = lambda normal, sp: engine.run("myreturn.year_tax", {"fy": fy, "regime": reg, "band": band, "normal": normal, "early": u.get("early") == "yes"} | sp)  # noqa: E731
    t0, t1 = yt(_num(u.get("orig_income")), sp0), yt(_num(u.get("orig_income")) + _num(u.get("added")), sp1)
    yr = {"regime": reg, "known": t0["known"], "over": False, "before": t0["tax"], "after": t1["tax"], "extra": t1["tax"] - t0["tax"]}
    # 234C (s.140B(2): the interest for any default in advance tax): the instalments short of the updated tax, less those short of the tax
    # before (chip compute.interest); the advance tax with no instalments typed is taken as paid by the last (chip myreturn.itru_rules c_default)
    ir = engine.run("myreturn.itru_rules")
    q = [_num(u.get(f"adv_q{n}")) for n in range(1, 5)]
    if not any(q) and _num(u.get("advance")):
        q[["jun", "sep", "dec", "mar"].index(ir["c_default"])] = _num(u.get("advance"))
    adv_by = [sum(q[: n + 1]) for n in range(4)]
    c_of = lambda tax, tds: engine.run("compute.interest", {"assessed": tax - tds, "adv_by": adv_by, "adv_total": adv_by[-1]})["c"]  # noqa: E731
    i234c = max(c_of(t1["tax"], _num(u.get("tds"))) - c_of(t0["tax"], _num(u.get("tds")) - _num(u.get("tds_added"))), 0) if yr["known"] else 0
    filed = (u.get("filed") or "none") != "none"
    dd = engine.run("close.dates", {"ay_year": int(ayu[:4]), "audit": False, "tp": False, "form": u.get("form") or "ITR-2", "filed_on": on, "today": on,
                                    "has_current": filed, "has_updated": "already_updated" in (u.get("bars") or [])})
    after_due = int((datetime.date(dd["due"] // 10000, dd["due"] // 100 % 100, dd["due"] % 100) + datetime.timedelta(days=1)).strftime("%Y%m%d"))
    extra = yr["extra"] - _num(u.get("tds_added"))
    bars = list(u.get("bars") or [])
    it = engine.run("myreturn.itru", {"known": yr["known"] is True and yr["over"] is not True,"filed_on": on, "updated_by": dd["updated_by"], "months": months_part(compute.year_day(ayu, "start", 1), on),
                                      "months_a": months_part(after_due, on), "months_b": months_part(compute.year_day(ayu, "start"), on),
                                      "extra_tax": extra, "tax_after": yr["after"], "tds": _num(u.get("tds")), "advance": adv_by[-1], "bars": bars, "i234c": i234c})
    fee = 0 if filed else engine.run("chat.fee_234f", {"income": t1["total"]})
    fee = fee if isinstance(fee, (int, float)) and it["ok"] else 0
    return u | it | {"fy": fy, "band": band, "regime_used": yr["regime"], "tax_before": yr["before"], "tax_after": yr["after"], "extra_tax": extra,
                     "updated_by": dd["updated_by"], "due": dd["due"], "fee_234f": fee, "pay": it["total"] + fee,
                     "income_after": t1["total"], "special_after": t1["total"] - _num(u.get("orig_income")) - _num(u.get("added")), "surcharge": t1["surcharge"], "schema": engine.run("myreturn.itru_rules")["schema_have"]}


def checks_of(st: dict, r: dict, regime: str = "new") -> list[dict]:
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
    # 2026-10-08: two employers (Form 16s of different TANs) - each took off the standard deduction / counted 80C (chip myreturn.check_employers)
    f16 = by_kind("form16")
    tans = {str(e.get("tan") or "").upper() for d in f16 for e in (d.get("facts") or {}).get("employers") or [] if e.get("tan")}
    if len(tans) >= 2:
        given = sum(_num((d.get("facts") or {}).get("via", {}).get(f)) for d in f16 for f in ("c80c", "c80ccc", "c80ccd1"))
        for part in ("std", "via"):
            c2 = engine.run("myreturn.check_employers", {"employers": len(tans), "regime": regime, "via_given": given, "part": part})
            if c2["level"] != "ok":
                out.append(c2 | {"field": c2["what"]})
    v = r["via"]
    if v["c80ee"] and v["c80eea"]:                              # 2026-10-07: 80EEA is not for one who claims 80EE
        out.append(engine.run("myreturn.check_80ee", {"c80ee": v["c80ee"], "c80eea": v["c80eea"]}))
    # 2026-10-07: the sales the AIS reports (SFT-017 / 018 securities and fund units; 194IA / SFT-012 property) beside the rows
    prop = engine.run("myreturn.cg_rules")["assets"]
    sold = lambda is_prop: round(sum(_num(x.get("sale")) for x in r.get("cg_rows") or [] if bool(prop.get(x.get("asset"), {}).get("property")) == is_prop), 2)  # noqa: E731
    for what, a, b in (("cg_sales", sold(False), r.get("sales_seen") or 0), ("property", sold(True), r.get("property_seen") or 0)):
        if b:
            out.append(engine.run("myreturn.checks", {"what": what, "a": a, "b": b}) | {"field": what, "a": a, "b": b})
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
    # 2026-10-07: the person's address - what they typed on Review, else the documents' (pre-filled JSON, AIS header), else the client's
    typed = str(ans.get("address") or "").strip()
    pins = lambda text: re.findall(r"\b[1-9][0-9]{5}\b", text or "")  # noqa: E731
    pin = re.sub(r"\D", "", str(ans.get("pin") or "")) or (pins(typed) or [""])[-1] or str(p.get("pin") or "") or (pins(c.get("address")) or [""])[-1]
    parts = [x.strip() for x in re.split(r",", re.sub(r"\b[1-9][0-9]{5}\b", "", typed or c.get("address") or "")) if x.strip()]
    if typed:                                                   # a typed address replaces the documents' lines, not just fills them
        p = {k2: v for k2, v in p.items() if k2 not in ("flat", "building", "road", "area", "city")}
    p = p | {k2: ans[k2] for k2 in ("city", "email", "state", "mobile") if str(ans.get(k2) or "").strip()}
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
    if i(g["gifts"]["total"]):                                     # 2026-10-07: gifts (s.56(2)(x)) - ITR-1 / ITR-4 "any other"
        os_rows.append({"code": js["gift_code"], "amount": i(g["gifts"]["total"]), "what": js["gift_words"]})
    b, gb, kb = r["business"], g["business"], engine.knobs("myreturn.business")
    pres = gb["presumptive"] is True                                # 2026-10-07: over the limit = the person's own P&L (ITR-3)
    ada, ad, aeq = pres and b["kind"] == "44ADA", pres and b["kind"] == "44AD", pres and b["kind"] == "44AE"
    code_key = {"44ADA": "CodeADA", "44AD": "CodeAD", "44AE": "CodeAE"}.get(b["kind"], "CodeAD")
    nature = [{"NameOfBusiness": b["name"] or c["name"], code_key: b["code"], "Description": dict(biz_codes().get(b["kind"], [])).get(b["code"], "")}] if b["kind"] else []
    ae_rows = [{"reg": x["reg"], "own": js["vehicle_own"].get(x["own"], x["own"]), "tons": i(x["tons"]), "months": int(x["months"]), "income": i(x["income"])}
               for x in gb.get("vehicles") or []] if aeq else []
    biz = {"income": i(gb["income"]), "nature_ada": nature if ada else [], "nature_ad": nature if ad else [], "nature_ae": nature if aeq else [],
           "ae_rows": ae_rows, "ae_income": i(gb["income"]) if aeq else 0,
           "ada_receipts": i(gb["receipts"]) if ada else 0, "ada_digital": i(b["digital"]) if ada else 0, "ada_cash": i(b["cash"]) if ada else 0,
           "ada_income": i(gb["income"]) if ada else 0, "ad_receipts": i(gb["receipts"]) if ad else 0, "ad_digital": i(b["digital"]) if ad else 0,
           "ad_cash": i(b["cash"]) if ad else 0, "ad_6": i(b["digital"] * kb["ad_digital_pct"] / 100) if ad else 0, "ad_8": i(b["cash"] * kb["ad_cash_pct"] / 100) if ad else 0,
           "ad_income": i(gb["income"]) if ad else 0, "gst_turnover": sum(i(x["turnover"]) for x in b["gst_rows"]),   # 2026-10-08: per GSTIN
           "gst_rows": [{"GSTINNo": x["gstin"], "AmtTurnGrossRcptGSTIN": i(x["turnover"])} for x in b["gst_rows"]]}
    # 2026-10-07 ITR-3: Part A-P&L 64 (no regular books - business, profession), Part A-BS, Schedule BP, Part A-GEN2 (chip itr.map ITR-3 myreturn)
    yn = js["yn"]
    own_pl, prf, inc = gb["pl"] is True, gb["profession"] is True, i(gb["income"])
    zero = {f: 0 for f in ("receipts", "bank", "other", "gp", "expenses", "np")}
    pl_row = {"receipts": i(gb["turnover"]), "bank": i(b["digital"]), "other": i(b["cash"]), "gp": i(b["gp"] or gb["net"] + b["expenses"]),
              "expenses": i(b["expenses"]), "np": max(i(gb["net"]), 0)}
    deemed = {"ad": inc if ad else 0, "ada": inc if ada else 0, "ae": inc if aeq else 0}
    words_pl = dict(biz_codes().get(b["kind"], [])) if own_pl else {}
    biz3 = deemed | {
        "has": yn[str(bool(b["kind"])).lower()], "books_44aa": yn[str(gb["liable_44aa"] is True).lower()], "declared_us": yn[str(pres).lower()],
        "nature_pl": [{"Code": b["code"], "TradeName1": (b["name"] or c["name"])[:75], "Description": words_pl.get(b["code"], "")[:75]}] if own_pl and b["code"] else [],
        "nb": pl_row if own_pl and not prf else zero, "nbp": pl_row if own_pl and prf else zero, "nb_total": pl_row["np"] if own_pl else 0,
        "bs": {f: i(b[f]) if own_pl else 0 for f in ("debtors", "creditors", "stock", "cash_in_hand")},
        "ae_months": sum(int(x["months"]) for x in gb.get("vehicles") or []) if aeq else 0,
        "pl_profit": max(inc, 0), "deemed": sum(deemed.values()), "balance": max(inc, 0) - sum(deemed.values()), "net": max(inc, 0)}
    vm, gv = r.get("via_more") or {}, g["via"]                    # the deduction schedules, only for what is claimed
    via_more = {"dd_nature": vm.get("dd_nature", "") if gv.get("d80DD") else "", "dd_type": (vm.get("dd_type") or "2") if gv.get("d80DD") else "",
                "dd_dependent": (vm.get("dd_dependent") or "1") if gv.get("d80DD") else "",
                "ddb_type": ("2" if vm.get("ddb_senior") else "1") if gv.get("d80DDB") else "", "stamp": i(vm.get("stamp")) if gv.get("d80EEA") else 0}
    loan = lambda sec, extra: ([{**{x: (i((vm.get(f"loan_{sec}") or {}).get(x)) if x in ("amount", "left") else (vm.get(f"loan_{sec}") or {}).get(x)) for x in LOAN}, "from": (vm.get(f"loan_{sec}") or {}).get("from") or "B",  # noqa: E731
                                 "interest": i(gv.get(f"d{sec.upper()}")), **extra}] if gv.get(f"d{sec.upper()}") else [])
    ggc_rows = [{"date": vm.get("ggc_date", ""), "amount": i(gv["d80GGC"]), "ref": vm.get("ggc_ref", ""), "ifsc": vm.get("ggc_ifsc", "").upper(),
                 "party": vm.get("ggc_party", ""), "pan": vm.get("ggc_pan", "").upper()}] if gv.get("d80GGC") else []
    hp_rows = []
    ex = r.get("extra") or {}
    emps_all = r["employers"] + (ex.get("employers") or [])          # 2026-10-07 wave 3: a foreign employer, a clubbed / foreign house
    for n, (h, x) in enumerate(zip(r["houses"] + (ex.get("houses") or []), g["houses"]), 1):
        hp_rows.append({"n": n, "address": (h.get("address") or (parts[0] if parts else ""))[:200] or "-",
                        "city": (h.get("city") or p.get("city") or (parts[-1] if parts else ""))[:50], "state": str(h.get("state") or p.get("state") or ans.get("state") or ""), "pin": int(pin) if pin.isdigit() and not h.get("zip") and not h.get("state") else "",
                        "country": h.get("country") or js["country_india"], "zip": h.get("zip") or None, "owner": h.get("owner") or js["owner_self"],
                        "let": "S" if h["kind"] == "self" else "L", "rent": i(h["rent"]), "municipal_tax": i(h["municipal_tax"]),
                        "balance": i(x["balance"]), "nav": i(x["nav"]), "std": i(x["std"]), "interest": i(x["interest"]), "deduct": i(x["std"] + x["interest"]), "net": i(x["net"]),
                        "share": _num(h.get("share") or 100), "co_flag": js["co_owned"][str(_num(h.get("share") or 100) < 100 or bool(h.get("co_owners"))).lower()],
                        "co_owners": [{"CoOwnersSNo": m2, "NameCoOwner": y["name"], **({"PAN_CoOwner": y["pan"]} if y.get("pan") else {}),
                                       "PercentShareProperty": _num(y.get("share"))} for m2, y in enumerate(h.get("co_owners") or [], 1)] or None})
    sec = lambda v: codes["sections"].get(re.sub(r"\s+", "", str(v or "")).upper(), codes["sections"].get(str(v or "")[:4].upper(), ""))  # noqa: E731
    tds_sal = [{"tan": x.get("tan", ""), "name": x.get("name", "") or x.get("tan", ""), "income": i(x.get("income")), "tds": i(x.get("tds"))}
               for x in r["tds"] if x.get("kind") == "salary"]
    tds_oth = [{"tan": x.get("tan", ""), "name": x.get("name", "") or x.get("tan", ""), "income": i(x.get("income")), "tds": i(x.get("tds")),
                "section": sec(x.get("section")), "year": str(int(ay[:4]) - 1), "year_n": int(ay[:4]) - 1,
                "head": js["tds_heads"]["business" if b["kind"] and re.sub(r"\s+", "", str(x.get("section") or "")).upper() in settings()["business_sections"] else "other"]}
               for x in r["tds"]
               if x.get("kind") != "salary" and sec(x.get("section")) not in js["tds3_sections"]]
    adv = sum(_num(x.get("amount")) for x in r["paid"] if engine.run("compute.paid_kind", {
        "minor": str(x.get("minor") or ""), "paid_on": compute._day(x.get("date")), "fy_end": compute.year_day(ay, "end")}) == "advance")  # noqa: SLF001
    t = g["tax"]
    # 2026-10-07: special-rate income - winnings (Schedule OS), virtual digital assets (Schedule VDA), every special rate (Schedule SI)
    names = [q2 for q2, _ in js["quarters"]]
    q_of = lambda day: _quarter(day, js)  # noqa: E731
    lq, gq = q_of(ans.get("lottery_on")), q_of(ans.get("games_on"))
    vda_rows = [{"acquired": _iso(x.get("acquired")), "transferred": _iso(x.get("transferred")), "head": js["vda_head"], "cost": i(x.get("cost")),
                 "sale": i(x.get("sale")), "income": i(y["income"])} for x, y in zip(r.get("vda") or [], g["vda"]["rows"])]
    vda_q = {q2: sum(x["income"] for x in vda_rows if q_of(x["transferred"]) == q2) for q2 in names}
    os_special = i(o["lottery"]) + i(o["online_games"])
    fin = g["cg"]                                                  # 2026-10-07: capital gains after every set-off (myreturn.cg_work)
    si_amt = {"stcg_111a": i(fin["stcg_111a"]), "ltcg_112a": i(max(fin["ltcg_112a"] - rates["exempt_112a"], 0)), "ltcg_112": i(fin["ltcg_112"]),
              "lottery": i(o["lottery"]), "online_games": i(o["online_games"]), "vda": i(g["vda"]["income"])}
    si_tax = {"stcg_111a": t["on_111a"], "ltcg_112a": t["on_112a"], "ltcg_112": t["on_112"], "lottery": t["on_115bb"], "online_games": t["on_115bbj"], "vda": t["on_115bbh"]}
    si_rows = [{"code": js["si_codes"][f][0], "rate": js["si_codes"][f][1], "income": si_amt[f], "tax": i(si_tax[f])} for f in js["si_codes"] if si_amt.get(f)]
    agri = i(ans.get("agri"))
    slab = i(t["on_normal"] + t["on_special"])
    rebate = i(t["rebate"] + t["relief_87a"])
    gross = i(slab - rebate + t["surcharge"] + t["cess"])
    interest = i(g["interest"]["total"] + g["fee_234f"])
    rl = {k2: i(g["relief"][k2]) for k2 in ("s89", "s90", "s91")}
    rl["total"] = min(sum(rl.values()), gross)
    net = gross - rl["total"]
    v = g["via"]
    banks = [{"ifsc": b.get("ifsc", ""), "bank": b.get("bank", ""), "account": b.get("account", ""),
              "type": codes["account_types"].get(str(b.get("type") or "").lower(), codes["default_account"]), "refund": "true" if n == 0 else "false"}
             for n, b in enumerate(r["banks"])]
    mobile = re.sub(r"\D", "", str(p.get("mobile") or c.get("phone") or ""))[-10:]
    w3 = wave3_facts(w, g, r, js, agri)
    return {
        "today": datetime.date.today().isoformat(), "ay_code": ay[:4], "form": w["form"]["form"], "ca_needed": w["ca_needed"],
        "sw_id": engine.run("itr.settings")["sw_id"], "sw_version": engine.run("itr.settings")["sw_version"],
        "client": {"status_code": js["status_codes"].get(c.get("status"), "I"), "capacity": js["capacity"].get(c.get("status"), "S"),
                   "signer_name": (ans.get("karta_name") if c.get("status") == "huf" else "") or p.get("name") or c["name"],
                   "signer_pan": (ans.get("karta_pan") or c.get("signer_pan") if c.get("status") == "huf" else "") or c["pan"], "name": p.get("name") or c["name"], "first": p.get("first") or " ".join(words[:-1]), "middle": p.get("middle") or "",
                   "surname": p.get("surname") or (words[-1] if words else ""), "pan": (p.get("pan") or c["pan"]).upper(),
                   "dob": p.get("dob") or c.get("dob") or ans.get("formed_on") or "", "flat": (p.get("flat") or (parts[0] if parts else ""))[:50],
                   "building": p.get("building", ""), "road": p.get("road", ""), "area": (p.get("area") or (parts[1] if len(parts) > 1 else "") or p.get("city") or (parts[-1] if parts else ""))[:50],
                   "city": (p.get("city") or (parts[-1] if len(parts) > 2 else ""))[:50], "state": str(p.get("state") or ans.get("state") or ""),
                   "pin": int(pin) if pin.isdigit() else "", "mobile": int(mobile) if mobile else "", "email": p.get("email") or c.get("email") or "",
                   "father": ans.get("father") or ""},
        "filing": {"section": codes["return_sec"].get(kind, 11), "due": _iso(w["dates"]["due"]), "due_rule": _iso(w["dates"].get("due_rule") or w["dates"]["due"]),
                   "orig_ack": "", "orig_date": "", "residential": w["res"]["code"], "employer_category": ans.get("employer_category") or (js["employer_default"] if r["employers"] else "NA")},
        "regime_opt_out": "Y" if w["regime"] == "old" else "N",
        "salary": {"gross": i(sal["gross"]), "s17_1": sum(i(e["gross_17_1"]) for e in emps_all), "s17_2": sum(i(e["perq_17_2"]) for e in emps_all),
                   "s17_3": sum(i(e["profit_17_3"]) for e in emps_all), "exempt": sum(x["amount"] for x in exempt_rows),
                   "net": i(sal["gross"]) - sum(x["amount"] for x in exempt_rows), "std": i(sal["std"]), "prof_tax": i(sal["prof_tax"]),
                   "d16": i(sal["std"] + sal["prof_tax"]), "income": i(sal["income"])},
        "exempt_rows": exempt_rows, "hp_rows": hp_rows, "hp": {"net": i(g["hp"]["net"])}, "biz": biz, "biz3": biz3, "ae_rows": ae_rows,
        "gst_rows3": [{"gstin": x["gstin"], "turnover": i(x["turnover"])} for x in b["gst_rows"]] if b["kind"] else [],   # 2026-10-08: ITR-3 Schedule GST
        "salary_rows": [{"name": e["name"] or "-", "category": e.get("category") or ans.get("employer_category") or js["employer_default"], "tan": e["tan"],
                         "address": (e.get("address") or (parts[0] if parts else "-"))[:200], "city": (e.get("city") or p.get("city") or (parts[-1] if parts else "-"))[:50],
                         "state": str(e.get("state") or p.get("state") or ans.get("state") or ""), "pin": int(e["pin"]) if str(e.get("pin") or "").isdigit() else "",
                         "zip": (e.get("zip") or None) if e.get("foreign") else None,
                         "gross": i(e["gross_17_1"] + e["perq_17_2"] + e["profit_17_3"]),
                         "s17_1": i(e["gross_17_1"]), "s17_2": i(e["perq_17_2"]), "s17_3": i(e["profit_17_3"])} for e in emps_all],
        "os": {"total": i(g["other"]), "fp_deduction": i(g["family_pension"]["deduction"]), "dividend": i(o["dividend"] + _num(ex.get("dividend"))),
               "interest": i(o["savings"] + o["deposits"] + o["refund_interest"] + _num(ex.get("interest"))), "savings": i(o["savings"]), "deposits": i(o["deposits"]),
               "interest_other": i(ex.get("interest")),
               "refund_interest": i(o["refund_interest"]), "family_pension": i(o["family_pension"]), "other": i(o["other"] + _num(ex.get("other"))),
               "gross": i(o["savings"] + o["deposits"] + o["refund_interest"] + o["dividend"] + o["family_pension"] + o["other"]) + i(g["gifts"]["total"])
               + i(ex.get("interest")) + i(ex.get("dividend")) + i(ex.get("other")),
               "gifts": {k2: i(g["gifts"][k2]) for k2 in ("money", "movable_free", "movable_less", "property_free", "property_less", "total")},
               "lottery": i(o["lottery"]), "online_games": i(o["online_games"]), "special": os_special, "all": i(g["other"]) + os_special}, "os_rows": os_rows,
        "lottery_q": {q2: i(o["lottery"]) if q2 == lq else 0 for q2 in names}, "games_q": {q2: i(o["online_games"]) if q2 == gq else 0 for q2 in names},
        "vda": {"income": i(g["vda"]["income"])}, "vda_rows": vda_rows, "vda_q": vda_q,
        "si_rows": si_rows, "si": {"income": sum(x["income"] for x in si_rows), "tax": sum(x["tax"] for x in si_rows)},
        "agri": {"net": agri, "gross": agri, "itr1": agri if agri <= rates["itr1_agri_max"] else 0},
        "agri_rows": [{"category": js["agri_category"], "amount": agri}] if agri else [],
        "gti_normal": i(g["gti_normal"]), "gti": i(g["gti"]),
        "cg": {k2: i(fin[k2]) for k2 in CG} | {"ltcg_all": i(fin["ltcg_112a"] + fin["ltcg_112"]), "short": i(fin["stcg_111a"] + fin["stcg_other"]),
                                                "total": i(sum(fin[k2] for k2 in CG)), "special": i(fin["stcg_111a"] + fin["ltcg_112a"] + fin["ltcg_112"]),
                                                "with_vda": i(sum(fin[k2] for k2 in CG)) + i(g["vda"]["income"]),
                                                "special_all": i(fin["stcg_111a"] + fin["ltcg_112a"] + fin["ltcg_112"]) + os_special + i(g["vda"]["income"])},
        **cg_facts(w, g, r, js, ay), "gti_pre_bf": i(g["gti_pre_bf"]),
        "total_gross": i(engine.run("compute.total_income", {"gti": g["gti"], "deductions": v["total"],    # rounded to 10 (section 288A)
                                                             "round_to": engine.run("myreturn.rates")["round_to"]})["income"]),
        "flags": {"unlisted": "Y" if ans.get("unlisted") else "N", "director": "Y" if ans.get("director") else "N",
                  "banks": "Y" if r["banks"] else "N", "foreign_word": "YES" if ans.get("foreign") or w3["fa_any"] else "NO"},
        **{k2: v for k2, v in w3.items() if k2 != "fa_any"},
        "via": {k2: i(v[k2]) for k2 in v}, "via_more": via_more, "loans_80ee": loan("80ee", {}), "loans_80eea": loan("80eea", {}),
        "loans_80eeb": loan("80eeb", {"vehicle": vm.get("vehicle", "")}), "ggc_rows": ggc_rows, "total_income": i(t["total"]),
        "cyla": (cy := {k2: i(x) for k2, x in g["cyla"].items()}),
        "heads": i(g["gti_pre_bf"]) + cy["loss"],   # PartB-TI TotalTI: the heads before the house loss is set off
        "d80d": {"total": i(v["d80D"]), "self": i(v["d80D_self"]) if w["band"] == "below60" else 0, "self_sr": 0 if w["band"] == "below60" else i(v["d80D_self"]),
                 "parents": 0 if ans.get("parents_senior") else i(v["d80D_parents"]), "parents_sr": i(v["d80D_parents"]) if ans.get("parents_senior") else 0,
                 "self_flag": ("N" if w["band"] == "below60" else "Y") if v["d80D"] else "", "parents_flag": ("Y" if ans.get("parents_senior") else "N") if v["d80D"] else ""},
        "tax2": {"slab": slab, "on_normal": i(t["on_normal"]), "on_special": i(t["on_special"]), "on_aggregate": i(t["on_aggregate"]),
                 "agri_rebate": i(t["on_aggregate"]) - i(t["on_normal"]), "rebate_all": rebate, "after_rebate": slab - rebate, "surcharge": i(t["surcharge"]), "cess": i(t["cess"]),
                 "gross": gross, "i234a": i(g["interest"]["a"]), "i234b": i(g["interest"]["b"]), "i234c": i(g["interest"]["c"]),
                 "fee_234f": i(g["fee_234f"]), "interest_fee": interest, "aggregate": net + interest,
                 "s89": rl["s89"], "s90": rl["s90"], "s91": rl["s91"], "relief": rl["total"], "net": net,          # 2026-10-07: relief u/s 89 / 90 / 91
                 "tds": i(g["tds"]), "advance": i(adv), "sat": i(g["paid"] - adv), "paid": i(g["paid"]), "paid_all": i(g["tds"] + g["paid"]),
                 "tds_salary": sum(x["tds"] for x in tds_sal), "tds_other": sum(x["tds"] for x in tds_oth),
                 "payable": max(net + interest - i(g["tds"] + g["paid"]), 0), "refund": max(i(g["tds"] + g["paid"]) - net - interest, 0)},
        "tds_salary": tds_sal, "tds_other": tds_oth,
        "paid_rows": [{"bsr": x.get("bsr", ""), "date": _iso(x.get("date")), "serial": int(re.sub(r"\D", "", str(x.get("challan") or "")) or 0),
                       "amount": i(x.get("amount"))} for x in r["paid"]],
        "bank_rows": banks}


def _spread(total: int, weights: dict, names: list, default: str) -> dict:
    """A figure laid out over the advance-tax periods in proportion to the gains made in each (Schedule CG Table F) - all in the
    first period when nothing says when."""
    out = {q: 0 for q in names}
    tw = sum(v for v in weights.values() if v > 0)
    if total <= 0:
        return out
    if not tw:
        out[default] = total
        return out
    for q in names:
        out[q] = int(total * max(weights.get(q, 0), 0) // tw)
    out[max(weights, key=lambda q: weights[q])] += total - sum(out.values())
    return out


def cg_facts(w: dict, g: dict, r: dict, js: dict, ay: str) -> dict:
    """What chip itr.map's ITR-2 capital-gain rows point at (2026-10-07): Schedule 112A per scrip, Schedule CG A (short-term: land /
    building, 111A, other assets) and B (long-term: land / building with both computations, 112A, other assets), Table D (54 / 54EC /
    54F), Table E (set-off of this year's losses), Table F (when the gains were made), CYLA / BFLA, Schedule CFL and Schedule TDS3
    (194IA). Python lays out the figures chip myreturn.cg_work worked out - no rule here."""
    i = lambda v: int(round(_num(v)))  # noqa: E731
    cgw, ans, p = r["cgw"], w["answers"], r["person"]
    rows, typed, codes = cgw["rows"], typed_cg(r), engine.run("itr.codes")
    names = [q for q, _ in js["quarters"]]
    base = int(engine.run("myreturn.cg_rules")["cii_base_year"])
    of = lambda b, prop: [x for x in rows if x["bucket"] == b and bool(x["property"]) == prop]  # noqa: E731

    def agg(xs: list, t: float = 0.0) -> dict:
        sale, cost = i(sum(x["consideration"] for x in xs) + max(t, 0)), i(sum(x["cost_used"] for x in xs) + max(-t, 0))
        imp, exp = i(sum(_num(x.get("improve")) for x in xs)), i(sum(_num(x.get("expenses")) for x in xs))
        f54 = i(sum((x.get("ex_by") or {}).get("54F", 0) for x in xs))
        return {"sale": sale, "cost": cost, "improve": imp, "expenses": exp, "dedn": cost + imp + exp, "balance": sale - cost - imp - exp, "f54": f54,
                "gain": sale - cost - imp - exp - f54, "n": len(xs) + (1 if t else 0)}
    sec48 = lambda a: {"AquisitCost": a["cost"], "ImproveCost": a["improve"], "ExpOnTrans": a["expenses"], "TotalDedn": a["dedn"]}  # noqa: E731
    state = str(p.get("state") or ans.get("state") or "")

    def buyers(x: dict) -> dict | None:
        if not x.get("buyer") or not (x.get("state") or state):   # the buyer's block needs the property's state
            return None
        pin = str(x.get("pin") or "")
        one = {"NameOfBuyer": x["buyer"][:125], "PercentageShare": _num(x.get("buyer_share")) or 100, "Amount": i(x["consideration"] * (_num(x.get("buyer_share")) or 100) / 100),
               "AddressOfProperty": (x.get("address") or "-")[:250], "StateCode": str(x.get("state") or state), "CountryCode": js["country_india"]}
        one |= {"PANofBuyer": x["buyer_pan"]} if x.get("buyer_pan") else {}
        one |= {"PinCode": int(pin)} if re.fullmatch(r"[1-9][0-9]{5}", pin) else {}
        return {"TrnsfImmblPrprtyDtls": [one]}
    fy_label = lambda day: (lambda y: f"{y}-{(y + 1) % 100:02d}")(max(int(engine.run("myreturn.fy_of", {"date": day}) or base), base))  # noqa: E731
    # Schedule CG A - short-term
    st_prop = [{"DateofPurchase": x.get("acquired") or None, "DateofSale": x.get("sold") or None, "FullConsideration": i(x.get("sale")), "PropertyValuation": i(x.get("stamp")),
                "FullConsideration50C": i(x["consideration"]), "AquisitCost": i(x["cost_used"]), "ImproveCost": i(x.get("improve")), "ExpOnTrans": i(x.get("expenses")),
                "TotalDedn": i(x["cost_used"]) + i(x.get("improve")) + i(x.get("expenses")), "Balance": i(x["gain"]), "DeductionUs54B": 0, "STCGonImmvblPrprty": i(x["final"]),
                "TrnsfImmblPrprty": buyers(x)} for x in of("stcg_app", True)]
    a111 = agg(of("stcg_111a", False), _num(typed.get("stcg_111a")))
    aoth = agg(of("stcg_app", False), _num(typed.get("stcg_other")))
    mf = [{"code": js["mf_111a_code"], "dtls": {"FullConsideration": a111["sale"], "DeductSec48": sec48(a111), "BalanceCG": a111["balance"], "LossSec94of7Or94of8": 0,
                                                "CapgainonAssets": a111["balance"]}}] if a111["n"] else []
    other_st = {"FullValueConsdRecvUnqshr": 0, "FairMrktValueUnqshr": 0, "FullValueConsdSec50CA": 0, "FullValueConsdOthUnqshr": aoth["sale"], "FullConsideration": aoth["sale"],
                "DeductSec48": sec48(aoth), "BalanceCG": aoth["balance"], "LossSec94of7Or94of8": 0, "CapgainonAssets": aoth["balance"]}
    total_st = a111["balance"] + aoth["balance"] + sum(x["STCGonImmvblPrprty"] for x in st_prop)
    # Schedule CG B - long-term: land / building with both computations, 112A per scrip, other assets
    lt_prop = []
    for x in of("ltcg_112", True):
        ix = bool(x["index_ok"])
        imp = [{"slno": 1, "ImproveCost": i(x.get("improve")), "ImproveDate": fy_label(x.get("improve_on") or x.get("acquired")),
                "CostOfImpIndex": i(x["improve_indexed"])}] if i(x.get("improve")) else []
        exs = [{"ExemptionSecCode": kd, "ExemptionAmount": i(v)} for kd, v in (x.get("ex_by") or {}).items() if i(v)]
        lt_prop.append({"FullConsideration": i(x.get("sale")), "DateofPurchase": x.get("acquired") or None, "DateofSale": x.get("sold") or None,
                        "PropertyValuation": i(x.get("stamp")), "FullConsideration50C": i(x["consideration"]), "AquisitCost": i(x["cost_used"]),
                        "AquisitCostIndex": i(x["cost_indexed"]) if ix else 0,
                        "CostOfImprovements": {"CostOfImprovementsDtls": imp, "TotalImprovecost": i(x.get("improve")), "TotalindexImprovecost": i(x["improve_indexed"]) if ix else 0} if imp else None,
                        "ExpOnTrans": i(x.get("expenses")), "TotalDedn": i(x["cost_used"]) + i(x.get("improve")) + i(x.get("expenses")),
                        "TotalDednForEiB": i(x["cost_indexed"]) + i(x["improve_indexed"]) + i(x.get("expenses")) if ix else None,
                        "Balance": i(x["gain"]), "BalanceForEiB": max(i(x["gain_indexed"]), 0) if ix else None,
                        "ExemptionOrDednUs54": {"ExemptionOrDednUs54Dtls": exs, "ExemptionGrandTotal": sum(e["ExemptionAmount"] for e in exs)},
                        "LTCGonImmvblPrprty": i(x["final"]), "LTCGonImmvblPrprtyBE": i(x["final_indexed"]) if ix else None,
                        "TaxSec1121aiiB": i(x["tax_indexed"]) if ix else None, "TaxSec1121a": i(x["tax_plain"]) if ix else None,
                        "ExcessAmtSec1121a": i(x["excess"]) if ix else None, "TrnsfImmblPrprty": buyers(x)})
    sh = js["share_before"]
    s112a = []
    for x in of("ltcg_112a", False):
        units, gf = _num(x.get("units")), bool(x["grandfathered"])
        sale, cost_used, exp = i(x["consideration"]), i(x["cost_used"]), i(x.get("expenses"))
        one = {"ShareOnOrBefore": sh[str(gf).lower()], "ISINCode": x.get("isin") or js["isin_none"], "ShareUnitName": (x.get("name") or "-")[:125],
               "TotSaleValue": sale, "CostAcqWithoutIndx": cost_used, "AcquisitionCost": i(x.get("cost")),
               "LTCGBeforelowerB1B2": min(i(x.get("fmv")), sale) if gf else 0, "FairMktValuePerShareunit": round(_num(x.get("fmv")) / units, 2) if gf and units else 0,
               "TotFairMktValueCapAst": i(x.get("fmv")) if gf else 0, "ExpExclCnctTransfer": exp, "TotalDeductions": cost_used + exp, "Balance": sale - cost_used - exp}
        one |= {"NumSharesUnits": units, "SalePricePerShareUnit": round(sale / units, 4)} if units else {}
        s112a.append(one)
    t112a = _num(typed.get("ltcg_112a"))
    if t112a:                                                       # a total typed on Review: one line, the department's "no ISIN"
        s112a.append({"ShareOnOrBefore": sh["false"], "ISINCode": js["isin_none"], "ShareUnitName": js["typed_name"], "TotSaleValue": max(i(t112a), 0),
                      "CostAcqWithoutIndx": max(-i(t112a), 0), "AcquisitionCost": max(-i(t112a), 0), "LTCGBeforelowerB1B2": 0, "FairMktValuePerShareunit": 0,
                      "TotFairMktValueCapAst": 0, "ExpExclCnctTransfer": 0, "TotalDeductions": max(-i(t112a), 0), "Balance": i(t112a)})
    tot = lambda f: sum(_num(x.get(f)) for x in s112a)  # noqa: E731
    s112a_tot = {"SaleValue112A": i(tot("TotSaleValue")), "CostAcqWithoutIndx112A": i(tot("CostAcqWithoutIndx")), "AcquisitionCost112A": i(tot("AcquisitionCost")),
                 "LTCGBeforelowerB1B2112A": i(tot("LTCGBeforelowerB1B2")), "FairMktValueCapAst112A": i(tot("TotFairMktValueCapAst")),
                 "ExpExclCnctTransfer112A": i(tot("ExpExclCnctTransfer")), "Deductions112A": i(tot("TotalDeductions")), "Balance112A": i(tot("Balance")), "TotalBalance112A": i(tot("Balance"))}
    f54_112a = i(sum((x.get("ex_by") or {}).get("54F", 0) for x in of("ltcg_112a", False)))
    eq112a = {"BalanceCG": s112a_tot["Balance112A"], "DeductionUs54F": f54_112a, "CapgainonAssets": s112a_tot["Balance112A"] - f54_112a}
    ana = agg(of("ltcg_112", False), _num(typed.get("ltcg_112")))
    na = {"FullValueConsdRecvUnqshr": 0, "FairMrktValueUnqshr": 0, "FullValueConsdSec50CA": 0, "FullValueConsdOthUnqshr": ana["sale"], "FullConsideration": ana["sale"],
          "DeductSec48": sec48(ana), "BalanceCG": ana["balance"], "DeductionUs54F": ana["f54"], "CapgainonAssets": ana["gain"]}
    total_lt = sum(x["LTCGonImmvblPrprty"] for x in lt_prop) + eq112a["CapgainonAssets"] + na["CapgainonAssets"]
    # Table D - the exemptions claimed
    claims = {"54": [], "54EC": [], "54F": []}
    for x in rows:
        for cl in x.get("claims") or []:                           # 2026-10-08: each claim on the sale, by its own section
            if not i(cl["amount"]) or cl.get("ex_kind") not in claims:
                continue
            base_ = {"DateofTransfer": x.get("sold") or None, "AmtDeducted": i(cl["amount"])}
            if cl["ex_kind"] == "54EC":
                claims["54EC"].append(base_ | {"AmtInvested": i(cl.get("ex_amount")), "DateofInvestment": cl.get("ex_on") or None})
            else:
                claims[cl["ex_kind"]].append(base_ | {"CostofNewResHouse": i(cl.get("ex_amount")), "DateofPurchase": cl.get("ex_on") or None,
                                                       "AmtDeposited": i(cl.get("cgas")), "DepositDate": cl.get("cgas_on") or None,
                                                       "AccountNo": (cl.get("cgas_acc") or None), "IFSC": (cl.get("cgas_ifsc") or None)})
    claims = {k2: [{f: v for f, v in c.items() if v is not None} for c in v2] for k2, v2 in claims.items()}
    # Table E - this year's losses set off; Table F - when the gains were made
    wn, pre, fin, cr, left = cgw["within"], cgw["pre_bf"], cgw["final"], cgw["cross"], cgw["left"]
    c_ = lambda a, b: i(cr.get(f"{a}>{b}", 0))  # noqa: E731
    l20, lapp = i(left["stcg_111a"]) + c_("stcg_111a", "used"), i(left["stcg_app"]) + c_("stcg_app", "used")
    z = {"StclSetoff20Per": 0, "StclSetoff30Per": 0, "StclSetoffAppRate": 0, "StclSetoffDTAARate": 0}
    table_e = {
        "InLossSetOff": z | {"StclSetoff20Per": l20, "StclSetoffAppRate": lapp, "LtclSetOff12_5Per": i(cgw["ltcl"]), "LtclSetOffDTAARate": 0},
        "InStcg20Per": {k2: v for k2, v in z.items() if k2 != "StclSetoff20Per"} | {"CurrYearIncome": i(wn["stcg_111a"]), "StclSetoffAppRate": c_("stcg_app", "stcg_111a"), "CurrYrCapGain": i(pre["stcg_111a"])},
        "InStcg30Per": {k2: v for k2, v in z.items() if k2 != "StclSetoff30Per"} | {"CurrYearIncome": 0, "CurrYrCapGain": 0},
        "InStcgAppRate": {k2: v for k2, v in z.items() if k2 != "StclSetoffAppRate"} | {"CurrYearIncome": i(wn["stcg_app"]), "StclSetoff20Per": c_("stcg_111a", "stcg_app"), "CurrYrCapGain": i(pre["stcg_app"])},
        "InStcgDTAARate": {k2: v for k2, v in z.items() if k2 != "StclSetoffDTAARate"} | {"CurrYearIncome": 0, "CurrYrCapGain": 0},
        "InLtcg12_5Per": z | {"CurrYearIncome": i(wn["ltcg_112"] + wn["ltcg_112a"]), "StclSetoff20Per": c_("stcg_111a", "ltcg_112") + c_("stcg_111a", "ltcg_112a"),
                              "StclSetoffAppRate": c_("stcg_app", "ltcg_112") + c_("stcg_app", "ltcg_112a"), "LtclSetOffDTAARate": 0, "CurrYrCapGain": i(pre["ltcg_112"] + pre["ltcg_112a"])},
        "InLtcgDTAARate": z | {"CurrYearIncome": 0, "LtclSetOff12_5Per": 0, "CurrYrCapGain": 0},
        "TotLossSetOff": z | {"StclSetoff20Per": c_("stcg_111a", "used"), "StclSetoffAppRate": c_("stcg_app", "used"), "LtclSetOff12_5Per": 0, "LtclSetOffDTAARate": 0},
        "LossRemainSetOff": z | {"StclSetoff20Per": i(left["stcg_111a"]), "StclSetoffAppRate": i(left["stcg_app"]), "LtclSetOff12_5Per": i(cgw["ltcl"]), "LtclSetOffDTAARate": 0}}
    wq = lambda bs: {q: sum(max(x["final"], 0) for x in rows if x["bucket"] in bs and _quarter(x.get("sold"), js) == q) for q in names}  # noqa: E731
    q20, qapp, qlt = wq({"stcg_111a"}), wq({"stcg_app"}), wq({"ltcg_112", "ltcg_112a"})
    for qq, t in ((q20, typed.get("stcg_111a")), (qapp, typed.get("stcg_other")), (qlt, _num(typed.get("ltcg_112")) + _num(typed.get("ltcg_112a")))):
        qq[js["quarter_default"]] += max(_num(t), 0)
    dq = js["quarter_default"]
    # Schedule CFL - the losses brought forward by year, what set off this year, this year's own loss going forward
    life, kinds = [x for x in cgw["life"] if x["usable"]], ("stcl", "ltcl", "hp")
    fld = js["cfl_fields"]
    cfl, bf = {}, {kd: sum(_num(x.get("amount")) for x in life if x["kind"] == kd) for kd in kinds}
    for n, blk in enumerate(js["cfl_blocks"], 1):
        xs = [x for x in life if x["age"] == n]
        if xs:
            day = next((x["filed_on"] for x in xs if x.get("filed_on")), "") or f"{int(ay[:4]) - n}-{js['cfl_date_default']}"
            cfl[blk] = {js["cfl_detail"]: {js["cfl_date"]: day} | {fld[kd]: i(sum(_num(x.get("amount")) for x in xs if x["kind"] == kd)) for kd in kinds}}
    adj = {"stcl": cgw["bf_avail"]["stcl"] - cgw["bf_left"]["stcl"], "ltcl": cgw["bf_avail"]["ltcl"] - cgw["bf_left"]["ltcl"], "hp": g["hp"]["bf"]}
    cur = {"stcl": cgw["cf"]["stcl"] if cgw.get("cf_ok", True) else 0, "ltcl": cgw["cf"]["ltcl"] if cgw.get("cf_ok", True) else 0,
           "hp": g["hp"]["cf"] if cgw.get("hp_cf_ok", True) else 0}
    # 2026-10-07 ITR-3: the earlier years' blocks are named by their AY, the summaries carry the business-loss columns (nil here)
    as3 = dict(zip(js["cfl_blocks"], js["cfl_blocks_itr3"]))
    cfl3 = {as3[k2]: v for k2, v in cfl.items() if k2 in as3}
    summ = lambda d, more=(): {js["cfl_summary"]: {fld[kd]: i(d[kd]) for kd in kinds} | {f: 0 for f in more}}  # noqa: E731
    any_loss = any(bf.values()) or any(cur.values())
    tot = {kd: bf[kd] - adj[kd] + cur[kd] for kd in kinds}
    cfl |= {js["cfl_bf_total"]: summ(bf), js["cfl_adjusted"]: summ(adj), js["cfl_current"]: summ(cur), js["cfl_total"]: summ(tot)}
    z3 = js["cfl_summary_zero_itr3"]
    cfl3 |= {js["cfl_bf_total"]: summ(bf, z3), js["cfl_adjusted"]: summ(adj, z3), js["cfl_current"]: summ(cur, z3), js["cfl_total"]: summ(tot, z3)}
    sec = lambda v: codes["sections"].get(re.sub(r"\s+", "", str(v or "")).upper(), "")  # noqa: E731
    pan_ok = lambda v: bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", str(v or "")))  # noqa: E731
    tds3 = [{"pan": x.get("pan"), "section": sec(x.get("section")), "tds": i(x.get("tds")), "income": i(x.get("income")), "head": js["tds3_head"]}
            for x in r["tds_194ia"] if pan_ok(x.get("pan")) and i(x.get("tds"))]
    tds3 += [{"pan": x.get("tan"), "section": sec(x.get("section")), "tds": i(x.get("tds")), "income": i(x.get("income")), "head": js["tds3_head"]}
             for x in r["tds"] if sec(x.get("section")) in js["tds3_sections"] and pan_ok(x.get("tan"))]
    hp_pos = max(i(g["hp"]["net"]), 0)
    if not cgw["any"]:                                             # no capital gain: Schedule CG stays out (a VDA alone seeds its own)
        mf, other_st, na, eq112a, table_e = [], None, None, None, None
    # 2026-10-07 ITR-3's Schedule CG: the gain of each block as CapgainonAssets, every block with its own exemption table
    ex = lambda rows_: {"ExemptionOrDednUs54Dtls": rows_, "ExemptionGrandTotal": sum(x["ExemptionAmount"] for x in rows_)}  # noqa: E731
    st3 = [{k2: v for k2, v in x.items() if k2 not in ("DeductionUs54B", "STCGonImmvblPrprty") and v is not None}
           | {"ExemptionOrDednUs54": ex([]), "CapgainonAssets": x["STCGonImmvblPrprty"]} for x in st_prop]
    lt3 = [{k2: v for k2, v in x.items() if k2 not in ("LTCGonImmvblPrprty", "LTCGonImmvblPrprtyBE") and v is not None}
           | {f: x.get(f) or 0 for f in ("TotalDednForEiB", "BalanceForEiB", "TaxSec1121aiiB", "TaxSec1121a", "ExcessAmtSec1121a", "AquisitCostIndex")}
           | {"CapgainonAssets": x["LTCGonImmvblPrprty"], "CapgainonAssets_1ea": x.get("LTCGonImmvblPrprtyBE") or 0} for x in lt_prop]
    other_st3 = other_st and other_st | {"DeemedStcgOnAssets": 0, "ExemptionOrDednUs54": ex([])}
    na3 = na and {k2: v for k2, v in na.items() if k2 != "DeductionUs54F"} | {
        "ExemptionOrDednUs54": ex([{"ExemptionSecCode": js["code_54f"], "ExemptionAmount": na["DeductionUs54F"]}] if na["DeductionUs54F"] else [])}
    return {
        "cg3_st_prop": st3, "cg3_lt_prop": lt3, "cg3_st_other": other_st3, "cg3_na": na3, "cfl3": cfl3 if any_loss else None,
        "cg112a_rows": s112a, "s112a": s112a_tot, "cg_eq112a": eq112a, "cg_mf111a": mf, "cg_st_other": other_st, "cg_na": na,
        "cg_st_prop": [{k2: v for k2, v in x.items() if v is not None} for x in st_prop], "cg_lt_prop": [{k2: v for k2, v in x.items() if v is not None} for x in lt_prop],
        "cg_claims54": claims["54"], "cg_claims54ec": claims["54EC"], "cg_claims54f": claims["54F"],
        "cg_table_e": table_e, "cg_q20": {"DateRange": _spread(i(fin["stcg_111a"]), q20, names, dq)} if cgw["any"] else None,
        "cg_qapp": {"DateRange": _spread(i(fin["stcg_app"]), qapp, names, dq)} if cgw["any"] else None,
        "cg_qlt": {"DateRange": _spread(i(fin["ltcg_112"] + fin["ltcg_112a"]), qlt, names, dq)} if cgw["any"] else None,
        "cgx": {"total_st": total_st, "total_lt": total_lt, "lt_prop": sum(x["LTCGonImmvblPrprty"] for x in lt_prop), "excess": i(sum(_num(x.get("ExcessAmtSec1121a")) for x in lt_prop)),
                "claims": sum(c["AmtDeducted"] for v2 in claims.values() for c in v2),
                "s20_pre": i(pre["stcg_111a"]), "app_pre": i(pre["stcg_app"]), "lt_pre": i(pre["ltcg_112"] + pre["ltcg_112a"]),
                "short_pre": i(pre["stcg_111a"]) + i(pre["stcg_app"]), "sum_pre": i(pre["stcg_111a"]) + i(pre["stcg_app"]) + i(pre["ltcg_112"] + pre["ltcg_112a"]),
                "with_vda_pre": i(pre["stcg_111a"]) + i(pre["stcg_app"]) + i(pre["ltcg_112"] + pre["ltcg_112a"]) + i(g["vda"]["income"]),
                "s20": i(fin["stcg_111a"]), "app": i(fin["stcg_app"]), "lt": i(fin["ltcg_112"] + fin["ltcg_112a"]),
                "bf_s20": i(cgw["bf_used"]["stcg_111a"]), "bf_app": i(cgw["bf_used"]["stcg_app"]), "bf_lt": i(cgw["bf_used"]["ltcg_112"] + cgw["bf_used"]["ltcg_112a"]),
                "bf_all": i(g["bf_used"]), "hp_pos": hp_pos, "hp_bf": i(g["hp"]["bf"]), "hp_after": hp_pos - i(g["hp"]["bf"]),
                "cf_now": i(sum(cur.values())), "any": bool(cgw["any"]), "rows": len(rows)},
        "cfl": cfl if any_loss else None, "tds3_rows": tds3, "tds3": {"total": sum(x["tds"] for x in tds3)}}


def wave3_facts(w: dict, g: dict, r: dict, js: dict, agri: int) -> dict:
    """What chip itr.map's wave-3 rows point at (2026-10-07): FilingStatus (residential status, the condition, the days, the country of
    residence and TIN of a non-resident, 115H), Schedule FSI / TR (per country and head - myreturn.reliefs worked them out), Schedule FA
    (each foreign asset, by kind - chip myreturn.json fa_kinds names the department's fields), Schedule SPI (whose income is clubbed),
    Schedule EI (the s.10(32) exemption). Python lays the figures out - no rule here."""
    i = lambda v: int(round(_num(v)))  # noqa: E731
    res, ans, ex, rel = w["res"], w["answers"], r.get("extra") or {}, g["relief"]
    rr = engine.run("myreturn.res_rules")
    names = dict(countries())
    cname = lambda c: (names.get(c) or c or "-")[:55]  # noqa: E731
    days = lambda q, most: (min(max(i(ans.get(q)), 0), most) if str(ans.get(q) or "").strip() != "" else None)  # noqa: E731
    juris = [{"code": ans.get("res_country"), "tin": (ans.get("res_tin") or js["tin_none"])[:75]}] if res["status"] == "NR" and ans.get("res_country") else []
    out = {"res": {"condition": res["condition"], "days_fy": days("days_fy", 365), "days_4y": days("days_4y", 1461), "juris": juris,
                   "h115": js["h115_no"] if res["resident"] else ""}}
    blocks, blocks3 = js["fsi_blocks"], js["fsi_blocks_itr3"]
    fsi, fsi3, tr = [], [], []
    for c in rel["fsi"] if res["status"] in rr["fsi_for"] else []:
        zero = {"IncFrmOutsideInd": 0, "TaxPaidOutsideInd": 0, "TaxPayableinInd": 0, "TaxReliefinInd": 0}
        one = {}
        for blk in blocks3:
            b = c["blocks"].get(blk)
            one[blk] = dict(zero) if not b else {"IncFrmOutsideInd": max(i(b["income"]), 0), "TaxPaidOutsideInd": i(b["paid"]), "TaxPayableinInd": i(b["indian"]),
                                                  "TaxReliefinInd": i(b["relief"])} | ({"DTAAReliefUs90or90A": b["article"][:16]} if b.get("article") else {})
        tot = {f: sum(one[blk][f] for blk in blocks3) for f in zero}
        head = {"CountryName": cname(c["country"]), "CountryCodeExcludingIndia": c["country"], "TaxIdentificationNo": (c["tin"] or js["tin_none"])[:75]}
        fsi.append(head | {blk: one[blk] for blk in blocks} | {"TotalCountryWise": {f: sum(one[blk][f] for blk in blocks) for f in zero}})
        fsi3.append(head | one | {"TotalCountryWise": tot})
        if tot["TaxPaidOutsideInd"]:
            tr.append(head | {"TaxPaidOutsideIndia": tot["TaxPaidOutsideInd"], "TaxReliefOutsideIndia": tot["TaxReliefinInd"],
                              "ReliefClaimedUsSection": c["sec"] or engine.run("myreturn.foreign_rules")["relief_secs"][0]})
    dtaa = set(engine.run("myreturn.foreign_rules")["dtaa_secs"])
    out |= {"fsi_rows": fsi, "fsi_rows3": fsi3, "tr_rows": tr,
            "tr": {"paid": sum(x["TaxPaidOutsideIndia"] for x in tr), "relief": sum(x["TaxReliefOutsideIndia"] for x in tr),
                   "dtaa": sum(x["TaxReliefOutsideIndia"] for x in tr if x["ReliefClaimedUsSection"] in dtaa),
                   "not_dtaa": sum(x["TaxReliefOutsideIndia"] for x in tr if x["ReliefClaimedUsSection"] not in dtaa), "flag": js["tr_refunded_no"] if tr else ""}}
    # Schedule FA - a resident and ordinarily resident's foreign assets, each kind in its own table
    fa_on = res["status"] in rr["fa_for"]
    kinds, dflt = js["fa_kinds"], js["fa_defaults"]
    for kind, spec in kinds.items():
        rows_ = []
        for x in (r.get("fa_rows") or []) if fa_on else []:
            if x.get("kind") != kind:
                continue
            one = {"CountryName": cname(x.get("country")), "CountryCodeExcludingIndia": x.get("country") or dflt["country"]}
            x = dict(x, flag=js["yn"][str(bool(_num(x.get("taxed")))).lower()])   # 2026-10-08 D-F: taxable and offered in this return - Y / N
            for field, src in spec["map"].items():
                v = x.get(src)
                one[field] = i(v) if src in FA_NUM else (str(v).strip() if str(v or "").strip() else (spec.get("defaults") or {}).get(src) or dflt.get(src, dflt["text"]))
                one[field] = ((spec.get("values") or {}).get(src) or {}).get(one[field], one[field])   # 2026-10-10: OWNER / DIRECT as the table takes it
            rows_.append(one)
        out[f"fa_{kind}"] = rows_
    out["fa_any"] = fa_on and bool(r.get("fa_rows"))
    # Schedule SPI - whose income is clubbed; Schedule EI - the minor's 1,500 (s.10(32))
    hs = g["houses"]
    words = js["club_words"]
    out["spi_rows"] = [{"SpecifiedPersonName": (x.get("name") or "-")[:125], **({"PANofSpecPerson": x["pan"]} if x.get("pan") else {}),
                        "ReltnShip": words.get(x["relation"], x["relation"])[:50],
                        "AmtIncluded": i(hs[x["house_i"]]["net"]) if x.get("house_i") is not None else i(x["included"]), "HeadIncIncluded": x["spi"]}
                       for x in ex.get("club") or [] if x["counts"]]
    cat, sub = engine.run("myreturn.club_rules")["ei_category"]
    e1032 = i(ex.get("exempt_10_32"))
    out["ei"] = {"others": e1032, "total": agri + e1032}
    out["ei_rows"] = [{"Category": cat, "SubCategory": sub, "OthAmount": e1032}] if e1032 else []
    out["res_juris"] = juris
    return out


def _quarter(day, js: dict) -> str:
    """The advance-tax period a day falls in (chip myreturn.json quarters: 15 June, 15 September, 15 December, 15 March, 31 March)."""
    d = _iso(day)
    if not d:
        return js["quarter_default"]
    at = lambda mmdd: (int(mmdd[:2]) < 4, mmdd)  # noqa: E731 - April first: the financial year's order
    return next((name for name, upto in js["quarters"] if at(d[5:7] + d[8:10]) <= at(upto)), js["quarters"][-1][0])


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
    rows_map = [r for r in itr_json.own_rows(their_form) if "from" in r]
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
    _no_ca_job(f)
    doc, rep = itr_json.assemble(f, f["form"])
    c = clients.get(cid)
    return f"{f['form']} {c['pan']} AY {ay}.json", json.dumps(doc, indent=1, ensure_ascii=False).encode("utf-8"), rep


def report(cid: str, ay: str) -> dict:
    import itr_json  # noqa: PLC0415
    f = facts(cid, ay)
    _no_ca_job(f)
    return itr_json.assemble(f, f["form"])[1]


def _no_ca_job(f: dict) -> None:
    """2026-10-07: a tax audit (s.44AB) or a business loss is a CA's job (the CA-firm side) - no JSON from My return."""
    ca = f.get("ca_needed")
    if ca:
        _bad(ca["why"], 409, **{k: _inr(v) for k, v in ca.items() if k != "why"})


def _inr(n) -> str:
    """12,34,567 - the Indian grouping."""
    n = int(round(_num(n)))
    s = str(abs(n))
    head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", s[:-3]) if len(s) > 3 else ""
    return ("-" if n < 0 else "") + (head + "," if head else "") + s[-3:]


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
