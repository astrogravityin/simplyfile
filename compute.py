"""Compute & close - SimplyFile phases 4 and 5 (2026-10-04 owner: "complete end to end, including Phase 4, all the way to
closure").

Phase 4, the computation: the books' mapped rows (Intake & map, only refs a person stands behind - recon.book_rows) are
added up per head of income (chip compute.settings heads: SF Ref tables -> head), house property gets its 30%, the total
income is rounded and taxed (chip compute.tax: slabs, 87A rebate, surcharge with marginal relief, cess - the rate tables
are chip rows), and the credit is taken as 26AS shows it (TDS, advance / self-assessment tax: what the return is checked
against). Chip compute.balance says payable, refund or nil. Out of it come three files: the computation as Excel, the
ITR utility's own CSV imports (CSV_TDS2 + CSV_IT, headers exactly as the utility ships them), and a 3CD clause schedule
(every row whose SF Ref names a 3CD clause).
Phase 5, closing: a reviewer signs the computation off (the figures are kept with the sign-off - a later change makes it
stale); a year moves to Filed only signed off and with its acknowledgement number, and Filed locks it (chip close.move
decides, clients.guard_open refuses every later write); leaving Filed needs the "reopen" right.
Python only reads the books and the portal and adds up; every rate, rule and word is a chip.
"""
from __future__ import annotations

import csv
import io
import re
import threading
import zipfile

from fastapi import HTTPException

import clients
import delegation
import recon
from core import engine, store
from core.ops import template

_LOCK = threading.Lock()


def settings() -> dict:
    return engine.run("compute.settings")


def say(key: str, **values) -> str:
    return template(engine.run("ui.compute")[key], values)


def _bad(key: str, code: int = 400, **values):
    raise HTTPException(code, say(key, **values))


def _state_name(cid: str, ay: str) -> str:
    clients.get(cid)                                        # 404 for a client not in the register
    if ay not in clients.settings()["years"]:               # both go into a file path: only known values
        raise HTTPException(400, clients.say("bad_ay", ay=ay))
    (store.DATA / "sf_compute" / cid).mkdir(parents=True, exist_ok=True)
    return f"sf_compute/{cid}/{ay}.json"


def year_day(ay: str, which: str, years: int = 0) -> int:
    """yyyymmdd of the AY's start (1 April) or of a financial year's end (31 March), from chip compute.settings.
    years: 0 = the AY's first year (its 1 April; the previous year's 31 March), 1 = the year after."""
    k = settings()
    return (int(ay[:4]) + years) * 10000 + int(k["year_start_mmdd"] if which == "start" else k["year_end_mmdd"])


def _day(s: str) -> int:
    """26AS 15-Jun-2025 / ISO 2025-06-15 -> 20250615 (0 when unreadable)."""
    m = re.fullmatch(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", str(s or "").strip())
    if m:
        return int(m.group(3)) * 10000 + _MONTHS.get(m.group(2).lower(), 0) * 100 + int(m.group(1))
    return int(re.sub(r"\D", "", str(s or ""))[:8] or 0)


def interest_234(cid: str, ay: str, k: dict, assessed: float, paid: list[dict], exempt: bool = False, filed_on: int = 0, due: int = 0) -> dict:
    """Interest u/s 234A / 234B / 234C (chip compute.interest). Here: which challan is advance tax and which self-assessment
    (chip compute.paid_kind), what was paid by each instalment date, and the months - counted by op months_part."""
    import datetime  # noqa: PLC0415
    from core.ops import months_part  # noqa: PLC0415
    ayy = int(ay[:4])
    y = clients.year_of(cid, ay)
    cur = current_filing(y)
    filing = filed_on or (_day(cur["filed_on"]) if cur and cur.get("filed_on") and not y.get("revising") else _day(datetime.date.today().isoformat()))
    due = due or dates(cid, ay)["due"]       # My return passes its own form's due date and the day it was (or will be) filed
    rows = [{"on": _day(e["date"]), "amount": e["tax"] or e["gross"],
             "kind": engine.run("compute.paid_kind", {"minor": str(e.get("minor") or ""), "paid_on": _day(e["date"]), "fy_end": year_day(ay, "end")})}
            for e in paid]
    adv = [r for r in rows if r["kind"] == "advance"]
    sat = [r for r in rows if r["kind"] == "self"]
    cut = [(ayy + yy) * 10000 + md for yy, md in k["advance_due"]]
    after_due = int((datetime.date(due // 10000, due // 100 % 100, due % 100) + datetime.timedelta(days=1)).strftime("%Y%m%d"))
    adv_total = sum(r["amount"] for r in adv)

    def upto(pays: list[dict], owed: float) -> list[dict]:
        """Self-assessment payments in date order, each counted only up to what was still owed."""
        out = []
        for r in sorted(pays, key=lambda r: r["on"]):
            take = max(0.0, min(r["amount"], owed))
            owed -= take
            out.append(r | {"amount": take})
        return out
    sat_b = upto(sat, assessed - adv_total)
    before = sum(r["amount"] for r in sat_b if r["on"] <= due)
    sat_a = upto([r for r in sat if r["on"] > due], assessed - adv_total - before)
    return engine.run("compute.interest", {
        "assessed": assessed, "adv_by": [sum(r["amount"] for r in adv if r["on"] <= c) for c in cut],
        "adv_total": adv_total, "sat_total": sum(r["amount"] for r in sat_b), "sat_before_due": before,
        "sat_im": sum(r["amount"] * months_part(year_day(ay, "start"), r["on"]) for r in sat_b),
        "sat_after_due": sum(r["amount"] for r in sat_a), "sat_after_im": sum(r["amount"] * months_part(after_due, r["on"]) for r in sat_a),
        "months_b": months_part(year_day(ay, "start"), filing), "months_a": months_part(after_due, filing),
        "presumptive": bool(y.get("presumptive")), "exempt": exempt}) | {"filing_day": filing, "exempt": exempt, "due": due}


def refund_interest(ay: str, st: dict, auto: dict, refund: float, tax_total: float) -> dict:
    """s.244A (chip compute.refund_interest): from 1 April when the return is on time, else from the filing, to the day
    the refund came (typed in) or today."""
    import datetime  # noqa: PLC0415
    from core.ops import months_part  # noqa: PLC0415
    filed, due = auto["filing_day"], auto["due"]
    start = year_day(ay, "start") if filed <= due else filed
    end = _day(st.get("refund_on") or datetime.date.today().isoformat())
    return engine.run("compute.refund_interest", {"refund": refund, "tax_determined": tax_total, "months": months_part(start, end)}) | {
        "from": start, "to": end, "refund_on": st.get("refund_on") or ""}


def regime_of(k: dict, status: str, chosen: str, ay: str = "") -> dict:
    """The rate table for this status - which one is chip compute.regime's answer (the chosen one if this status may)."""
    rid = engine.run("compute.regime", {"chosen": chosen or "", "allowed": k["status_regimes"].get(status, []),
                                        "default": k["status_default"].get(status, "")})
    return next(r for r in k["regimes_by_ay"].get(ay, k["regimes"]) if r["id"] == rid)   # the AY's own slabs


# --- the computation ------------------------------------------------------------------------------------------------------

def compute(cid: str, ay: str) -> dict:
    k = settings()
    c = clients.get(cid)
    y = clients.year_of(cid, ay)
    st = store.read(_state_name(cid, ay), {})
    reg = regime_of(k, c["status"], st.get("regime") or "", ay)
    books = recon.book_rows(cid, ay)

    heads = []
    for h in k["heads"]:
        rows = [r for r in books if r["table"] in h["tables"]]
        if h["id"] == "HP":
            rows = [r for r in rows if not re.search(k["hp_skip_pattern"], r["label"] or "")]
        lines = [{"label": r["label"], "amount": r["amount"] if recon.is_income(r["label"]) else -r["amount"],
                  "file": r["file"], "key": r["key"]} for r in rows]
        net = sum(x["amount"] for x in lines)
        head = {"id": h["id"], "lines": lines, "gross": net}
        if h["id"] == "HP" and lines:
            head |= engine.run("compute.hp", {"nav": net, "std_pct": k["hp_std_pct"], "loss_cap": k["hp_loss_cap"]})
        else:
            head["net"] = net
        if lines:
            heads.append(head)
    gti = sum(h["net"] for h in heads)
    ded_rows = [r for r in books if r["table"] in k["deduction_tables"]] if reg["allows_via"] else []
    ti = engine.run("compute.total_income", {"gti": gti, "deductions": sum(r["amount"] for r in ded_rows), "round_to": k["round_to"]})
    deductions, income = ti["deductions"], ti["income"]
    tax = engine.run("compute.tax", {"income": income, "status": c["status"], "slabs": reg["slabs"], "steps": reg["surcharge"],
                                     "cess_pct": k["cess_pct"], "round_to": k["round_to"], "rebate_statuses": reg["rebate_statuses"], "resident": not c.get("nri"),
                                     "rebate_upto": reg["rebate_upto"], "rebate_most": reg["rebate_most"]})

    portal = recon.portal_entries(cid, ay)
    src = next((x for x in k["credit_sources"] if any(e["source"] == x for e in portal)), None)   # the credit as 26AS shows it
    src26 = [e for e in portal if e["source"] == src] if src else portal
    tds = [e for e in src26 if e["kind"] in k["prepaid_tds_kinds"] and e["tax"]]
    paid = [e for e in src26 if e["kind"] in k["prepaid_paid_kinds"] and (e["tax"] or e["gross"])]
    tds_total = sum(e["tax"] for e in tds)
    paid_total = sum(e["tax"] or e["gross"] for e in paid)
    born = int(str(c.get("dob") or "0").replace("-", "") or 0)
    exempt = engine.run("compute.no_advance", {"status": c["status"], "nri": bool(c.get("nri")), "born": born,
                                               "fy_end": year_day(ay, "end"),
                                               "has_business": any(h["id"] == "BP" and h["lines"] for h in heads)}) is True
    auto = interest_234(cid, ay, k, tax["total"] - tds_total, paid, exempt)
    over = st.get("interest_override")
    interest = float(over) if over is not None else auto["total"]
    bal = engine.run("compute.balance", {"total": tax["total"], "interest": interest, "tds": tds_total, "paid": paid_total})
    refund_int = refund_interest(ay, st, auto, -bal["net"], tax["total"])

    figures = {"income": income, "tax": tax["total"], "net": bal["net"]}
    sign = st.get("signoff")
    signed = bool(sign) and sign.get("figures") == figures      # a sign-off stands behind these exact figures
    open_red = recon.findings(cid, ay)["open_red"]
    has_26as = any(e["source"] == "26as" for e in portal)
    stage = refresh(cid, ay, signed=signed, open_red=open_red, has_26as=has_26as)
    y = clients.year_of(cid, ay)
    locked = clients.locked(cid, ay)
    cur = current_filing(y)
    steps = engine.run("close.steps", {"has_books": bool(books), "has_26as": has_26as, "open_red": open_red, "signed": signed,
                                       "has_ack": bool(cur), "locked": locked})
    return {"client": clients.row(clients.get(cid), ay), "ay": ay, "stage": stage, "ack_no": (cur or {}).get("ack_no", ""),
            "filings": y.get("filings", []), "current": cur, "revising": bool(y.get("revising")), "dates": (dd := dates(cid, ay)),
            "itr_u": itr_u(cid, ay, bal["net"]) if dd["kind"] == "updated" else None, "tp": bool(y.get("tp")),
            "regime": reg["id"], "regimes": k["status_regimes"].get(c["status"], [reg["id"]]),
            "heads": heads, "gti": gti, "deductions": deductions, "deduction_rows": ded_rows, "income": income, "tax": tax,
            "tds": [{"party": e["party"], "tan": e["tan"], "section": e["section"], "gross": e["gross"], "tax": e["tax"]} for e in tds],
            "paid": [{"date": e["date"], "bsr": e["bsr"], "challan": e["challan"], "amount": e["tax"] or e["gross"], "minor": e.get("minor", "")}
                     for e in paid],
            "tds_total": tds_total, "paid_total": paid_total, "interest": interest, "interest_auto": auto,
            "interest_override": over, "refund_interest": refund_int, "presumptive": bool(y.get("presumptive")), "balance": bal,
            "has_books": bool(books), "has_26as": has_26as, "steps": steps,
            "signoff": sign, "signed": signed, "figures": figures, "locked": locked, "open_red": open_red,
            "imported": y.get("imported")}


def set_state(user: dict, cid: str, ay: str, body: dict) -> dict:
    """The person's choices: the regime, an interest override, and the day the refund came (allowed after filing too)."""
    if set(body) - {"refund_on"}:
        clients.guard_open(cid, ay)
    k = settings()
    with _LOCK:
        st = store.read(_state_name(cid, ay), {})
        if "regime" in body:
            if str(body["regime"]) not in {r["id"] for r in k["regimes"]}:
                _bad("bad_regime")
            st["regime"] = str(body["regime"])
        if "refund_on" in body:                  # the day the refund was granted (244A interest stops there); blank = today
            v = str(body["refund_on"] or "")[:10]
            if v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                _bad("bad_date")
            st["refund_on"] = v
        if "interest" in body:                   # an override of the calculated 234A/B/C; blank = back to calculated
            if body["interest"] in (None, ""):
                st.pop("interest_override", None)
            else:
                try:
                    v = float(body["interest"])
                except (TypeError, ValueError):
                    _bad("bad_interest")
                if not 0 <= v <= k["interest_max"]:
                    _bad("bad_interest")
                st["interest_override"] = v
        st["updated_at"], st["updated_by"] = store.now(), user["id"]
        store.write(_state_name(cid, ay), st)
    return compute(cid, ay)


def sign_off(user: dict, cid: str, ay: str, on: bool = True) -> dict:
    """A reviewer stands behind these figures. Kept with the figures, so a later change shows the sign-off as stale."""
    clients.guard_open(cid, ay)
    d = compute(cid, ay)
    if on:   # chip close.signoff: only in a sign-off stage, only with every red finding explained
        verdict = engine.run("close.signoff", {"facts": {"in_stage": d["stage"] in engine.run("close.settings")["signoff_stages"],
                                                         "has_red": d["open_red"] > 0}})
        if not verdict.get("ok"):
            _bad(verdict["say"], n=d["open_red"])
    with _LOCK:
        st = store.read(_state_name(cid, ay), {})
        if on:
            st["signoff"] = {"by": delegation.actor(user), "at": store.now(), "figures": d["figures"]}
        else:
            st.pop("signoff", None)
        store.write(_state_name(cid, ay), st)
    return compute(cid, ay)


# --- the stage and the filings (2026-10-04 owner: "Stage should move automatically ... discard old filing and create new") ---

def current_filing(y: dict) -> dict | None:
    """The return that stands for the year: the last one filed and not withdrawn or superseded."""
    return next((f for f in reversed(y.get("filings") or []) if f.get("status") == "current"), None)


def _ymd(d) -> int:
    return int(str(d).replace("-", "")[:8] or 0)


def dates(cid: str, ay: str, filed_on: str = "") -> dict:
    """Due date, last day to revise, last day for an ITR-U, and what a return filed on `filed_on` (today) would be."""
    import datetime  # noqa: PLC0415
    y = clients.year_of(cid, ay)
    today = datetime.date.today().isoformat()
    filings = y.get("filings") or []
    return engine.run("close.dates", {"ay_year": int(ay[:4]), "audit": bool(y.get("audit")), "tp": bool(y.get("tp")), "form": y.get("form") or "", "filed_on": _ymd(filed_on or today),
                                      "today": _ymd(today), "has_current": bool(current_filing(y)),
                                      "has_updated": any(f["kind"] == "updated" and f["status"] != "withdrawn" for f in filings)})


def itr_u(cid: str, ay: str, net_now: float, filed_on: str = "") -> dict:
    """What an updated return filed on `filed_on` (today) would mean: allowed?, the further tax, 140B's % and amount."""
    import datetime  # noqa: PLC0415
    day = datetime.date.fromisoformat(filed_on or datetime.date.today().isoformat())
    e = year_day(ay, "end", 1)                                           # the AY ends on 31 March of the next year
    end = datetime.date(e // 10000, e // 100 % 100, e % 100)
    months = (day.year - end.year) * 12 + (day.month - end.month) + (day.day - end.day) / 31
    before = ((current_filing(clients.year_of(cid, ay)) or {}).get("figures") or {}).get("net") or 0
    return engine.run("close.itr_u", {"net_now": net_now, "net_before": before, "months": round(months, 3)}) | {"net_before": before}


def refresh(cid: str, ay: str, *, signed: bool | None = None, open_red: int | None = None, has_26as: bool | None = None) -> str:
    """Work out the year's stage from what has happened (chip close.stage) and keep it. Called after every change."""
    import intake  # noqa: PLC0415 - intake imports nothing of ours
    if signed is None:
        return compute(cid, ay)["stage"]                    # compute() gathers every fact and calls back here
    y = clients.year_of(cid, ay)
    if y.get("ack_no") and not y.get("filings"):           # filed before filings were kept (2026-10-04): its record, once
        c = clients.get(cid)
        clients.change_year(cid, ay, lambda yy: yy.update(filings=[{
            "n": 1, "kind": "original", "ack_no": yy["ack_no"], "filed_on": str(c.get("updated_at") or store.now())[:10],
            "by": say("legacy_by"), "at": store.now(), "figures": {}, "status": "current", "revises": "", "note": ""}]))
        y = clients.year_of(cid, ay)
    files = intake.files(cid, ay)["files"]
    open_states = engine.run("page.intake")["open_states"]
    stage = engine.run("close.stage", {
        "has_files": bool(files), "open_rows": sum(f.get(s, 0) for f in files for s in open_states),
        "has_26as": bool(has_26as), "open_red": open_red or 0, "signed": signed,
        "filed": bool(current_filing(y)) and not y.get("revising")})
    if y.get("stage") != stage:
        clients.change_year(cid, ay, lambda yy: yy.update(stage=stage))
    return stage


def act(user: dict, cid: str, ay: str, action: str, body: dict) -> dict:
    """file / withdraw / revise / discard - facts here, chip close.move decides, nothing filed is ever deleted."""
    d = compute(cid, ay)
    y = clients.year_of(cid, ay)
    ack = re.sub(r"\s+", "", str(body.get("ack_no") or ""))
    filed_on = str(body.get("filed_on") or "")[:10]
    when = dates(cid, ay, filed_on)
    upd = itr_u(cid, ay, d["balance"]["net"], filed_on) if when["kind"] == "updated" else None
    note = re.sub(r"\s+", " ", str(body.get("note") or "")).strip()[: settings()["note_max"]]
    facts = {"action": action, "signed": d["signed"], "ack_ok": engine.run("close.ack_ok", {"ack": ack}) is True,
             "kind": when["kind"], "filed": bool(d["current"]) and not d["revising"], "revising": d["revising"],
             "has_note": bool(note), "may_revise": when["may_revise"], "may_update": when["may_update"],
             "future": _ymd(filed_on or "0") > _ymd(store.now()[:10]),
             "itru_ok": bool(upd and upd["ok"]), "itru_confirmed": bool(body.get("itru_confirm"))}
    verdict = engine.run("close.move", {"facts": facts})
    if not verdict.get("ok"):
        _bad(verdict["say"], 409)
    who, now = delegation.actor(user), store.now()

    def change(yy: dict) -> None:
        fl = yy.setdefault("filings", [])
        cur = current_filing(yy)
        if action == "file":
            if cur:
                cur["status"], cur["superseded_at"] = "superseded", now
            fl.append({"n": len(fl) + 1, "kind": when["kind"], "ack_no": ack, "filed_on": filed_on or now[:10], "by": who, "at": now,
                       "figures": d["figures"], "status": "current", "revises": (cur or {}).get("ack_no", ""),
                       "itr_u": {k: upd[k] for k in ("extra", "pct", "additional")} if upd else None})
            yy["revising"] = False
            yy["ack_no"] = ack
        elif action == "withdraw":
            cur["status"], cur["withdrawn_by"], cur["withdrawn_at"], cur["note"] = "withdrawn", who, now, note
            prev = next((f for f in reversed(fl) if f["status"] == "superseded" and f["ack_no"] == cur.get("revises")), None)
            if prev:          # a revised return undone: the one it revised stands again, and the revision is open again
                prev["status"] = "current"
                prev.pop("superseded_at", None)
                yy["revising"] = True
            yy["ack_no"] = (current_filing(yy) or {}).get("ack_no", "")
        elif action == "revise":
            yy["revising"], yy["revising_since"], yy["revising_by"] = True, now, who
        elif action == "discard":
            yy["revising"] = False
    clients.change_year(cid, ay, change)
    if action in engine.run("close.settings")["clear_signoff_on"]:   # the figures will change: a fresh sign-off is needed
        with _LOCK:
            st = store.read(_state_name(cid, ay), {})
            st.pop("signoff", None)
            store.write(_state_name(cid, ay), st)
    return compute(cid, ay)


# --- the three files ------------------------------------------------------------------------------------------------------

def _inr(v: float) -> str:
    return recon._inr(v).replace("₹", "")


def computation_xlsx(cid: str, ay: str) -> tuple[str, bytes]:
    import openpyxl  # noqa: PLC0415
    from openpyxl.styles import Alignment, Font, PatternFill  # noqa: PLC0415
    d = compute(cid, ay)
    w = engine.run("ui.compute")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = w["x_sheet"][:31]
    bold, head = Font(bold=True), Font(bold=True, size=13)
    band = PatternFill("solid", fgColor="EEF0FB")
    put = lambda *cells, font=None, fill=None: (ws.append(list(cells)), [setattr(c, "font", font) for c in ws[ws.max_row] if font],  # noqa: E731
                                                 [setattr(c, "fill", fill) for c in ws[ws.max_row] if fill])
    put(w["x_title"], font=head)
    put(f"{d['client']['name']} · PAN {d['client']['pan']} · {d['client']['status']} · {w['ay']} {ay} · {w['regime_' + d['regime']]}")
    put()
    for h in d["heads"]:
        put(w["head_" + h["id"]], font=bold, fill=band)
        for x in h["lines"]:
            put("", x["label"], x["amount"])
        if "std" in h:
            put("", w["hp_nav"], h["gross"])
            put("", w["hp_std"], -h["std"])
        put("", w["head_total"], h["net"], font=bold)
    rows = [(w["gti"], d["gti"]), (w["deductions"], -d["deductions"]), (w["total_income"], d["income"]),
            (w["t_tax"], d["tax"]["tax"]), (w["t_rebate"], -d["tax"]["rebate"]), (w["t_surcharge"], d["tax"]["surcharge"]),
            (w["t_relief"], -d["tax"]["relief"]), (w["t_cess"], d["tax"]["cess"]), (w["t_total"], d["tax"]["total"]),
            (w["t_interest"], d["interest"]), (w["t_tds"], -d["tds_total"]), (w["t_paid"], -d["paid_total"]),
            (w["bal_" + d["balance"]["kind"]], d["balance"]["amount"])]
    put()
    for label, v in rows:
        put(label, "", v, font=bold if label in (w["total_income"], w["t_total"], w["bal_" + d["balance"]["kind"]]) else None)
    put()
    put(w["tds_title"], font=bold, fill=band)
    for e in d["tds"]:
        put("", f"{e['party']} ({e['tan']}) u/s {e['section']}", e["tax"])
    put(w["paid_title"], font=bold, fill=band)
    for e in d["paid"]:
        put("", f"{e['date']} · BSR {e['bsr']} · {w['challan']} {e['challan']}", e["amount"])
    if d["signoff"]:
        put()
        put(say("signed_by", by=d["signoff"]["by"], at=d["signoff"]["at"][:16]))
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 58
    ws.column_dimensions["C"].width = 18
    for r in ws.iter_rows(min_col=3, max_col=3):
        for cell in r:
            cell.number_format = "#,##,##0"
            cell.alignment = Alignment(horizontal="right")
    buf = io.BytesIO()
    wb.save(buf)
    return f"Computation {d['client']['name']} AY {ay}.xlsx", buf.getvalue()


def _csv(header: list, rows: list) -> bytes:
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\r\n")
    wr.writerow(header)
    wr.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")   # the utility's own files start with a BOM


def utility_zip(cid: str, ay: str) -> tuple[str, bytes]:
    """CSV_TDS2.csv + CSV_IT.csv in the ITR utility's import layout: import them on the utility's TDS2 and IT sheets."""
    k, d = settings(), compute(cid, ay)
    tds2 = []
    for e in d["tds"]:
        head = k["csv_head_codes"].get(recon.group_of(e["section"]), k["csv_head_default"])
        tds2.append([k["csv_self"], "", "", e["tan"], e["section"], "", "", round(e["tax"]), "", "", round(e["tax"]), "", "", "", "",   # Col 5/6: brought-forward TDS only
                     round(e["gross"]), head, ""])
    it = [[e["bsr"], _ddmmyyyy(e["date"]), e["challan"], round(e["amount"])] for e in d["paid"]]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("CSV_TDS2.csv", _csv(k["csv_tds2_header"], tds2))
        z.writestr("CSV_IT.csv", _csv(k["csv_it_header"], it))
    return f"ITR utility imports {d['client']['name']} AY {ay}.zip", buf.getvalue()


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _ddmmyyyy(s: str) -> str:
    """26AS writes 13-Jun-2025; the utility wants 13/06/2025."""
    m = re.fullmatch(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", str(s or "").strip())
    return f"{int(m.group(1)):02d}/{_MONTHS.get(m.group(2).lower(), 0):02d}/{m.group(3)}" if m else str(s or "")


def schedule_3cd_xlsx(cid: str, ay: str) -> tuple[str, bytes]:
    """Every row whose SF Ref names a Form 3CD clause, by clause and serial - what goes into the 3CD utility."""
    import openpyxl  # noqa: PLC0415
    from openpyxl.styles import Font  # noqa: PLC0415
    import intake  # noqa: PLC0415
    w = engine.run("ui.compute")
    c = clients.get(cid)
    out = []
    for m in intake.files(cid, ay)["files"]:
        for x in intake.view(cid, ay, m["id"])["rows"]:
            if x["state"] != "tagged":
                continue
            for p in intake.parse_ref(x["ref"]) or []:
                if p["form"] == "3CD":
                    out.append([p["table"], p.get("serial") or "", x["label"], *x["numbers"][:3], m["name"], x["key"]])
    out.sort(key=lambda r: ([int(n) if n.isdigit() else n for n in re.split(r"(\d+)", str(r[0]))], int(r[1] or 0)))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = w["s_sheet"][:31]
    ws.append([f"{w['s_title']} · {c['name']} · {w['ay']} {ay}"])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([w["s_clause"], w["s_serial"], w["s_label"], w["s_amount"], "", "", w["s_file"], w["s_row"]])
    for cell in ws[2]:
        cell.font = Font(bold=True)
    for r in out:
        ws.append(r)
    for col, width in zip("ABCDEFGH", (12, 8, 48, 16, 16, 16, 40, 12)):
        ws.column_dimensions[col].width = width
    buf = io.BytesIO()
    wb.save(buf)
    return f"3CD schedule {c['name']} AY {ay}.xlsx", buf.getvalue()


if __name__ == "__main__":  # ponytail: one runnable self-check - the rate chips on the dummy client's figures
    import store as _portal_store  # noqa: F401 - registers this portal's chips
    k = settings()
    reg = regime_of(k, "huf", "new")
    t = engine.run("compute.tax", {"income": 20721500, "status": "huf", "slabs": reg["slabs"], "steps": reg["surcharge"],
                                   "cess_pct": k["cess_pct"], "round_to": k["round_to"], "rebate_statuses": reg["rebate_statuses"], "resident": True,
                                   "rebate_upto": reg["rebate_upto"], "rebate_most": reg["rebate_most"]})
    assert t["total"] == 7424040 and t["relief"] == 107062.5, t
    assert regime_of(k, "firm", "new")["id"] == "firm" and regime_of(k, "huf", "old")["id"] == "old" and regime_of(k, "huf", "")["id"] == "new"
    assert engine.run("compute.hp", {"nav": 2340000, "std_pct": 30, "loss_cap": 200000}) == {"std": 702000, "net": 1638000}
    assert engine.run("compute.hp", {"nav": -500000, "std_pct": 30, "loss_cap": 200000}) == {"std": 0, "net": -200000}
    assert _ddmmyyyy("13-Jun-2025") == "13/06/2025"
    assert engine.run("close.move", {"facts": {"action": "file", "signed": False, "ack_ok": True}})["say"] == "need_signoff"
    assert engine.run("close.stage", {"has_files": True, "has_26as": True}) == "review"
    print("compute self-check OK")
