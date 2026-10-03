"""Rules: what the portal DOES when chips hold — the Rule Chip Builder's runtime.

A chip answers a question ("how bad is memory?"). A rule acts on the answer:

    WHEN   a trigger fires           server.sample · signup.submit · upload.start · page.view · daily
    GIVEN  the facts of its subject  server{rss_mb, limit_mb…} · signup{email, domain…} · …
    IF     its test holds            chips and ops over the facts (+ its own knobs and named values)
    THEN   outcomes                  refuse · banner · notify · value · flag

Python registers SUBJECTS (which facts exist), TRIGGERS (where `fire` is called) and OUTCOME KINDS
(what an outcome can do). Everything a rule decides — the test, the numbers, the words, who is told,
how often — is JSON the Rule Chip Builder shows and edits (the two-way rule).

Where a rule lives — later layers win for the same rule_id, exactly like chips:
    core/rules/*.json · <portal>/rules/*.json · data/builder/rules/*.json (published from the builder)
Only `status: published` rules fire. Drafts run only inside the builder, on scenarios, with no side effect.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from core import engine, ops, store

HERE = Path(__file__).resolve().parent
DIRS: list[Path] = [HERE / "rules"]
DAY = 86400  # seconds in a day: a unit, not a policy
SUBJECTS: dict[str, dict] = {}
TRIGGERS: dict[str, dict] = {}
KINDS: dict[str, dict] = {}
_cache: dict[str, Any] = {"at": 0.0, "sig": None, "rules": {}}
_lock = threading.Lock()


# --- registries (Python says what exists; JSON says what happens) ------------------------------

def subject(name: str, label: str, facts: list[dict], doc: str = "") -> None:
    """facts: [{name, type: number|text|boolean|list|rows|record, label}]"""
    SUBJECTS[name] = {"name": name, "label": label, "facts": facts, "doc": doc}


def trigger(name: str, subject_name: str, label: str, kinds: list[str], doc: str = "") -> None:
    TRIGGERS[name] = {"name": name, "subject": subject_name, "label": label, "kinds": kinds, "doc": doc}


def kind(name: str, label: str, fields: list[dict], doc: str = "",
         act: Callable[[dict, dict, dict], None] | None = None) -> None:
    """fields: [{name, type: text|longtext|number|choice|boolean, label, choices?, default?}].
    `act(outcome, facts, context)` performs a side effect; kinds without one are answers returned
    to the caller (refuse, value, flag)."""
    KINDS[name] = {"name": name, "label": label, "fields": fields, "doc": doc, "act": act}


def register_dir(path) -> None:
    p = Path(path).resolve()
    if p not in DIRS:
        DIRS.append(p)
        _cache["at"] = 0.0


def settings() -> dict:
    """The rule id pattern, cooldown memory, banner and subject lengths, default banner minutes: chip rules.settings."""
    return engine.run("rules.settings")


def say(key: str, **values) -> str:
    return engine.say("rules.messages", key, **values)


def id_allowed(rule_id: str) -> bool:
    return engine.run("builder.id_allowed", {"id": rule_id, "pattern": settings()["rule_id_pattern"]}) is True


def data_dir() -> Path:
    return store.DATA / "builder" / "rules"


def rules() -> dict[str, dict]:
    with _lock:
        if time.time() - _cache["at"] < engine.RELOAD_S and _cache["rules"]:
            return _cache["rules"]
        layers = [("core" if d == HERE / "rules" else "portal", d) for d in DIRS] + [("data", data_dir())]
        files = [(layer, f) for layer, d in layers if d.is_dir() for f in sorted(d.glob("*.json"))]
        sig = tuple((str(f), f.stat().st_mtime_ns) for _, f in files)
        if sig != _cache["sig"]:
            loaded: dict[str, dict] = {}
            for layer, f in files:
                r = json.loads(f.read_text(encoding="utf-8"))
                if r.get("rule_id") != f.stem:
                    raise engine.ChipError(f"{f.name}: rule_id must equal the file name")
                r.setdefault("status", "published")
                r["_source"] = layer
                loaded[r["rule_id"]] = r
            _cache.update(rules=loaded, sig=sig)
        _cache["at"] = time.time()
        return _cache["rules"]


def refresh() -> None:
    _cache["at"] = 0.0


# --- evaluation ---------------------------------------------------------------------------------

def _knobs(rule: dict) -> dict:
    return {p["name"]: p.get("default") for p in rule.get("params") or []}


def render(rule: dict, facts: dict, lib: dict | None = None) -> dict:
    """{matched, values, outcomes, error} for one rule on these facts — no side effect."""
    lib = lib if lib is not None else engine.chips()
    env = _knobs(rule) | dict(facts)
    try:
        for name, node in (rule.get("values") or {}).items():      # named values, in order
            env[name] = engine.value(node, env, lib)
        matched = engine.test(rule.get("when"), env, lib)
        outcomes = []
        if matched is True:
            for i, o in enumerate(rule.get("then") or []):
                done = {"n": i}
                for k, v in o.items():
                    plain_text = isinstance(v, str) and not v.startswith("$")
                    done[k] = ops.template(v, env) if plain_text else engine.value(v, env, lib)
                outcomes.append(done)
        return {"matched": matched, "values": {k: env[k] for k in (rule.get("values") or {})}, "outcomes": outcomes}
    except Exception as e:  # noqa: BLE001 - one broken rule never breaks a request
        return {"matched": None, "values": {}, "outcomes": [], "error": str(e)}


def fire(trigger_name: str, facts: dict, context: dict | None = None) -> list[dict]:
    """Run every published rule on this trigger, highest priority first. Side-effect outcomes (banner,
    notify) are performed here; every outcome is also returned, so the caller can act on refuse,
    value and flag. A rule that errors is logged and skipped."""
    context = context or {}
    out: list[dict] = []
    live = sorted((r for r in rules().values() if r.get("trigger") == trigger_name and r.get("status") == "published"),
                  key=lambda r: -int(r.get("priority") or 0))
    for r in live:
        res = render(r, facts)
        if res.get("error"):
            print(f"[rules] {r['rule_id']}: {res['error']}", file=sys.stderr, flush=True)
            continue
        for o in res["outcomes"]:
            o["rule_id"] = r["rule_id"]
            spec = KINDS.get(o.get("kind"))
            if spec and spec["act"] and _cool(r, o, context):
                try:
                    spec["act"](o, facts, context)
                except Exception as e:  # noqa: BLE001
                    print(f"[rules] {r['rule_id']} {o.get('kind')}: {e}", file=sys.stderr, flush=True)
            out.append(o)
        if res["outcomes"] and r.get("stop"):
            break
    return out


def refusal(outcomes: list[dict]) -> str | None:
    """The first refuse message, if any rule refused."""
    return next((o.get("message") or say("refused") for o in outcomes if o.get("kind") == "refuse"), None)


def _cool(rule: dict, outcome: dict, context: dict) -> bool:
    """At most once per `cooldown_minutes` for the same rule, outcome and person."""
    minutes = ops._num(outcome.get("cooldown_minutes"))
    if not minutes:
        return True
    key = f"{rule['rule_id']}#{outcome['n']}#{(context.get('person') or {}).get('id', '')}"
    now = time.time()
    with store._LOCK:  # noqa: SLF001
        seen = store.read("rule_cooldowns", {})
        if now - seen.get(key, 0) < minutes * 60:
            return False
        seen[key] = now
        keep = float(settings()["cooldown_keep_days"]) * DAY
        store.write("rule_cooldowns", {k: v for k, v in seen.items() if now - v < keep})
    return True


# --- structure ----------------------------------------------------------------------------------

def problems(rule: dict, lib: dict | None = None) -> list[str]:
    lib = lib if lib is not None else engine.chips()
    rid = rule.get("rule_id") or ""
    out: list[str] = []
    if not id_allowed(rid):
        out.append(say("bad_id"))
    if not rule.get("label"):
        out.append(say("no_label", rule=rid))
    trig = TRIGGERS.get(rule.get("trigger"))
    if not trig:
        out.append(say("no_trigger", rule=rid))
    if not rule.get("when"):
        out.append(say("no_when", rule=rid))
    if not rule.get("then"):
        out.append(say("no_then", rule=rid))
    facts = {f["name"] for f in (SUBJECTS.get(trig["subject"], {}).get("facts", []) if trig else [])}
    known = facts | set(_knobs(rule)) | set(rule.get("values") or {})
    found = engine.refs([rule.get("values"), rule.get("when"), rule.get("then")])
    subject_name = trig["subject"] if trig else say("its_subject")
    out += [say("unknown_name", rule=rid, name=p, subject=subject_name) for p in sorted(found["params"] - known)]
    out += [say("no_op", rule=rid, name=v) for v in sorted(found["vops"] - set(ops.OPS))]
    out += [say("no_chip", rule=rid, name=c) for c in sorted(found["chips"] - set(lib))]
    out += [say("chip_off", rule=rid, name=c) for c in sorted(found["chips"] & set(lib))
            if lib[c].get("status") == "inactive"]
    for o in rule.get("then") or []:
        if o.get("kind") not in KINDS:
            out.append(say("no_kind", rule=rid, kind=repr(o.get("kind"))))
        elif trig and o["kind"] not in trig["kinds"]:
            out.append(say("kind_not_here", rule=rid, kind=o["kind"], trigger=trig["name"]))
    if not rule.get("test_cases"):
        out.append(say("no_tests", rule=rid))
    return out


def run_tests(rule: dict, lib: dict, scenarios: dict) -> list[dict]:
    results = []
    for i, case in enumerate(rule.get("test_cases") or []):
        facts = dict((scenarios.get(case.get("scenario")) or {}).get("facts") or {}) | (case.get("facts") or {})
        res = render(rule, facts, lib)
        row = {"n": i + 1, "scenario": case.get("scenario", ""), "want": case.get("expect"), "got": res["matched"],
               "outcomes": res["outcomes"], "error": res.get("error")}
        row["ok"] = not res.get("error") and res["matched"] == case.get("expect")
        results.append(row)
    return results


def certify(scenarios: dict) -> list[str]:
    out = []
    lib = engine.chips()
    for rid, r in rules().items():
        if r.get("status") != "published":
            continue
        out += problems(r, lib)
        out += [say("test_failed", rule=rid, n=t["n"], scenario=t["scenario"], want=repr(t["want"]),
                    got=t.get("error") or repr(t["got"]))
                for t in run_tests(r, lib, scenarios) if not t["ok"]]
    return out


# --- the framework's own outcome kinds ----------------------------------------------------------

def _banner(o: dict, facts: dict, context: dict) -> None:
    k = settings()
    minutes = ops._num(o.get("expires_minutes")) or ops._num(k["banner_minutes_default"])
    person = context.get("person") or {}
    row = {"id": store.new_id(), "rule_id": o["rule_id"], "n": o.get("n", 0), "audience": o.get("audience") or "owner",
           "user_id": person.get("id", "") if o.get("audience") == "person" else "",
           "tone": o.get("tone") or "info", "text": str(o.get("text") or "")[:int(k["banner_text_max"])],
           "at": store.now(),
           "until": (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds")}
    with store._LOCK:  # noqa: SLF001
        rows = [b for b in store.read("banners", []) if b["until"] > store.now()
                and not (b["rule_id"] == row["rule_id"] and b.get("n", 0) == row["n"]
                         and b["audience"] == row["audience"] and b["user_id"] == row["user_id"])]
        store.write("banners", rows + [row])


def _notify(o: dict, facts: dict, context: dict) -> None:
    from core import mailer  # noqa: PLC0415
    person = context.get("person") or {}
    to = [u["email"] for u in store.users() if u.get("role") == "owner"] if o.get("to") != "person" else [person.get("email")]
    to = [t for t in to if t]
    if mailer.configured() and to:
        for t in to:
            mailer.send(t, str(o.get("subject") or say("notice_subject"))[:int(settings()["notice_subject_max"])],
                        str(o.get("text") or ""))
    else:  # no mail: the notice still reaches someone, as a banner
        _banner(o | {"audience": "owner" if o.get("to") != "person" else "person", "tone": o.get("tone") or "warn",
                     "text": o.get("text") or o.get("subject")}, facts, context)


# Registries, not decisions: the tones are the classes the shell's CSS draws, and each kind's fields are the
# form the Rule Chip Builder shows. What a rule SAYS and WHEN lives in the rule JSON and in rules.settings.
TONES = ["info", "ok", "warn", "bad"]
kind("refuse", "Refuse", [{"name": "message", "type": "text", "label": "What the person is told"}],
     "Stops the action; the caller shows the message.")
kind("banner", "Banner", [
    {"name": "audience", "type": "choice", "label": "Shown to", "choices": ["owner", "everyone", "person"], "default": "owner"},
    {"name": "tone", "type": "choice", "label": "Tone", "choices": TONES, "default": "info"},
    {"name": "text", "type": "longtext", "label": "Text ({fact} and {value.field} fill in)"},
    {"name": "expires_minutes", "type": "number", "label": "Shown for (minutes)",
     "default": engine.knobs("rules.settings")["banner_minutes_default"]},
    {"name": "cooldown_minutes", "type": "number", "label": "At most once every (minutes)", "default": 0}],
    "A strip across the top of every page until it expires or is dismissed.", _banner)
kind("notify", "Email", [
    {"name": "to", "type": "choice", "label": "Send to", "choices": ["owner", "person"], "default": "owner"},
    {"name": "subject", "type": "text", "label": "Subject"},
    {"name": "text", "type": "longtext", "label": "Message"},
    {"name": "cooldown_minutes", "type": "number", "label": "At most once every (minutes)", "default": 60}],
    "An email through the portal's SMTP; without mail it becomes a banner, so it is never lost.", _notify)
kind("value", "Answer a value", [{"name": "name", "type": "text", "label": "Name"},
                                 {"name": "value", "type": "text", "label": "Value"}],
     "Hands a value back to the screen or job that fired the trigger.")
kind("flag", "Flag", [{"name": "name", "type": "text", "label": "Flag"},
                      {"name": "value", "type": "text", "label": "Value", "default": "true"}],
     "Marks the thing the trigger is about (a visit, an account) for the screen that shows it.")


def banners_for(u: dict | None) -> list[dict]:
    if not u:
        return []
    now = store.now()
    hidden = set((store.read("banner_dismissed", {}) or {}).get(u["id"], []))
    return [{k: b[k] for k in ("id", "tone", "text", "rule_id")} for b in store.read("banners", [])
            if b["until"] > now and b["id"] not in hidden
            and (b["audience"] == "everyone" or (b["audience"] == "owner" and u.get("role") == "owner")
                 or (b["audience"] == "person" and b["user_id"] == u["id"]))]


def bootstrap_extra(request, u: dict | None) -> dict:
    return {"banners": banners_for(u)}
