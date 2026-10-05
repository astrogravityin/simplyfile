"""Delegations - a person lends some of their own powers to a colleague, for a scope and dates (2026-10-04 owner: "delegate
... filing level, client level, all clients for entire year, few clients for entire year or portal level"; chose "lend my
powers").

Rows only: who lent what to whom, for which clients / year / portal screens, from when to when, taken back or not.
Chip delegation.check decides whether one may be made; chip delegation.covers whether one covers an action today.
firms.may adds what is lent to the person's own role grants; core access asks lent_screen() for portal screens.
Whatever a delegate does is recorded as "<delegate> for <lender>" (actor()). Words: ui.delegate.
"""
from __future__ import annotations

import datetime
import threading

from fastapi import HTTPException

from core import access, auth, demo, engine, lists, store

FILE = "sf_delegations"
_LOCK = threading.Lock()


def settings() -> dict:
    return engine.run("delegation.settings", {})


def say(key: str, **v) -> str:
    s = str(engine.run("ui.delegate", {}).get(key, key))
    for k, x in v.items():
        s = s.replace("{" + k + "}", str(x))
    return s


def _all() -> list[dict]:
    return store.read(FILE, [])


def _n(iso: str) -> int:
    return int(str(iso or "0")[:10].replace("-", "") or 0)


def _today() -> int:
    return _n(datetime.date.today().isoformat())


def _covers(d: dict, want: str, cid: str = "", ay: str = "", anywhere: bool = False) -> bool:
    return engine.run("delegation.covers", {
        "kind": d["kind"], "clients": d.get("clients") or [], "d_ay": d.get("ay", ""), "grants": d["grants"],
        "revoked": bool(d.get("revoked_at")), "starts": _n(d["starts"]), "ends": _n(d["ends"]), "today": _today(),
        "want": want, "cid": cid or "", "ay": ay or "", "anywhere": anywhere}) is True


def _to_me(u: dict | None) -> list[dict]:
    return [d for d in _all() if u and d["to_id"] == u.get("id")]


def lent(u: dict | None, wants: list[str], cid: str = "", ay: str = "", anywhere: bool = False) -> tuple[list[str], list[str]]:
    """(grants lent to this person for this action, who lent them). Only rows of the person's own firm count."""
    grants, lenders = [], []
    for d in _to_me(u):
        if d.get("firm_id", "") != (u or {}).get("firm_id", "") or d["kind"] == "portal":
            continue
        hit = [w for w in wants if w and _covers(d, w, cid, ay, anywhere)]
        if hit:
            grants += hit
            lenders.append(d["from_label"])
    return sorted(set(grants)), lenders


def lent_screen(u: dict | None, screen_id: str) -> bool:
    """A portal screen the owner lent this person, today."""
    return any(d["kind"] == "portal" and _covers(d, screen_id) for d in _to_me(u))


def has_any(u: dict | None) -> bool:
    """Delegations shows for someone who can lend (the owner; an approved firm's member with client work) or holds a loan."""
    import firms  # noqa: PLC0415
    f = firms.firm_of(u)
    return firms.is_owner(u) or bool(_to_me(u)) or bool(f and f.get("state") == firms.settings()["working_state"] and _mine_lendable(u))


def actor(u: dict) -> str:
    """Who did it, as it is recorded: the person, and - when a lent power let them - for whom."""
    who = u.get("email") or u.get("id", "")
    return say("on_behalf", who=who, lender=", ".join(u["on_behalf"])) if u.get("on_behalf") else who


# --- the page ----------------------------------------------------------------------------------------------------------

def _label(g: str) -> str:
    s, _, f = g.partition(".")
    return access.label_of(s, f)


def _mine_lendable(u: dict) -> list[str]:
    import firms  # noqa: PLC0415 - firms imports this module
    k = settings()
    if firms.is_owner(u):
        return list(k["portal_screens"])
    own = firms.role_of(u.get("firm_role", ""))["grants"]
    return [g for g in k["lendable"] if g in own]


def _state(d: dict) -> str:
    t = _today()
    return "revoked" if d.get("revoked_at") else "future" if _n(d["starts"]) > t else "ended" if _n(d["ends"]) < t else "active"


def _row(d: dict) -> dict:
    return d | {"state": _state(d), "grant_labels": [_label(g) for g in d["grants"]]}


def page(u: dict) -> dict:
    import clients  # noqa: PLC0415
    import firms  # noqa: PLC0415
    owner = firms.is_owner(u)
    fid = (u or {}).get("firm_id", "")
    rows = _all()
    people = [{"id": x["id"], "name": x.get("name") or x.get("email"), "email": x.get("email", ""), "role": x.get("firm_role", "")}
              for x in store.users() if x["id"] != u["id"] and x.get("role") != "owner" and not demo.visitor(x)
              and ((not owner and x.get("firm_id") == fid and fid) or (owner and not x.get("firm_id")))]
    cs = clients.settings()
    return {"kinds": [k for k in settings()["kinds"] if k["portal"] == owner], "default_days": settings()["default_days"],
            "lendable": [{"id": g, "label": _label(g)} for g in _mine_lendable(u)], "people": people,
            "clients": [] if owner else [{"id": c["id"], "name": c["name"], "pan": c.get("pan", "")} for c in clients._mine(u) if not c.get("archived_at")],  # noqa: SLF001
            "years": cs["years"], "ay": cs["current_ay"], "today": datetime.date.today().isoformat(),
            "given": any(d["from_id"] == u["id"] for d in rows), "received": any(d["to_id"] == u["id"] for d in rows),
            "firm": any(_side(u, "firm")(d) for d in rows)}


def _side(u: dict, side: str):
    """Which delegations a person sees on each table: lent by me, lent to me, the rest of the firm (a firm admin)."""
    import firms  # noqa: PLC0415
    fid = (u or {}).get("firm_id", "")
    head = not firms.is_owner(u) and settings()["head_grant"] in firms.role_of(u.get("firm_role", ""))["grants"]
    return {"given": lambda d: d["from_id"] == u["id"], "received": lambda d: d["to_id"] == u["id"],
            "firm": lambda d: bool(head and fid and d.get("firm_id") == fid and u["id"] not in (d["from_id"], d["to_id"]))}.get(side, lambda d: False)


def listed(u: dict, args: dict) -> list:
    """One table of delegations (args side), searched and paged on the server - chip list.delegations."""
    keep = _side(u, str(args.get("side") or ""))
    return [_row(d) | {"clients_text": ", ".join(d.get("client_names") or [])} for d in reversed(_all()) if keep(d)]


def create(u: dict, body: dict) -> dict:
    import clients  # noqa: PLC0415
    import firms  # noqa: PLC0415
    owner = firms.is_owner(u)
    to = store.user_by_id(str(body.get("to") or "")) or {}
    kind = str(body.get("kind") or "")
    mine_clients = {c["id"]: c["name"] for c in ([] if owner else clients._mine(u))}  # noqa: SLF001
    picked = [c for c in dict.fromkeys(str(x) for x in (body.get("clients") or [])) if c in mine_clients]
    starts, ends = str(body.get("starts") or "")[:10], str(body.get("ends") or "")[:10]
    try:
        days = (datetime.date.fromisoformat(ends) - datetime.date.fromisoformat(starts)).days
    except ValueError:
        days = -1
    grants = [str(g) for g in (body.get("grants") or [])]
    if settings()["with_screen"]:   # a lent button needs its screen too
        grants = list(dict.fromkeys([g.split(".")[0] for g in grants] + grants))
    same = (owner and not to.get("firm_id")) or (not owner and to.get("firm_id") and to.get("firm_id") == u.get("firm_id"))
    v = engine.run("delegation.check", {
        "kind": kind, "kinds": [k["id"] for k in settings()["kinds"]], "from_owner": owner, "self": to.get("id") == u["id"],
        "to_ok": bool(to) and to.get("role") != "owner" and bool(same), "to_in_firm": bool(to.get("firm_id")),
        "grants": grants, "mine": _mine_lendable(u), "n_clients": len(picked), "has_ay": str(body.get("ay") or "") in clients.settings()["years"],
        "days": days, "max_days": settings()["max_days"]})
    if not v["ok"]:
        raise HTTPException(400, say(v["say"]))
    d = {"id": store.new_id(), "firm_id": "" if owner else u.get("firm_id", ""), "kind": kind,
         "from_id": u["id"], "from_label": u.get("name") or auth.who(u), "to_id": to["id"], "to_label": to.get("name") or to.get("email", ""),
         "clients": picked, "client_names": [mine_clients[c] for c in picked],
         "ay": str(body.get("ay") or "") if kind in ("filing", "year_some", "year_all") else "",
         "grants": grants, "starts": starts, "ends": ends, "note": str(body.get("note") or "").strip()[:300],
         "at": store.now(), "revoked_at": "", "revoked_by": ""}
    with _LOCK:
        rows = _all()
        rows.append(d)
        store.write(FILE, rows)
    return _row(d) | {"say": say("d_made")}


def revoke(u: dict, did: str) -> dict:
    """The lender, the firm's admin, or the portal owner may take a delegation back. Nothing is deleted."""
    import firms  # noqa: PLC0415
    with _LOCK:
        rows = _all()
        d = next((x for x in rows if x["id"] == did), None)
        head = d and d.get("firm_id") and d["firm_id"] == u.get("firm_id") and settings()["head_grant"] in firms.role_of(u.get("firm_role", ""))["grants"]
        if not d or not (d["from_id"] == u["id"] or head or firms.is_owner(u)):
            raise HTTPException(404, say("d_gone"))
        if not d.get("revoked_at"):
            d["revoked_at"], d["revoked_by"] = store.now(), auth.who(u)
            store.write(FILE, rows)
    return _row(d) | {"say": say("d_revoked")}


lists.source("delegations", listed, screen="delegate")


if __name__ == "__main__":  # ponytail: dates read, a lent power covers only its own client and year
    import store as _s  # noqa: F401 - registers this portal's chips
    assert _n("2026-10-04") == 20261004 and _n("") == 0
    t = datetime.date.today()
    d = {"kind": "filing", "clients": ["c1"], "ay": "2026-27", "grants": ["compute.signoff"],
         "starts": (t - datetime.timedelta(days=1)).isoformat(), "ends": (t + datetime.timedelta(days=1)).isoformat()}
    assert _covers(d, "compute.signoff", "c1", "2026-27") and not _covers(d, "compute.signoff", "c2", "2026-27")
    assert not _covers(d | {"revoked_at": "x"}, "compute.signoff", "c1", "2026-27") and _covers(d, "compute.signoff", anywhere=True)
    print("delegation OK")
