"""Firms - SimplyFile is many tenants (2026-10-04 owner): a CA firm signs up, gives its PAN, TAN, GSTIN, ICAI FRN, the
owner's masked Aadhaar and the phone linked to its tax papers, uploads the papers, and waits; the portal admin checks
them by hand (DigiLocker later) and approves. Until then the firm's people see no Filing screen. The firm admin then
adds the team, each with a role. An individual or a HUF can sign up the same way to file their own return: a firm of
kind `self`, whose one client is itself.

A firm is a tenant: every client carries the firm_id of the firm that made it, and another firm's client does not exist
for you - not even for the portal admin, who has their own house register (firm_id "") and the Approvals screen.

This module gathers facts and keeps files. Every rule is a chip: firm.settings (kinds, papers, states, the review clock),
firm.roles, firm.problem, firm.ready, firm.move, firm.may, firm.sla, firm.client_room, firm.team_ok. Words: ui.firm.
"""
from __future__ import annotations

import re
import secrets
import threading
from pathlib import Path

from fastapi import HTTPException, Request

import delegation
from core import access, auth, engine, lists, mailer, ops, store

FILE = "sf_firms"
_LOCK = threading.Lock()  # ponytail: one lock for every firm; per-firm locks if sign-ups ever queue
FILING = ("clients", "intake", "recon", "compute", "analytics", "itrimport")


def settings() -> dict:
    return engine.run("firm.settings")


def say(key: str, **values) -> str:
    return ops.template(engine.run("ui.firm")[key], values)


def _all() -> list[dict]:
    return store.read(FILE, [])


def _save(rows: list[dict]) -> None:
    store.write(FILE, rows)


def kind_of(kid: str) -> dict:
    return next((k for k in settings()["kinds"] if k["id"] == kid), None) or settings()["kinds"][0]


def role_of(rid: str) -> dict:
    return next((r for r in engine.run("firm.roles")["rows"] if r["id"] == rid), {"id": rid, "grants": [], "label": rid})


def firm_of(u: dict | None) -> dict | None:
    fid = (u or {}).get("firm_id")
    return next((f for f in _all() if f["id"] == fid), None) if fid else None


def is_owner(u: dict | None) -> bool:
    return engine.run("people.is_owner", {"role": (u or {}).get("role") or ""}) is True


def acts_as_admin(u: dict | None) -> bool:
    """The portal owner, or someone the owner lent Firm approvals to (delegation.py) - never from inside a firm."""
    return is_owner(u) or (not (u or {}).get("firm_id") and delegation.lent_screen(u, "approvals"))


def tenant(u: dict | None) -> str:
    """Whose register this person works in: their firm's, or "" (the portal admin's own house register)."""
    return (u or {}).get("firm_id") or ""


# --- the one question: may this person do this, here? ------------------------------------------------------------------

def may(u: dict | None, want: str, fn: str = "", client_firm: str | None = None, cid: str = "", ay: str = "",
        anywhere: bool = False) -> dict:
    """Chip firm.may over the person's role grants plus what colleagues lent them for this client and year (delegation.py).
    `on_behalf` names the lenders when only a lent power let this through - the action is then recorded as done for them."""
    f = firm_of(u)
    own = role_of((u or {}).get("firm_role", ""))["grants"]
    facts = {"is_owner": is_owner(u), "has_firm": bool(f), "state": (f or {}).get("state", ""),
             "working_state": settings()["working_state"], "grants": own,
             "want": want, "want_fn": f"{want}.{fn}" if fn else "",
             "same_firm": client_firm is None or client_firm == tenant(u)}
    v = engine.run("firm.may", facts)
    if v["ok"] or not f:
        return v | {"on_behalf": []}
    extra, lenders = delegation.lent(u, [want, facts["want_fn"]], cid, ay, anywhere)
    if not extra:
        return v | {"on_behalf": []}
    v2 = engine.run("firm.may", facts | {"grants": own + extra})
    return v2 | {"on_behalf": lenders if v2["ok"] else []}


def refuse(verdict: dict, u: dict | None = None):
    f = firm_of(u) or {}
    state = next((s["label"] for s in settings()["states"] if s["id"] == f.get("state")), "")
    return HTTPException(int(verdict["code"]), say(verdict["say"], state=state))


def gate(screen_id: str, fn: str = ""):
    """FastAPI dependency for every Filing route: the framework's screen check, then firm.may - and when the path names
    a client, that client must be this person's firm's."""
    inner = access.screen(screen_id, fn)

    def guard(request: Request) -> dict:
        u = inner(request)
        cid = request.path_params.get("cid")
        client_firm = None
        if cid:
            import clients  # noqa: PLC0415 - clients imports nothing of ours; this keeps it that way
            client_firm = clients.get(cid).get("firm_id", "")
        v = may(u, screen_id, fn, client_firm, cid or "", request.path_params.get("ay", ""))
        if not v["ok"]:
            raise refuse(v, u)
        return u | {"on_behalf": v["on_behalf"]} if v["on_behalf"] else u
    guard.screen_id, guard.function_id = screen_id, fn          # the selfcheck ratchet looks for these
    return guard


def install() -> None:
    """The Filing menu stays shut until the firm is approved (access.decide's `available` fact)."""
    access.register_lender(delegation.lent_screen)
    access.register_available("delegate", delegation.has_any)
    for s in FILING:
        access.register_available(s, lambda u, fn, s=s: may(u, s, fn, anywhere=True)["ok"], functions=True)


# --- the application ---------------------------------------------------------------------------------------------------

def _txt(v, most: int) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:most]


def _code(v) -> str:
    return re.sub(r"[\s-]+", "", str(v or "")).upper()


def _clean(f: dict, body: dict) -> dict:
    """Only the fields this kind of account has, tidied. Codes upper-cased and unspaced; digits kept as digits."""
    st = settings()
    ml, out = st["max_len"], {}
    for k in kind_of(f["kind"])["fields"]:
        if k not in body:
            continue
        v = body[k]
        out[k] = (_code(v) if k in st["code_fields"] else re.sub(r"\D", "", str(v or ""))[:16]
                  if k in st["digit_fields"] else _txt(v, ml.get(k, ml["field"])))
    if "phone" in out:
        out["phone"] = out["phone"][-int(st["phone_digits"]):]   # +91 / 0 prefixes dropped
    if "email" in out:
        out["email"] = out["email"].lower()
    if "consent" in body:
        out["consent_at"] = store.now() if body["consent"] else ""
    return out


def problem(f: dict) -> str:
    k = kind_of(f["kind"])
    return engine.run("firm.problem", {x: f.get(x, "") for x in k["fields"]} | {
        "consent": bool(f.get("consent_at")), "required": k["required"], "pan_letters": k["pan_letters"]})


def ready(f: dict) -> dict:
    k = kind_of(f["kind"])
    return engine.run("firm.ready", {"problem": problem(f), "docs_required": k["docs_required"],
                                     "docs_have": [d["kind"] for d in f.get("docs", [])]})


def _note(f: dict, u: dict, action: str, note: str = "") -> None:
    f.setdefault("history", []).append({"at": store.now(), "by": u["id"], "who": auth.who(u), "action": action, "note": note})


def _set_user(uid: str, **fields) -> None:
    with store._LOCK:  # noqa: SLF001 - the framework's users file
        rows = store.users()
        for x in rows:
            if x["id"] == uid:
                for k, v in fields.items():
                    if v is None:
                        x.pop(k, None)
                    else:
                        x[k] = v
        store.write("users", rows)


def start(u: dict, kind: str) -> dict:
    """Make this person's firm (a draft) and make them its first member - firm admin, or self-filer."""
    if firm_of(u):
        raise HTTPException(409, say("has_firm"))
    if is_owner(u) and not settings()["owner_may_start"]:          # the portal admin keeps the house register
        raise HTTPException(409, say("owner_house"))
    if kind not in {k["id"] for k in settings()["kinds"]}:
        raise HTTPException(400, say("bad_kind"))
    f = {"id": store.new_id(), "kind": kind, "state": settings()["states"][0]["id"], "email": u.get("email", ""), "name": "",
         "docs": [], "created_at": store.now(), "created_by": u["id"]}
    _note(f, u, "created")
    with _LOCK:
        _save(_all() + [f])
    _set_user(u["id"], firm_id=f["id"], firm_role=kind_of(kind)["first_role"])
    return f


def _mine(u: dict, grant: str = "firm") -> tuple[list[dict], dict]:
    """(all firms, this person's firm) - refused unless their role holds `grant`."""
    rows = _all()
    f = next((x for x in rows if x["id"] == tenant(u)), None)
    if not f:
        raise HTTPException(404, say("no_firm"))
    if grant not in role_of(u.get("firm_role", ""))["grants"]:
        raise HTTPException(403, say("role_no"))
    return rows, f


def update(u: dict, body: dict) -> dict:
    with _LOCK:
        rows, f = _mine(u)
        if f["state"] not in settings()["editable_states"]:
            raise HTTPException(409, say("not_editable"))
        new = _clean(f, body)
        bad = problem(f | new)
        if bad in {f"bad_{x}" for x in settings()["refuse_fields"]}:   # a full Aadhaar number is never written, not even once
            raise HTTPException(400, say(bad))
        f.update(new)
        f["updated_at"] = store.now()
        _save(rows)
        return _public(f)


def add_doc(u: dict, kind: str, name: str, data: bytes) -> dict:
    k = settings()
    ext = Path(name).suffix.lower()
    if ext not in k["doc_exts"]:
        raise HTTPException(400, say("bad_ext", exts=" ".join(k["doc_exts"])))
    if len(data) > int(k["doc_max_mb"]) * 1024 * 1024:
        raise HTTPException(400, say("too_big", mb=k["doc_max_mb"]))
    with _LOCK:
        rows, f = _mine(u)
        fk = kind_of(f["kind"])
        if kind not in fk["docs_required"] + fk["docs_optional"]:
            raise HTTPException(400, say("bad_doc"))
        if f["state"] not in k["editable_states"]:
            raise HTTPException(409, say("not_editable"))
        folder = store.DATA / "sf_firms" / f["id"]
        folder.mkdir(parents=True, exist_ok=True)
        for old in f["docs"]:
            if old["kind"] == kind:
                (folder / old["file"]).unlink(missing_ok=True)
        doc = {"id": store.new_id(), "kind": kind, "name": _txt(name, 120), "size": len(data), "at": store.now()}
        doc["file"] = doc["id"] + ext
        (folder / doc["file"]).write_bytes(data)
        f["docs"] = [d for d in f["docs"] if d["kind"] != kind] + [doc]
        _save(rows)
        return f


def doc_path(u: dict, fid: str, did: str) -> tuple[Path, str]:
    """A paper is seen by the portal admin and by the firm's own profile keepers - nobody else."""
    f = next((x for x in _all() if x["id"] == fid), None)
    if not f or not (acts_as_admin(u) or (tenant(u) == fid and "firm" in role_of(u.get("firm_role", ""))["grants"])):
        raise HTTPException(404, say("no_doc"))
    d = next((d for d in f["docs"] if d["id"] == did), None)
    if not d:
        raise HTTPException(404, say("no_doc"))
    return store.DATA / "sf_firms" / fid / d["file"], d["name"]


def _mail(to: str, subject_key: str, body_key: str, **values) -> None:
    """Best effort: no mail set up, or a failed send, never blocks a decision (it is on the screen either way)."""
    if not to or not mailer.configured():
        return
    try:
        mailer.send(to, say(subject_key, **values), say(body_key, **values))
    except RuntimeError:
        pass


def move(u: dict, fid: str, action: str, note: str = "") -> dict:
    """Submit (the firm), approve / return / reject / suspend / restore / reopen (the portal admin) - chip firm.move."""
    with _LOCK:
        rows = _all()
        f = next((x for x in rows if x["id"] == fid), None)
        admin = acts_as_admin(u)
        if not f or not (admin or tenant(u) == fid):
            raise HTTPException(404, say("no_firm"))
        by = "admin" if admin and tenant(u) != fid else u.get("firm_role", "")
        if action == "submit":
            r = ready(f)
            if r["say"]:
                raise HTTPException(400, say(r["say"], missing=", ".join(_doc_label(x) for x in r["missing"])))
        if action in settings()["needs_note"] and not _txt(note, 5):
            raise HTTPException(400, say("need_note"))
        to = engine.run("firm.move", {"facts": {"action": action, "state": f["state"], "by": by}})
        if not to["to"]:
            raise HTTPException(409, say(to["say"]))
        f["state"] = to["to"]
        f[f"{to['to']}_at"] = store.now()
        _note(f, u, action, _txt(note, settings()["max_len"]["note"]))
        _save(rows)
    k = settings()
    if to["to"] == k["working_state"] and kind_of(f["kind"])["self_client"]:
        _self_client(f)
    admin = next((x["email"] for x in store.users() if is_owner(x)), "")
    if to["to"] == k["waiting_state"]:
        _mail(admin, "mail_submitted_subject", "mail_submitted_body", firm=f.get("name"), hours=settings()["review_hours"])
    else:
        _mail(f.get("email"), "mail_decided_subject", "mail_decided_body", firm=f.get("name"), state=to["to"], note=note)
    return f | {"say": say(to["say"])}


def _doc_label(kid: str) -> str:
    return next((d["label"] for d in settings()["docs"] if d["id"] == kid), kid)


def _self_client(f: dict) -> None:
    """A self-filer's one client is themselves, made from the approved application (once)."""
    import clients  # noqa: PLC0415
    if any(c.get("firm_id") == f["id"] for c in clients._all()):  # noqa: SLF001
        return
    status = kind_of(f["kind"])["client_status"].get(f.get("pan", "")[3:4], "individual")
    owner = store.user_by_id(f["created_by"]) or {"id": f["created_by"]}
    clients.save(owner | {"firm_id": f["id"]}, {"name": f["name"], "pan": f["pan"], "status": status,
                                                "email": f.get("email", ""), "phone": f.get("phone", ""), "address": f.get("address", "")})


def may_add_client(u: dict, count: int) -> None:
    f = firm_of(u)
    most = kind_of(f["kind"])["max_clients"] if f else 0
    if engine.run("firm.client_room", {"count": count, "most": most}) is not True:
        raise HTTPException(409, say("client_room", n=most))


# --- the page: my firm, the queue --------------------------------------------------------------------------------------

def _public(f: dict, admin: bool = False) -> dict:
    k = settings()
    sub = f.get("submitted_at", "")
    r = ready(f)
    steps = engine.run("firm.steps", {"details_ok": not problem(f), "docs_ok": not r["missing"], "state": f["state"],
                                      "working_state": k["working_state"]})
    out = f | {"ready": r, "steps": steps, "editable": f["state"] in k["editable_states"], "kind_label": kind_of(f["kind"])["label"]}
    if sub and f["state"] == k["waiting_state"]:
        waited = store.seconds_since(sub) / 3600
        out |= {"waited_hours": round(waited, 1), "sla": engine.run("firm.sla", {"waited_hours": waited, "review_hours": k["review_hours"]})}
    if admin:
        out["members"] = len([x for x in store.users() if x.get("firm_id") == f["id"]])
    return out


def me(u: dict) -> dict:
    f = firm_of(u)
    role = role_of(u.get("firm_role", ""))
    out = {"settings": settings(), "roles": engine.run("firm.roles")["rows"], "role": role, "is_owner": is_owner(u),
           "firm": _public(f) if f else None}
    if f and "team" in role["grants"]:
        out["team"] = len(team(u))   # the people themselves: list.firm_team, one searched page at a time
    return out


def queue(state: str = "") -> list[dict]:
    rows = [_public(f, admin=True) for f in _all() if not state or f["state"] == state]
    wait = settings()["waiting_state"]
    return sorted(rows, key=lambda f: (f["state"] != wait, f.get("submitted_at") or f.get("created_at", "")))


# the approvals queue, one searched page at a time (chip list.firm_requests): waiting first, oldest first - `queue_at` is that order
lists.source("firm_requests", lambda u, args: [f | {"queue_at": f"{int(f['state'] != settings()['waiting_state'])}{f.get('submitted_at') or f.get('created_at', '')}"}
                                               for f in queue(str(args.get("state") or ""))], screen="approvals")


def counts() -> dict:
    out = {s["id"]: 0 for s in settings()["states"]}
    for f in _all():
        out[f["state"]] = out.get(f["state"], 0) + 1
    return out


# --- the team ----------------------------------------------------------------------------------------------------------

def team(u: dict) -> list[dict]:
    fid = tenant(u)
    return [{"id": x["id"], "name": x.get("name", ""), "email": x["email"], "role": x.get("firm_role", ""),
             "last_seen": x.get("last_seen", ""), "must_change": bool(x.get("must_change_password"))}
            for x in store.users() if x.get("firm_id") == fid]


lists.source("firm_team", lambda u, args: team(u) if "team" in role_of(u.get("firm_role", ""))["grants"] and firm_of(u) else [], screen="firm")


def _team_check(u: dict, role: str, admins_after: int) -> None:
    r = role_of(role)
    bad = engine.run("firm.team_ok", {"admins_after": admins_after, "role_ok": bool(r.get("assignable"))})
    if bad:
        raise HTTPException(400, say(bad))


def add_member(request: Request, u: dict, body: dict) -> dict:
    """The firm admin adds a person: a new account inside the firm with a one-time password (shown once, must be
    changed at first sign-in), or an emailed invitation when the portal sends mail."""
    _, f = _mine(u, "team")
    if f["state"] != settings()["working_state"]:
        raise HTTPException(409, say("firm_wait", state=f["state"]))
    role = str(body.get("role") or "")
    _team_check(u, role, 1)
    email = str(body.get("email") or "").strip().lower()
    name = _txt(body.get("name"), settings()["max_len"]["owner_name"]) or email.split("@")[0]
    auth.check_fields(email=email, name=name)
    if store.find_user(email):
        raise auth.fail(409, "taken_email", field="email")
    knobs = engine.run("people.reset_password")
    password = "".join(secrets.choice(knobs["alphabet"]) for _ in range(int(knobs["length"])))
    nu = store.add_user(email, password, name, engine.run("people.new_account_role"), verified=True)
    store.set_password(email, password, must_change=True)
    _set_user(nu["id"], firm_id=f["id"], firm_role=role)
    emailed = False
    if mailer.configured():
        try:
            mailer.send(email, say("mail_welcome_subject", firm=f.get("name")),
                        say("mail_welcome_body", firm=f.get("name"), who=auth.who(u), url=auth.portal_base(request),
                            email=email, password=password, role=role_of(role)["label"]))
            emailed = True
        except RuntimeError:
            pass
    return {"member": next(m for m in team(u) if m["id"] == nu["id"]), "emailed": emailed,
            "password": None if emailed else password}


def set_member(u: dict, uid: str, role: str | None) -> dict:
    """A new role, or (role None) out of the firm. The account stays; it simply no longer belongs here."""
    _, f = _mine(u, "team")
    members = team(u)
    m = next((x for x in members if x["id"] == uid), None)
    if not m:
        raise HTTPException(404, say("no_member"))
    head = settings()["head_role"]
    admins = sum(1 for x in members if x["role"] == head and x["id"] != uid) + (role == head)
    _team_check(u, role or head, admins)
    if role is None:
        _set_user(uid, firm_id=None, firm_role=None)
        store.end_sessions_for(uid)
    else:
        _set_user(uid, firm_role=role)
    return {"team": team(u)}


if __name__ == "__main__":  # ponytail: the chips this module leans on, asked directly
    import store as _portal_store  # noqa: F401 - registers this portal's chips, as the app does
    k = settings()
    assert {x["id"] for x in k["kinds"]} == {"ca_firm", "self"}
    f = {"kind": "ca_firm", "name": "Prabhakar PVR & Co", "pan": "AAFFP1234C", "tan": "HYDP12345E", "gstin": "36AAFFP1234C1Z5",
         "frn": "012345S", "owner_name": "P V Rao", "aadhaar_last4": "4821", "phone": "9849012345", "email": "o@pvr.in",
         "consent_at": "x", "docs": [{"kind": "pan_card"}]}
    assert problem(f) == "" and ready(f)["say"] == "need_docs" and "tan_letter" in ready(f)["missing"]
    assert _clean({"kind": "ca_firm"}, {"phone": "+91 98490 12345", "pan": "aaffp 1234c", "aadhaar_last4": "48-21", "x": 1}) == \
        {"phone": "9849012345", "pan": "AAFFP1234C", "aadhaar_last4": "4821"}
    v = engine.run("firm.may", {"has_firm": True, "state": "approved", "grants": role_of("preparer")["grants"],
                                "want": "compute", "want_fn": "compute.signoff"})
    assert v["say"] == "role_no", "a preparer does not sign off"
    print("firms self-check OK")
