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


def regime_of(k: dict, status: str, chosen: str) -> dict:
    """The rate table for this status - which one is chip compute.regime's answer (the chosen one if this status may)."""
    rid = engine.run("compute.regime", {"chosen": chosen or "", "allowed": k["status_regimes"].get(status, []),
                                        "default": k["status_default"].get(status, "")})
    return next(r for r in k["regimes"] if r["id"] == rid)


# --- the computation ------------------------------------------------------------------------------------------------------

def compute(cid: str, ay: str) -> dict:
    k = settings()
    c = clients.get(cid)
    y = clients.year_of(cid, ay)
    st = store.read(_state_name(cid, ay), {})
    reg = regime_of(k, c["status"], st.get("regime") or "")
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
                                     "cess_pct": k["cess_pct"], "round_to": k["round_to"], "rebate_statuses": reg["rebate_statuses"],
                                     "rebate_upto": reg["rebate_upto"], "rebate_most": reg["rebate_most"]})

    portal = recon.portal_entries(cid, ay)
    src = next((x for x in k["credit_sources"] if any(e["source"] == x for e in portal)), None)   # the credit as 26AS shows it
    src26 = [e for e in portal if e["source"] == src] if src else portal
    tds = [e for e in src26 if e["kind"] in k["prepaid_tds_kinds"] and e["tax"]]
    paid = [e for e in src26 if e["kind"] in k["prepaid_paid_kinds"] and (e["tax"] or e["gross"])]
    tds_total = sum(e["tax"] for e in tds)
    paid_total = sum(e["tax"] or e["gross"] for e in paid)
    interest = float(st.get("interest") or 0)
    bal = engine.run("compute.balance", {"total": tax["total"], "interest": interest, "tds": tds_total, "paid": paid_total})

    figures = {"income": income, "tax": tax["total"], "net": bal["net"]}
    sign = st.get("signoff")
    signed = bool(sign) and sign.get("figures") == figures      # a sign-off stands behind these exact figures
    open_red = recon.findings(cid, ay)["open_red"]
    locked = clients.locked(cid, ay)
    has_26as = any(e["source"] == "26as" for e in portal)
    steps = engine.run("close.steps", {"has_books": bool(books), "has_26as": has_26as, "open_red": open_red, "signed": signed,
                                       "has_ack": bool(str(y.get("ack_no") or "").strip()), "locked": locked})
    return {"client": clients.row(c, ay), "ay": ay, "stage": y.get("stage", ""), "ack_no": y.get("ack_no", ""),
            "regime": reg["id"], "regimes": k["status_regimes"].get(c["status"], [reg["id"]]),
            "heads": heads, "gti": gti, "deductions": deductions, "deduction_rows": ded_rows, "income": income, "tax": tax,
            "tds": [{"party": e["party"], "tan": e["tan"], "section": e["section"], "gross": e["gross"], "tax": e["tax"]} for e in tds],
            "paid": [{"date": e["date"], "bsr": e["bsr"], "challan": e["challan"], "amount": e["tax"] or e["gross"]} for e in paid],
            "tds_total": tds_total, "paid_total": paid_total, "interest": interest, "balance": bal,
            "has_books": bool(books), "has_26as": has_26as, "steps": steps,
            "signoff": sign, "signed": signed, "figures": figures, "locked": locked, "open_red": open_red}


def set_state(user: dict, cid: str, ay: str, body: dict) -> dict:
    """The person's choices on the computation: the regime, and interest u/s 234A/B/C as worked out by them."""
    clients.guard_open(cid, ay)
    k = settings()
    with _LOCK:
        st = store.read(_state_name(cid, ay), {})
        if "regime" in body:
            if str(body["regime"]) not in {r["id"] for r in k["regimes"]}:
                _bad("bad_regime")
            st["regime"] = str(body["regime"])
        if "interest" in body:
            try:
                v = float(body["interest"] or 0)
            except (TypeError, ValueError):
                _bad("bad_interest")
            if not 0 <= v <= k["interest_max"]:
                _bad("bad_interest")
            st["interest"] = v
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
            st["signoff"] = {"by": user.get("email") or user["id"], "at": store.now(), "figures": d["figures"]}
        else:
            st.pop("signoff", None)
        store.write(_state_name(cid, ay), st)
    return compute(cid, ay)


def gate_move(user: dict, cid: str, ay: str, to_stage: str, ack_no: str | None, may_reopen: bool) -> None:
    """May the year move to `to_stage`? Facts here; chip close.move decides (filed needs sign-off + ack; leaving it, reopen)."""
    k = engine.run("close.settings")
    d = compute(cid, ay)
    ack = d["ack_no"] if ack_no is None else ack_no
    facts = {"to_filed": to_stage == k["filed_stage"], "signed": d["signed"], "has_ack": bool(str(ack or "").strip()),
             "from_closed": d["stage"] in k["locked_stages"], "to_closed": to_stage in k["locked_stages"], "may_reopen": may_reopen}
    verdict = engine.run("close.move", {"facts": facts})
    if not verdict.get("ok"):
        _bad(verdict.get("say") or "not_allowed", 409)


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
                                   "cess_pct": k["cess_pct"], "round_to": k["round_to"], "rebate_statuses": reg["rebate_statuses"],
                                   "rebate_upto": reg["rebate_upto"], "rebate_most": reg["rebate_most"]})
    assert t["total"] == 7424040 and t["relief"] == 107062.5, t
    assert regime_of(k, "firm", "new")["id"] == "firm" and regime_of(k, "huf", "old")["id"] == "old" and regime_of(k, "huf", "")["id"] == "new"
    assert engine.run("compute.hp", {"nav": 2340000, "std_pct": 30, "loss_cap": 200000}) == {"std": 702000, "net": 1638000}
    assert engine.run("compute.hp", {"nav": -500000, "std_pct": 30, "loss_cap": 200000}) == {"std": 0, "net": -200000}
    assert _ddmmyyyy("13-Jun-2025") == "13/06/2025"
    assert engine.run("close.move", {"facts": {"to_filed": True, "signed": False, "has_ack": True}})["say"] == "need_signoff"
    print("compute self-check OK")
