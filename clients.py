"""Clients & years - SimplyFile's client master (2026-10-03 client voice note: "master data is the client's name, email,
bank details ... partners' details ... if we input it once, it will be there every year").

One row per assessee, shared by the whole firm (a CA office works one register, not one per person): name, PAN,
status, address, contacts, GST, bank accounts, partners, and per assessment year the form, audit flag and stage.
Statuses, the PAN shape, stages and years are chip clients.settings; every word is chip ui.clients.
Two checks a typist misses are made here: the PAN's 4th letter must match the status (H = HUF, F = firm ...), and a
GSTIN must carry the same PAN in characters 3-12.
"""
from __future__ import annotations

import re
import threading

from fastapi import HTTPException

from core import engine, lists
from core import store

FILE = "sf_clients.json"
_LOCK = threading.Lock()  # ponytail: one lock for the whole register; per-client locks if many staff save at once


def settings() -> dict:
    return engine.run("clients.settings")


def say(key: str, **values) -> str:
    return engine.run("ui.clients")[key].format(**values)


def _bad(key: str, **values):
    raise HTTPException(400, say(key, **values))


def _all() -> list[dict]:
    return store.read(FILE, [])


def status_of(sid: str) -> dict | None:
    return next((s for s in settings()["statuses"] if s["id"] == sid), None)


def _txt(v, field: str) -> str:
    """Spaces tidied, cut to the field's length (chip clients.settings max_len)."""
    return re.sub(r"\s+", " ", str(v or "")).strip()[: settings()["max_len"][field]]


def _code(v) -> str:
    return re.sub(r"\s+", "", str(v or "")).upper()


def shape_ok(kind: str, value: str) -> bool:
    return engine.run("clients.shape_ok", {"kind": kind, "value": value}) is True


def clean(body: dict) -> dict:
    """The client as typed -> the client as kept, or a 400 naming the first thing wrong (chip clients.problem)."""
    st = status_of(str(body.get("status") or ""))
    if not st:
        _bad("bad_status")
    name, pan, gst, email = _txt(body.get("name"), "name"), _code(body.get("pan")), _code(body.get("gst")), _txt(body.get("email"), "email")
    problem = engine.run("clients.problem", {"name": name, "pan": pan, "want_letter": st["pan_letter"], "gst": gst, "email": email})
    if problem:
        _bad(problem, pan=pan or "-", letter=pan[3:4], status=st["label"], want=st["pan_letter"], gst=gst, email=email)
    banks = [{f: _code(b.get(f)) if f == "ifsc" else _txt(b.get(f), "bank_field") for f in ("bank", "branch", "type", "account", "ifsc")}
             for b in (body.get("banks") or []) if isinstance(b, dict) and _txt(b.get("account"), "bank_field")]
    for b in banks:
        if b["ifsc"] and not shape_ok("ifsc", b["ifsc"]):
            _bad("bad_ifsc", ifsc=b["ifsc"])
    partners = []
    for p in body.get("partners") or []:
        if not isinstance(p, dict) or not _txt(p.get("name"), "partner_name"):
            continue
        ppan = _code(p.get("pan"))
        if ppan and not shape_ok("pan", ppan):
            _bad("bad_pan", pan=ppan)
        partners.append({"name": _txt(p.get("name"), "partner_name"), "pan": ppan, "share": _txt(p.get("share"), "share")})
    return {"name": name, "pan": pan, "status": st["id"], "relation": _txt(body.get("relation"), "relation"),
            "address": _txt(body.get("address"), "address"), "email": email, "phone": _txt(body.get("phone"), "phone"),
            "gst": gst, "banks": banks, "partners": partners if st["has_partners"] else [],
            "notes": _txt(body.get("notes"), "notes")}


def get(cid: str) -> dict:
    c = next((c for c in _all() if c["id"] == cid), None)
    if not c:
        raise HTTPException(404, say("not_found"))
    return c


def save(user: dict, body: dict, cid: str = "") -> dict:
    data = clean(body)
    with _LOCK:
        rows = _all()
        if any(c["pan"] == data["pan"] and c["id"] != cid for c in rows):
            _bad("pan_taken", pan=data["pan"])
        if cid:
            c = next((c for c in rows if c["id"] == cid), None)
            if not c:
                raise HTTPException(404, say("not_found"))
            c.update(data)
        else:
            c = data | {"id": store.new_id(), "years": {}, "created_at": store.now(), "created_by": user["id"]}
            ay = settings()["current_ay"]
            c["years"][ay] = year_defaults(c)            # a new client starts in this year, carried from the master
            rows.append(c)
        c["updated_at"], c["updated_by"] = store.now(), user["id"]
        store.write(FILE, rows)
        return c


def year_defaults(c: dict) -> dict:
    return {"form": status_of(c["status"])["form"], "audit": False, "stage": settings()["stages"][0]["id"],
            "assigned": "", "ack_no": ""}


def set_year(user: dict, cid: str, ay: str, body: dict) -> dict:
    k = settings()
    if ay not in k["years"]:
        _bad("bad_ay", ay=ay)
    with _LOCK:
        rows = _all()
        c = next((c for c in rows if c["id"] == cid), None)
        if not c:
            raise HTTPException(404, say("not_found"))
        y = c.setdefault("years", {}).setdefault(ay, year_defaults(c))
        if "stage" in body:
            if body["stage"] not in {s["id"] for s in k["stages"]}:
                _bad("bad_stage")
            y["stage"] = body["stage"]
        if "form" in body:
            if body["form"] not in k["forms"]:
                _bad("bad_form")
            y["form"] = body["form"]
        if "audit" in body:
            y["audit"] = bool(body["audit"])
        for f in ("assigned", "ack_no"):
            if f in body:
                y[f] = _txt(body[f], "year_field")
        c["updated_at"], c["updated_by"] = store.now(), user["id"]
        store.write(FILE, rows)
        return c


def archive(user: dict, cid: str, on: bool) -> dict:
    """Archive (or bring back) a client. Nothing is deleted: the master and every year stay, the client only
    moves to the Archived tab. Statements and reconciliations already filed keep pointing at it."""
    with _LOCK:
        rows = _all()
        c = next((c for c in rows if c["id"] == cid), None)
        if not c:
            raise HTTPException(404, say("not_found"))
        if on:
            c["archived_at"], c["archived_by"] = store.now(), user["id"]
        else:
            c.pop("archived_at", None)
            c.pop("archived_by", None)
        c["updated_at"], c["updated_by"] = store.now(), user["id"]
        store.write(FILE, rows)
        return c


def row(c: dict, ay: str) -> dict:
    y = (c.get("years") or {}).get(ay) or {}
    st = status_of(c["status"]) or {}
    return {"id": c["id"], "name": c["name"], "pan": c["pan"], "status": st.get("label", c["status"]),
            "form": y.get("form") or st.get("form", ""), "audit": bool(y.get("audit")), "stage": y.get("stage", ""),
            "in_year": bool(y), "updated_at": c.get("updated_at", ""), "archived_at": c.get("archived_at", "")}


def listed(args: dict) -> list[dict]:
    """The Clients list: `view=archived` is the Archived tab, anything else the active clients."""
    archived = str(args.get("view") or "") == "archived"
    ay = str(args.get("ay") or settings()["current_ay"])
    return [row(c, ay) for c in _all() if bool(c.get("archived_at")) == archived]


lists.source("clients", lambda user, args: listed(args), screen="clients")


def summary(ay: str) -> dict:
    """The headline numbers above the Clients list: active / archived, who is in this year, 3CD audits, per stage."""
    rows = _all()
    live = [c for c in rows if not c.get("archived_at")]
    years = [(c.get("years") or {}).get(ay) for c in live]
    years = [y for y in years if y]
    stages = {s["id"]: 0 for s in settings()["stages"]}
    for y in years:
        stages[y.get("stage", "")] = stages.get(y.get("stage", ""), 0) + 1
    return {"active": len(live), "archived": len(rows) - len(live), "in_year": len(years),
            "audit": sum(1 for y in years if y.get("audit")), "stages": stages}


if __name__ == "__main__":  # ponytail: one runnable self-check - a made-up client and the two cross-checks
    import store as _portal_store  # noqa: F401 - registers this portal's chips, as the app does
    assert shape_ok("pan", "AAAHS1234K") and not shape_ok("ifsc", "HDFC1000700")
    ok = clean({"name": "Sample HUF", "status": "huf", "pan": "AAAHS 1234 K", "gst": "36AAAHS1234K1Z5",
                "banks": [{"bank": "HDFC Bank", "account": "x", "ifsc": "hdfc0000700"}, {"bank": "empty row"}],
                "partners": [{"name": "ignored for a HUF"}]})
    assert ok["pan"] == "AAAHS1234K" and ok["banks"][0]["ifsc"] == "HDFC0000700" and len(ok["banks"]) == 1
    assert ok["partners"] == [], "only firms and LLPs carry partners"
    for bad, why in [({"status": "huf", "pan": "AAAHS1234K"}, "need_name"),
                     ({"name": "x", "status": "individual", "pan": "AAAHS1234K"}, "4th letter H is not an individual"),
                     ({"name": "x", "status": "huf", "pan": "ABCD1234E"}, "a 9-character PAN"),
                     ({"name": "x", "status": "huf", "pan": "AAAHS1234K", "gst": "36AAAHS9999K1Z5"}, "GSTIN of another PAN")]:
        try:
            clean(bad)
            raise AssertionError(why)
        except HTTPException as e:
            assert e.status_code == 400 and e.detail, why
    assert status_of("firm")["form"] == "ITR-5" and status_of("huf")["form"] == "ITR-3"
    print("clients self-check OK")
