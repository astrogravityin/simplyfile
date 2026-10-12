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

from core import engine, limits, lists
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


def firm_id(user: dict | None) -> str:
    """The register this person works in (firms.py): their firm's, or "" - the portal admin's house register."""
    return (user or {}).get("firm_id") or ""


def _mine(user: dict | None) -> list[dict]:
    return [c for c in _all() if c.get("firm_id", "") == firm_id(user)]


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
    parties = []                                     # 2026-10-05 the party master: lenders, payees, relatives - typed once, every year
    for p in body.get("parties") or []:
        if not isinstance(p, dict) or not _txt(p.get("name"), "party_name"):
            continue
        ppan = _code(p.get("pan"))
        if ppan and not shape_ok("pan", ppan):
            _bad("bad_pan", pan=ppan)
        parties.append({"name": _txt(p.get("name"), "party_name"), "address": _txt(p.get("address"), "party_address"), "pan": ppan,
                        "relation": _txt(p.get("relation"), "party_relation"), "mode": _code(p.get("mode"))[: settings()["max_len"]["party_mode"]]})
    signer = _code(body.get("signer_pan"))
    if signer and not shape_ok("pan", signer):
        _bad("bad_pan", pan=signer)
    dob = str(body.get("dob") or "").strip()[:10]
    if dob and not shape_ok("date", dob):
        _bad("bad_dob", dob=dob)
    extra = {}
    if st.get("has_company"):                        # 2026-10-11 a company (ITR-6): CIN, incorporation, option, key persons, shareholders
        import company  # noqa: PLC0415 - company imports this module
        extra["company"] = company.clean(body.get("company") or {})
    return extra | {"name": name, "pan": pan, "status": st["id"], "relation": _txt(body.get("relation"), "relation"),
            "dob": dob, "nri": bool(body.get("nri")), "father": _txt(body.get("father"), "relation"), "signer_pan": signer,
            "address": _txt(body.get("address"), "address"), "email": email, "phone": _txt(body.get("phone"), "phone"),
            "gst": gst, "banks": banks, "partners": partners if st["has_partners"] else [], "parties": parties,
            "notes": _txt(body.get("notes"), "notes")}


def get(cid: str) -> dict:
    c = next((c for c in _all() if c["id"] == cid), None)
    if not c:
        raise HTTPException(404, say("not_found"))
    return c


def save(user: dict, body: dict, cid: str = "") -> dict:
    data = clean(body)
    if "parties" not in body:                        # a save that does not carry the party master (an import, a firm's own row) keeps it
        data.pop("parties")
    with _LOCK:
        rows = _all()
        if any(c["pan"] == data["pan"] and c["id"] != cid and c.get("firm_id", "") == firm_id(user) for c in rows):
            _bad("pan_taken", pan=data["pan"])
        if cid:
            c = next((c for c in rows if c["id"] == cid), None)
            if not c:
                raise HTTPException(404, say("not_found"))
            c.update(data)
        else:
            c = data | {"id": store.new_id(), "firm_id": firm_id(user), "years": {}, "created_at": store.now(), "created_by": user["id"]}
            ay = body.get("ay") if body.get("ay") in settings()["years"] else settings()["current_ay"]
            c["years"][ay] = year_defaults(c)            # a new client starts in the year being looked at (else this year)
            rows.append(c)
        c["updated_at"], c["updated_by"] = store.now(), user["id"]
        store.write(FILE, rows)
        return c


def party_key(name: str, pan: str = "") -> str:
    """One party, however a statement spells it: its PAN, else its name without honorifics, spaces or case (chip
    clients.settings party_name_drop)."""
    if pan:
        return _code(pan)
    return re.sub(r"[^a-z0-9]", "", re.sub(settings()["party_name_drop"], "", str(name or "")).lower())


def party_of(c: dict, name: str, pan: str = "") -> dict | None:
    """The client's master entry for this party - by PAN first, then by name."""
    ps = c.get("parties") or []
    return next((p for p in ps if pan and p.get("pan") == _code(pan)), None)         or next((p for p in ps if party_key(p["name"]) == party_key(name)), None)


def learn_parties(user: dict, cid: str, found: list[dict]) -> dict:
    """Statement parties into the master: a new one is added; a known one gets what it lacks (address, PAN). What the CA
    typed is never overwritten."""
    added = filled = 0
    with _LOCK:
        rows = _all()
        c = next((x for x in rows if x["id"] == cid), None)
        if not c:
            raise HTTPException(404, say("not_found"))
        c.setdefault("parties", [])
        for f in found:
            if not f.get("name"):
                continue
            have = party_of(c, f["name"], f.get("pan", ""))
            if not have:
                c["parties"].append({k: f.get(k, "") for k in ("name", "address", "pan", "relation", "mode")})
                added += 1
                continue
            gap = [k for k in ("address", "pan", "relation") if f.get(k) and not have.get(k)]
            for k in gap:
                have[k] = f[k]
            filled += bool(gap)
        if added or filled:
            c["updated_at"], c["updated_by"] = store.now(), user["id"]
            store.write(FILE, rows)
    return {"added": added, "filled": filled, "client": c}


def year_defaults(c: dict) -> dict:
    return {"form": status_of(c["status"])["form"], "audit": False, "stage": settings()["stages"][0]["id"],
            "assigned": "", "ack_no": ""}


def year_of(cid: str, ay: str) -> dict:
    c = get(cid)
    return (c.get("years") or {}).get(ay) or year_defaults(c)


def locked(cid: str, ay: str) -> bool:
    """A closed year (stage in chip close.settings locked_stages) takes no new statements, refs, portal files or notes."""
    return year_of(cid, ay).get("stage") in engine.run("close.settings")["locked_stages"]


def guard_open(cid: str, ay: str) -> None:
    if locked(cid, ay):
        raise HTTPException(409, say("year_closed", ay=ay))


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
        if "form" in body:                                # the stage moves by itself (compute.refresh); filing has its own road
            if body["form"] not in k["forms"]:
                _bad("bad_form")
            y["form"] = body["form"]
        if "audit" in body:
            y["audit"] = bool(body["audit"])
        if "presumptive" in body:                         # 44AD / 44ADA: one advance tax instalment, 15 March (234C)
            y["presumptive"] = bool(body["presumptive"])
        if "tp" in body:                                  # Form 3CEB (s.92E): the due date moves to 30 November
            y["tp"] = bool(body["tp"])
        for f in ("assigned",):
            if f in body:
                y[f] = _txt(body[f], "year_field")
        c["updated_at"], c["updated_by"] = store.now(), user["id"]
        store.write(FILE, rows)
        return c


def change_year(cid: str, ay: str, fn) -> dict:
    """Run fn(year) on a client's year under the lock and keep it (the stage, the filings - compute.py decides them)."""
    with _LOCK:
        rows = _all()
        c = next((c for c in rows if c["id"] == cid), None)
        if not c:
            raise HTTPException(404, say("not_found"))
        y = c.setdefault("years", {}).setdefault(ay, year_defaults(c))
        if fn(y) is not False:
            store.write(FILE, rows)
        return y


def live_years(c: dict) -> dict:
    """A client's filings still in play - an archived filing (alone, or with its client) counts nowhere."""
    return {a: y for a, y in (c.get("years") or {}).items() if not y.get("archived_at")}


def _set_archived(c: dict, user: dict, on: bool) -> None:
    """2026-10-04 owner: "if Parent is Archived child should also be archived". Archiving a client archives every filing
    still live, marked as archived WITH it (chip clients.settings with_parent); Restore brings back exactly those -
    a filing archived on its own before stays archived."""
    now, mark = store.now(), settings()["with_parent"]
    if on:
        c["archived_at"], c["archived_by"] = now, user["id"]
        for y in (c.get("years") or {}).values():
            if not y.get("archived_at"):
                y.update(archived_at=now, archived_by=user["id"], archived_with=mark)
    else:
        c.pop("archived_at", None)
        c.pop("archived_by", None)
        for y in (c.get("years") or {}).values():
            if y.get("archived_with") == mark:
                for f in ("archived_at", "archived_by", "archived_with"):
                    y.pop(f, None)
    c["updated_at"], c["updated_by"] = now, user["id"]


def _of_firm(rows: list[dict], user: dict, cid: str) -> dict:
    """One client of THIS person's firm (2026-10-04: archive found any firm's client by id)."""
    c = next((c for c in rows if c["id"] == cid and c.get("firm_id", "") == firm_id(user)), None)
    if not c:
        raise HTTPException(404, say("not_found"))
    return c


def archive(user: dict, cid: str, on: bool) -> dict:
    """Archive (or bring back) a client and its filings. Nothing is deleted: the master and every year stay, the client
    only moves to the Archived tab. Statements and reconciliations already filed keep pointing at it."""
    with _LOCK:
        rows = _all()
        c = _of_firm(rows, user, cid)
        _set_archived(c, user, on)
        store.write(FILE, rows)
        return c


def archive_many(user: dict, ids: list, on: bool) -> dict:
    """The ticked clients at once (2026-10-04 owner: "multi select and move to Archive"), in one write."""
    ids = [str(x) for x in ids or [] if str(x)]
    if not limits.within(len(ids), settings()["bulk_max"]):
        _bad("bulk_too_many", max=settings()["bulk_max"])
    with _LOCK:
        rows = _all()
        mine = {c["id"]: c for c in rows if c.get("firm_id", "") == firm_id(user)}
        hit = [mine[i] for i in dict.fromkeys(ids) if i in mine]
        for c in hit:
            _set_archived(c, user, on)
        if hit:
            store.write(FILE, rows)
    return {"done": len(hit), "message": say("archived_n" if on else "restored_n", n=len(hit))}


def archive_year(user: dict, cid: str, ay: str, on: bool) -> dict:
    """One year's filing alone - the client stays active. A filing never comes back under an archived client
    (chip clients.may_restore_filing)."""
    with _LOCK:
        rows = _all()
        c = _of_firm(rows, user, cid)
        y = (c.get("years") or {}).get(ay)
        if y is None:
            _bad("no_filing", name=c["name"], ay=ay)
        if on:
            y.update(archived_at=store.now(), archived_by=user["id"], archived_with="")
        else:
            if engine.run("clients.may_restore_filing", {"client_archived": bool(c.get("archived_at"))}) is not True:
                _bad("parent_archived", name=c["name"])
            for f in ("archived_at", "archived_by", "archived_with"):
                y.pop(f, None)
        c["updated_at"], c["updated_by"] = store.now(), user["id"]
        store.write(FILE, rows)
        return c


def row(c: dict, ay: str) -> dict:
    y = (c.get("years") or {}).get(ay) or {}
    st = status_of(c["status"]) or {}
    return {"id": c["id"], "name": c["name"], "pan": c["pan"], "status": st.get("label", c["status"]),
            "form": y.get("form") or st.get("form", ""), "audit": bool(y.get("audit")), "stage": y.get("stage", ""),
            "in_year": bool(y), "updated_at": c.get("updated_at", ""), "archived_at": c.get("archived_at", ""),
            "year_archived": bool(y.get("archived_at"))}


def listed(args: dict, user: dict | None = None) -> list[dict]:
    """The Clients list (this person's firm's only): `view=archived` is the Archived tab, anything else the active clients."""
    archived = str(args.get("view") or "") == "archived"
    ay = str(args.get("ay") or settings()["current_ay"])
    # which tab: chip clients.in_tab (the Archived tab also holds an active client whose filing was archived alone)
    view = "archived" if archived else ""
    return [row(c, ay) for c in _mine(user) if engine.run("clients.in_tab", {
        "view": view, "client_archived": bool(c.get("archived_at")),
        "filing_archived": bool(((c.get("years") or {}).get(ay) or {}).get("archived_at"))}) is True]


lists.source("clients", lambda user, args: listed(args, user), screen="clients")


def count(user: dict | None) -> int:
    return len(_mine(user))


def summary(ay: str, user: dict | None = None) -> dict:
    """The headline numbers above the Clients list: active / archived, who is in this year, 3CD audits, per stage."""
    rows = _mine(user)
    live = [c for c in rows if not c.get("archived_at")]
    years = [live_years(c).get(ay) for c in live]
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
