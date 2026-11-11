"""Who may open what: people, groups, and allow/deny rules per screen and per function.

One resolver answers every question — the menu, the API guard, "why can't Ravi see this?" — so the
screen and the server can never disagree. The model is the studio's, the same as SteadyMove's core (owner
2026-10-19: "apply the studio's access logic to all the portals", day one "nobody loses anything"):

    available    → a screen (or button) the host registered a test for, with nothing on it for this person → no,
                   before every rule, the owner included (register_available; functions=True answers per button).
    owner        → everything, always (the way back in can never be locked)
    admin screen → owner ONLY - or a person the owner LENT it to today (register_lender, the host's delegations).
                   No rule, group or request can open it to anyone else.
    DENY WINS    → any deny for the person, a group they are in, or a group those inherit from → no.
    MANAGED      → in a group other than Catch All: they see ONLY the union of what their groups, the
                   groups those INHERIT from and their own rules allow. Nothing allows it → no.
    UNASSIGNED   → in no group: the built-in group CATCH ALL decides (its allows, minus its denies),
                   with the person's own rules on top. New sign-ups land here.
    INHERIT      → a group may name ONE parent (`inherits`); members get the parent's rules live, plus the
                   group's own. A loop is refused when saved, and the reader stops at one anyway.

Catch All (id `catch_all`, name from chip access.messages, renamable, never deletable, no member list) is
"what an account nobody has placed sees". A personal rule alone does NOT make a person managed (chip
knob access.decide personal_rule_manages, off): approving a request writes a personal allow, and that must
never empty an unassigned person's menu. A screen nobody allowed is closed; chip knob access.settings
new_screens_to_catch_all adds each newly catalogued non-admin screen to Catch All once (`seen_screens`).

The old built-in group "Everyone" is RETIRED. Day one (`_migrate`, once, on the first read of the access
file with a catalog loaded, saved): Catch All gets an allow for every non-admin screen an unassigned account
could open under the old rules (not denied and not "Only allowed" on Everyone); Everyone's denies become
Catch All's denies; Everyone's allows and every "only" rule go (a function-level "only", which the screen
never offered, opens wider - nobody loses); every existing group inherits Catch All. Every menu is the
same the next morning - the self-check below proves it against the old resolver on a fixture.

The facts are gathered here; the verdict and every sentence are chip `access.decide`.

The admin screens — People & access (with sign-up and SMTP), Portal activity, Visitors, Memory watch,
How to Use pages — are the portal owner's alone (owner decision, 2026-09-17). The Check tab shows the
outcome and the reason for any person.

A host portal hands install() its catalog: [{id, label, group, icon, admin?, functions?: [{id, label}]}].
Routes guard themselves with `Depends(screen("video"))` or `Depends(screen("video", "draft"))`.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from core import auth, engine, lists, mailer, notify, store


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

CATCH_ALL = "catch_all"          # the built-in group for every account in no group (stable id; the name is a word)
_RETIRED_EVERYONE = "everyone"   # the old built-in group; read only by the day-one migration
#: The framework's own screens. `admin` = owner only, always; rules and requests cannot open them.
CORE_SCREENS = [
    {"id": "access", "label": "People & access", "group": "Admin", "icon": "users", "admin": True},
    {"id": "activity", "label": "Portal activity", "group": "Admin", "icon": "clock", "admin": True},
    {"id": "visitors", "label": "Visitors", "group": "Admin", "icon": "eye", "admin": True},
    {"id": "storage", "label": "Storage", "group": "Admin", "icon": "folder", "admin": True},
    {"id": "issues", "label": "Reported issues", "group": "Admin", "icon": "alert", "admin": True},
    {"id": "memory", "label": "Memory watch", "group": "Admin", "icon": "spark", "admin": True},
    {"id": "agents", "label": "Agents", "group": "Admin", "icon": "agent", "admin": True},          # 2026-10-24 core/agents.py
    {"id": "connect-ai", "label": "Connect your AI", "group": "Admin", "icon": "plug", "admin": True},    # 2026-10-24 core/mcp.py
    {"id": "howto-config", "label": "How to Use pages", "group": "Admin", "icon": "help", "admin": True},
    {"id": "menus", "label": "Menu builder", "group": "Admin", "icon": "menu", "admin": True},           # 2026-10-26 core/menus.py
    # 2026-09-17 owner: the builders change what the whole portal does, so they are the owner's alone -
    # hidden from everyone else and closed to grants, like every Admin screen.
    {"id": "ocb", "label": "Ops & chips", "group": "Build", "icon": "chip", "admin": True},
    {"id": "rcb", "label": "Rules", "group": "Build", "icon": "spark", "admin": True},
]
CATALOG: list[dict] = []
BASE: list[dict] = []            # the catalog as the host gave it; CATALOG = BASE with the owner's Menu builder edits on top
_BY_ID: dict[str, dict] = {}

router = APIRouter()


def load(catalog: list[dict] | str | Path) -> None:
    if not isinstance(catalog, list):
        catalog = json.loads(Path(catalog).read_text(encoding="utf-8"))
    core_ids = {c["id"] for c in CORE_SCREENS}
    # 2026-10-26 a portal may take a framework screen off its menu ({"id": "ocb", "hidden": true} in its catalog) -
    # still the owner's alone and still opens by its link; nothing else about it can be changed from the host.
    off = {s["id"] for s in catalog if s["id"] in core_ids and s.get("hidden")}
    BASE[:] = [s for s in catalog if s["id"] not in core_ids] + [c | ({"hidden": True} if c["id"] in off else {}) for c in CORE_SCREENS]
    reapply()


def reapply() -> None:
    """Rebuild CATALOG from BASE and the Menu builder's edits (core/menus.py) - at start and after every save."""
    from core import menus  # noqa: PLC0415 - menus reads the store; access is imported first
    CATALOG[:] = menus.apply(BASE)
    _BY_ID.clear()
    _BY_ID.update({s["id"]: s for s in CATALOG})
    # 2026-10-24 Connect your AI: one function per tool of the portal's chip mcp.tools (gated per tool, deny wins)
    try:
        tools = engine.run("mcp.tools")["tools"]
    except Exception:  # noqa: BLE001 - a portal with no tools chip yet: the screen has no tool functions
        tools = []
    _BY_ID["connect-ai"] = _BY_ID["connect-ai"] | {"functions": [{"id": r["function"], "label": r.get("title") or r["name"]}
                                                                for r in tools if r.get("function")]}
    CATALOG[:] = [_BY_ID.get(s["id"], s) for s in CATALOG]


def label_of(screen_id: str, function_id: str = "") -> str:
    s = _BY_ID.get(screen_id) or {}
    f = next((f for f in s.get("functions", []) if f["id"] == function_id), None)
    return say("function_label", screen=s.get("label", screen_id), function=f["label"]) if f else s.get("label", screen_id)


# --- the data -----------------------------------------------------------------------------------

def _open_screens() -> list[str]:
    """Every screen a rule may speak about: the catalog minus the owner's admin screens."""
    return [s["id"] for s in CATALOG if not s.get("admin")]


def _raw() -> dict:
    return {"groups": [], "grants": [], "requests": []} | store.read("access", {})


def _migrate(d: dict) -> None:
    """Day one of Catch All (2026-10-19), in place. See the module docstring; run once, by data()."""
    everyone = f"group:{_RETIRED_EVERYONE}"
    shut = {g["screen"] for g in d["grants"] if g["subject"] == everyone and not g.get("function")
            and g["effect"] in ("deny", "only")}
    kept = []
    for g in d["grants"]:
        if g["subject"] == everyone:
            if g["effect"] == "deny":                    # a deny for every account stays a deny for every account
                kept.append(g | {"subject": f"group:{CATCH_ALL}"})
            continue                                     # its allows are the Catch All list below; "only" = left out
        if g["effect"] in ("allow", "deny"):             # "only" lived on Everyone alone
            kept.append(g)
    by, at = say("migration_by"), store.now()
    d["grants"] = kept + [{"id": store.new_id(), "subject": f"group:{CATCH_ALL}", "screen": sid, "function": "",
                           "effect": "allow", "by": by, "at": at} for sid in _open_screens() if sid not in shut]
    groups = [g for g in d["groups"] if g["id"] not in (_RETIRED_EVERYONE, CATCH_ALL)]
    for g in groups:
        g.setdefault("inherits", CATCH_ALL)             # My Family keeps everything it saw, plus its own allows
    d["groups"] = [{"id": CATCH_ALL, "name": say("catch_all_name"), "description": say("catch_all_description"),
                    "members": []}] + groups
    d["seen_screens"] = [s["id"] for s in CATALOG]
    d["catch_all_since"] = at


def _add_new_screens(d: dict) -> bool:
    """A non-admin screen the portal has gained since the last look joins Catch All once (chip knob
    access.settings new_screens_to_catch_all); either way it is remembered, so a later removal sticks."""
    seen = set(d.get("seen_screens") or [])
    every = [s["id"] for s in CATALOG]                   # 2026-10-26 owner: a draft is remembered too, so putting it
    if set(every) <= seen:                               # live never opens it to everyone - Access Control decides
        return False
    new = [sid for sid in _open_screens() if sid not in seen]
    if engine.setting("access.settings", "new_screens_to_catch_all"):
        by, at = say("migration_by"), store.now()
        d["grants"] += [{"id": store.new_id(), "subject": f"group:{CATCH_ALL}", "screen": sid, "function": "",
                         "effect": "allow", "by": by, "at": at} for sid in new
                        if not any(g["subject"] == f"group:{CATCH_ALL}" and g["screen"] == sid and not g.get("function")
                                   for g in d["grants"])]
    d["seen_screens"] = sorted(seen | set(every))
    return True


def data() -> dict:
    """The access file. With a catalog loaded, the first read migrates it to Catch All (saved, once) and every
    read adds a newly catalogued screen to Catch All (saved, once). No catalog yet = nothing decided or saved."""
    d = _raw()
    if not CATALOG:
        return d
    if not any(g["id"] == CATCH_ALL for g in d["groups"]) or not {s["id"] for s in CATALOG} <= set(d.get("seen_screens") or []):
        with store._LOCK:                                 # noqa: SLF001
            d = _raw()
            changed = not any(g["id"] == CATCH_ALL for g in d["groups"])
            if changed:
                _migrate(d)
            if _add_new_screens(d) or changed:
                save(d)
    return d


def save(d: dict) -> None:
    store.write("access", d)


def groups_of(user_id: str, d: dict | None = None) -> list[str]:
    """The groups this person was PUT in. Catch All is never one of them: it is the absence of a choice."""
    d = d or data()
    return [g["id"] for g in d["groups"] if g["id"] != CATCH_ALL and user_id in g.get("members", [])]


def chain(group_id: str, d: dict) -> list[str]:
    """This group, then the groups it inherits from, nearest first (INHERIT). Stops at a loop or a missing group."""
    by_id = {g["id"]: g for g in d["groups"]}
    out: list[str] = []
    while group_id and group_id in by_id and group_id not in out:
        out.append(group_id)
        group_id = by_id[group_id].get("inherits") or ""
    return out


def subject_label(subject: str, d: dict, users: list[dict], via: dict | None = None) -> str:
    kind, _, sid = subject.partition(":")
    if kind == "group":
        names = {g["id"]: g["name"] for g in d["groups"]}
        if sid not in names:
            return say("deleted_group")
        if (via or {}).get(sid):
            return say("inherited_label", name=names[sid], via=names.get(via[sid], ""))
        return say("group_label", name=names[sid])
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


def facts_for(user: dict | None, screen_id: str, function_id: str = "", d: dict | None = None,
              users: list[dict] | None = None) -> dict:
    """What chip access.decide is told - facts only, no verdict. A function check honours rules on the whole
    screen AND on that function; a screen check ignores function-only rules, so denying one button never
    hides the page. Two lanes of rules: the person's OWN (themselves, their groups, the groups those inherit
    from - Catch All too when inherited) and CATCH ALL's (for when they are in no group); the chip picks."""
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
        mine = groups_of(user["id"], d)
        via: dict[str, str] = {}                          # a parent group -> the person's own group it came through
        for gid in mine:
            for parent in chain(gid, d)[1:]:
                if parent not in mine:
                    via.setdefault(parent, gid)
        own = {f"user:{user['id']}"} | {f"group:{g}" for g in mine} | {f"group:{g}" for g in via}
        here = [g for g in d["grants"] if g["screen"] == screen_id and g.get("function", "") in {"", function_id}]
        facts["in_group"] = bool(mine)
        facts["has_personal"] = any(g["subject"] == f"user:{user['id']}" for g in d["grants"])
        who = users if users is not None else None
        for lane, subjects in (("", own), ("ca_", {f"group:{CATCH_ALL}"})):
            for effect in ("deny", "allow"):
                hit = next((g for g in here if g["subject"] in subjects and g["effect"] == effect), None)
                if hit:
                    who = who if who is not None else store.users()
                    facts[f"{lane}{effect}_by"] = subject_label(hit["subject"], d, who, via if lane == "" else None)
                    facts[f"{lane}{effect}_on"] = label_of(screen_id, hit.get("function", ""))
    return facts


def decide(user: dict | None, screen_id: str, function_id: str = "", d: dict | None = None,
           users: list[dict] | None = None) -> dict:
    """{allowed, why} — the facts are gathered here, the decision is chip `access.decide`."""
    return engine.run("access.decide", facts_for(user, screen_id, function_id, d, users))


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
    sets = {g["id"]: set(g.get("members") or []) for g in d["groups"] if g["id"] != CATCH_ALL}
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


# 2026-10-19 owner "allow flexi search here" (Groups & rules): the screens a rule can name, searched forgivingly on the
# server by list access_screens (op fuzzy_rows) - the page only shows the ids that come back.
def _screen_rows(user: dict, args: dict) -> list[dict]:
    if not may(user, "access"):
        raise HTTPException(403, say("no_access", label=label_of("access", "")))
    return [{"id": s["id"], "label": s["label"], "group": s.get("group") or "", "order": i,
             "functions_text": " ".join(f["label"] for f in s.get("functions") or [])}
            for i, s in enumerate(CATALOG) if not s.get("admin")]


lists.source("access_screens", _screen_rows)


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
            "new_account_role": engine.run("people.new_account_role"), "catch_all": CATCH_ALL,
            "new_group_inherits": CATCH_ALL if engine.setting("access.settings", "new_group_inherits_catch_all") else ""}


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
            g = {"id": store.new_id(), "members": [],
                 "inherits": CATCH_ALL if engine.setting("access.settings", "new_group_inherits_catch_all") else ""}
            d["groups"].append(g)
        g["name"], g["description"] = name, str(body.get("description") or "").strip()[:limit("group_description_max")]
        if g["id"] == CATCH_ALL and (body.get("members") or body.get("add") or body.get("inherits")):
            raise HTTPException(400, say("catch_all_no_members"))
        if g["id"] != CATCH_ALL and "inherits" in body:   # INHERIT: one parent, or none; never a loop
            parent = str(body.get("inherits") or "")
            if parent and not any(x["id"] == parent for x in d["groups"]):
                raise HTTPException(400, say("inherit_unknown"))
            if parent and g["id"] in chain(parent, d):
                raise HTTPException(400, say("inherit_loop", name=next(x["name"] for x in d["groups"] if x["id"] == parent)))
            g["inherits"] = parent
        if g["id"] != CATCH_ALL and ("members" in body or "add" in body or "remove" in body):
            known = {u["id"] for u in store.users()}
            # 2026-09-28 a group of thousands is edited by what CHANGED (add / remove), not by resending everyone
            base = set(body["members"]) if "members" in body else set(g.get("members") or [])
            base = (base | set(body.get("add") or [])) - set(body.get("remove") or [])
            g["members"] = sorted(m for m in base if m in known)
        save(d)
    return {"group": g}


@router.delete("/api/core/access/groups/{group_id}")
def delete_group(group_id: str, _: dict = Depends(screen("access"))):
    if group_id == CATCH_ALL:
        raise HTTPException(400, say("catch_all_builtin"))
    with store._LOCK:                                 # noqa: SLF001
        d = data()
        gone = next((g for g in d["groups"] if g["id"] == group_id), {})
        for g in d["groups"]:                          # a child inherits from the deleted group's own parent
            if g.get("inherits") == group_id:
                g["inherits"] = gone.get("inherits") or ""
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
    names = {g["id"]: g["name"] for g in d["groups"]}
    # WHY, before the screens: in no group -> Catch All decides; otherwise each group with the parents it inherits
    return {"user": store.public_user(u), "groups": groups_of(user_id, d),
            "chains": [[names[x] for x in chain(gid, d)] for gid in groups_of(user_id, d)],
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
    notify.fire("access_request", user_id=me["id"], who=auth.who(me), screen=label_of(screen_id, function_id), reason=r["reason"])
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
    notify.fire("access_decided", user_id=r["user_id"], screen=label_of(r["screen"], r.get("function", "")), verdict=r["status"],
                why=verdict_now["why"])
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


@router.put("/api/core/access/people/{user_id}/block")
def set_blocked(user_id: str, body: dict = Body(...), me: dict = Depends(auth.owner)):
    """2026-11-05 (ValueStream CC Clean-up): a blocked person cannot sign in, and every sign-in they hold ends now."""
    with store._LOCK:                                 # noqa: SLF001
        rows = store.users()
        u = next((x for x in rows if x["id"] == user_id), None)
        if not u:
            raise HTTPException(404, say("no_account"))
        if u["id"] == me["id"]:
            raise HTTPException(400, say("no_self_block"))
        u["blocked"] = body.get("blocked") is True
        store.write("users", rows)
    if u["blocked"]:
        store.end_sessions_for(user_id)
    return {"user": store.public_user(u) | {"blocked": u["blocked"]}}


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


def _legacy_may(d: dict, u: dict, screen_id: str, function_id: str = "") -> bool:
    """The WHOLE resolver as it was until 2026-10-19, facts and verdict (Everyone built in; available -> owner -> lent
    Admin screen -> admin -> role gate -> deny -> allow -> open; the studio's "only" read too, though this template's
    save_grant never wrote one). Kept ONLY as the oracle for the self-check and the live-data proof: the day-one
    migration must give every person the very same screens AND buttons it gave."""
    s = _BY_ID.get(screen_id)
    if not u or not s:
        return False
    if _AVAILABLE.get(screen_id) is not None and not _AVAILABLE[screen_id](u, function_id):
        return False
    if u.get("role") == "owner":
        return True
    if s.get("admin"):
        return bool(_LENDER and _LENDER[0](u, screen_id))
    if s.get("gate_chip") and engine.run(s["gate_chip"], {"role": u.get("role", "member"), "action": "view"}) is not True:
        return False
    subjects = {f"user:{u['id']}", f"group:{_RETIRED_EVERYONE}"} | {
        f"group:{g['id']}" for g in d["groups"] if u["id"] in g.get("members", [])}
    here = [g for g in d["grants"] if g["screen"] == screen_id and g.get("function", "") in {"", function_id}]
    mine = [g["effect"] for g in here if g["subject"] in subjects]
    if "deny" in mine:
        return False
    if "allow" in mine:
        return True
    return not any(g["subject"] == f"group:{_RETIRED_EVERYONE}" and g["effect"] == "only" for g in here)


def _menu(u: dict, d: dict, users: list[dict]) -> dict:
    return {s["id"]: (decide(u, s["id"], "", d, users)["allowed"],
                      {f["id"]: decide(u, s["id"], f["id"], d, users)["allowed"] for f in s.get("functions", [])})
            for s in CATALOG}


def _legacy_menu(u: dict, d: dict) -> dict:
    return {s["id"]: (_legacy_may(d, u, s["id"]), {f["id"]: _legacy_may(d, u, s["id"], f["id"]) for f in s.get("functions", [])})
            for s in CATALOG}


def prove_migration(old: dict, people: list[dict]) -> dict:
    """The day-one proof on a COPY of an access file (nothing is saved): every person's screens and buttons under the
    old resolver against the migrated file under chip access.decide. Returns {people, changed: [ids], catch_all}."""
    import copy  # noqa: PLC0415
    old = {"groups": [], "grants": [], "requests": []} | copy.deepcopy(old)
    new = copy.deepcopy(old)
    if not any(g["id"] == CATCH_ALL for g in new["groups"]):
        _migrate(new)
    changed = [p["id"] for p in people if _legacy_menu(p, old) != _menu(p, new, people)]
    return {"people": len(people), "changed": changed,
            "catch_all": sorted({g["screen"] for g in new["grants"] if g["subject"] == f"group:{CATCH_ALL}"
                                 and g["effect"] == "allow" and not g.get("function")})}


def writes_real_data(main_block: str) -> bool:
    """A module self-check that reaches access but never points the store at a temp folder: since 2026-10-19 data()
    SAVES its day-one migration, so it would write the portal's real data/access.json (the studio's core/find.py did)."""
    return "access." in main_block and ".DATA = " not in main_block


if __name__ == "__main__":  # ponytail: one runnable self-check of the resolver and the day-one migration
    import copy
    import tempfile

    def refused(fn, *a, **kw) -> int:
        try:
            fn(*a, **kw)
        except HTTPException as e:
            return e.status_code
        return 0

    def opens(u: dict) -> list[str]:
        return [s for s, (ok, _) in _menu(u, data(), store.users()).items() if ok]

    SCREENS = [{"id": "video", "label": "Videos", "functions": [{"id": "draft", "label": "Draft"}]},
               {"id": "books", "label": "Books"}, {"id": "sound", "label": "Sound from Video"},
               {"id": "yt", "label": "YouTube Transcript"}, {"id": "keys", "label": "Keys"}]
    with tempfile.TemporaryDirectory() as tmp:
        # --- 1. day one: an access file written by the OLD model (Everyone, "only") ----------------------------
        store.DATA = Path(tmp)
        load(SCREENS)
        own = store.add_user("o@x.io", "password-1", role="owner")
        fam = [store.add_user(f"m{i}@x.io", f"password-m{i}") for i in range(3)]
        lone = store.add_user("u@x.io", "password-u")          # unassigned, no rule
        pdeny = store.add_user("pd@x.io", "password-pd")       # unassigned, a personal deny
        pallow = store.add_user("pa@x.io", "password-pa")      # unassigned, a personal allow on an "only" screen
        people = [own, *fam, lone, pdeny, pallow]

        def rule(subj: str, scr: str, eff: str, fn: str = "") -> dict:
            return {"id": store.new_id(), "subject": subj, "screen": scr, "function": fn, "effect": eff, "by": "t",
                    "at": "2026-10-01T00:00:00"}
        old = {"groups": [{"id": "everyone", "name": "Everyone", "members": [], "description": ""},
                          {"id": "fam", "name": "My Family", "members": [p["id"] for p in fam], "description": ""}],
               "grants": [rule("group:everyone", "sound", "only"), rule("group:everyone", "yt", "only"),
                          rule("group:fam", "sound", "allow"), rule("group:fam", "yt", "allow"),
                          rule("group:everyone", "keys", "deny"), rule("group:everyone", "video", "allow"),
                          rule("group:everyone", "video", "deny", "draft"), rule(f"user:{fam[0]['id']}", "books", "deny"),
                          rule(f"user:{pdeny['id']}", "books", "deny"), rule(f"user:{pallow['id']}", "sound", "allow")],
               "requests": []}
        store.write("access", old)
        # the template's two extras ride through unchanged: an Admin screen LENT for the day (the host's delegations)
        # and availability per screen and per button (a tenant's role: a preparer sees no Sign off)
        register_lender(lambda u, sid: u["id"] == fam[1]["id"] and sid == "activity")
        register_available("video", lambda u, fn: not (fn == "draft" and u["id"] == fam[2]["id"]), functions=True)
        register_available("books", lambda u: u["id"] != pallow["id"])
        before = {p["id"]: _legacy_menu(p, old) for p in people}
        assert prove_migration(old, people)["changed"] == [], "the live-data proof finds a changed menu on the fixture"
        _real_migrate = _migrate                              # bite (in memory): a migration that drops INHERIT is caught
        globals()["_migrate"] = lambda d_: (_real_migrate(d_), d_["groups"][1].pop("inherits"))
        assert prove_migration(old, people)["changed"], "the live-data proof cannot bite"
        globals()["_migrate"] = _real_migrate
        # bite (in memory): a migration that forgets to make old groups inherit Catch All empties My Family's menu
        broken = copy.deepcopy(old)
        _migrate(broken)
        next(g for g in broken["groups"] if g["id"] == "fam").pop("inherits")
        assert _menu(fam[1], broken, people) != before[fam[1]["id"]], "the menu-identical guard cannot bite"
        d = data()                                            # migrates, once, and saves
        users = store.users()
        for p in people:
            assert _menu(p, d, users) == before[p["id"]], (p["email"], _menu(p, d, users), before[p["id"]])
            assert {k: (v["allowed"], v["functions"]) for k, v in my_access(p).items()} == before[p["id"]], p["email"]
        assert d["groups"][0]["id"] == CATCH_ALL and d["groups"][0]["name"] == say("catch_all_name")
        assert not any(g["id"] == "everyone" for g in d["groups"]), "Everyone is retired"
        assert not any(g["effect"] not in ("allow", "deny") or g["subject"] == "group:everyone" for g in d["grants"]), \
            "no 'only' rule and no Everyone rule survives the migration"
        ca = {g["screen"] for g in d["grants"] if g["subject"] == f"group:{CATCH_ALL}" and g["effect"] == "allow"}
        assert ca == {"video", "books"}, ca                    # Only-allowed and denied screens are left out
        assert next(g for g in d["groups"] if g["id"] == "fam")["inherits"] == CATCH_ALL
        assert store.read("access", {}) == data(), "the migration runs once: a second read changes nothing"
        assert not may(lone, "sound") and may(fam[2], "sound") and may(pallow, "sound"), "the owner's two screens"
        assert may(fam[1], "activity") and not may(fam[0], "activity") and not may(lone, "activity"), \
            "a lent Admin screen opens for that one person and nobody else"
        assert not may(pallow, "books") and facts_for(fam[2], "video", "draft")["available"] == "no" and \
            facts_for(fam[2], "video")["available"] == "yes", "availability answers per screen and per button, before the rules"
        chip = copy.deepcopy(engine.chips()["access.decide"])        # bite (in memory): no lent case = no lent screen
        chip["expr"]["cases"] = [c for c in chip["expr"]["cases"] if c["then"]["fields"]["why"]["text"] != "$msg_lent"]
        assert engine.run("access.decide", facts_for(fam[1], "activity"), engine.with_drafts([chip]))["allowed"] is False, \
            "the lent-screen guard cannot bite"
        _AVAILABLE.clear()
        _LENDER.clear()

        # --- 2. the model ------------------------------------------------------------------------------------
        assert may(own, "memory") and not may(lone, "memory"), "admin screens are the owner's"
        assert may(own, "keys") and may(own, "sound"), "an owner can never be locked out"
        d = data()
        _add_grant(d, f"user:{fam[1]['id']}", "memory", "", "allow", "t")
        _add_grant(d, "group:fam", "keys", "", "allow", "t")
        save(d)
        assert not may(fam[1], "memory"), "no rule opens an admin screen to anyone but an owner"
        assert not may(fam[1], "keys"), "deny wins: Catch All's deny reaches My Family through INHERIT"
        why = decide(fam[1], "keys")["why"]
        assert say("inherited_label", name="Catch All", via="My Family") in why, why
        # bite (in memory): a decide chip without its deny-wins case lets the allow through
        chip = copy.deepcopy(engine.chips()["access.decide"])
        chip["expr"]["cases"] = [c for c in chip["expr"]["cases"]
                                 if c["when"] != {"op": "ne", "left": "$deny_by", "right": ""}]
        assert engine.run("access.decide", facts_for(fam[1], "keys"), engine.with_drafts([chip]))["allowed"] is True, \
            "the deny-wins guard cannot bite"
        # MANAGED sees only its allows; INHERIT gives the parent's, live
        solo = store.add_user("s@x.io", "password-s")
        kid = store.add_user("k@x.io", "password-k")
        d = data()
        d["groups"] += [{"id": "solo", "name": "Solo", "members": [solo["id"]], "inherits": ""},
                        {"id": "kid", "name": "Kid", "members": [kid["id"]], "inherits": "solo"}]
        _add_grant(d, "group:solo", "video", "", "allow", "t")
        save(d)
        assert opens(solo) == ["video"], "managed = only what its groups allow"
        assert may(kid, "video") and not may(kid, "books"), "INHERIT: the child gets its parent's allows"
        why = decide(kid, "video")["why"]
        assert "Solo" in why and "Kid" in why, why
        chip = copy.deepcopy(engine.chips()["access.decide"])
        chip["expr"]["cases"] = [c for c in chip["expr"]["cases"]
                                 if c["then"]["fields"]["why"]["text"] != "$msg_not_granted"]
        assert engine.run("access.decide", facts_for(solo, "books"), engine.with_drafts([chip]))["allowed"] is True, \
            "the managed-only guard cannot bite"
        assert refused(save_group, {"id": "solo", "name": "Solo", "inherits": "kid"}, {}) == 400, "a loop is refused"
        assert refused(save_group, {"id": "solo", "name": "Solo", "inherits": "solo"}, {}) == 400, "so is itself"
        loop = copy.deepcopy(data())
        next(g for g in loop["groups"] if g["id"] == "solo")["inherits"] = "kid"
        assert chain("kid", loop) == ["kid", "solo"], "a loop written by hand still ends"
        assert save_group({"name": "Readers"}, {})["group"]["inherits"] == CATCH_ALL, \
            "a new group starts from Catch All (access.settings new_group_inherits_catch_all)"
        # UNASSIGNED = Catch All; a personal rule never empties the menu (a request approval writes one)
        newbie = store.add_user("n@x.io", "password-n")
        assert opens(newbie) == ["video", "books"], opens(newbie)
        assert "Catch All" in decide(newbie, "video")["why"]
        d = data()
        _add_grant(d, f"user:{newbie['id']}", "sound", "", "allow", "t")
        save(d)
        assert opens(newbie) == ["video", "books", "sound"], "a personal allow sits on top of Catch All"
        d["grants"] = [g for g in d["grants"] if not (g["subject"] == f"group:{CATCH_ALL}" and g["screen"] == "books")]
        save(d)
        assert not may(newbie, "books") and not may(lone, "books") and not may(fam[1], "books"), "Catch All decides, live"
        # Catch All is built in; the effect "only" is gone
        assert refused(delete_group, CATCH_ALL, {}) == 400, "Catch All cannot be deleted"
        assert refused(save_group, {"id": CATCH_ALL, "name": "Catch All", "add": [lone["id"]]}, {}) == 400
        assert save_group({"id": CATCH_ALL, "name": "Unassigned"}, {})["group"]["name"] == "Unassigned", "renamable"
        assert refused(save_grant, {"subject": f"group:{CATCH_ALL}", "screen": "sound", "effect": "only"}, own) == 400
        # a new screen joins Catch All once (access.settings new_screens_to_catch_all); a later removal sticks
        load(SCREENS + [{"id": "fresh", "label": "Fresh"}])
        assert may(lone, "fresh") and may(fam[1], "fresh") and not may(solo, "fresh"), "a new screen: nobody loses it"
        d = data()
        d["grants"] = [g for g in d["grants"] if not (g["subject"] == f"group:{CATCH_ALL}" and g["screen"] == "fresh")]
        save(d)
        assert not may(lone, "fresh"), "removed from Catch All stays removed"
        load(SCREENS + [{"id": "fresh", "label": "Fresh"}, {"id": "wip", "label": "Wip", "admin": True}])
        data()                                           # a draft (admin until live) is seen as it arrives
        load(SCREENS + [{"id": "fresh", "label": "Fresh"}, {"id": "wip", "label": "Wip"}])
        assert not may(lone, "wip") and not may(fam[1], "wip"), "a draft put live opens to nobody until allowed"
        # deleting a parent hands its children the grandparent
        delete_group("solo", {})
        assert next(g for g in data()["groups"] if g["id"] == "kid")["inherits"] == ""
        d = data()
        _add_grant(d, "group:kid", "video", "", "allow", "t")
        _add_grant(d, "group:kid", "video", "", "deny", "t")
        assert len([x for x in d["grants"] if x["subject"] == "group:kid"]) == 1, "saving a rule again replaces it"
        # 2026-10-19 owner "allow flexi search here": Groups & rules finds a screen with a typo or half a word
        found = lists.page("access_screens", own, {"q": "sound frm"})["rows"]
        assert found and found[0]["id"] == "sound", found
        assert {r["id"] for r in lists.page("access_screens", own, {"q": "draf"})["rows"]} == {"video"}, "a function's name finds its screen"
        assert not lists.page("access_screens", own, {"q": "zzqx"})["rows"] and len(lists.page("access_screens", own, {})["rows"]) == len([s for s in CATALOG if not s.get("admin")])
        assert refused(lists.page, "access_screens", fam[0], {}) == 403, "the screen list is the owner's, like the page"
    # 2026-10-19: data() SAVES its day-one migration, so every core module's self-check that reaches access must point the
    # store at a temp folder - the studio's core/find.py once wrote its real data/access.json this way
    for p_ in sorted(Path(__file__).resolve().parent.glob("*.py")):
        main_ = p_.read_text(encoding="utf-8").partition('if __name__ == "__main__"')[2]
        assert not writes_real_data(main_), f"core/{p_.name}: its self-check reads access without a temp store.DATA"
    find_ = (Path(__file__).resolve().parent / "find.py").read_text(encoding="utf-8").partition('if __name__ == "__main__"')[2]
    assert writes_real_data(find_.replace("access.store.DATA = ", "_was = ")), "the real-data guard cannot bite"
    print("core.access self-check OK")
