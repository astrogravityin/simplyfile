"""Who may open what: people, groups, and allow/deny rules per screen and per function.

One resolver answers every question — the menu, the API guard, "why can't Ravi see this?" — so the
screen and the server can never disagree.

    owner                         → everything, always (the way back in can never be locked)
    admin screen                  → owner ONLY. No rule, group or request can open it to anyone else.
    any DENY on the screen/function for the person or a group they are in → no
    any ALLOW                     → yes
    nothing said                  → open to every account

The admin screens — People & access (with sign-up and SMTP), Portal activity, Visitors, Memory watch,
How to Use pages — are the portal owner's alone (owner decision, 2026-09-17). Rules exist for the
portal's OWN screens: "Everyone" is a built-in group every account is in, so a deny on Everyone shuts
a screen for all but owners, and an allow for a group reopens nothing a deny has shut. The Check tab
shows the outcome and the reason for any person.

A host portal hands install() its catalog: [{id, label, group, icon, admin?, functions?: [{id, label}]}].
Routes guard themselves with `Depends(screen("video"))` or `Depends(screen("video", "draft"))`.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from core import auth, engine, lists, mailer, store


def say(key: str, **values) -> str:
    return engine.say("access.messages", key, **values)


def limit(key: str) -> int:
    return int(engine.setting("access.settings", key))


def role_ids() -> list[str]:
    return [r["id"] for r in engine.run("people.roles")]


def migrate_roles() -> None:
    """Once per portal (2026-09-17): "editor" used to mean every ordinary account. It now means someone
    who may publish in the builders, so the accounts that were editors become members. The owner
    promotes whoever should build."""
    with store._LOCK:  # noqa: SLF001
        s = store.read("settings", {})
        if int(s.get("roles_version") or 1) >= 2:
            return
        rows = store.users()
        for u in rows:
            if u.get("role") == "editor":
                u["role"] = "member"
        if rows:
            store.write("users", rows)
        store.write("settings", s | {"roles_version": 2})

EVERYONE = "everyone"
#: The framework's own screens. `admin` = owner only, always; rules and requests cannot open them.
CORE_SCREENS = [
    {"id": "access", "label": "People & access", "group": "Admin", "icon": "users", "admin": True},
    {"id": "activity", "label": "Portal activity", "group": "Admin", "icon": "clock", "admin": True},
    {"id": "visitors", "label": "Visitors", "group": "Admin", "icon": "eye", "admin": True},
    {"id": "storage", "label": "Storage", "group": "Admin", "icon": "folder", "admin": True},
    {"id": "issues", "label": "Reported issues", "group": "Admin", "icon": "alert", "admin": True},
    {"id": "memory", "label": "Memory watch", "group": "Admin", "icon": "spark", "admin": True},
    {"id": "howto-config", "label": "How to Use pages", "group": "Admin", "icon": "help", "admin": True},
    # 2026-09-17 owner: the builders change what the whole portal does, so they are the owner's alone -
    # hidden from everyone else and closed to grants, like every Admin screen.
    {"id": "ocb", "label": "Ops & chips", "group": "Build", "icon": "chip", "admin": True},
    {"id": "rcb", "label": "Rules", "group": "Build", "icon": "spark", "admin": True},
]
CATALOG: list[dict] = []
_BY_ID: dict[str, dict] = {}

router = APIRouter()


def load(catalog: list[dict] | str | Path) -> None:
    if not isinstance(catalog, list):
        catalog = json.loads(Path(catalog).read_text(encoding="utf-8"))
    CATALOG[:] = [s for s in catalog if s["id"] not in {c["id"] for c in CORE_SCREENS}] + CORE_SCREENS
    _BY_ID.clear()
    _BY_ID.update({s["id"]: s for s in CATALOG})


def label_of(screen_id: str, function_id: str = "") -> str:
    s = _BY_ID.get(screen_id) or {}
    f = next((f for f in s.get("functions", []) if f["id"] == function_id), None)
    return say("function_label", screen=s.get("label", screen_id), function=f["label"]) if f else s.get("label", screen_id)


# --- the data -----------------------------------------------------------------------------------

def data() -> dict:
    d = {"groups": [], "grants": [], "requests": []} | store.read("access", {})
    if not any(g["id"] == EVERYONE for g in d["groups"]):
        d["groups"].insert(0, {"id": EVERYONE, "name": say("everyone_name"), "members": [],
                               "description": say("everyone_description")})
    return d


def save(d: dict) -> None:
    store.write("access", d)


def groups_of(user_id: str, d: dict | None = None) -> list[str]:
    d = d or data()
    return [EVERYONE] + [g["id"] for g in d["groups"] if g["id"] != EVERYONE and user_id in g.get("members", [])]


def subject_label(subject: str, d: dict, users: list[dict]) -> str:
    kind, _, sid = subject.partition(":")
    if kind == "group":
        return next((say("group_label", name=g["name"]) for g in d["groups"] if g["id"] == sid), say("deleted_group"))
    return next((u["email"] for u in users if u["id"] == sid), say("deleted_account"))


# --- the one resolver ---------------------------------------------------------------------------

# A screen that only exists for some people some of the time: nothing to show there = not there.
# The host portal registers a test; the chip access.decide turns a "no" into a refusal, and the shell
# leaves a screen marked `hide_when_denied` out of the menu entirely instead of showing it locked.
# (2026-09-23: Buy a key is invisible until somebody has put a key up for sale.)
_AVAILABLE: dict = {}


_LENDER: list = []


def register_lender(test) -> None:
    """`test(user, screen_id) -> bool`: did the owner lend this Admin screen to this person, today? (The host portal's
    delegations, 2026-10-04.) The chip access.decide opens a lent Admin screen; nothing else can."""
    _LENDER[:] = [test]


def register_available(screen_id: str, test, functions: bool = False) -> None:
    """`test(user) -> bool`: has this person anything at all on that screen right now? With functions=True the test is
    `test(user, function_id)` and answers per button too (a tenant's role: a preparer sees no Sign off)."""
    _AVAILABLE[screen_id] = (lambda u, _fn: test(u)) if not functions else test


def decide(user: dict | None, screen_id: str, function_id: str = "", d: dict | None = None,
           users: list[dict] | None = None) -> dict:
    """{allowed, why} — the facts are gathered here, the decision is chip `access.decide`.
    A function check honours rules on the whole screen AND on that function; a screen check ignores
    function-only rules, so denying one button never hides the page."""
    screen = _BY_ID.get(screen_id) or {}
    facts = {"signed_in": bool(user), "role": (user or {}).get("role", "member"), "known": bool(screen),
             "admin": bool(screen.get("admin")), "screen": screen_id, "label": screen.get("label", screen_id)}
    if user and screen.get("admin") and user.get("role") != "owner" and _LENDER and _LENDER[0](user, screen_id):
        facts["lent"] = "yes"
    if user and screen and _AVAILABLE.get(screen_id) is not None:
        facts["available"] = "yes" if _AVAILABLE[screen_id](user, function_id) else "no"
    if user and screen and user.get("role") != "owner" and not screen.get("admin"):
        if screen.get("gate_chip"):
            facts["gate"] = "yes" if engine.run(screen["gate_chip"], {"role": facts["role"], "action": "view"}) is True else "no"
        d = d or data()
        subjects = {f"user:{user['id']}"} | {f"group:{g}" for g in groups_of(user["id"], d)}
        grants = [g for g in d["grants"] if g["subject"] in subjects and g["screen"] == screen_id
                  and g.get("function", "") in {"", function_id}]
        for effect in ("deny", "allow"):
            hit = next((g for g in grants if g["effect"] == effect), None)
            if hit:
                facts[f"{effect}_by"] = subject_label(hit["subject"], d, users if users is not None else store.users())
                facts[f"{effect}_on"] = label_of(screen_id, hit.get("function", ""))
    return engine.run("access.decide", facts)


def may(user: dict | None, screen_id: str, function_id: str = "") -> bool:
    return decide(user, screen_id, function_id)["allowed"]


def screen(screen_id: str, function_id: str = ""):
    """FastAPI dependency: the signed-in person, if they may use this screen (or this function)."""
    def guard(request: Request) -> dict:
        u = auth.signed_in(request)
        request.state.screen = screen_id              # the activity ledger reads this
        request.state.user = u
        if not may(u, screen_id, function_id):
            raise HTTPException(403, say("no_access", label=label_of(screen_id, function_id)))
        return u
    guard.screen_id = screen_id                       # the selfcheck ratchet looks for this
    guard.function_id = function_id
    return guard


def my_access(u: dict | None) -> dict:
    """What the shell needs: every screen with may/why, and which functions inside it are allowed."""
    if not u:
        return {}
    d, users = data(), store.users()
    out = {}
    for s in CATALOG:
        verdict = decide(u, s["id"], "", d, users)
        out[s["id"]] = {"allowed": verdict["allowed"],
                        "functions": {f["id"]: decide(u, s["id"], f["id"], d, users)["allowed"]
                                      for f in s.get("functions", [])}}
    return out


def bootstrap_extra(request: Request, u: dict | None) -> dict:
    d = data() if u else {}
    return {"catalog": CATALOG, "access": my_access(u),
            "pending_requests": [r["screen"] for r in d.get("requests", [])
                                 if u and r["user_id"] == u["id"] and r["status"] == "pending"]}


# --- the page -----------------------------------------------------------------------------------

# 2026-09-28 owner: "it goes beyond 10 we are gone ... tens of thousands": people are list access_people (core/lists.py)
# - one searched page reaches the screen; the page's rows alone get their personal rules.
def _people_rows(user: dict, args: dict) -> list[dict]:
    if not may(user, "access"):
        raise HTTPException(403, say("no_access", label=label_of("access", "")))
    d = data()
    sets = {g["id"]: set(g.get("members") or []) for g in d["groups"] if g["id"] != EVERYONE}
    group, only = str(args.get("group") or ""), str(args.get("id") or "")
    rows = []
    for u in store.users():
        if (only and u["id"] != only) or (group and u["id"] not in sets.get(group, ())) or (args.get("not_owner") and u.get("role") == "owner"):
            continue
        rows.append(store.public_user(u) | {"groups": [gid for gid, m in sets.items() if u["id"] in m]})
    return rows


def _people_fill(user: dict, rows: list[dict], args: dict) -> list[dict]:
    grants = data()["grants"]
    return [p | {"grants": [g for g in grants if g["subject"] == f"user:{p['id']}"]} for p in rows]


lists.source("access_people", _people_rows, _people_fill)


@router.get("/api/core/access")
def overview(_: dict = Depends(screen("access"))):
    """Groups (few) whole; people are list access_people, so only their COUNT is here, and only the groups' rules -
    a person's own rules come with their row."""
    d = data()
    people = store.users()
    return {"catalog": CATALOG, "grants": [g for g in d["grants"] if g["subject"].startswith("group:")],
            "groups": [{k: v for k, v in g.items() if k != "members"} | {"members_n": len(g.get("members") or [])} for g in d["groups"]],
            "people_n": len(people), "editors_n": sum(1 for u in people if u.get("role") != "owner"),
            "requests": sorted(d["requests"], key=lambda r: r["at"], reverse=True)[:limit("requests_shown")],
            "settings": {k: auth.settings()[k] for k in auth.CORE_SETTINGS},
            "can_email": mailer.configured(), "roles": engine.run("people.roles"),
            "reset_defaults": {k: v for k, v in engine.run("people.reset_password").items() if k != "alphabet"},
            "password_min_length": engine.knobs("auth.password_problem")["min_length"],
            "new_account_role": engine.run("people.new_account_role")}


@router.post("/api/core/access/groups")
def save_group(body: dict = Body(...), _: dict = Depends(screen("access"))):
    name = str(body.get("name") or "").strip()[:limit("group_name_max")]
    if not name:
        raise HTTPException(400, say("group_needs_name"))
    with store._LOCK:                                 # noqa: SLF001
        d = data()
        g = next((g for g in d["groups"] if g["id"] == body.get("id")), None)
        if g is None:
            if any(x["name"].lower() == name.lower() for x in d["groups"]):
                raise HTTPException(409, say("group_exists", name=name))
            g = {"id": store.new_id(), "members": []}
            d["groups"].append(g)
        g["name"], g["description"] = name, str(body.get("description") or "").strip()[:limit("group_description_max")]
        if g["id"] != EVERYONE and ("members" in body or "add" in body or "remove" in body):
            known = {u["id"] for u in store.users()}
            # 2026-09-28 a group of thousands is edited by what CHANGED (add / remove), not by resending everyone
            base = set(body["members"]) if "members" in body else set(g.get("members") or [])
            base = (base | set(body.get("add") or [])) - set(body.get("remove") or [])
            g["members"] = sorted(m for m in base if m in known)
        save(d)
    return {"group": g}


@router.delete("/api/core/access/groups/{group_id}")
def delete_group(group_id: str, _: dict = Depends(screen("access"))):
    if group_id == EVERYONE:
        raise HTTPException(400, say("everyone_builtin"))
    with store._LOCK:                                 # noqa: SLF001
        d = data()
        d["groups"] = [g for g in d["groups"] if g["id"] != group_id]
        d["grants"] = [g for g in d["grants"] if g["subject"] != f"group:{group_id}"]
        save(d)
    return {"ok": True}


def _add_grant(d: dict, subject: str, screen_id: str, function_id: str, effect: str, by: str) -> dict:
    """One rule per subject + screen + function: saving again replaces the effect, never stacks."""
    d["grants"] = [g for g in d["grants"]
                   if not (g["subject"] == subject and g["screen"] == screen_id and g.get("function", "") == function_id)]
    g = {"id": store.new_id(), "subject": subject, "screen": screen_id, "function": function_id,
         "effect": effect, "by": by, "at": store.now()}
    d["grants"].append(g)
    return g


@router.post("/api/core/access/grants")
def save_grant(body: dict = Body(...), me: dict = Depends(screen("access"))):
    subject, screen_id = str(body.get("subject") or ""), str(body.get("screen") or "")
    function_id, effect = str(body.get("function") or ""), body.get("effect")
    if effect not in {"allow", "deny"}:
        raise HTTPException(400, say("allow_or_deny"))
    s = _BY_ID.get(screen_id)
    if not s or (function_id and function_id not in {f["id"] for f in s.get("functions", [])}):
        raise HTTPException(400, say("pick_screen"))
    if s.get("admin"):
        raise HTTPException(400, say("owner_alone_rule", label=s["label"]))
    with store._LOCK:                                 # noqa: SLF001
        d = data()
        kind, _, sid = subject.partition(":")
        ok = (kind == "group" and any(g["id"] == sid for g in d["groups"])) or \
             (kind == "user" and store.user_by_id(sid))
        if not ok:
            raise HTTPException(400, say("pick_subject"))
        g = _add_grant(d, subject, screen_id, function_id, effect, auth.who(me))
        save(d)
    return {"grant": g}


@router.delete("/api/core/access/grants/{grant_id}")
def delete_grant(grant_id: str, _: dict = Depends(screen("access"))):
    with store._LOCK:                                 # noqa: SLF001
        d = data()
        d["grants"] = [g for g in d["grants"] if g["id"] != grant_id]
        save(d)
    return {"ok": True}


@router.get("/api/core/access/check/{user_id}")
def check(user_id: str, _: dict = Depends(screen("access"))):
    """Every screen and function for one person, with the reason — the answer to "why can't they?"."""
    users = store.users()
    u = next((x for x in users if x["id"] == user_id), None)
    if not u:
        raise HTTPException(404, say("no_account"))
    d = data()
    return {"user": store.public_user(u), "groups": groups_of(user_id, d),
            "screens": [{"id": s["id"], "label": s["label"], "group": s.get("group", ""),
                         **decide(u, s["id"], "", d, users),
                         "functions": [{"id": f["id"], "label": f["label"], **decide(u, s["id"], f["id"], d, users)}
                                       for f in s.get("functions", [])]} for s in CATALOG]}


# --- asking for access --------------------------------------------------------------------------

@router.post("/api/core/access/requests")
def request_access(body: dict = Body(...), me: dict = Depends(auth.signed_in)):
    screen_id, function_id = str(body.get("screen") or ""), str(body.get("function") or "")
    if screen_id not in _BY_ID:
        raise HTTPException(400, say("unknown_screen"))
    if _BY_ID[screen_id].get("admin"):
        raise HTTPException(400, say("owner_alone_request"))
    if may(me, screen_id, function_id):
        raise HTTPException(400, say("already_open"))
    from core import limits  # noqa: PLC0415 - 2026-10-01: requests had no limit (and pushed everyone else's out)
    if not limits.allow("access_request", me["id"]):
        raise HTTPException(429, say("too_many_requests"))
    with store._LOCK:                                 # noqa: SLF001
        d = data()
        if any(r["user_id"] == me["id"] and r["screen"] == screen_id and r.get("function", "") == function_id
               and r["status"] == "pending" for r in d["requests"]):
            raise HTTPException(409, say("already_asked"))
        r = {"id": store.new_id(), "user_id": me["id"], "email": me["email"], "screen": screen_id,
             "function": function_id, "reason": str(body.get("reason") or "").strip()[:limit("request_reason_max")],
             "status": "pending", "at": store.now()}
        d["requests"] = (d["requests"] + [r])[-limit("requests_kept"):]
        save(d)
    return {"request": r}


@router.post("/api/core/access/requests/{request_id}/{verdict}")
def review_request(request_id: str, verdict: str, me: dict = Depends(screen("access"))):
    if verdict not in {"approve", "reject"}:
        raise HTTPException(404, say("approve_or_reject"))
    with store._LOCK:                                 # noqa: SLF001
        d = data()
        r = next((x for x in d["requests"] if x["id"] == request_id), None)
        if not r or r["status"] != "pending":
            raise HTTPException(404, say("request_gone"))
        r["status"] = "approved" if verdict == "approve" else "rejected"
        r["reviewed_by"], r["reviewed_at"] = auth.who(me), store.now()
        if verdict == "approve":
            _add_grant(d, f"user:{r['user_id']}", r["screen"], r.get("function", ""), "allow", auth.who(me))
        save(d)
    # Deny wins: an allow for the person does nothing against a deny on a group they are in. Say so,
    # rather than letting "Approved" mean "still shut".
    who = store.user_by_id(r["user_id"])
    verdict_now = decide(who, r["screen"], r.get("function", "")) if who else {"allowed": False, "why": say("account_gone")}
    return {"request": r, "allowed": verdict_now["allowed"], "why": verdict_now["why"]}


# --- people -------------------------------------------------------------------------------------
# People & access is an admin screen, so only an owner reaches these at all. The owner-only checks
# inside stay as a second wall, in case a fork ever marks the screen non-admin.

@router.get("/api/users")
def list_users(request: Request, u: dict = Depends(screen("access"))):
    """One searched page of people (list access_people) - never everyone at once."""
    got = lists.page("access_people", u, dict(request.query_params))
    return got | {"users": got["rows"]}


@router.post("/api/users")
def create_user(request: Request, body: dict = Body(...), me: dict = Depends(screen("access"))):
    """With a password, the owner hands it over themselves. Leave it blank and the portal emails an
    invitation instead, so nobody has to send a password through a chat window."""
    email = (body.get("email") or "").strip().lower()
    username = (body.get("username") or "").strip().lower()
    name = str(body.get("display_name") or body.get("name") or email.split("@")[0]).strip()
    role = body.get("role") if body.get("role") in role_ids() else engine.run("people.new_account_role")
    if role == "owner" and me.get("role") != "owner":
        raise HTTPException(403, say("only_owner_makes_owner"))
    invite = not (body.get("password") or "").strip()
    if invite and not mailer.configured():
        raise HTTPException(400, say("invite_needs_mail"))
    auth.check_fields(email=email, name=name, username=username or None,
                      password=None if invite else body.get("password", ""))
    if store.find_user(email):
        raise auth.fail(409, "taken_email", field="email")
    if username and store.username_taken(username):
        raise auth.fail(409, "taken_username", field="username")
    try:
        # An invited account gets an unguessable placeholder; the invitation link is the only way in.
        u = store.add_user(email, body.get("password") or store.new_id() + store.new_id(),
                           name, role, verified=not invite, username=username)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if invite:
        ttl = int(auth.codes()["invite_ttl_seconds"])
        token = store.make_token("invite", email, ttl)
        subject, text = mailer.compose("invite", product=auth.settings()["product_name"], who=auth.who(me),
                                       url=f"{auth.portal_base(request)}/#/invite?token={token}", days=ttl // 86400)
        try:
            mailer.send(email, subject, text)
        except RuntimeError as e:
            store.delete_user_by_email(email)
            raise HTTPException(502, say("invite_failed", error=e))
    return {"user": store.public_user(u), "invited": invite}


@router.put("/api/core/access/people/{user_id}/role")
def set_role(user_id: str, body: dict = Body(...), me: dict = Depends(auth.owner)):
    role = body.get("role")
    if role not in role_ids():
        raise HTTPException(400, say("bad_role", roles=", ".join(role_ids())))
    with store._LOCK:                                 # noqa: SLF001
        rows = store.users()
        u = next((x for x in rows if x["id"] == user_id), None)
        if not u:
            raise HTTPException(404, say("no_account"))
        if u["id"] == me["id"] and role != "owner":
            raise HTTPException(400, say("no_self_demote"))
        u["role"] = role
        store.write("users", rows)
    return {"user": store.public_user(u)}


@router.post("/api/core/people/{user_id}/password")
def reset_password(user_id: str, body: dict = Body(default={}), me: dict = Depends(auth.owner)):
    """User Access → Reset Password (AUTH.md §6). The owner types a password or has the SERVER make one,
    chooses whether the person must change it at next sign-in and whether it is emailed. The person is
    signed out everywhere. The password is returned only when it was generated or not emailed."""
    target = store.user_by_id(user_id)
    if not target:
        raise HTTPException(404, say("no_account"))
    if target["id"] == me["id"]:
        raise auth.fail(400, "self_reset")
    knobs = engine.run("people.reset_password")
    generated = bool(body.get("generate")) or not str(body.get("password") or "")
    password = "".join(secrets.choice(knobs["alphabet"]) for _ in range(int(knobs["length"]))) if generated \
        else str(body.get("password"))
    if not generated:
        auth.check_fields(password=password, known_user=target.get("username", ""))
    require_change = bool(body.get("require_change", knobs["require_change_default"]))
    store.set_password(target["email"], password, must_change=require_change)
    store.end_sessions_for(target["id"])
    auth.clear_fails(target["email"])
    auth.clear_fails(target.get("username", ""))
    emailed, email_error = False, None
    if body.get("send_email", knobs["email_default"]):
        texts = engine.run("mail.texts")
        subject, text = mailer.compose("reset_by_owner", product=auth.settings()["product_name"], who=auth.who(me),
                                       password=password, change_note=texts["change_note"] if require_change else "")
        try:
            mailer.send(target["email"], subject, text)
            emailed = True
        except RuntimeError as e:
            email_error = str(e)
    return {"user": store.public_user(store.find_user(target["email"])), "require_change": require_change,
            "generated": generated, "emailed": emailed, "email_error": email_error,
            "password": password if (generated or not emailed) else None}


@router.delete("/api/users/{user_id}")
def remove_user(user_id: str, me: dict = Depends(screen("access"))):
    if user_id == me["id"]:
        raise HTTPException(400, say("no_self_remove"))
    target = store.user_by_id(user_id)
    if target and target.get("role") == "owner" and me.get("role") != "owner":
        raise HTTPException(403, say("only_owner_removes_owner"))
    try:
        store.delete_user(user_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    with store._LOCK:                                 # noqa: SLF001 - no rule may outlive its person
        d = data()
        for g in d["groups"]:
            g["members"] = [m for m in g.get("members", []) if m != user_id]
        d["grants"] = [g for g in d["grants"] if g["subject"] != f"user:{user_id}"]
        save(d)
    return {"ok": True}


@router.put("/api/core/settings")
def put_core_settings(body: dict = Body(...), _: dict = Depends(auth.owner)):
    return {"settings": auth.save_settings(body)}


if __name__ == "__main__":  # ponytail: one runnable self-check of the resolver
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        store.DATA = Path(tmp)
        load([{"id": "video", "label": "Videos", "functions": [{"id": "draft", "label": "Draft"}]},
              {"id": "books", "label": "Books"}])
        own = store.add_user("o@x.io", "password-1", role="owner")
        ed = store.add_user("e@x.io", "password-2")
        fin = store.add_user("f@x.io", "password-3")
        assert may(own, "memory") and not may(ed, "memory"), "admin screens are the owner's"
        assert may(ed, "video") and may(ed, "video", "draft"), "normal screens are open by default"
        d = data()
        g = {"id": "fin", "name": "Finance", "members": [fin["id"]]}
        d["groups"].append(g)
        _add_grant(d, "group:everyone", "books", "", "deny", "t")
        _add_grant(d, "group:fin", "books", "", "allow", "t")
        _add_grant(d, f"user:{ed['id']}", "video", "draft", "deny", "t")
        _add_grant(d, f"user:{fin['id']}", "memory", "", "allow", "t")
        save(d)
        assert not may(fin, "books"), "deny wins over allow, even a narrower allow"
        assert may(own, "books"), "an owner can never be locked out"
        assert may(ed, "video") and not may(ed, "video", "draft"), "a function deny never hides the screen"
        assert not may(fin, "memory"), "no rule opens an admin screen to anyone but an owner"
        assert decide(ed, "books")["why"].startswith('Denied for group "Everyone"'), decide(ed, "books")
        _add_grant(d, "group:everyone", "books", "", "allow", "t")
        assert len([x for x in d["grants"] if x["screen"] == "books" and x["subject"] == "group:everyone"]) == 1, \
            "saving a rule again replaces it"
    print("core.access self-check OK")
