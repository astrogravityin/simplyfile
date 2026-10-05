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
    hist = history(cid, ay, before)
    rows = []
    for key in sorted(set(now) | (set(before) & set(now) if src == "return" and k["return_only_current"] else set(before))):
        t = engine.run("audit.trend", {"now": now.get(key, 0.0), "before": before.get(key, 0.0), "revenue": r_now, "rev_pct": r["pct"],
                                       "has_before": bool(before)})
        past = [h["figures"].get(key, 0.0) for h in hist]
        pat = engine.run("audit.pattern", {"now": now.get(key, 0.0), "history": past, "rev_now": r_now, "rev_history": [rev(h["figures"]) for h in hist]})
        rows.append({"id": f"{key[0]}:{key[1]}", "table": key[0], "item": key[1], "now": now.get(key, 0.0), "before": before.get(key, 0.0),
                     "history": past} | t | pat)
    return {"rows": rows, "source": src, "before_known": bool(before), "prev_ay": pay, "revenue": r_now, "revenue_before": r_before, "revenue_pct": r["pct"],
            "history_ays": [h["ay"] for h in hist]}


def history(cid: str, ay: str, last: dict) -> list[dict]:
    """The earlier years with figures, oldest first, up to chip audit.settings history_years: each from that year's statements or
    its imported return (chip history_from); last year may instead be the one trend() already found (`last`, e.g. the column)."""
    k = settings()
    years = (clients.get(cid).get("years") or {})
    out, y = [], ay
    for i in range(int(k["history_years"])):
        y = analytics._prev(y)  # noqa: SLF001
        have = {"statements": lambda y=y: figures(cid, y)[0], "return": lambda y=y: from_return(cid, y)} if y in years else {}
        f = next((v for s in k["history_from"] if s in have and (v := have[s]())), None) or (last if i == 0 else None)
        if f:
            out.append({"ay": y, "figures": f})
    return out[::-1]


# --- GST returns against the books (phase 2) ---------------------------------------------------------------------------

def _walk(node, path: str) -> list[float]:
    """Every number at a chip path: dotted; name[] = each item of a list; name[k=v] = the items whose k is v."""
    if not path:
        return [float(node)] if isinstance(node, (int, float)) and not isinstance(node, bool) else []
    head, _, rest = path.partition(".")
    m = re.fullmatch(r"([^\[]+)(?:\[(?:([^=\]]+)=([^\]]*))?\])?", head)
    if not m or not isinstance(node, dict) or m[1] not in node:
        return []
    nxt = node[m[1]]
    if "[" not in head:
        return _walk(nxt, rest)
    items = nxt if isinstance(nxt, list) else []
    return [v for x in items if not m[2] or (isinstance(x, dict) and str(x.get(m[2])) == m[3]) for v in _walk(x, rest)]


def _sum(doc: dict, paths: dict) -> float:
    return round(sum(sum(_walk(doc, p)) for p in paths["plus"]) - sum(sum(_walk(doc, p)) for p in paths["minus"]), 2)


def _fy_periods(ay: str) -> list[str]:
    """The return periods (mmyyyy) of the financial year an assessment year taxes, first month first."""
    k = engine.run("audit.gst_read")
    start, y = int(k["fy_start_month"]), int(ay[:4]) - 1
    return [f"{(start - 1 + i) % 12 + 1:02d}{y + (start - 1 + i) // 12}" for i in range(12)]


def read_gst(name: str, data: bytes) -> list[dict]:
    """One upload - a portal JSON, or the zip it comes in - as returns: {kind, gstin, period, taxable, tax}."""
    import io  # noqa: PLC0415
    import json  # noqa: PLC0415
    import zipfile  # noqa: PLC0415
    k = engine.run("audit.gst_read")
    docs = []
    if data[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            docs = [(f"{name}/{n}", z.read(n)) for n in z.namelist() if n.lower().endswith(".json")]
    else:
        docs = [(name, data)]
    out = []
    for n, raw in docs:
        try:
            doc = json.loads(raw.decode("utf-8-sig"))
        except ValueError:
            raise HTTPException(400, say("gst_bad_file", name=n)) from None
        kind = next((x for x in k["kinds"] if isinstance(doc, dict) and x["has"] in doc), None)
        period = str((doc or {}).get(kind["period"], "")) if kind else ""
        if not kind or not re.fullmatch(k["period_pattern"], period):
            raise HTTPException(400, say("gst_bad_file", name=n))
        out.append({"kind": kind["id"], "gstin": str(doc.get(kind["gstin"], "")), "period": period, "name": n,
                    "taxable": _sum(doc, kind["taxable"]), "tax": _sum(doc, kind["tax"])})
    return out


def add_gst(u: dict, cid: str, ay: str, files: list[tuple[str, bytes]]) -> dict:
    """Add GST returns to the year's audit; a return for the same kind, GSTIN and month replaces the one there."""
    clients.get(cid)
    got = [r for n, d in files for r in read_gst(n, d)]
    fy = _fy_periods(ay)
    bad = next((r for r in got if r["period"] not in fy), None)
    if bad:
        raise HTTPException(400, say("gst_bad_period", name=bad["name"], period=f"{bad['period'][:2]}/{bad['period'][2:]}",
                                     fy=f"{fy[0][:2]}/{fy[0][2:]} - {fy[-1][:2]}/{fy[-1][2:]}"))

    def change(w: dict) -> None:
        have = w.setdefault("gst", [])
        for r in got:
            have[:] = [x for x in have if (x["kind"], x["gstin"], x["period"]) != (r["kind"], r["gstin"], r["period"])]
            have.append(r | {"id": store.new_id(), "by": delegation.actor(u), "at": store.now()})
    _save(cid, ay, change)
    return page(u, cid, ay) | {"added": len(got)}


def remove_gst(u: dict, cid: str, ay: str, gid: str) -> dict:
    _save(cid, ay, lambda w: w.__setitem__("gst", [x for x in w.get("gst") or [] if x["id"] != gid]))
    return page(u, cid, ay)


def gst_view(w: dict, ay: str, books: float) -> dict:
    """Month by month, GSTR-3B against GSTR-1 (every GSTIN together), and the year against the books (chips audit.gst*)."""
    rows = w.get("gst") or []
    months = []
    for p in _fy_periods(ay):
        r3 = [x for x in rows if x["period"] == p and x["kind"] == "gstr3b"]
        r1 = [x for x in rows if x["period"] == p and x["kind"] == "gstr1"]
        a, b = sum(x["taxable"] for x in r3), sum(x["taxable"] for x in r1)
        months.append({"period": p, "r3b": a, "r1": b, "has_3b": bool(r3), "has_1": bool(r1),
                       "state": engine.run("audit.gst_month", {"r3b": a, "r1": b, "has_3b": bool(r3), "has_1": bool(r1)})})
    year = engine.run("audit.gst", {"books": books, "r3b": sum(m["r3b"] for m in months), "r1": sum(m["r1"] for m in months),
                                    "months_3b": sum(m["has_3b"] for m in months), "months_1": sum(m["has_1"] for m in months)})
    return {"files": sorted(rows, key=lambda x: (x["period"][2:], x["period"][:2], x["kind"])), "months": months, "books": books,
            "r3b": sum(m["r3b"] for m in months), "r1": sum(m["r1"] for m in months)} | year


# --- statutory audit, non-corporate entities (phase 2) -------------------------------------------------------------------

def statutory(c: dict, w: dict, tr: dict, have: set[str]) -> dict:
    """Whether an LLP's accounts are to be audited, the entity's level for Accounting Standards, and the standards at that level
    with this client's work on them (chips audit.llp_audit, audit.as_level, audit.as_list)."""
    k = settings()
    now = {(r["table"], r["item"]): r["now"] for r in tr["rows"]}
    borrow = sum(now.get(("BS", i), 0.0) for i in k["borrowing_items"])
    contrib = sum(now.get(("BS", i), 0.0) for i in k["contribution_items"])
    ans = w.get("facts") or {}
    llp = engine.run("audit.llp_audit", {"llp": c.get("status") == "llp", "turnover": tr["revenue"], "contribution": contrib})
    level = engine.run("audit.as_level", {"turnover": tr["revenue"], "borrowings": borrow, "listed": bool(ans.get("listed"))})
    states = w.get("as_checks") or {}
    rows = [r | {"applies": r["applies"][level]} | (states.get(r["id"]) or {"state": "todo", "note": ""})
            for r in engine.run("audit.as_list")["rows"] if not r["any"] or set(r["any"]) & have]
    return {"llp": llp | {"turnover": tr["revenue"], "contribution": contrib}, "level": level, "borrowings": borrow,
            "facts": {f: bool(ans.get(f)) for f in k["stat_fact_keys"]}, "standards": rows}


def set_as(u: dict, cid: str, ay: str, sid: str, body: dict) -> dict:
    """Mark one Accounting Standard worked through; an issue opens an audit point, as a 3CD clause does."""
    k = settings()
    state = str(body.get("state") or "todo")
    row = next((r for r in engine.run("audit.as_list")["rows"] if r["id"] == sid), None)
    if state not in k["check_states"] or not row:
        raise HTTPException(400, say("saved"))

    def change(w: dict) -> None:
        w.setdefault("as_checks", {})[sid] = {"state": state, "note": str(body.get("note") or "")[: k["note_max"]], "by": delegation.actor(u), "at": store.now()}
        pts = w.setdefault("points", [])
        if state == k["issue_state"] and k["issue_raises_point"] and not any(p["ref"] == f"as:{sid}" and p["status"] == k["open_state"] for p in pts):
            pts.append(_point(u, say("point_from_as", std=row["std"], title=row["title"]), k["as_source"], f"as:{sid}"))
    _save(cid, ay, change)
    return page(u, cid, ay)


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


def checklist(have: set[str], states: dict, tr: dict | None = None, sector: str = "") -> list[dict]:
    """The chip's rows that apply: every `needs` fact holds and, when `any` is given, at least one of it - riskiest first (chip
    audit.risk): the clause's own risk, this line of business, and the lines it watches that are flagged this year."""
    flagged = {r["item"] for r in (tr or {}).get("rows", []) if r.get("flag") or r.get("pattern")}
    out = []
    for r in engine.run("audit.checklist")["rows"]:
        if not (set(r["needs"]) <= have and (not r["any"] or set(r["any"]) & have)):
            continue
        hits = sorted(set(r.get("watch") or []) & flagged)
        risk = engine.run("audit.risk", {"base": r.get("risk", 1), "sector_hit": sector in (r.get("sectors") or []), "flagged": len(hits),
                                         "turnover": (tr or {}).get("revenue", 0)})
        out.append(r | (states.get(r["id"]) or {"state": "todo", "note": ""}) | risk
                   | {"level": engine.run("audit.risk_level", {"score": risk["score"]}), "flagged_lines": hits,
                      "sector_hit": sector in (r.get("sectors") or [])})
    return sorted(out, key=lambda r: -r["score"])      # stable: equal scores keep the form's own order


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
            "checklist": checklist(have, w.get("checks") or {}, tr, w.get("sector", "")), "points": w.get("points") or [],
            "sector": w.get("sector", ""), "sectors": settings()["sectors"], "gst": gst_view(w, ay, tr["revenue"]),
            "stat": statutory(c, w, tr, have), "as_source": settings()["as_source"],
            "gst_source": settings()["gst_source"], "gst_exts": engine.run("audit.gst_read")["exts"],
            "people": [{"id": m["id"], "name": m["name"] or m["email"]} for m in firms.team(u)] if u.get("firm_id") else [],
            "states": settings()["check_states"], "done_states": settings()["done_states"], "trend_source": settings()["trend_source"], "pattern_source": settings()["pattern_source"], "may_clear": firms.may(u, "audit", "clear", cid=cid, ay=ay)["ok"]}


def _save(cid: str, ay: str, change) -> dict:
    with _LOCK:
        w = _work(cid, ay)
        change(w)
        (store.DATA / "sf_audit" / cid).mkdir(parents=True, exist_ok=True)
        store.write(_file(cid, ay), w)
    return w


def set_facts(u: dict, cid: str, ay: str, body: dict) -> dict:
    keys = settings()["fact_keys"] + settings()["stat_fact_keys"]
    if "sector" in body and body["sector"] not in ["", *settings()["sectors"]]:
        raise HTTPException(400, say("saved"))

    def change(w: dict) -> None:
        w.setdefault("facts", {}).update({k: bool(body[k]) for k in keys if k in body})
        if "sector" in body:
            w["sector"] = body["sector"]
    _save(cid, ay, change)
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
    assert engine.run("audit.pattern", {"now": 900000, "history": [480000, 500000, 520000], "rev_now": 10000000,
                                        "rev_history": [9500000, 9800000, 10000000]})["pattern"] == "above_pattern"
    rows = checklist({"business", "status_firm", "partners", "has_rent", "has_sales"}, {})
    ids = {r["id"] for r in rows}
    assert {"c9", "c21b", "c35", "c40"} <= ids and "c12" not in ids and "c18" not in ids, ids
    ranked = checklist({"business", "status_firm", "partners", "has_rent", "has_sales"}, {}, {"rows": [{"item": "rent", "flag": "spike"}], "revenue": 0}, "trading")
    top = ranked[0]
    assert top["id"] == "c21b" and top["level"] == "high" and top["flagged_lines"] == ["rent"], top     # rent up sharply: TDS on rent first
    assert ranked[-1]["level"] == "low" and [r["score"] for r in ranked] == sorted((r["score"] for r in ranked), reverse=True)
    assert _walk({"cdnr": [{"nt": [{"ntty": "C", "v": 5}, {"ntty": "D", "v": 7}]}]}, "cdnr[].nt[ntty=C].v") == [5.0]
    assert _fy_periods("2026-27")[0] == "042025" and _fy_periods("2026-27")[-1] == "032026"
    import json as _j
    r1 = read_gst("r1.json", _j.dumps({"gstin": "29AAAAA0000A1Z5", "fp": "052025", "b2b": [{"inv": [{"itms": [{"itm_det": {"txval": 1000, "iamt": 180}}]}]}],
                                       "b2cs": [{"txval": 500, "camt": 45, "samt": 45}], "cdnr": [{"nt": [{"ntty": "C", "itms": [{"itm_det": {"txval": 100}}]}]}]}).encode())
    assert r1 == [{"kind": "gstr1", "gstin": "29AAAAA0000A1Z5", "period": "052025", "name": "r1.json", "taxable": 1400.0, "tax": 270.0}], r1
    st = statutory({"status": "llp"}, {}, {"rows": [{"table": "BS", "item": "capital", "now": 3000000}, {"table": "BS", "item": "secured_bank", "now": 25000000}],
                                           "revenue": 120000000}, {"business", "has_stock", "has_salaries"})
    assert st["llp"]["need"] == "yes" and st["level"] == "III" and st["borrowings"] == 25000000, st
    by = {r["id"]: r["applies"] for r in st["standards"]}
    assert by["as3"] == "no" and by["as18"] == "full" and by["as15"] == "relaxed" and "as2" in by and "as13" not in by, by
    print("audit OK")
