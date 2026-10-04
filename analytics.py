"""Firm analytics - how a CA firm's year is going and where its next work comes from (2026-10-04 owner).

Facts only: each client-year of the firm (its computation, due date, filings, sign-off) is gathered here; chip
analytics.client decides its deadline bucket, whether it was on time and which advisory leads it raises, and chip
analytics.rollup adds them up. Settings: analytics.settings. Words: ui.analytics. Colours: page.analytics.
"""
from __future__ import annotations

import datetime

import clients
import compute
from core import engine


def settings() -> dict:
    return engine.run("analytics.settings", {})


def _day(n) -> datetime.date | None:
    s = str(n or "")
    return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8])) if len(s) == 8 else None


def _prev(ay: str) -> str:
    a = int(ay[:4]) - 1
    return f"{a}-{str(a + 1)[2:]}"


def _one(c: dict, ay: str, k: dict, today: datetime.date) -> tuple[dict, list[dict]]:
    """One client-year: the facts, the chip's verdict on them, and who signed off / filed it."""
    y = c["years"][ay]
    imp = (y.get("imported") or {}).get("figures")
    try:
        d = None if imp else compute.compute(c["id"], ay)     # an imported return speaks for itself: its figures as filed
    except Exception:  # noqa: BLE001 - a year with nothing in it yet still counts on the radar
        d = None
    if imp:
        d = {"tax": {"total": imp.get("tax_net", 0)}, "interest": imp.get("interest", 0), "open_red": 0, "income": imp.get("income", 0),
             "interest_auto": {"a": imp.get("i234a", 0), "b": imp.get("i234b", 0), "c": imp.get("i234c", 0)},
             "balance": {"kind": "refund", "amount": imp["refund"]} if imp.get("refund") else {"kind": "payable", "amount": imp.get("payable", 0)}}
    filings = [f for f in y.get("filings") or [] if f.get("status") != "withdrawn"]
    kinds = [f["kind"] for f in filings]
    due = _day(compute.dates(c["id"], ay)["due"])
    days_left = (due - today).days if due else 0
    bal = (d or {}).get("balance") or {}
    auto = (d or {}).get("interest_auto") or {}
    ri = (d or {}).get("refund_interest") or {}
    refund = bal.get("amount", 0) if bal.get("kind") == "refund" else 0
    facts = {"filed": bool(filings), "days_left": days_left, "first_kind": kinds[0] if kinds else "", "kinds": kinds,
             "interest_a": auto.get("a", 0) or 0, "interest_bc": (auto.get("b", 0) or 0) + (auto.get("c", 0) or 0),
             "refund": refund, "open_red": (d or {}).get("open_red", 0) or 0}
    v = engine.run("analytics.client", facts | {x: k[x] for x in ("week_days", "month_days", "refund_lead_min", "interest_lead_min",
                                                                   "on_time_kinds", "late_kinds", "rework_kinds")})
    row = clients.row(c, ay)
    out = {"id": c["id"], "name": c["name"], "form": row["form"], "status": row["status"], "stage": row["stage"], "audit": row["audit"],
           "assigned": (y.get("assigned") or "").strip(), "due": due.isoformat() if due else "", "days_left": days_left,
           "filed_n": 1 if filings else 0, "income": (d or {}).get("income", 0) or 0, "tax": ((d or {}).get("tax") or {}).get("total", 0) or 0, "refund": refund,
           "payable": bal.get("amount", 0) if bal.get("kind") == "payable" else 0, "interest": (d or {}).get("interest", 0) or 0,
           "interest_bc": facts["interest_bc"], "refund_interest": ri.get("interest", 0) if ri.get("eligible") else 0} | v
    acts = [{"who": f.get("by") or "", "what": "filed"} for f in filings]
    if (d or {}).get("signoff"):
        acts.append({"who": d["signoff"].get("by") or "", "what": "signed"})
    return out, acts


def report(user: dict, ay: str = "") -> dict:
    k = settings()
    cs = clients.settings()
    ay = ay if ay in cs["years"] else cs["current_ay"]
    today = datetime.date.today()
    live = [c for c in clients._mine(user) if not c.get("archived_at")]
    rows, acts = [], []
    for c in live:
        if ay in (c.get("years") or {}):
            r, a = _one(c, ay, k, today)
            rows.append(r)
            acts += a
    def income_of(c: dict, a: str) -> float:
        cur = compute.current_filing(c["years"][a])
        if cur:
            return (cur.get("figures") or {}).get("income") or 0
        return next((r["income"] for r in rows if r["id"] == c["id"]), 0) if a == ay else 0
    history = [{"ay": a, "id": c["id"], "filed_n": 1 if compute.current_filing(c["years"][a]) else 0, "income": income_of(c, a)}
               for a in cs["years"] for c in live if a in (c.get("years") or {}) and a <= ay]
    prev_ids = [c["id"] for c in live if _prev(ay) in (c.get("years") or {})]
    older_ids = [c["id"] for c in live if any(a < _prev(ay) for a in (c.get("years") or {}))]
    recent_ids = [c["id"] for c in live if {_prev(ay), ay} & set(c.get("years") or {})]
    roll = engine.run("analytics.rollup", {"rows": rows, "prev_ids": prev_ids, "history": history, "acts": acts,
                                           "older_ids": older_ids, "recent_ids": recent_ids})
    names = {c["id"]: c["name"] for c in live}
    leads = {lid: [r for r in rows if r.get(lid)] for lid in k["leads"] if lid not in ("not_renewed", "lapsed", "growing", "shrinking")}
    leads["not_renewed"] = [{"id": i, "name": names[i]} for i in roll["not_renewed"]]
    leads["lapsed"] = [{"id": i, "name": names[i]} for i in roll["lapsed"]]
    leads["growing"], leads["shrinking"] = [], []
    for c in live:                                   # the latest two years with an income: the chip says growing / shrinking
        seen = sorted((h["ay"], h["income"]) for h in history if h["id"] == c["id"] and h["income"])
        if len(seen) >= 2:
            t = engine.run("analytics.trend", {"now": seen[-1][1], "before": seen[-2][1], "grow_pct": k["grow_pct"], "drop_pct": k["drop_pct"]})
            if t["trend"]:
                leads[t["trend"]].append({"id": c["id"], "name": c["name"], "pct": t["pct"], "from": seen[-2][0], "to": seen[-1][0]})
    radar = sorted([r for r in rows if r["bucket"] != "filed"], key=lambda r: r["days_left"])
    return {"ay": ay, "years": cs["years"], "today": today.isoformat(), "roll": roll, "radar": radar, "leads": leads,
            "bucket_order": k["buckets"], "lead_order": k["leads"], "top_n": k["top_n"], "grow_pct": k["grow_pct"], "drop_pct": k["drop_pct"],
            "history_years": sorted({h["ay"] for h in history})}
