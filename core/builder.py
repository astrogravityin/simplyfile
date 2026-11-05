"""The builders' server: Ops & Chips Builder (OCB) and Rule Chip Builder (RCB).

    author   drafts and tests their own chips and rules, submits them for review
    editor   edits any draft, publishes, returns a draft with a note, switches things off, restores
    owner    everything, plus switching an op off and deleting what the builder made

Who may do what is itself a chip — `builder.can` (a decision table) — so the roles are data too.
Framework chips (shipped in core/, or `audience: admin`) are the owner's alone to change.

Life of a chip or a rule:
    draft ──submit──▶ review ──publish──▶ LIVE (data/builder/<kind>/<id>.json, version n+1)
      ▲                  │
      └──── return ◀─────┘            every publish, switch-off and restore leaves a history copy
A publish is refused while the item has a problem or a failing test — nothing half-right goes live.

Drafts, history, scenarios and op switches live under data/builder/, never in git: a save on the server
can never block a `git pull`.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from core import access, auth, engine, ops, rules, store

router = APIRouter()
HERE = Path(__file__).resolve().parent
SCENARIO_DIRS: list[Path] = [HERE / "scenarios"]
KINDS = {"chips": "chip_id", "rules": "rule_id"}
#: The catalog of actions chip `builder.can` answers for: a vocabulary the screens ask about, not a decision.
#: Who may do each one is that chip; every sentence is `builder.messages`; lengths and the scenario id pattern
#: are `builder.settings`.
ACTIONS = ("view", "test", "draft", "submit", "publish", "return", "deactivate", "restore", "delete",
           "scenario", "op_override")
SCREEN = {"chips": "ocb", "rules": "rcb"}


def say(key: str, **values) -> str:
    return engine.say("builder.messages", key, **values)


def settings() -> dict:
    return engine.run("builder.settings")


def plain_file_name(item_id: str) -> bool:
    """An id becomes a file name on disk. Whatever pattern a chip allows, it never climbs out of its folder
    (infrastructure, not policy)."""
    return bool(item_id) and item_id.strip() == item_id and ".." not in item_id \
        and not any(ch in item_id for ch in "/\\:")


def root() -> Path:
    return store.DATA / "builder"


def _read(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, value) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(p)


# --- permissions --------------------------------------------------------------------------------

def _enter(request: Request, wanted: list[str]) -> dict:
    u = auth.signed_in(request)
    ok = next((sid for sid in wanted if access.may(u, sid)), None)
    request.state.screen, request.state.user = ok or wanted[0], u   # the activity ledger reads these
    if not ok:
        raise HTTPException(403, access.decide(u, wanted[0])["why"])
    return u


def guard_kind(request: Request, kind: str) -> dict:
    """Chips are the Ops & Chips Builder's; rules are the Rule Chip Builder's."""
    return _enter(request, [SCREEN.get(kind, "ocb")])


def guard_any(request: Request) -> dict:
    """What both builders read (catalog, scenarios, a trial run)."""
    return _enter(request, ["ocb", "rcb"])


guard_kind.screen_id = guard_any.screen_id = "ocb|rcb"   # the selfcheck route ratchet looks for this


def can(u: dict, action: str, *, own: bool = False, framework: bool = False) -> bool:
    return engine.run("builder.can", {"role": u.get("role", "member"), "action": action,
                                      "own": own, "framework": framework}) is True


def need(u: dict, action: str, **kw) -> None:
    if not can(u, action, **kw):
        raise HTTPException(403, say("cannot_framework" if kw.get("framework") else "cannot",
                                     role=u.get("role", "member"), action=action.replace("_", " ")))


def is_framework(kind: str, item: dict | None) -> bool:
    return bool(item) and kind == "chips" and (item.get("audience") == "admin" or item.get("_source") == "core")


# --- live items, drafts, history ----------------------------------------------------------------

def live(kind: str) -> dict:
    return engine.chips() if kind == "chips" else rules.rules()


def refresh(kind: str) -> None:
    (engine.refresh if kind == "chips" else rules.refresh)()


def draft_path(kind: str, item_id: str) -> Path:
    return root() / "drafts" / kind / f"{item_id}.json"


def drafts(kind: str) -> dict:
    d = root() / "drafts" / kind
    return {f.stem: _read(f, {}) for f in sorted(d.glob("*.json"))} if d.is_dir() else {}


def history(kind: str, item_id: str) -> list[dict]:
    d = root() / "history" / kind / item_id
    rows = [(_read(f, {}) or {}).get("meta", {}) | {"file": f.stem} for f in sorted(d.glob("*.json"))] if d.is_dir() else []
    return rows[::-1]


def _snapshot(kind: str, item: dict, u: dict, action: str) -> None:
    item_id = item[KINDS[kind]]
    n = len(history(kind, item_id)) + 1
    _write(root() / "history" / kind / item_id / f"{n:04d}.json",
           {"item": _clean(item), "meta": {"n": n, "version": item.get("version"), "status": item.get("status"),
                                           "action": action, "by": u["email"], "at": store.now()}})


def _clean(item: dict) -> dict:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def scenarios() -> dict:
    out: dict[str, dict] = {}
    for d in SCENARIO_DIRS + [root() / "scenarios"]:
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                s = _read(f, {})
                if s.get("scenario_id") == f.stem:
                    out[f.stem] = s | {"source": "data" if d == root() / "scenarios" else "shipped"}
    return out


def disabled_ops() -> set:
    return {k for k, v in store.read("op_overrides", {}).items() if v.get("inactive")}


def check(kind: str, item: dict, extra_drafts: list | None = None) -> dict:
    """{problems, tests} for an item as it would be published."""
    if kind == "chips":
        lib = engine.with_drafts([item] + (extra_drafts or []))
        return {"problems": engine.problems(item, lib, disabled_ops()), "tests": engine.run_tests(item, lib, scenarios())}
    lib = engine.with_drafts(extra_drafts or [])
    probs = rules.problems(item, lib)
    return {"problems": probs, "tests": rules.run_tests(item, lib, scenarios())}


def summary(kind: str, item: dict, draft: dict | None) -> dict:
    key = KINDS[kind]
    base = {"id": item.get(key) if item else draft["item"][key]}
    src = item or draft["item"]
    fields = ("label", "set", "kind", "returns", "audience", "aliases") if kind == "chips" else ("label", "trigger", "priority")
    out = base | {f: src.get(f) for f in fields} | {
        "status": item.get("status") if item else "unpublished", "source": (item or {}).get("_source", "draft"),
        "version": (item or {}).get("version", 1 if item else 0),
        "draft": ({"status": draft["meta"].get("status"), "author": draft["meta"].get("author_email"),
                   "note": draft["meta"].get("note", ""), "at": draft["meta"].get("at")} if draft else None)}
    return out


# --- the catalog ------------------------------------------------------------------------------

@router.get("/api/core/build/catalog")
def catalog(u: dict = Depends(guard_any)):
    need(u, "view")
    chips, chip_drafts = engine.chips(), drafts("chips")
    rule_live, rule_drafts = rules.rules(), drafts("rules")
    overrides = store.read("op_overrides", {})
    # one pass over the chips, not one per op (2026-11-04 ui_audit: 1.9 s as ops x chips re-parsed every expr; portal-builder 6a)
    used = Counter(v for c in chips.values() for v in engine.refs(c.get("expr"))["vops"])
    op_list = [o | {"inactive": bool(overrides.get(o["op"], {}).get("inactive")), "note": overrides.get(o["op"], {}).get("note", ""),
                    "used_by": used[o["op"]]} for o in ops.catalog()]
    visible = lambda c: u.get("role") == "owner" or c.get("audience") != "admin"  # noqa: E731
    return {
        "me": {"role": u.get("role"), "can": {a: can(u, a, own=True) for a in ACTIONS}, "id": u["id"]},  # own work
        "ops": op_list, "tests": list(engine.TESTS),
        "chips": [summary("chips", chips.get(i), chip_drafts.get(i)) for i in sorted(set(chips) | set(chip_drafts))
                  if visible(chips.get(i) or chip_drafts[i]["item"])],
        "rules": [summary("rules", rule_live.get(i), rule_drafts.get(i)) for i in sorted(set(rule_live) | set(rule_drafts))],
        "subjects": list(rules.SUBJECTS.values()),
        "triggers": list(rules.TRIGGERS.values()),
        "kinds": [{k: v for k, v in s.items() if k != "act"} for s in rules.KINDS.values()],
        "scenarios": list(scenarios().values()),
        # what the screens would otherwise repeat: the id rules and the words an empty outcome falls back to
        "rules_ui": {"chip_id_pattern": engine.ID_RE.pattern, "rule_id_pattern": rules.settings()["rule_id_pattern"],
                     "scenario_id_pattern": engine.setting("builder.settings", "scenario_id_pattern"),
                     "tones": list(rules.TONES), "notice_subject": engine.say("rules.messages", "notice_subject"),
                     "refused": engine.say("rules.messages", "refused")},
    }


@router.get("/api/core/build/{kind}/{item_id}")
def item(kind: str, item_id: str, u: dict = Depends(guard_kind)):
    _kind(kind)
    need(u, "view")
    it, d = live(kind).get(item_id), drafts(kind).get(item_id)
    if not it and not d:
        raise HTTPException(404, say("not_found"))
    if kind == "chips" and it and it.get("audience") == "admin" and u.get("role") != "owner":
        raise HTTPException(404, say("not_found"))
    fw = is_framework(kind, it)
    own = bool(d) and d["meta"].get("author_id") == u["id"]
    return {"live": engine.public(it) if it else None, "draft": d, "history": history(kind, item_id),
            "usages": engine.usages("chip", item_id, rules.rules()) if kind == "chips" else {"chips": [], "rules": []},
            "framework": fw, "shipped": bool(it and it.get("_shipped")),
            "can": {a: can(u, a, own=own or not d, framework=fw) for a in ACTIONS},
            "check": check(kind, d["item"] if d else _clean(it))}


def _kind(kind: str) -> None:
    if kind not in KINDS:
        raise HTTPException(404, say("chips_or_rules"))




# --- drafts -------------------------------------------------------------------------------------

@router.put("/api/core/build/{kind}/{item_id}/draft")
def save_draft(kind: str, item_id: str, body: dict = Body(...), u: dict = Depends(guard_kind)):
    _kind(kind)
    new = body.get("item") or {}
    if new.get(KINDS[kind]) != item_id:
        raise HTTPException(400, say("id_mismatch", key=KINDS[kind], id=item_id))
    it, d = live(kind).get(item_id), drafts(kind).get(item_id)
    own = not d or d["meta"].get("author_id") == u["id"]
    need(u, "draft", own=own, framework=is_framework(kind, it) or (kind == "chips" and new.get("audience") == "admin"))
    if not it and not d:
        # A chip id's shape is the engine's grammar (engine.ID_RE, which also loads every chip file); a rule id's
        # shape is chip rules.settings.
        valid = bool(engine.ID_RE.match(item_id)) if kind == "chips" else rules.id_allowed(item_id)
        if not valid or not plain_file_name(item_id):
            raise HTTPException(400, say("bad_chip_id" if kind == "chips" else "bad_rule_id"))
    meta = (d or {}).get("meta") or {"author_id": u["id"], "author_email": u["email"], "created": store.now()}
    meta |= {"status": "draft", "at": store.now(), "last_by": u["email"]}
    clean = _clean(new) | {"status": (it or {}).get("status", "published"), "version": (it or {}).get("version", 0)}
    _write(draft_path(kind, item_id), {"item": clean, "meta": meta})
    return {"draft": {"item": clean, "meta": meta}, "check": check(kind, clean, body.get("with_drafts"))}


@router.post("/api/core/build/{kind}/{item_id}/submit")
def submit(kind: str, item_id: str, u: dict = Depends(guard_kind)):
    _kind(kind)
    d = _draft_or_404(kind, item_id)
    need(u, "submit", own=d["meta"].get("author_id") == u["id"])
    d["meta"] |= {"status": "review", "at": store.now(), "note": ""}
    _write(draft_path(kind, item_id), d)
    return {"draft": d}


@router.post("/api/core/build/{kind}/{item_id}/return")
def send_back(kind: str, item_id: str, body: dict = Body(default={}), u: dict = Depends(guard_kind)):
    _kind(kind)
    d = _draft_or_404(kind, item_id)
    need(u, "return", framework=is_framework(kind, live(kind).get(item_id)))
    d["meta"] |= {"status": "draft", "note": str(body.get("note") or "")[:int(settings()["return_note_max"])], "returned_by": u["email"], "at": store.now()}
    _write(draft_path(kind, item_id), d)
    return {"draft": d}


@router.delete("/api/core/build/{kind}/{item_id}/draft")
def discard(kind: str, item_id: str, u: dict = Depends(guard_kind)):
    _kind(kind)
    d = _draft_or_404(kind, item_id)
    if d["meta"].get("author_id") != u["id"]:
        need(u, "publish", framework=is_framework(kind, live(kind).get(item_id)))
    draft_path(kind, item_id).unlink(missing_ok=True)
    return {"ok": True}


def _draft_or_404(kind: str, item_id: str) -> dict:
    d = drafts(kind).get(item_id)
    if not d:
        raise HTTPException(404, say("no_draft"))
    return d


@router.post("/api/core/build/{kind}/{item_id}/publish")
def publish(kind: str, item_id: str, u: dict = Depends(guard_kind)):
    _kind(kind)
    d = _draft_or_404(kind, item_id)
    it = live(kind).get(item_id)
    need(u, "publish", framework=is_framework(kind, it) or d["item"].get("audience") == "admin")
    result = check(kind, d["item"])
    failing = [t for t in result["tests"] if not t["ok"]]
    if result["problems"] or failing:
        raise HTTPException(422, {"message": say("not_published"), **result})
    out = d["item"] | {"version": int((it or {}).get("version") or 0) + 1, "status": "published",
                       "updated_by": u["email"], "updated_at": store.now()}
    _write(root() / kind / f"{item_id}.json", out)
    _snapshot(kind, out, u, "publish")
    draft_path(kind, item_id).unlink(missing_ok=True)
    refresh(kind)
    return {"item": out}


# --- live items: switch off / on, delete, restore ------------------------------------------------

@router.post("/api/core/build/{kind}/{item_id}/status")
def set_status(kind: str, item_id: str, body: dict = Body(...), u: dict = Depends(guard_kind)):
    _kind(kind)
    it = live(kind).get(item_id)
    if not it:
        raise HTTPException(404, say("only_live_switch"))
    status = "inactive" if body.get("status") == "inactive" else "published"
    need(u, "deactivate", framework=is_framework(kind, it))
    if kind == "chips" and status == "inactive":
        users = engine.usages("chip", item_id, rules.rules())
        live_users = [c for c in users["chips"] if engine.chips()[c].get("status") != "inactive"] + \
                     [r for r in users["rules"] if rules.rules()[r].get("status") == "published"]
        if live_users:
            raise HTTPException(409, {"message": say("switch_off_users_first"), "used_by": live_users})
    out = _clean(it) | {"status": status, "updated_by": u["email"], "updated_at": store.now()}
    _write(root() / kind / f"{item_id}.json", out)
    _snapshot(kind, out, u, "switch off" if status == "inactive" else "switch on")
    refresh(kind)
    return {"item": out}


@router.delete("/api/core/build/{kind}/{item_id}")
def delete(kind: str, item_id: str, u: dict = Depends(guard_kind)):
    _kind(kind)
    it = live(kind).get(item_id)
    need(u, "delete", framework=is_framework(kind, it))
    if not it:
        raise HTTPException(404, say("nothing_live"))
    if it.get("_shipped") or it.get("_source") != "data":
        raise HTTPException(400, say("shipped_no_delete"))
    if kind == "chips" and any(engine.usages("chip", item_id, rules.rules()).values()):
        raise HTTPException(409, say("in_use"))
    _snapshot(kind, _clean(it), u, "delete")
    (root() / kind / f"{item_id}.json").unlink(missing_ok=True)
    refresh(kind)
    return {"ok": True}


@router.post("/api/core/build/{kind}/{item_id}/restore/{n}")
def restore(kind: str, item_id: str, n: int, u: dict = Depends(guard_kind)):
    """An old version comes back as a DRAFT: it is re-checked before it can go live again."""
    _kind(kind)
    snap = _read(root() / "history" / kind / item_id / f"{n:04d}.json")
    if not snap:
        raise HTTPException(404, say("no_version"))
    need(u, "restore", framework=is_framework(kind, live(kind).get(item_id)))
    meta = {"author_id": u["id"], "author_email": u["email"], "created": store.now(), "status": "draft",
            "at": store.now(), "note": say("restored_note", version=snap["meta"].get("version"))}
    _write(draft_path(kind, item_id), {"item": snap["item"], "meta": meta})
    return {"draft": {"item": snap["item"], "meta": meta}}


@router.get("/api/core/build/{kind}/{item_id}/history/{n}")
def history_item(kind: str, item_id: str, n: int, u: dict = Depends(guard_kind)):
    _kind(kind)
    need(u, "view")
    snap = _read(root() / "history" / kind / item_id / f"{n:04d}.json")
    if not snap:
        raise HTTPException(404, say("no_version"))
    return snap


# --- trying things ------------------------------------------------------------------------------

@router.post("/api/core/build/check/{kind}")
def check_unsaved(kind: str, body: dict = Body(...), u: dict = Depends(guard_kind)):
    """Problems and test results for an item that is not saved at all (the builder's live preview)."""
    _kind(kind)
    need(u, "test")
    return check(kind, body.get("item") or {}, body.get("with_drafts"))


@router.post("/api/core/build/eval")
def evaluate(body: dict = Body(...), u: dict = Depends(guard_any)):
    """Run one node (or a whole unsaved rule) on a scenario's facts plus arguments, with drafts in play."""
    need(u, "test")
    lib = engine.with_drafts(body.get("with_drafts"))
    facts = dict((scenarios().get(body.get("scenario")) or {}).get("facts") or {}) | (body.get("args") or {})
    try:
        if body.get("rule"):
            return rules.render(body["rule"], facts, lib)
        node = body.get("node")
        if body.get("as") == "test":
            return {"result": engine.test(node, facts, lib)}
        return {"result": engine.value(node, facts, lib)}
    except Exception as e:  # noqa: BLE001 - shown to the author, not raised
        return {"error": str(e)}


@router.get("/api/core/build/usages/{what}/{name}")
def who_uses(what: str, name: str, u: dict = Depends(guard_any)):
    """Every live chip, draft and rule that uses an op, a chip or a scenario (by its tests) — the impact
    of changing it, answered on the server so a screen never has to fetch the whole library."""
    need(u, "view")
    if what not in ("op", "chip", "scenario"):
        raise HTTPException(404, say("op_chip_or_scenario"))
    key = {"op": "vops", "chip": "chips"}.get(what)
    out = {"chips": [], "rules": [], "drafts": []}
    for kind, items in (("chips", engine.chips()), ("rules", rules.rules())):
        for item_id, it in items.items():
            if _uses(it, key, name, what):
                out[kind].append(item_id)
        for item_id, d in drafts(kind).items():
            if _uses(d.get("item") or {}, key, name, what):
                out["drafts"].append(f"{kind}:{item_id}")
    return {k: sorted(v) for k, v in out.items()}


def _uses(item: dict, key: str | None, name: str, what: str) -> bool:
    if what == "scenario":
        return any(c.get("scenario") == name for c in item.get("test_cases") or [])
    return name in engine.refs([item.get("expr"), item.get("values"), item.get("when"), item.get("then")])[key]


# --- scenarios and ops --------------------------------------------------------------------------

@router.put("/api/core/build/scenario/{scenario_id}")
def save_scenario(scenario_id: str, body: dict = Body(...), u: dict = Depends(guard_any)):
    need(u, "scenario")
    k = settings()
    if engine.run("builder.id_allowed", {"id": scenario_id, "pattern": k["scenario_id_pattern"]}) is not True \
            or not plain_file_name(scenario_id):
        raise HTTPException(400, say("bad_scenario_id"))
    if body.get("subject") not in rules.SUBJECTS:
        raise HTTPException(400, say("scenario_subject"))
    if not isinstance(body.get("facts"), dict):
        raise HTTPException(400, say("scenario_facts"))
    s = {"scenario_id": scenario_id, "subject": body["subject"],
         "label": str(body.get("label") or scenario_id)[:int(k["scenario_label_max"])],
         "facts": body["facts"], "updated_by": u["email"], "updated_at": store.now()}
    _write(root() / "scenarios" / f"{scenario_id}.json", s)
    return {"scenario": s}


@router.delete("/api/core/build/scenario/{scenario_id}")
def delete_scenario(scenario_id: str, u: dict = Depends(guard_any)):
    need(u, "publish")
    p = root() / "scenarios" / f"{scenario_id}.json"
    if not p.exists():
        raise HTTPException(400, say("scenario_not_deletable"))
    p.unlink()
    return {"ok": True}


@router.put("/api/core/build/ops/{op}")
def op_override(op: str, body: dict = Body(...), u: dict = Depends(guard_any)):
    """An op is Python and cannot be rewritten from a screen. The owner can switch it off (no new chip
    may use it) and leave a note; chips already using it keep working and are listed."""
    need(u, "op_override")
    if op not in ops.OPS:
        raise HTTPException(404, say("no_op"))
    with store._LOCK:  # noqa: SLF001
        rows = store.read("op_overrides", {})
        rows[op] = {"inactive": bool(body.get("inactive")), "note": str(body.get("note") or "")[:int(settings()["op_note_max"])],
                    "by": u["email"], "at": store.now()}
        store.write("op_overrides", rows)
    return {"op": op, **rows[op], "used_by": engine.usages("op", op, rules.rules())}


@router.post("/api/core/banners/{banner_id}/dismiss")
def dismiss(banner_id: str, u: dict = Depends(auth.signed_in)):
    with store._LOCK:  # noqa: SLF001
        rows = store.read("banner_dismissed", {})
        rows[u["id"]] = (rows.get(u["id"], []) + [banner_id])[-int(settings()["dismissed_banners_kept"]):]
        store.write("banner_dismissed", rows)
    return {"ok": True}
