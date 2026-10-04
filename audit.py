"""Tax audit (s.44AB) for SMEs - phase 1 (2026-10-04 owner: "Go with phase 1, tax audit for SMEs").

One client-year at a time: is an audit needed (chip audit.applicable), every mapped profit-and-loss and balance-sheet line this
year against last with the lines worth a look (chip audit.trend), the Form 3CD clauses that apply to this client (chip
audit.checklist), and the audit points still open. The figures are the statement rows already tagged in Intake & map
(ITR3 PL #rent, ITR5 BS #creditors ...) - a trial balance or P&L uploaded there is all it needs. Last year comes from last year's
statements, else from the previous-year column of this year's file (chip audit.settings prev_pattern).

Stored per client-year in sf_audit/<cid>/<ay>.json: the facts a person answers, each checklist line's state and note, the points.
Words: ui.audit. Look: page.audit.
"""
from __future__ import annotations

import re
import threading

from fastapi import HTTPException

import analytics
import clients
import delegation
import firms
import intake
import itr_import
from core import engine, store

_LOCK = threading.Lock()


def settings() -> dict:
    return engine.run("audit.settings")


def say(key: str, **v) -> str:
    return engine.say("ui.audit", key, **v)


def _file(cid: str, ay: str) -> str:
    return f"sf_audit/{cid}/{ay}.json"


def _work(cid: str, ay: str) -> dict:
    return store.read(_file(cid, ay), {}) or {}


# --- the figures ---------------------------------------------------------------------------------------------------------

def figures(cid: str, ay: str) -> tuple[dict, dict]:
    """{(table, item): amount} this year, and {(table, item): amount} from the previous-year column of the same files."""
    k = settings()
    prev = re.compile(k["prev_pattern"])
    now: dict = {}
    before: dict = {}
    for m in intake.files(cid, ay)["files"]:
        for x in intake.view(cid, ay, m["id"])["rows"]:
            if x["state"] != "tagged":
                continue
            last = next((v for t, v in x.get("by_col") or [] if prev.search(str(t))), None)
            for p in intake.parse_ref(x["ref"]) or []:
                if p["table"] in k["tables"] and p["serial"]:
                    key = (p["table"], str(p["serial"]))
                    now[key] = now.get(key, 0.0) + abs(float(x.get("amount", x["numbers"][0] if x["numbers"] else 0.0)))
                    if last is not None:
                        before[key] = before.get(key, 0.0) + abs(float(last))
    return now, before


def from_return(cid: str, ay: str) -> dict:
    """{(table, item): amount} from the return filed for `ay` and imported (Import old returns): the ITR's own P&L and balance
    sheet, read at the places chip itr.books names (with its ITR-5 rewrites)."""
    y = (clients.get(cid).get("years") or {}).get(ay) or {}
    imp = y.get("imported") or {}
    path = store.DATA / "sf_files" / cid / ay / f"itr-{imp.get('digest', '')}.json"
    if not imp or not path.exists():
        return {}
    import json  # noqa: PLC0415
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    k = itr_import.settings()
    body = doc.get(k["wrap"], doc) if isinstance(doc, dict) else {}
    body = next((body[f] for f in k["forms"] if isinstance(body, dict) and f in body), {})
    books = engine.run("itr.books")
    out = {}
    for item, where in books["items"].items():
        for a, b in books["rewrites"].get(imp.get("form", ""), []):
            where = where.replace(a, b)
        v = abs(itr_import._num(itr_import._at(body, where)))  # noqa: SLF001
        if v:
            out[("BS" if where.startswith(settings()["bs_prefix"]) else "PL", item)] = v   # trading account lines are P&L too
    return out


def trend(cid: str, ay: str) -> dict:
    k = settings()
    now, column = figures(cid, ay)
    pay = analytics._prev(ay)  # noqa: SLF001
    known = pay in (clients.get(cid).get("years") or {})
    last = figures(cid, pay)[0] if known else {}
    filed = from_return(cid, pay) if known and not last else {}
    # last year, best first (chip audit.settings last_year_from): last year's statements, last year's filed return, this year's column
    have = {"statements": last, "return": filed, "column": column}
    src = next((s for s in k["last_year_from"] if have.get(s)), "none")
    before = have.get(src) or {}
    rev = lambda f: sum(v for (t, i), v in f.items() if t == "PL" and i in k["revenue_items"])  # noqa: E731
    r_now, r_before = rev(now), rev(before)
    r = engine.run("audit.trend", {"now": r_now, "before": r_before, "revenue": r_now})
    rows = []
    for key in sorted(set(now) | (set(before) & set(now) if src == "return" and k["return_only_current"] else set(before))):
        t = engine.run("audit.trend", {"now": now.get(key, 0.0), "before": before.get(key, 0.0), "revenue": r_now, "rev_pct": r["pct"],
                                       "has_before": bool(before)})
        rows.append({"id": f"{key[0]}:{key[1]}", "table": key[0], "item": key[1], "now": now.get(key, 0.0), "before": before.get(key, 0.0)} | t)
    return {"rows": rows, "source": src, "before_known": bool(before), "prev_ay": pay, "revenue": r_now, "revenue_before": r_before, "revenue_pct": r["pct"]}


# --- the checklist -------------------------------------------------------------------------------------------------------

def facts(c: dict, ay: str, tr: dict) -> set[str]:
    k = settings()
    y = (c.get("years") or {}).get(ay) or {}
    status = next((s for s in clients.settings()["statuses"] if s["id"] == c.get("status")), {})
    f = {f"has_{r['item']}" for r in tr["rows"] if r["now"]} | {f"status_{c.get('status', '')}"}
    if status.get("has_partners"):
        f.add("partners")
    if y.get("presumptive"):
        f.add("presumptive")
    prof = any(r["now"] for r in tr["rows"] if r["table"] == "PL" and r["item"] in k["profession_items"])
    other = any(r["now"] for r in tr["rows"] if r["table"] == "PL" and r["item"] in k["revenue_items"] and r["item"] not in k["profession_items"])
    f.add(engine.run("audit.kind", {"profession": prof, "other": other}))
    return f


def checklist(have: set[str], states: dict) -> list[dict]:
    """The chip's rows that apply: every `needs` fact holds and, when `any` is given, at least one of it."""
    return [r | (states.get(r["id"]) or {"state": "todo", "note": ""}) for r in engine.run("audit.checklist")["rows"]
            if set(r["needs"]) <= have and (not r["any"] or set(r["any"]) & have)]


# --- the page ------------------------------------------------------------------------------------------------------------

def page(u: dict, cid: str, ay: str) -> dict:
    c = clients.get(cid)
    if ay not in clients.settings()["years"]:
        raise HTTPException(400, say("why_unknown"))
    w = _work(cid, ay)
    tr = trend(cid, ay)
    have = facts(c, ay, tr)
    ans = w.get("facts") or {}
    need = engine.run("audit.applicable", {"business": "business" in have, "turnover": tr["revenue"],
                                           **{f: bool(ans.get(f)) for f in settings()["fact_keys"]}})
    y = (c.get("years") or {}).get(ay) or {}
    return {"client": {"id": c["id"], "name": c["name"], "pan": c.get("pan", ""), "status": c.get("status", "")}, "ay": ay,
            "marked": bool(y.get("audit")), "facts": {f: bool(ans.get(f)) for f in settings()["fact_keys"]},
            "applicable": need["verdict"] | {"turnover": tr["revenue"], "limit": need["limit"]}, "trend": tr,
            "checklist": checklist(have, w.get("checks") or {}), "points": w.get("points") or [],
            "people": [{"id": m["id"], "name": m["name"] or m["email"]} for m in firms.team(u)] if u.get("firm_id") else [],
            "states": settings()["check_states"], "done_states": settings()["done_states"], "trend_source": settings()["trend_source"], "may_clear": firms.may(u, "audit", "clear", cid=cid, ay=ay)["ok"]}


def _save(cid: str, ay: str, change) -> dict:
    with _LOCK:
        w = _work(cid, ay)
        change(w)
        (store.DATA / "sf_audit" / cid).mkdir(parents=True, exist_ok=True)
        store.write(_file(cid, ay), w)
    return w


def set_facts(u: dict, cid: str, ay: str, body: dict) -> dict:
    keys = settings()["fact_keys"]
    _save(cid, ay, lambda w: w.setdefault("facts", {}).update({k: bool(body[k]) for k in keys if k in body}))
    return page(u, cid, ay)


def _point(u: dict, title: str, source: str, ref: str, owner: str = "") -> dict:
    k = settings()
    return {"id": store.new_id(), "title": str(title)[: k["title_max"]], "source": source, "ref": ref, "owner": owner, "status": k["open_state"],
            "note": "", "by": delegation.actor(u), "at": store.now()}


def set_check(u: dict, cid: str, ay: str, iid: str, body: dict) -> dict:
    k = settings()
    state = str(body.get("state") or "todo")
    if state not in k["check_states"]:
        raise HTTPException(400, say("saved"))
    row = next((r for r in engine.run("audit.checklist")["rows"] if r["id"] == iid), None)
    if not row:
        raise HTTPException(404, say("saved"))

    def change(w: dict) -> None:
        w.setdefault("checks", {})[iid] = {"state": state, "note": str(body.get("note") or "")[: k["note_max"]], "by": delegation.actor(u), "at": store.now()}
        pts = w.setdefault("points", [])
        if state == k["issue_state"] and k["issue_raises_point"] and not any(p["ref"] == f"check:{iid}" and p["status"] == k["open_state"] for p in pts):
            pts.append(_point(u, say("point_from_check", clause=row["clause"], title=row["title"]), k["check_source"], f"check:{iid}"))
    _save(cid, ay, change)
    return page(u, cid, ay)


def add_point(u: dict, cid: str, ay: str, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, say("point_title_ph"))
    k = settings()
    source = str(body.get("source") or "")
    _save(cid, ay, lambda w: w.setdefault("points", []).append(_point(u, title, source if source in k["point_sources"] else k["hand_source"],
                                                                      str(body.get("ref") or ""), str(body.get("owner") or ""))))
    return page(u, cid, ay)


def set_point(u: dict, cid: str, ay: str, pid: str, body: dict) -> dict:
    status = body.get("status")
    if status is not None and status not in settings()["point_states"]:
        raise HTTPException(400, say("saved"))

    def change(w: dict) -> None:
        p = next((x for x in w.get("points") or [] if x["id"] == pid), None)
        if not p:
            raise HTTPException(404, say("points_none"))
        for f in ("owner", "note"):
            if f in body:
                p[f] = str(body[f] or "")[: settings()["note_max"]]
        if status is not None:
            p["status"] = status
            p["closed_by"], p["closed_at"] = (delegation.actor(u), store.now()) if status == settings()["cleared_state"] else ("", "")
    _save(cid, ay, change)
    return page(u, cid, ay)


if __name__ == "__main__":  # ponytail: the three rules on made-up figures - applicability, a flagged line, the chosen clauses
    import store as _s  # noqa: F401 - registers this portal's chips
    assert engine.run("audit.applicable", {"business": True, "turnover": 25000000})["verdict"]["need"] == "yes"
    assert engine.run("audit.trend", {"now": 900000, "before": 500000, "revenue": 10000000, "rev_pct": 2})["flag"] == "spike"
    rows = checklist({"business", "status_firm", "partners", "has_rent", "has_sales"}, {})
    ids = {r["id"] for r in rows}
    assert {"c9", "c21b", "c35", "c40"} <= ids and "c12" not in ids and "c18" not in ids, ids
    print("audit OK")
