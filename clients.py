"""Clients & years - SimplyFile's client master (2026-10-03 client voice note: "master data is the client's name, email,
bank details ... partners' details ... if we input it once, it will be there every year").

One row per assessee, shared by the whole firm (a CA office works one register, not one per person): name, PAN,
status, address, contacts, GST, bank accounts, partners, and per assessment year the form, audit flag and stage.
Statuses, the PAN shape, stages and years are chip clients.settings; every word is chip ui.clients.
Two checks a typist misses are made here: the PAN's 4th letter must match the status (H = HUF, F = firm ...), and a
GSTIN must carry the same PAN in characters 3-12.

Kept in SQL (core/sqlstore.py, db "clients", one row per client; 2026-11-12 W1.1): the register used to be one JSON file
rewritten whole on every save. The old file moves in once (the first read in a data folder) and stays on disk untouched.
"""
from __future__ import annotations

import copy
import json
import re
import threading

from fastapi import HTTPException

from core import engine, limits, lists, sqlstore
from core import store

FILE = "sf_clients.json"   # History's name for a client save (chip changes.watch), and the JSON file moved in once
DB = "clients"
sqlstore.register(DB, """CREATE TABLE IF NOT EXISTS clients (id TEXT PRIMARY KEY, firm_id TEXT NOT NULL DEFAULT '',
    pan TEXT NOT NULL DEFAULT '', archived_at TEXT, created_at TEXT, updated_at TEXT, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS clients_firm ON clients (firm_id, archived_at);
CREATE INDEX IF NOT EXISTS clients_pan ON clients (firm_id, pan);""")
_LOCK = threading.Lock()  # ponytail: one lock per process; several workers need a row lock (W1.1 multi-worker)
_MOVED: set = set()       # data folders whose old JSON register is already in the table


def settings() -> dict:
    return engine.run("clients.settings")


def say(key: str, **values) -> str:
    return engine.run("ui.clients")[key].format(**values)


def _bad(key: str, **values):
    raise HTTPException(400, say(key, **values))


def _moved_in() -> None:
    """The first read in a data folder moves an old JSON register into the table (a register made before 2026-11-12)."""
    if str(store.DATA) in _MOVED:
        return
    if not sqlstore.one(DB, "SELECT 1 AS x FROM clients LIMIT 1"):      # the table first: the old file is read only when empty
        old = [c for c in store.read(FILE, []) or [] if isinstance(c, dict) and c.get("id")]
        with sqlstore.tx(DB) as x:
            for c in old:
                _put(x, c)
    _MOVED.add(str(store.DATA))


def _put(x, c: dict) -> None:
    x.execute("INSERT INTO clients (id, firm_id, pan, archived_at, created_at, updated_at, data) VALUES (?, ?, ?, ?, ?, ?, ?) "
              "ON CONFLICT(id) DO UPDATE SET firm_id = excluded.firm_id, pan = excluded.pan, archived_at = excluded.archived_at, "
              "updated_at = excluded.updated_at, data = excluded.data",
              (c["id"], c.get("firm_id", "") or "", c.get("pan", "") or "", c.get("archived_at") or None, c.get("created_at", "") or "",
               c.get("updated_at", "") or "", json.dumps(c, ensure_ascii=False)))


def _q(where: str = "", args: tuple = ()) -> list[dict]:
    _moved_in()
    return [json.loads(r["data"]) for r in sqlstore.rows(DB, "SELECT data FROM clients" + where + " ORDER BY created_at, id", args)]


def _save(c: dict, old: dict | None) -> dict:
    """One client written (its whole row), then History told as the JSON register told it (name sf_clients.json)."""
    with sqlstore.tx(DB) as x:
        _put(x, c)
    sqlstore._tell(FILE, [old] if old else [], [c])   # noqa: SLF001 - the same watchers store.write called
    return c


def _all() -> list[dict]:
    """Every firm's clients (the portal admin's views, firms.py's "still has clients"); a firm's own screen uses _mine."""
    return _q()


def rows_for_scan() -> list[dict]:
    """The clean-up scan's reader (core/artifacts, chip artifacts.types row "client" reader "clients")."""
    return _all()


def firm_id(user: dict | None) -> str:
    """The register this person works in (firms.py): their firm's, or "" - the portal admin's house register."""
    return (user or {}).get("firm_id") or ""


def _mine(user: dict | None) -> list[dict]:
    return _q(" WHERE firm_id = ?", (firm_id(user),))


def _row(cid: str) -> dict:
    got = _q(" WHERE id = ?", (cid,))
    if not got:
        raise HTTPException(404, say("not_found"))
    return got[0]


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
    return _row(cid)


def save(user: dict, body: dict, cid: str = "") -> dict:
    data = clean(body)
    if "parties" not in body:                        # a save that does not carry the party master (an import, a firm's own row) keeps it
        data.pop("parties")
    with _LOCK:
        _moved_in()
        if sqlstore.one(DB, "SELECT id FROM clients WHERE firm_id = ? AND pan = ? AND id != ?", (firm_id(user), data["pan"], cid)):
            _bad("pan_taken", pan=data["pan"])
        old = None
        if cid:
            c = _row(cid)
            old = copy.deepcopy(c)
            c.update(data)
        else:
            c = data | {"id": store.new_id(), "firm_id": firm_id(user), "years": {}, "created_at": store.now(), "created_by": user["id"]}
            ay = body.get("ay") if body.get("ay") in settings()["years"] else settings()["current_ay"]
            c["years"][ay] = year_defaults(c)            # a new client starts in the year being looked at (else this year)
        c["updated_at"], c["updated_by"] = store.now(), user["id"]
        return _save(c, old)


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
        c = _row(cid)
        old = copy.deepcopy(c)
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
            _save(c, old)
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
        c = _row(cid)
        old = copy.deepcopy(c)
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
        return _save(c, old)


def change_year(cid: str, ay: str, fn) -> dict:
    """Run fn(year) on a client's year under the lock and keep it (the stage, the filings - compute.py decides them)."""
    with _LOCK:
        c = _row(cid)
        old = copy.deepcopy(c)
        y = c.setdefault("years", {}).setdefault(ay, year_defaults(c))
        if fn(y) is not False:
            _save(c, old)
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


def _of_firm(user: dict, cid: str) -> dict:
    """One client of THIS person's firm (2026-10-04: archive found any firm's client by id)."""
    got = _q(" WHERE id = ? AND firm_id = ?", (cid, firm_id(user)))
    if not got:
        raise HTTPException(404, say("not_found"))
    return got[0]


def archive(user: dict, cid: str, on: bool) -> dict:
    """Archive (or bring back) a client and its filings. Nothing is deleted: the master and every year stay, the client
    only moves to the Archived tab. Statements and reconciliations already filed keep pointing at it."""
    with _LOCK:
        c = _of_firm(user, cid)
        old = copy.deepcopy(c)
        _set_archived(c, user, on)
        return _save(c, old)


def archive_many(user: dict, ids: list, on: bool) -> dict:
    """The ticked clients at once (2026-10-04 owner: "multi select and move to Archive"), in one write."""
    ids = [str(x) for x in ids or [] if str(x)]
    if not limits.within(len(ids), settings()["bulk_max"]):
        _bad("bulk_too_many", max=settings()["bulk_max"])
    with _LOCK:
        mine = {c["id"]: c for c in _mine(user)}
        hit = [mine[i] for i in dict.fromkeys(ids) if i in mine]
        for c in hit:
            old = copy.deepcopy(c)
            _set_archived(c, user, on)
            _save(c, old)
    return {"done": len(hit), "message": say("archived_n" if on else "restored_n", n=len(hit))}


def archive_year(user: dict, cid: str, ay: str, on: bool) -> dict:
    """One year's filing alone - the client stays active. A filing never comes back under an archived client
    (chip clients.may_restore_filing)."""
    with _LOCK:
        c = _of_firm(user, cid)
        old = copy.deepcopy(c)
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
        return _save(c, old)


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
    # 2026-11-12 W1.1: the register in SQL - the old JSON moves in once, every save is one row, History still told
    import tempfile
    from pathlib import Path
    kept_data = store.DATA
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        store.DATA = Path(d)
        sqlstore.configure(**({} if sqlstore.cfg()["engine"] == "sqlite" else {"engine": "postgres"}))
        store.write(FILE, [{"id": "c1", "firm_id": "f1", "name": "Old One", "pan": "AAAHS1234K", "status": "huf", "years": {},
                            "created_at": "2026-01-01"}])
        assert [c["id"] for c in _all()] == ["c1"] and get("c1")["name"] == "Old One", "the old JSON register did not move in"
        reads: list = []   # 2026-11-12: a start with rows in the table never reads the old file (TradyFy parsed 3.5 MB per start)
        real_read = store.read
        store.read = lambda n, *a, **kw: (reads.append(n), real_read(n, *a, **kw))[1]
        _MOVED.discard(str(store.DATA))
        _all()
        store.read = real_read
        assert not {FILE} & set(reads), f"the old file was read with rows in the table: {reads}"
        told = []
        store.watch(r"^sf_clients\.json$", lambda n, o, w: told.append((o, w)))
        u1, u2 = {"id": "u1", "firm_id": "f1"}, {"id": "u2", "firm_id": "f2"}
        new = save(u1, {"name": "New Two", "status": "huf", "pan": "AAAHT1234K"})
        assert told[-1][0] == [] and told[-1][1][0]["id"] == new["id"], "History is told of a new client"
        try:
            save(u1, {"name": "Copy", "status": "huf", "pan": "AAAHS1234K"})
            raise AssertionError("a PAN already in this firm's register was taken twice")
        except HTTPException as e:
            assert e.status_code == 400
        assert save(u2, {"name": "Other firm", "status": "huf", "pan": "AAAHS1234K"})["firm_id"] == "f2", "another firm may hold the PAN"
        set_year(u1, "c1", settings()["current_ay"], {"audit": True})
        assert told[-1][0][0]["years"] == {} and get("c1")["years"][settings()["current_ay"]]["audit"] is True, "old and new row told"
        assert archive_many(u1, ["c1", new["id"], "nope"], True)["done"] == 2 and all(c.get("archived_at") for c in _mine(u1))
        assert [c["firm_id"] for c in _mine(u2)] == ["f2"] and len(_all()) == 3, "the tenant wall"
        assert "store.write(FILE" not in Path(__file__).read_text(encoding="utf-8").split("\nif __name__")[0], \
            "the register is never written as one JSON file again"
        sqlstore.configure()
    store.DATA = kept_data
    print("clients self-check OK")
