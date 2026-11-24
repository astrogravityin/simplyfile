"""Providers: which AI does each paid kind of work - text, image, video - for THIS person.

2026-09-19 owner: "do we have only Gemini? what if a new model comes?" - Gemini stays the default; any other
provider is a row in chip providers.settings (who, what kinds, where its key comes from, how it is spoken to),
any model a row in providers.models (which provider, which kind, what it costs). A new Google model is a chip
row edit; a new provider that speaks the OpenAI chat/images shape is a chip row too; only a new WIRE (a new
SDK) is code here. Three call sites in the portal ask this module: text_json, image, video.

- Keys stay per person (store.keys_of); the person picks a provider + model per kind (Account & key).
- Prices: providers.models rows; a model with no row costs None (the screen says unknown, never $0).
- Sentences: providers.messages. Nothing about a provider is decided in Python.
"""
from __future__ import annotations

from typing import Any
import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import HTTPException

import store
from core import egress, engine

def kinds() -> list[str]:
    """The kinds of work a model does (chip providers.settings) - 2026-09-26, was a tuple here."""
    return list(engine.setting("providers.settings", "kinds"))


def say(key: str, **values) -> str:
    return engine.say("providers.messages", key, **values)


def settings() -> dict:
    return engine.run("providers.settings")


def rows() -> list[dict]:
    return settings()["rows"]


def row(pid: str) -> dict | None:
    return next((r for r in rows() if r["id"] == pid), None)


def _edition() -> str:
    import edition  # noqa: PLC0415 - which product this server is (chip edition.settings)
    try:
        return edition.current()["id"]
    except RuntimeError:
        return ""


def shown() -> list[dict]:
    """The providers this edition offers on its screens: a row with `editions` (chip providers.settings) only on those
    editions - Runway and fal.ai make video clips, which only the Studio makes (2026-10-09 owner)."""
    ed = _edition()
    return [r for r in rows() if not r.get("editions") or ed in r["editions"]]


def model_rows(kind: str | None = None) -> list[dict]:
    out = engine.run("providers.models")["rows"]
    return [r for r in out if not kind or r["kind"] == kind]


def model_row(kind: str, model: str) -> dict | None:
    return next((r for r in model_rows(kind) if r["id"] == model), None)


# --- the key pool: several keys per provider, default first, rotated on quota / invalid (chip providers.rotate) ---
# 2026-09-19 owner: "I should be able to add multiple Gemini keys and you rotate" - the way the studio's Key
# Management does it (UserApiKey rows, default first, callers try each candidate). The old single field
# (gemini_api_key …) becomes pool entry #1 on first read and is kept equal to the default key, so every older
# reader still finds a key.

POOL = "keypool"


def _pool_all() -> dict:
    return store.read(POOL, {}) or {}


def _pool_write(allv: dict) -> None:
    store.write(POOL, allv)


def _mine(user_id: str) -> dict:
    """{extra: [spare keys], meta: {"field:<pid>": {name, status, reason, since, last_ok}}} - the DEFAULT key is
    the old single field itself (so every older reader keeps working); the spares live here."""
    m = _pool_all().get(user_id) or {}
    return {"extra": list(m.get("extra") or []), "meta": dict(m.get("meta") or {})}


def _save_mine(user_id: str, mine: dict) -> None:
    # 2026-10-02 review: read-change-write of the one shared pool file under the store lock - two people saving keys at
    # once never wipe each other's entry
    with store._LOCK:                                   # noqa: SLF001 - this portal's own store
        allv = _pool_all()
        allv[user_id] = mine
        _pool_write(allv)


def own_keys(user_id: str, pid: str | None = None) -> list[dict]:
    """The keys this person PUT IN: the single field first (it is the default), then the spares.
    Nothing borrowed — this is the list a lender lends from and a borrower reads through."""
    out = []
    for r in rows():
        if (pid and r["id"] != pid) or not r.get("key_field"):
            continue
        mine = _mine(user_id)
        legacy = str(store.keys_of(user_id).get(r["key_field"]) or "")
        if legacy:
            meta = mine["meta"].get(f"field:{r['id']}") or {}
            out.append({"id": f"field:{r['id']}", "provider": r["id"],
                        "name": meta.get("name") or engine.say("providers.rotate", "name_default", n=1),
                        "secret": legacy, "hint": store.mask(legacy), "is_default": True, "status": meta.get("status") or "active",
                        "reason": meta.get("reason") or "", "since": meta.get("since") or "", "added": meta.get("added") or "", "last_ok": meta.get("last_ok") or ""})
        out += [dict(k, is_default=False) for k in mine["extra"] if k.get("provider") == r["id"]]
    return out


def pool(user_id: str, pid: str) -> list[dict]:
    """Every key this person may spend on for one provider: their OWN first (never somebody else's
    money while you have your own), then the ones lent to them (keyshare.borrowed)."""
    r = row(pid)
    if not r or not r.get("key_field"):
        return []
    import keyshare                                      # late: keyshare asks own_keys back
    return own_keys(user_id, pid) + keyshare.borrowed(user_id, pid)


def pool_all(user_id: str) -> list[dict]:
    """Every key this person may spend on, every provider."""
    return [k for r in rows() for k in pool(user_id, r["id"])]


def _new_key(pid: str, secret: str, name: str, is_default: bool) -> dict:
    return {"id": store.new_id(), "provider": pid, "name": name, "secret": secret, "hint": store.mask(secret),
            "is_default": is_default, "status": "active", "reason": "", "since": "", "added": store.now(), "last_ok": ""}


def _set_field(user_id: str, pid: str, secret: str, name: str = "") -> None:
    """The default key IS the single field (blank = none); its name and state live in meta."""
    r = row(pid)
    store.save_keys_for(user_id, {r["key_field"]: secret}, keep_blank_secrets=False)
    mine = _mine(user_id)
    mine["meta"][f"field:{pid}"] = {"name": name or engine.say("providers.rotate", "name_default", n=1), "status": "active",
                                    "reason": "", "since": "", "added": store.now(), "last_ok": ""} if secret else {}
    _save_mine(user_id, mine)


def pool_view(user_id: str) -> dict:
    """Every pooled key, without its secret, for the screen."""
    out = {}
    for r in rows():
        if r.get("key_field"):
            out[r["id"]] = [{a: b for a, b in k.items() if a != "secret"} | {"usable": _usable(k)} for k in pool(user_id, r["id"])]
    return out


def _minutes_since(stamp: str) -> float:
    from datetime import datetime, timezone  # noqa: PLC0415
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds() / 60
    except (ValueError, TypeError):
        return 1e9                                      # no readable stamp = long ago


def _usable(k: dict) -> bool:
    """Chip providers.key_usable decides; Python only measures the clock. `blocked` is set on a
    BORROWED key whose lender's spending cap is spent (keyshare.limit_block)."""
    return engine.run("providers.key_usable", {"status": k.get("status") or "active", "minutes_since": _minutes_since(k.get("since") or ""),
                                              "revive_minutes": engine.setting("providers.rotate", "revive_minutes"),
                                              "blocked": bool(k.get("blocked"))}) is True


def no_key_text(user_id: str, pid: str) -> str:
    """Why no key can be used: none on the account, or (2026-09-28 a real Veo run: a 429 quota answer was reported as
    "No key on your account") every key resting after the provider's refusal - said with its reason and when it wakes."""
    r = row(pid) or {"label": pid}
    rest = [k for k in pool(user_id, pid) if not _usable(k)]
    if not rest:
        return say("no_key", provider=r["label"])
    k = rest[0]
    if k.get("blocked") and k.get("blocked_reason"):     # 2026-09-28 a lent key's cap or an empty wallet says so
        return str(k["blocked_reason"])
    left = max(1, int(float(engine.setting("providers.rotate", "revive_minutes")) - _minutes_since(k.get("since") or "")))
    return say("keys_resting", provider=r["label"], minutes=left, reason=str(k.get("reason") or "")[:160])


def name_max() -> int:
    return int(engine.setting("providers.rotate", "name_max"))


def _label(name: str, n: int) -> str:
    """Chip providers.rotate: trimmed to name_max; blank = name_default for place n."""
    return (name or "").strip()[:name_max()] or engine.say("providers.rotate", "name_default", n=n)


def pool_add(user_id: str, pid: str, secret: str, name: str = "") -> dict:
    r = row(pid)
    if not r or not r.get("key_field"):
        raise HTTPException(400, say("no_provider", provider=pid))
    secret = "".join(ch for ch in str(secret or "") if ch.isprintable() and not ch.isspace())
    if len(secret) < int(engine.setting("store.settings", "mask_min_length")):
        raise HTTPException(400, say("key_too_short"))
    have = own_keys(user_id, pid)
    if len(have) >= int(engine.setting("providers.rotate", "keys_max")):
        raise HTTPException(400, say("too_many_keys", max=engine.setting("providers.rotate", "keys_max")))
    name = _label(name, len(have) + 1)
    if not have:                                        # the first key IS the field
        _set_field(user_id, pid, secret, name)
        return {a: b for a, b in pool(user_id, pid)[0].items() if a != "secret"}
    k = _new_key(pid, secret, name, False)
    mine = _mine(user_id)
    mine["extra"].append(k)
    _save_mine(user_id, mine)
    return {a: b for a, b in k.items() if a != "secret"}


def _find(user_id: str, key_id: str) -> dict:
    for r in rows():
        for k in pool(user_id, r["id"]):
            if k["id"] == key_id:
                return k
    raise HTTPException(404, say("no_such_key"))


def pool_default(user_id: str, key_id: str) -> None:
    """A spare becomes the default: it moves into the field, the old default becomes a spare (state kept)."""
    hit = _find(user_id, key_id)
    if hit.get("shared"):
        import keyshare  # noqa: PLC0415 - a borrowed secret never enters your own key box
        raise HTTPException(400, keyshare.say("borrowed_no_default"))
    if hit["is_default"]:
        return
    pid = hit["provider"]
    old = next((k for k in pool(user_id, pid) if k["is_default"]), None)
    mine = _mine(user_id)
    mine["extra"] = [k for k in mine["extra"] if k["id"] != key_id]
    if old:
        mine["extra"].insert(0, {a: b for a, b in old.items() if a != "is_default"} | {"id": store.new_id()})
    _save_mine(user_id, mine)
    _set_field(user_id, pid, hit["secret"], hit["name"])
    if hit.get("status") != "active":
        _mark(user_id, f"field:{pid}", hit["status"], hit.get("reason", ""))


def pool_rename(user_id: str, key_id: str, name: str) -> dict:
    """A label says which account a key came from, so "Key 2 hit its limit" names the one to top up.
    Blank = the default name for its place in the list."""
    hit = _find(user_id, key_id)
    if hit.get("shared"):
        # 2026-09-23 owner: "Key Label can be modified by user 2 ... may want to give Owner name to
        # Key for his or her understanding purpose." The borrower's label is theirs; the owner keeps theirs.
        import keyshare  # noqa: PLC0415
        return keyshare.relabel(user_id, hit["grant_id"], name)
    pid = hit["provider"]
    n = 1 + [k["id"] for k in own_keys(user_id, pid)].index(key_id)
    name = _label(name, n)
    mine = _mine(user_id)
    if key_id.startswith("field:"):
        mine["meta"][key_id] = (mine["meta"].get(key_id) or {}) | {"name": name}
    else:
        for k in mine["extra"]:
            if k["id"] == key_id:
                k["name"] = name
    _save_mine(user_id, mine)
    return {"id": key_id, "name": name}


def pool_remove(user_id: str, key_id: str) -> None:
    hit = _find(user_id, key_id)
    if hit.get("shared"):
        import keyshare  # noqa: PLC0415 - give it back (revoke the share); deleting is the owner's
        raise HTTPException(400, keyshare.say("borrowed_no_remove"))
    pid = hit["provider"]
    mine = _mine(user_id)
    if hit["is_default"]:
        spares = [k for k in mine["extra"] if k.get("provider") == pid]
        if spares:                                      # the next spare takes the field
            nxt = spares[0]
            mine["extra"] = [k for k in mine["extra"] if k["id"] != nxt["id"]]
            _save_mine(user_id, mine)
            _set_field(user_id, pid, nxt["secret"], nxt["name"])
            if nxt.get("status") != "active":
                _mark(user_id, f"field:{pid}", nxt["status"], nxt.get("reason", ""))
        else:
            _set_field(user_id, pid, "")
        return
    mine["extra"] = [k for k in mine["extra"] if k["id"] != key_id]
    _save_mine(user_id, mine)


def _keeper(user_id: str, k: dict) -> str:
    """Whose meta holds a key's state. A borrowed key's status (exhausted, invalid) is the OWNER's —
    one key at its quota is at its quota for everybody who was lent it."""
    return k.get("owner_id") or user_id


def _mark(user_id: str, key_id: str, status: str, reason: str = "") -> None:
    mine = _mine(user_id)
    patch = {"status": status, "reason": reason[:200], "since": store.now() if status != "active" else ""}
    if status == "active":
        patch["last_ok"] = store.now()
    if key_id.startswith("field:"):
        mine["meta"][key_id] = (mine["meta"].get(key_id) or {}) | patch
    else:
        for k in mine["extra"]:
            if k["id"] == key_id:
                k.update(patch)
    _save_mine(user_id, mine)


def classify_failure(text: str) -> str:
    """exhausted | invalid | other - chip providers.failure_kind reads the provider's own sentence."""
    return str(engine.run("providers.failure_kind", {"detail": text or ""}) or "other")


def candidates(user_id: str, pid: str) -> list[dict]:
    """The keys to try, in order: default first, only the usable ones; a provider with no key field gets one blank."""
    r = row(pid)
    if r and not r.get("key_field"):
        return [{"id": "", "name": r["label"], "secret": ""}]
    return [k for k in pool(user_id, pid) if _usable(k)]


def gone() -> dict:
    """Models a provider answered "not found / withdrawn" for, as seen at call time: {model: {provider, at, detail}}.
    State, not a rule: Check models clears a mark when the provider lists the model again."""
    return store.read("models_gone", {}) or {}


def mark_gone(pid: str, model: str, detail: str) -> None:
    if model:
        d = gone()
        d[model] = {"provider": pid, "at": store.now(), "detail": detail[:300]}
        store.write("models_gone", d)


def call_with_keys(user_id: str, pid: str, call, log=lambda line: None, model: str = ""):
    """`call(secret)` on each usable key in turn. A quota / invalid answer marks the key and moves on; any other
    error is the call's own and is raised as is. Returns (result, key row)."""
    tried = candidates(user_id, pid)
    r = row(pid) or {"label": pid}
    if not tried:
        raise HTTPException(400, no_key_text(user_id, pid))
    last, broke = "", False
    for k in tried:
        store.using_key(user_id, k)                     # whose key pays for what follows (store.spend / store.log_run)
        try:
            out = call(k["secret"])
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001 - classified by the provider's own words
            detail = str(e).strip().splitlines()[0][:300] if str(e) else type(e).__name__
            kind = classify_failure(detail)
            if kind == "model_gone":                    # 2026-09-26: the MODEL is gone, not the key - out of every list
                mark_gone(pid, model, detail)
                raise RuntimeError(say("model_gone", provider=r["label"], model=model or "?")) from e
            if kind == "other":
                raise
            if kind == "no_credit":                     # this account is out of money: try the person's next key, but
                broke, last = True, detail              # never park this one - after a top-up it must work at once
                log(say("key_no_credit", name=k.get("name", ""), reason=detail[:120]))
                continue
            if k.get("id"):
                _mark(_keeper(user_id, k), k["id"], kind, detail)
            log(say("key_exhausted" if kind == "exhausted" else "key_invalid", name=k.get("name", ""), reason=detail[:120]))
            last = detail
            continue
        if k.get("id") and k.get("status") != "active":
            _mark(_keeper(user_id, k), k["id"], "active")
        return out, k
    if broke:
        from core.jobs import OutOfCredit  # noqa: PLC0415
        raise OutOfCredit(say("no_credit", provider=r["label"], reason=last[:160]))
    raise RuntimeError(say("all_keys_failed", provider=r["label"], reason=last))


def key_for(user_id: str, pid: str) -> str:
    """The first usable key (default first) - for callers that make one call themselves."""
    r = row(pid)
    if not r:
        raise HTTPException(400, say("no_provider", provider=pid))
    if not r.get("key_field"):
        return ""
    c = candidates(user_id, pid)
    if not c:
        return ""
    store.using_key(user_id, c[0])                      # whose key pays for what follows
    return c[0]["secret"]


def have_key(user_id: str, pid: str) -> bool:
    r = row(pid)
    return bool(r) and (not r.get("key_field") or bool(candidates(user_id, pid)))


def shared_secrets() -> list[dict]:
    """Every secret held by more than one account. A key belongs to ONE person (store.keys_of has no
    portal-wide key and no environment fallback on purpose); two accounts on the same secret means
    somebody is spending a balance they cannot see. Run `python providers.py --shared-keys` on a
    portal's data dir to confirm the live answer is empty."""
    seen: dict[str, set[str]] = {}
    for uid in set(store.read("user_keys", {}) or {}) | set(_pool_all()):
        for r in rows():
            for k in pool(uid, r["id"]):
                seen.setdefault(k["secret"], set()).add(uid)
    return [{"hint": store.mask(s), "users": sorted(u)} for s, u in seen.items() if len(u) > 1]


def test_key(user_id: str, key_id: str) -> dict:
    """One cheap real call on ONE pooled key: Gemini's four words, or an OpenAI-shaped chat; a pass revives it."""
    import narrator  # noqa: PLC0415
    k = _find(user_id, key_id)
    r = row(k["provider"])
    started = time.time()
    try:
        if r["sdk"] == "google":
            model = narrator.probe_key(k["secret"], _gemini_model(user_id, "text"))
        elif r.get("test_url"):
            # 2026-09-28 owner's fal.ai key failed Test: a video-only provider was sent an OpenAI chat ("Application
            # completions not found") and the good key was marked invalid. Its row names one GET that needs the key.
            _get_json(r["test_url"], "", float(settings()["timeout_seconds"]),
                      {"Authorization": f'{r.get("test_auth") or "Bearer"} {k["secret"]}'})
            model = r["label"]
        else:
            model = next((m["id"] for m in model_rows("text") if m["provider"] == r["id"]), "")
            openai_json(k["secret"], r["base_url"], model, engine.setting("providers.rotate", "test_prompt"))
    except Exception as e:  # noqa: BLE001 - the provider's own sentence, classified, marked on the key
        detail = str(e).strip().splitlines()[0][:300] if str(e) else type(e).__name__
        kind = classify_failure(detail)
        _mark(user_id, key_id, kind if kind != "other" else "invalid", detail)
        raise HTTPException(400, detail)
    _mark(user_id, key_id, "active")
    return {"ok": True, "model": model, "elapsed_s": round(time.time() - started, 1), "message": say("key_ok", name=k["name"], model=model, secs=round(time.time() - started, 1))}


def _unit_price(kind: str, m: dict) -> float | None:
    """One comparable price per model: a second of video, one picture, a million tokens in plus out."""
    if kind == "video":
        v = m.get("usd_per_second", m.get("usd_per_second_high"))
    elif kind == "image":
        v = m.get("usd_per_image")
    elif m.get("in") is not None and m.get("out") is not None:
        v = float(m["in"]) + float(m["out"])
    else:
        import media  # noqa: PLC0415 - Gemini's own text prices
        v = media.cost_usd(m["id"], 1_000_000, 1_000_000)
    return None if v in (None, "") else float(v)


def is_gone(model: str) -> bool:
    facts = {r["id"]: r for r in engine.run("providers.model_facts")["rows"]}
    return bool(model) and (model in gone() or (facts.get(model) or {}).get("status") == "retired")


def successor(kind: str, model: str) -> str:
    """2026-09-28 owner "auto-replace": the model that takes over from a gone one - chip providers.watch: the same
    provider, a known price no higher than the old one's (x max_price_ratio), the best quality, then the cheapest.
    Blank = none fits: the person picks another (never a dearer model nobody chose)."""
    w = engine.run("providers.watch")
    rows_ = catalog(kind)                               # gone ones are already out of this list
    old = next((m for m in [*rows_, *(model_rows(kind))] if m["id"] == model), None) or model_row(kind, model) or {}
    if kind == "video" and not old:
        old = video_row(model) or {}
    was = _unit_price(kind, old | {"id": model}) if old else None
    facts = {r["id"]: r for r in engine.run("providers.model_facts")["rows"]}
    pid = old.get("provider") or ""
    fit = []
    for m in rows_:
        price = _unit_price(kind, m)
        if m["id"] == model or (facts.get(m["id"]) or {}).get("status") == "retired" or price is None or was is None:
            continue
        if (w["same_provider"] and m["provider"] != pid) or price > was * float(w["max_price_ratio"]) + 1e-12:
            continue
        fit.append((-(int((facts.get(m["id"]) or {}).get("quality") or 0)), price, m["id"]))
    return sorted(fit)[0][2] if fit else ""


def current(kind: str, model: str) -> str:
    """The model to use for `model`: itself, or its successor when it is gone (the same one when none fits)."""
    return (successor(kind, model) or model) if is_gone(model) else model


def choice(user_id: str, kind: str, model: str | None = None) -> dict:
    """The model this person uses - a gone one swapped for its successor (providers.watch), said in `swapped`."""
    got = _choice(user_id, kind, model)
    now = current(kind, got["model"]) if got.get("model") else ""
    if now and now != got["model"]:
        was = got["model"]
        got = _choice(user_id, kind, now) | {"swapped": say("model_swapped", old=was, new=now, provider=got["label"])}
    return got


def _choice(user_id: str, kind: str, model: str | None = None) -> dict:
    """The provider + model this person uses for one kind of work: their pick, else the chip's default.
    For Gemini the model is what the older fields already hold (gemini_model / board.settings / film.settings).
    2026-09-23 `model` names one outright (a comic's road: chip comics.roads): its provider comes from
    providers.models, or Gemini when it is one of Gemini's own."""
    k = settings()
    mine = store.keys_of(user_id)
    if model:
        mrow = model_row(kind, model)
        pid = str(mrow["provider"]) if mrow else k["gemini_id"]
        r = row(pid)
        return {"kind": kind, "provider": pid, "label": r["label"], "sdk": r["sdk"], "base_url": r.get("base_url", ""), "model": model,
                "key": key_for(user_id, pid), "have_key": have_key(user_id, pid), "free": bool(r.get("free")), "price": mrow}
    pid = str(mine.get(f"{kind}_provider") or "") or k[f"{kind}_default"]
    r = row(pid)
    if not r or kind not in r["kinds"]:
        pid, r = k[f"{kind}_default"], row(k[f"{kind}_default"])
    model = str(mine.get(f"{kind}_model") or "")
    if pid == k["gemini_id"] or not model:
        model = _gemini_model(user_id, kind) if pid == k["gemini_id"] else (next((m["id"] for m in model_rows(kind) if m["provider"] == pid), ""))
    return {"kind": kind, "provider": pid, "label": r["label"], "sdk": r["sdk"], "base_url": r.get("base_url", ""), "model": model,
            "key": key_for(user_id, pid), "have_key": have_key(user_id, pid), "free": bool(r.get("free")),
            "price": model_row(kind, model)}


def _gemini_model(user_id: str, kind: str) -> str:
    mine = store.keys_of(user_id)
    if kind == "text":
        return mine.get("gemini_model") or store.DEFAULT_KEYS["gemini_model"]
    src = engine.setting("providers.settings", "default_from").get(kind)   # which chip holds this kind's default model
    if not src or src["chip"] not in engine.chips():   # 2026-10-10: an edition without Gemini's image / video chips has no such default
        return ""
    return engine.setting(src["chip"], src["key"])


def _edition_setting(chip_id: str, key: str, default):
    """2026-10-10: board.settings / film.settings (Gemini's own image and video models) are one edition's chips - a portal
    without them offers no Gemini image / video model; the other providers' (chip providers.models) stay."""
    return engine.setting(chip_id, key) if chip_id in engine.chips() else default


def catalog(kind: str) -> list[dict]:
    """Every model of one kind the portal offers today (a gone one is out) - nobody's keys asked."""
    k = settings()
    models = []
    if kind == "text":
        for m in engine.run("store.models")["choices"]:
            models.append({"provider": k["gemini_id"], "kind": kind, "id": m, "label": m})
    elif kind == "image":
        if _edition_setting("board.settings", "model", ""):
            models.append({"provider": k["gemini_id"], "kind": kind, "id": engine.setting("board.settings", "model"),
                           "label": engine.setting("board.settings", "model"), "usd_per_image": engine.setting("board.settings", "usd_per_image")})
    else:
        for m in _edition_setting("film.settings", "models", []):
            models.append({"provider": k["gemini_id"], "kind": kind} | m)
    models += [dict(m) for m in model_rows(kind)]
    off = gone()                                        # 2026-09-26: withdrawn by the provider (seen at call time)
    return [m for m in models if m["id"] not in off]


def offered(user_id: str) -> dict:
    """Every provider and model the screens can pick from, with whether this person's key is in."""
    mine, here = store.keys_of(user_id), shown()
    ids = {r["id"] for r in here}
    out = {"kinds": {}, "chosen": {kind: {a: b for a, b in choice(user_id, kind).items() if a != "key"} for kind in kinds()},
           "providers": [{"id": r["id"], "label": r["label"], "kinds": r["kinds"], "key_field": r.get("key_field", ""),
                          "where": r.get("where", ""), "free": bool(r.get("free")), "have_key": have_key(user_id, r["id"])} for r in here]}
    for kind in kinds():
        models = [m for m in catalog(kind) if m["provider"] in ids]
        for m in models:
            m["have_key"] = have_key(user_id, m["provider"])
        out["kinds"][kind] = models
    out["set"] = {r["key_field"]: bool(mine.get(r["key_field"])) for r in here if r.get("key_field")}
    return out


def options(user_id: str, kind: str, cost_of) -> list[dict]:
    """2026-09-26 owner: "by the job, every model that can do it, with price and quality". Every offered model of one
    kind with its price for THIS job (`cost_of(model_id)`, None = unknown, never $0), its quality and use (chip
    providers.model_facts). Which are listed, their order and the Recommended one are chip providers.model_options -
    a pre-selection the person still confirms, never a silent choice."""
    facts = {r["id"]: r for r in engine.run("providers.model_facts")["rows"]}
    rows_ = [{"id": m["id"], "label": m.get("label") or m["id"], "provider": m["provider"], "have_key": m["have_key"],
              "cost_usd": cost_of(m["id"]), "quality": (facts.get(m["id"]) or {}).get("quality"),
              "good_for": (facts.get(m["id"]) or {}).get("good_for", ""), "status": (facts.get(m["id"]) or {}).get("status", "active")}
             for m in sorted(offered(user_id)["kinds"].get(kind) or [], key=lambda m: cost_of(m["id"]) if cost_of(m["id"]) is not None else 1e9)]
    got = engine.run("providers.model_options", {"rows": rows_})       # chip: listed, order, Recommended - no rule here
    return [r | {"recommended": r["id"] == got["recommended"]} for r in got["models"]]


def choose(user_id: str, kind: str, model: str) -> dict:
    """The picked model becomes this person's own for that kind of work - every job that uses "your model" follows it."""
    m = next((x for x in offered(user_id)["kinds"].get(kind) or [] if x["id"] == model), None)
    if not m:
        raise HTTPException(400, say("no_model", model=str(model)[:80], provider=""))
    return save_choice(user_id, kind, m["provider"], model)


def save_choice(user_id: str, kind: str, pid: str, model: str) -> dict:
    if kind not in kinds():
        raise HTTPException(400, say("no_kind", kind=kind))
    r = row(pid)
    if not r or kind not in r["kinds"]:
        raise HTTPException(400, say("no_provider", provider=pid))
    model = str(model or "").strip()
    if pid == settings()["gemini_id"]:
        if kind == "text" and model:
            store.save_keys_for(user_id, {"gemini_model": model})
        store.save_keys_for(user_id, {f"{kind}_provider": pid, f"{kind}_model": ""})
    else:
        if not model_row(kind, model) or model_row(kind, model)["provider"] != pid:
            raise HTTPException(400, say("no_model", model=model, provider=r["label"]))
        store.save_keys_for(user_id, {f"{kind}_provider": pid, f"{kind}_model": model})
    return choice(user_id, kind) | {"key": ""}


# --- the wire: OpenAI-shaped HTTP (chat, images) and Runway's task API ----------------------------------------

def _post_json(url: str, key: str, body: dict, timeout: float, extra_headers: dict | None = None) -> dict:
    """One JSON POST. Kept as one function so a self-check can stand in for the network."""
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} | ({"Authorization": f"Bearer {key}"} if key else {}) | (extra_headers or {})
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with egress.fetch(req, timeout=timeout, purpose="providers") as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(say("refused", status=e.code, reason=detail))


def _get_json(url: str, key: str, timeout: float, extra_headers: dict | None = None) -> dict:
    headers = ({"Authorization": f"Bearer {key}"} if key else {}) | (extra_headers or {})
    req = urllib.request.Request(url, headers=headers, method="GET")
    with egress.fetch(req, timeout=timeout, purpose="providers") as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, out: Path, timeout: float) -> None:
    import shutil  # noqa: PLC0415
    out.parent.mkdir(parents=True, exist_ok=True)
    with egress.fetch(url, timeout=timeout, purpose="providers") as resp, out.open("wb") as f:
        shutil.copyfileobj(resp, f, 1024 * 1024)       # 2026-10-02 review: streamed to disk, never the whole clip in memory


def _same_site(url: str, base: str) -> bool:
    """A polling address the provider handed back carries OUR key: only ever to the provider's own site, over https
    (2026-10-02 review: a reply naming another host would have been sent the key)."""
    from urllib.parse import urlparse  # noqa: PLC0415
    u, b = urlparse(str(url or "")), urlparse(str(base or ""))
    tail = lambda h: ".".join((h or "").lower().split(".")[-2:])   # noqa: E731 - queue.fal.run and fal.run are one site
    return u.scheme == "https" and bool(u.hostname) and tail(u.hostname) == tail(b.hostname)


def data_url(p: Path) -> str:
    mime = "image/png" if p.suffix.lower() == ".png" else "image/webp" if p.suffix.lower() == ".webp" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode('ascii')}"


def openai_chat_body(model: str, prompt: str, images: list[Path] | None) -> dict:
    content: list = [{"type": "text", "text": prompt}]
    for p in images or []:
        content.append({"type": "image_url", "image_url": {"url": data_url(p)}})
    return {"model": model, "messages": [{"role": "user", "content": content if images else prompt}],
            "response_format": {"type": "json_object"}}


def openai_json(key: str, base_url: str, model: str, prompt: str, images: list[Path] | None = None):
    k = settings()
    resp = _post_json(f"{base_url.rstrip('/')}/chat/completions", key, openai_chat_body(model, prompt, images), float(k["timeout_seconds"]))
    text = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    usage = resp.get("usage") or {}
    return text, int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)


def _post_multipart(url: str, key: str, fields: dict, files: list[tuple[str, Path]], timeout: float) -> dict:
    """One multipart POST (form fields + picture files). Kept as one function so a self-check can stand in for the network."""
    edge = f"----sm{int(time.time() * 1000)}"
    crlf = "\r\n"
    parts = [f'--{edge}{crlf}Content-Disposition: form-data; name="{n}"{crlf}{crlf}{v}{crlf}'.encode() for n, v in fields.items()]
    for n, p in files:
        head = f'--{edge}{crlf}Content-Disposition: form-data; name="{n}"; filename="{p.name}"{crlf}Content-Type: image/png{crlf}{crlf}'
        parts.append(head.encode() + p.read_bytes() + crlf.encode())
    req = urllib.request.Request(url, data=b"".join(parts) + f"--{edge}--{crlf}".encode(), method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={edge}", "Authorization": f"Bearer {key}"})
    try:
        with egress.fetch(req, timeout=timeout, purpose="providers") as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(say("refused", status=e.code, reason=e.read().decode("utf-8", "replace")[:300]))


def openai_image(key: str, base_url: str, model: str, prompt: str, size: str, out: Path, refs: list[Path] | None = None) -> None:
    """2026-09-27 owner: "fix the character drift for Leonard" - reference pictures (the character sheet, the scene before)
    were never sent to OpenAI: /images/generations takes none, while the prompt named "Image 1, Image 2". A model whose
    row says `refs` gets them through /images/edits, in the prompt's order."""
    k = settings()
    if refs:
        resp = _post_multipart(f"{base_url.rstrip('/')}/images/edits", key, {"model": model, "prompt": prompt, "n": 1, "size": size},
                               [("image[]", p) for p in refs], float(k["image_timeout_seconds"]))
    else:
        resp = _post_json(f"{base_url.rstrip('/')}/images/generations", key, {"model": model, "prompt": prompt, "n": 1, "size": size},
                          float(k["image_timeout_seconds"]))
    item = (resp.get("data") or [{}])[0]
    if item.get("b64_json"):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(base64.b64decode(item["b64_json"]))
    elif item.get("url"):
        _download(item["url"], out, float(k["image_timeout_seconds"]))
    else:
        raise RuntimeError(say("nothing_back"))


def runway_ratio(aspect: str, mrow: dict) -> str:
    return (mrow.get("ratios") or {}).get(aspect) or next(iter((mrow.get("ratios") or {"16:9": "1280:720"}).values()))


def runway_clip(key: str, base_url: str, mrow: dict, prompt: str, seconds: int, aspect: str, out: Path,
                first_frame: Path | None, wait=lambda secs: None, ticket: dict | None = None, on_ticket=lambda t: None) -> None:
    """Runway's image-to-video task: a first frame is REQUIRED (the storyboard still or the chain's last frame),
    then the task is polled until it succeeds and its file downloaded."""
    k = settings()
    if not first_frame:
        raise RuntimeError(say("needs_image", model=mrow["id"]))
    head = {"X-Runway-Version": str(k["runway_version"])}
    body = {"model": mrow["id"], "promptImage": data_url(first_frame), "promptText": prompt[:int(k["runway_prompt_max"])],
            "ratio": runway_ratio(aspect, mrow), "duration": int(seconds)}
    task = ticket if ticket and ticket.get("id") else _post_json(f"{base_url.rstrip('/')}/image_to_video", key, body, float(k["timeout_seconds"]), head)
    tid = task.get("id")
    if not tid:
        raise RuntimeError(say("nothing_back"))
    on_ticket({"id": tid})
    started = time.time()
    for _ in range(int(k["max_polls"])):
        time.sleep(float(k["poll_seconds"]))
        wait(int(time.time() - started))
        t = _poll_get(f"{base_url.rstrip('/')}/tasks/{tid}", key, float(k["timeout_seconds"]), head)
        if t is None:
            continue
        status = str(t.get("status") or "").upper()
        if status == "SUCCEEDED":
            urls = t.get("output") or []
            if not urls:
                raise RuntimeError(say("nothing_back"))
            _download(urls[0], out, float(k["download_timeout_seconds"]))
            return
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(say("refused", status=status, reason=str(t.get("failure") or t.get("failureCode") or "")[:200]))
    raise RuntimeError(say("timed_out", secs=int(k["poll_seconds"] * k["max_polls"])))


def _dig(d, path: str):
    """A value at a dotted path in a JSON answer ("video.url"); None when any step is missing."""
    cur = d
    for part in str(path or "").split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _poll_get(url: str, key: str, timeout: float, head: dict) -> dict | None:
    """One status look at a clip already PAID for. A network hiccup (timeout, dropped connection) is None - look again
    at the same request. 2026-09-28 owner's fal credit: "The read operation timed out" while polling made the whole
    step retry, i.e. a second paid submission of the same clip. An HTTP answer (401, 404, 5xx) is still raised."""
    import socket  # noqa: PLC0415
    try:
        return _get_json(url, key, timeout, head)
    except urllib.error.HTTPError:
        raise
    except (TimeoutError, socket.timeout, urllib.error.URLError, ConnectionError):
        return None


def fal_clip(key: str, base_url: str, mrow: dict, prompt: str, seconds: int, aspect: str, out: Path,
             first_frame: Path | None, negative: str = "", wait=lambda secs: None, ticket: dict | None = None,
             on_ticket=lambda t: None) -> None:
    """fal.ai's queue (2026-09-20 owner: the cheap road - Kling, Hailuo, Seedance, Wan on one key): submit to the
    model's endpoint (the image-to-video one when a first frame leads), poll its status URL, fetch the answer, download
    the file. Every field name, status word and price is the model's row in providers.models / providers.settings -
    this function knows no model."""
    k = settings()
    fields = mrow.get("fields") or {}
    model_id = str(mrow.get("image_id") or mrow["id"]) if first_frame else str(mrow["id"])
    body = {fields["prompt"]: prompt[:int(k["fal_prompt_max"])]}
    if first_frame and fields.get("image"):
        body[fields["image"]] = data_url(first_frame)
    if fields.get("duration"):
        body[fields["duration"]] = str(int(seconds)) if mrow.get("duration_text") else int(seconds)
    if fields.get("aspect") and mrow.get("ratios") and not (first_frame and mrow.get("aspect_from_image")):
        body[fields["aspect"]] = runway_ratio(aspect, mrow)
    if fields.get("resolution") and mrow.get("resolution"):
        body[fields["resolution"]] = mrow["resolution"]
    if fields.get("negative") and negative:
        body[fields["negative"]] = negative
    head = {"Authorization": f"{k['fal_auth_scheme']} {key}"}
    if ticket and ticket.get("status_url"):             # sent (and paid) before a restart: collect it, never send again
        task = ticket
    else:
        task = _post_json(f"{base_url.rstrip('/')}/{model_id}", "", body, float(k["timeout_seconds"]), head)
    status_url, response_url = task.get("status_url"), task.get("response_url")
    if not status_url or not response_url or not (_same_site(status_url, base_url) and _same_site(response_url, base_url)):
        raise RuntimeError(say("nothing_back"))
    on_ticket({"status_url": status_url, "response_url": response_url})
    started = time.time()
    failed = {str(s).upper() for s in k["fal_status_failed"]}
    for _ in range(int(k["max_polls"])):
        time.sleep(float(k["poll_seconds"]))
        wait(int(time.time() - started))
        t = _poll_get(status_url, "", float(k["timeout_seconds"]), head)
        if t is None:
            continue                                     # paid already: look at the same request again, never resubmit
        status = str(t.get("status") or "").upper()
        if status == str(k["fal_status_done"]).upper():
            answer = _poll_get(response_url, "", float(k["timeout_seconds"]), head)
            if answer is None:
                continue
            url = _dig(answer, mrow.get("video_path"))
            if not url:
                raise RuntimeError(say("nothing_back"))
            _download(str(url), out, float(k["download_timeout_seconds"]))
            return
        if status in failed:
            raise RuntimeError(say("refused", status=status, reason=str(t.get("error") or t.get("detail") or "")[:200]))
    raise RuntimeError(say("timed_out", secs=int(k["poll_seconds"] * k["max_polls"])))


# --- the three doors the portal knocks on --------------------------------------------------------------------

def text_json(user_id: str, prompt: str, images: list[Path] | None = None, model: str | None = None):
    """JSON from this person's text model. Returns (text, tokens_in, tokens_out, provider, model)."""
    import narrator  # noqa: PLC0415 - narrator imports store; the Gemini wire lives there
    c = choice(user_id, "text", model)
    model = model or c["model"]
    if not c["have_key"]:
        raise HTTPException(400, no_key_text(user_id, c["provider"]))
    if c["sdk"] == "google":
        extra = {"images": images} if images else {}   # the older wire (and its stand-ins) take no images
        (text, tin, tout), _k = call_with_keys(user_id, c["provider"], lambda key: narrator.gemini_json(key, model, prompt, **extra), model=model)
    else:
        (text, tin, tout), _k = call_with_keys(user_id, c["provider"], lambda key: openai_json(key, c["base_url"], model, prompt, images), model=model)
    return text, tin, tout, c["provider"], model


def video_row(model: str) -> dict | None:
    """A video model from film.settings (Gemini) or providers.models (the rest), with its provider named."""
    k = settings()
    g = next((r for r in _edition_setting("film.settings", "models", []) if r["id"] == model), None)
    if g:
        return dict(g) | {"provider": k["gemini_id"]}
    return model_row("video", model)


# --- Check models (2026-09-26 owner: "how will the portal know when models come and go?") --------------------------
def _dig(obj, path: str):
    for part in [x for x in str(path or "").split(".") if x]:
        obj = obj.get(part) if isinstance(obj, dict) else None
    return obj


def model_check(user_id: str) -> dict:
    """Ask each provider (chip providers.model_lists, with this person's key) which models it offers today, and compare
    with what the portal offers: `new` = listed there, not here (kind guessed, OpenRouter's price carried); `gone` = offered
    here, not listed there. A provider that answers clears any "gone" mark it lists again."""
    import re  # noqa: PLC0415
    k = engine.run("providers.model_lists")
    offer = offered(user_id)["kinds"]
    facts = {r["id"]: r for r in engine.run("providers.model_facts")["rows"]}
    marks = gone()
    out = []
    for lr in k["rows"]:
        pid, r = lr["provider"], row(lr["provider"])
        if not r:
            continue
        mine = {m["id"]: kind for kind, ms in offer.items() for m in ms if m["provider"] == pid}
        mine |= {m: v.get("kind", "") for m, v in marks.items() if v.get("provider") == pid}
        entry = {"provider": pid, "label": r["label"], "new": [], "gone": [], "error": ""}
        keys = candidates(user_id, pid)
        if lr["auth"] != "none" and (not keys or not keys[0].get("secret")):
            entry["error"] = say("check_no_key", provider=r["label"])
            out.append(entry)
            continue
        key = keys[0]["secret"] if keys else ""
        url = lr["url"].replace("{base}", str(r.get("base_url") or "").rstrip("/")).replace("{key}", key)
        try:
            got = _get_json(url, key if lr["auth"] == "bearer" else "", float(k["timeout_seconds"]))
        except Exception as e:  # noqa: BLE001 - said to the owner, per provider
            entry["error"] = say("check_failed", provider=r["label"], reason=str(e)[:160])
            out.append(entry)
            continue
        listed = {}
        for x in _dig(got, lr["list"]) or []:
            mid = str(_dig(x, lr["id"]) or "")
            mid = mid[len(lr["strip"]):] if lr["strip"] and mid.startswith(lr["strip"]) else mid
            if mid:
                listed[mid] = x
        for mid in listed:
            if mid in marks and marks[mid].get("provider") == pid:
                marks.pop(mid)                          # listed again: not gone after all
        for mid, x in sorted(listed.items()):
            if mid in mine or not re.search(lr["include"], mid) or (lr["exclude"] and re.search(lr["exclude"], mid)):
                continue
            kind = next((kr["kind"] for kr in k["kind_rows"] if re.search(kr["pattern"], mid)), "text")
            if kind not in r["kinds"]:
                continue
            pr = x.get("pricing") if isinstance(x, dict) else None       # OpenRouter says its price per token
            price = {"in": round(float(pr["prompt"]) * 1e6, 4), "out": round(float(pr["completion"]) * 1e6, 4)} if pr and pr.get("prompt") not in (None, "") else {}
            x = x if isinstance(x, dict) else {}
            lab = x.get("displayName") or x.get("display_name") or ("" if str(x.get("name", "")).startswith("models/") else x.get("name")) or mid
            entry["new"].append({"id": mid, "kind": kind, "label": str(lab)[:80], "price": price})
        for mid, kind in sorted(mine.items()):
            if listed and mid not in listed and (facts.get(mid) or {}).get("status") != "retired":
                entry["gone"].append({"id": mid, "kind": kind, "seen_gone": mid in marks})
        out.append(entry)
    store.write("models_gone", marks)
    return {"providers": out, "at": store.now()}


def watch() -> dict:
    """The daily model watch (rule models_daily, outcome model_watch): Check models on the first owner's keys; a model
    offered here that its provider no longer lists is marked gone (chip providers.watch auto_mark_gone), and the
    owner gets one message saying what went, what came, and what took over."""
    w = engine.run("providers.watch")
    owner = next((u for u in store.users() if u.get("role") == "owner"), None)
    if not owner:
        return {"lines": [], "changed": False}
    got = model_check(owner["id"])
    lines, n_gone, n_new = [], 0, 0
    for e in got["providers"]:
        if e["error"]:
            lines.append(say("watch_error", provider=e["label"], reason=e["error"][:160]))
        for g in e["gone"]:
            n_gone += 1
            if w["auto_mark_gone"] and not g["seen_gone"]:
                mark_gone(e["provider"], g["id"], say("watch_subject", gone=1, new=0))
            nxt = successor(g["kind"], g["id"])
            lines.append(say("watch_gone", model=g["id"], provider=e["label"],
                             swap=say("watch_swap", new=nxt) if nxt else say("watch_noswap")))
        for m in e["new"]:
            n_new += 1
            lines.append(say("watch_new", model=m["id"], provider=e["label"], kind=m["kind"]))
    out = {"at": got["at"], "lines": lines, "gone": n_gone, "new": n_new, "changed": bool(n_gone or n_new)}
    store.write("model_watch", out)
    return out


def _publish_chip(u: dict, chip_id: str, change) -> dict:
    """A new version of one chip, the way the Ops & Chips Builder publishes it (history kept, tests must pass)."""
    import copy  # noqa: PLC0415
    from core import builder  # noqa: PLC0415
    item = copy.deepcopy(engine.chips()[chip_id])
    change(item)
    got = builder.check("chips", item)
    bad = [t for t in got["tests"] if not t["ok"]]
    if got["problems"] or bad:
        raise HTTPException(422, say("chip_refused", reason="; ".join([str(x) for x in got["problems"]] + [str(t.get("name") or t.get("error") or "test") for t in bad])[:300]))
    out = item | {"version": int(item.get("version") or 0) + 1, "status": "published", "updated_by": u["email"], "updated_at": store.now()}
    builder._write(builder.root() / "chips" / f"{chip_id}.json", out)      # noqa: SLF001
    builder._snapshot("chips", out, u, "publish")                          # noqa: SLF001
    builder.refresh("chips")
    return out


def _rows_param(item: dict, name: str = "rows") -> list:
    return next(p for p in item["params"] if p["name"] == name)["default"]


def _sync_default_tests(item: dict) -> None:
    """A chip whose test case runs on its defaults expects its own rows: keep that case true to the new rows."""
    for t in item.get("test_cases") or []:
        if not t.get("args") and isinstance(t.get("expect_value"), dict) and "rows" in t["expect_value"]:
            t["expect_value"]["rows"] = _rows_param(item)


def model_add(u: dict, body: dict) -> dict:
    """Check models -> Add: the model's price row (providers.models) and its quality row (providers.model_facts)."""
    pid, mid, kind = str(body.get("provider") or ""), str(body.get("id") or "").strip(), str(body.get("kind") or "")
    if not row(pid) or not mid:
        raise HTTPException(400, say("no_provider", provider=pid))
    if kind not in ("text", "image", "video"):
        raise HTTPException(400, say("model_kind_bad"))
    if any(r["id"] == mid for r in model_rows()):
        raise HTTPException(400, say("model_exists", model=mid))
    num = lambda v: round(float(v), 6) if str(v).strip() not in ("", "None") else None  # noqa: E731
    new = {"provider": pid, "kind": kind, "id": mid, "label": str(body.get("label") or mid)[:80]}
    if kind == "text":
        new |= {"in": num(body.get("in")), "out": num(body.get("out"))}
    elif kind == "image":
        new |= {"usd_per_image": num(body.get("usd_per_image")), "size": str(body.get("size") or settings()["image_size"])}
    else:
        new |= {"usd_per_second": num(body.get("usd_per_second"))}

    def add_price(item):
        _rows_param(item).append(new)
        _sync_default_tests(item)
    _publish_chip(u, "providers.models", add_price)

    def add_fact(item):
        rows_ = [r for r in _rows_param(item) if r["id"] != mid]
        rows_.append({"id": mid, "quality": int(body.get("quality") or 3), "good_for": str(body.get("good_for") or "")[:120], "status": "active"})
        next(p for p in item["params"] if p["name"] == "rows")["default"] = rows_
        _sync_default_tests(item)
    _publish_chip(u, "providers.model_facts", add_fact)
    return {"ok": True, "model": new}


def model_retire(u: dict, body: dict) -> dict:
    """Check models -> Retire: status retired in providers.model_facts - out of every picker, prices kept for history."""
    mid = str(body.get("id") or "").strip()
    if not mid:
        raise HTTPException(400, say("no_model", model="", provider=""))

    def retire_it(item):
        rows_ = _rows_param(item)
        hit = next((r for r in rows_ if r["id"] == mid), None)
        if hit:
            hit["status"] = "retired"
        else:
            rows_.append({"id": mid, "quality": None, "good_for": "", "status": "retired"})
        _sync_default_tests(item)
    _publish_chip(u, "providers.model_facts", retire_it)
    marks = gone()
    marks.pop(mid, None)
    store.write("models_gone", marks)
    return {"ok": True}


def price_row(model: str) -> dict | None:
    """Text prices for media.cost_usd: a providers.models text row {in, out} for a non-Gemini model."""
    m = model_row("text", model)
    return {"model": m["id"], "in": m["in"], "out": m["out"]} if m and "in" in m else None


if __name__ == "__main__":  # ponytail: one runnable self-check of the wire's shapes and the registry
    # 2026-09-28 an empty wallet said "keys resting, wakes in 60 minutes": a blocked key says its own reason
    _real_pool = pool
    globals()["pool"] = lambda uid, pid: [{"id": "g", "blocked": True, "blocked_reason": "credit used up", "status": "active"}]
    assert no_key_text("u", "gemini") == "credit used up", no_key_text("u", "gemini")
    globals()["pool"] = _real_pool
    # 2026-09-28 owner "auto-replace": a gone model hands over to the same provider's best model at no higher price
    _real_gone = gone
    # 2026-10-10: on whatever video models this portal offers (film.settings - Gemini's Veo - is one edition's chip, not every portal's):
    # the dearest model of a provider with two or more hands over to one of that provider's at no higher price
    vids_ = [m for m in catalog("video") if _unit_price("video", m) is not None]
    pick_ = next((m for m in sorted(vids_, key=lambda m: -_unit_price("video", m))
                  if any(o["provider"] == m["provider"] and o["id"] != m["id"] for o in vids_)), None)
    if pick_:
        globals()["gone"] = lambda: {pick_["id"]: {"provider": pick_["provider"]}}
        nxt_ = successor("video", pick_["id"])
        got_ = next((o for o in vids_ if o["id"] == nxt_), None)
        assert got_ and got_["provider"] == pick_["provider"] and _unit_price("video", got_) <= _unit_price("video", pick_), (pick_["id"], nxt_)
        assert current("video", pick_["id"]) == nxt_ and current("video", nxt_) == nxt_
    globals()["gone"] = lambda: {"gpt-image-1-mini": {"provider": "openai"}}
    assert successor("image", "gpt-image-1-mini") == "", "nothing dearer takes over a cheap model nobody chose"
    globals()["gone"] = lambda: {"gpt-image-1": {"provider": "openai"}}
    assert successor("image", "gpt-image-1") == "gpt-image-1-mini", "same provider, cheaper, takes over"
    globals()["gone"] = _real_gone
    # the daily watch marks what a provider stopped listing and says who takes over - on throwaway data, no network
    import tempfile as _tf
    from core import store as _cs
    _was_data = _cs.DATA
    _cs.DATA = Path(_tf.mkdtemp())
    store.write("users", [{"id": "o1", "email": "o@x.org", "role": "owner"}])
    _real_check = model_check
    globals()["model_check"] = lambda uid: {"at": "2026-09-28T00:00:00", "providers": [
        {"provider": "openai", "label": "OpenAI", "error": "", "new": [{"id": "gpt-9", "kind": "text"}],
         "gone": [{"id": "gpt-image-1", "kind": "image", "seen_gone": False}]}]}
    wv_ = watch()
    assert "gpt-image-1" in gone() and wv_["changed"] and any("gpt-image-1-mini" in ln for ln in wv_["lines"]), wv_
    assert any("gpt-9" in ln for ln in wv_["lines"]) and current("image", "gpt-image-1") == "gpt-image-1-mini"
    globals()["model_check"] = _real_check
    _cs.DATA = _was_data
    import sys
    import tempfile
    import core.store as cs
    if "--shared-keys" in sys.argv:                     # audit a LIVE portal: no output = every account on its own key
        shared = shared_secrets()
        for s in shared:
            print("SHARED", s["hint"], "->", ", ".join(s["users"]))
        print(f"{len(shared)} shared key(s) in {cs.DATA}")
        sys.exit(1 if shared else 0)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        cs.DATA = Path(tmp)
        u = "u1"
        assert row("gemini") and "text" in row("gemini")["kinds"] and row("openai")["sdk"] == "openai"
        c = choice(u, "text")
        assert c["provider"] == "gemini" and c["model"] == "gemini-flash-latest" and not c["have_key"], c
        store.save_keys_for(u, {"openai_api_key": "sk-test-000000000000"})
        got = save_choice(u, "text", "openai", "gpt-4.1-nano")
        assert got["provider"] == "openai" and got["model"] == "gpt-4.1-nano" and got["have_key"] and got["price"]["in"] == 0.1, got
        try:
            save_choice(u, "text", "openai", "made-up-model")
            raise AssertionError("an unknown model was accepted")
        except HTTPException as e:
            assert "made-up-model" in e.detail
        try:
            save_choice(u, "video", "openai", "gpt-4.1-nano")
            raise AssertionError("a provider that makes no video was accepted for video")
        except HTTPException:
            pass
        assert choice(u, "image")["provider"] == "gemini"
        if "film.settings" in engine.chips():              # 2026-10-10: Gemini's own video models are one edition's chip (the Studio's)
            assert choice(u, "video")["model"] == "veo-3.1-fast-generate-preview"
        # 2026-09-23 a comic's road names the model outright: its provider follows (providers.models), Gemini for its own
        assert choice(u, "image", "gpt-image-1-mini")["provider"] == "openai" and choice(u, "image", "gpt-image-1-mini")["price"]["usd_per_image"] == 0.011
        assert choice(u, "image", "gemini-2.5-flash-image")["provider"] == "gemini" and choice(u, "text", "gemini-2.5-pro")["model"] == "gemini-2.5-pro"
        # 2026-09-27 owner: "fix the character drift for Leonard" - OpenAI never got the reference pictures
        assert model_row("image", "gpt-image-1").get("refs") and model_row("image", "gpt-image-1-mini").get("refs"), "gpt-image models take references"
        _pj, _pm, sent = _post_json, _post_multipart, []
        png = Path(tempfile.mkdtemp()) / "sheet.png"
        png.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
        globals()["_post_json"] = lambda url, *a, **k: sent.append(("json", url)) or {"data": [{"b64_json": base64.b64encode(png.read_bytes()).decode()}]}
        globals()["_post_multipart"] = lambda url, key, fields, files, t: sent.append(("multi", url, [n for n, _p in files])) or {"data": [{"b64_json": base64.b64encode(png.read_bytes()).decode()}]}
        try:
            openai_image("k", "https://x/v1", "gpt-image-1", "p", "1536x1024", png.with_name("a.png"), [png, png])
            openai_image("k", "https://x/v1", "gpt-image-1", "p", "1536x1024", png.with_name("b.png"))
        finally:
            globals()["_post_json"], globals()["_post_multipart"] = _pj, _pm
        assert sent[0] == ("multi", "https://x/v1/images/edits", ["image[]", "image[]"]) and sent[1][0] == "json", sent
        _ed = _edition
        globals()["_edition"] = lambda: "studio"           # the Studio makes clips: Runway and fal.ai are offered there
        try:
            off = offered(u)
        finally:
            globals()["_edition"] = _ed
        assert any(m["id"] == "gpt-4.1-nano" and m["have_key"] for m in off["kinds"]["text"]) and off["chosen"]["text"]["provider"] == "openai"
        assert "video" not in kinds() or any(m["provider"] == "runway" for m in off["kinds"]["video"])   # 2026-10-10: a portal that makes no video lists none
        assert off["set"]["openai_api_key"] and not off["set"]["runway_api_key"]
        if "studio" not in _edition():                     # 2026-10-09: an edition that makes no clips never offers their keys
            here = offered(u)
            assert "runway_api_key" not in here["set"] and not any(m["provider"] in ("runway", "fal") for m in here["kinds"].get("video") or []), here["set"]
        body = openai_chat_body("gpt-4.1-nano", "Say hi as JSON", None)
        assert body["response_format"] == {"type": "json_object"} and body["messages"][0]["content"] == "Say hi as JSON"
        pic = Path(tmp) / "f.png"
        pic.write_bytes(b"\x89PNG fake")
        body = openai_chat_body("gpt-4.1-nano", "Look", [pic])
        assert body["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"), body
        vr = video_row("gen4_turbo")
        assert vr and vr["provider"] == "runway" and runway_ratio("9:16", vr) == "720:1280"
        assert "film.settings" not in engine.chips() or video_row("veo-3.1-fast-generate-preview")["provider"] == "gemini"   # 2026-10-10: the Studio's chip
        assert price_row("gpt-4.1-nano") == {"model": "gpt-4.1-nano", "in": 0.1, "out": 0.4} and price_row("gemini-flash-latest") is None
        # the wire, stood in for: an OpenAI-shaped answer becomes (text, tokens in, tokens out). This file runs as
        # __main__ here, so the stand-in goes into THIS module's globals (an `import providers` would be a second copy)
        real_post = _post_json
        globals()["_post_json"] = lambda url, key, body, timeout, extra_headers=None: {"choices": [{"message": {"content": "{\"ok\": true}"}}], "usage": {"prompt_tokens": 12, "completion_tokens": 3}}
        try:
            assert openai_json("k", "https://x/v1", "m", "p") == ("{\"ok\": true}", 12, 3)
        finally:
            globals()["_post_json"] = real_post
        store.save_keys_for(u, {"openai_api_key": ""}, keep_blank_secrets=False)
        assert not choice(u, "text")["have_key"], "no key = no call"
        assert choice(u, "text")["provider"] == "openai", "the pick stays; the screen says the key is missing"
        # --- the key pool: several keys, default first, quota moves to the next, invalid waits for a test ------------
        store.save_keys_for(u, {"gemini_api_key": "AIza-legacy-000000000000"})
        assert [k["name"] for k in pool(u, "gemini")] == ["Key 1"] and pool(u, "gemini")[0]["secret"] == "AIza-legacy-000000000000", "the single field IS key 1"
        b = pool_add(u, "gemini", "AIza-second-000000000000", "Spare")
        assert [k["name"] for k in pool(u, "gemini")] == ["Key 1", "Spare"] and key_for(u, "gemini") == "AIza-legacy-000000000000"
        assert store.keys_of(u)["gemini_api_key"] == "AIza-legacy-000000000000", "a spare never touches the field"
        seen_keys: list[Any] = []

        def flaky(secret):
            seen_keys.append(secret)
            if "legacy" in secret:                      # the stand-in trips on key 1 only (never a prefix: AQ. keys exist)
                raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded")
            return "fine"
        out, used = call_with_keys(u, "gemini", flaky)
        assert out == "fine" and used["name"] == "Spare" and seen_keys == ["AIza-legacy-000000000000", "AIza-second-000000000000"]
        assert pool(u, "gemini")[0]["status"] == "exhausted" and "quota" in pool(u, "gemini")[0]["reason"]
        assert key_for(u, "gemini") == "AIza-second-000000000000", "an exhausted key steps aside"
        assert classify_failure("API key not valid. Please pass a valid API key.") == "invalid" and classify_failure("bad prompt") == "other"
        try:
            call_with_keys(u, "gemini", lambda s: (_ for _ in ()).throw(ValueError("the picture was refused")))
            raise AssertionError("an error that is not the key's must be raised as is")
        except ValueError:
            pass
        try:
            call_with_keys(u, "gemini", lambda s: (_ for _ in ()).throw(RuntimeError("401 Unauthorized")))
            raise AssertionError("every key failed: said so")
        except RuntimeError as e:
            assert "Every" in str(e)
        assert [k["status"] for k in pool(u, "gemini")] == ["exhausted", "invalid"] and not have_key(u, "gemini")
        pool_default(u, b["id"])
        top = pool(u, "gemini")[0]
        assert top["is_default"] and top["name"] == "Spare" and store.keys_of(u)["gemini_api_key"] == "AIza-second-000000000000", "default = the field"
        assert top["status"] == "invalid" and pool(u, "gemini")[1]["status"] == "exhausted", "each key keeps its state through the swap"
        _mark(u, top["id"], "active")
        assert have_key(u, "gemini") and pool_view(u)["gemini"][0]["usable"] and "secret" not in pool_view(u)["gemini"][0]
        pool_remove(u, top["id"])
        assert store.keys_of(u)["gemini_api_key"] == "AIza-legacy-000000000000" and len(pool(u, "gemini")) == 1, "the next key takes the field"
        pool_remove(u, pool(u, "gemini")[0]["id"])
        assert store.keys_of(u)["gemini_api_key"] == "" and pool(u, "gemini") == [], "the last one gone = no key at all"
        # --- nobody spends another account's key: the same secret under two accounts is a finding -------------------
        store.save_keys_for(u, {"gemini_api_key": "AIza-mine-0000000000000"})
        store.save_keys_for("u2", {"gemini_api_key": "AIza-theirs-000000000"})
        assert shared_secrets() == [], "two accounts, two keys, nothing shared"
        store.save_keys_for("u2", {"gemini_api_key": "AIza-mine-0000000000000"})
        assert [s["users"] for s in shared_secrets()] == [["u1", "u2"]], "one secret under two accounts IS reported"
        pool_add("u2", "gemini", "AIza-mine-0000000000000", "Copied spare")
        assert len(shared_secrets()) == 1, "a spare copied from someone else counts once, not twice"
        # 2026-09-25 owner: out of money = told at once, and after a top-up the same key works (never parked)
        from core.jobs import OutOfCredit  # noqa: PLC0415
        pool_add("pc1", "gemini", "AIza-pc1-0000000000000000", "Mine")

        def broke_(_s):
            raise RuntimeError("The provider refused (402): Payment Required")
        try:
            call_with_keys("pc1", "gemini", broke_)
            raise AssertionError("out of credit must stop the work")
        except OutOfCredit as e:
            assert "run out of credit" in str(e), str(e)
        assert _usable(pool("pc1", "gemini")[0]) and call_with_keys("pc1", "gemini", lambda _s: "fine")[0] == "fine", "a key out of credit is not parked"
    # 2026-09-28 a real Veo run: a key resting after "429 RESOURCE_EXHAUSTED" was reported as "No key on your account"
    _pool = pool
    try:
        globals()["pool"] = lambda u, p: [{"id": "k", "status": "exhausted", "since": store.now(), "reason": "429 RESOURCE_EXHAUSTED"}]
        t_ = no_key_text("u", "gemini")
        assert "resting" in t_ and "429" in t_ and "No Google" not in t_, t_
        globals()["pool"] = lambda u, p: []
        assert no_key_text("u", "gemini") == say("no_key", provider=row("gemini")["label"])
    finally:
        globals()["pool"] = _pool
    # 2026-09-28 owner's fal.ai key: Test sent an OpenAI chat to a video-only provider and marked a good key invalid
    _find_, _gj, _oj, _mk = _find, _get_json, openai_json, _mark
    hit_ = []
    try:
        globals()["_find"] = lambda u, kid: {"provider": "fal", "secret": "abc", "name": "K"}
        globals()["_get_json"] = lambda url, key, t, head=None: hit_.append((url, head)) or {}
        globals()["openai_json"] = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("fal was sent a chat"))
        globals()["_mark"] = lambda *a, **kw: None
        test_key("u", "field:fal")
        assert hit_ and hit_[0][0] == row("fal")["test_url"] and hit_[0][1]["Authorization"] == "Key abc", hit_
    finally:
        globals().update({"_find": _find_, "_get_json": _gj, "openai_json": _oj, "_mark": _mk})
    # 2026-09-28 owner's fal credit: a poll timeout re-submitted (and re-paid) the same clip - it must look again instead
    _pj, _gj, _dl, _sl = _post_json, _get_json, _download, time.sleep
    posts_, answers_ = [], iter([TimeoutError("The read operation timed out"), {"status": "COMPLETED"}, {"video": {"url": "u"}}])

    def _next_answer(*a, **kw):
        x = next(answers_)
        if isinstance(x, Exception):
            raise x
        return x
    try:
        globals()["_post_json"] = lambda *a, **kw: posts_.append(1) or {"status_url": "https://queue.fal.run/m/requests/1/status", "response_url": "https://queue.fal.run/m/requests/1"}
        globals()["_get_json"] = _next_answer
        globals()["_download"] = lambda *a, **kw: None
        time.sleep = lambda s: None
        fal_clip("k", "https://queue.fal.run", {"id": "m", "fields": {"prompt": "prompt"}, "video_path": "video.url"}, "p", 5, "16:9", Path("x.mp4"), None)
        assert posts_ == [1], "a poll timeout must not submit (and pay for) the clip again"
        # 2026-09-28 a restart mid-clip: the saved ticket is collected - nothing is sent again - and a sent request
        # reports its ticket at once
        posts_.clear()
        answers_ = iter([{"status": "COMPLETED"}, {"video": {"url": "u"}}])
        seen_: list[Any] = []
        fal_clip("k", "https://queue.fal.run", {"id": "m", "fields": {"prompt": "prompt"}, "video_path": "video.url"}, "p", 5, "16:9",
                 Path("x.mp4"), None, ticket={"status_url": "https://queue.fal.run/m/requests/1/status", "response_url": "https://queue.fal.run/m/requests/1"}, on_ticket=seen_.append)
        assert posts_ == [] and seen_ == [{"status_url": "https://queue.fal.run/m/requests/1/status", "response_url": "https://queue.fal.run/m/requests/1"}], ("a ticket is collected, never re-sent", posts_, seen_)
        # 2026-10-02 review: a reply naming another host is never sent our key
        try:
            fal_clip("k", "https://queue.fal.run", {"id": "m", "fields": {"prompt": "prompt"}, "video_path": "video.url"}, "p", 5, "16:9",
                     Path("x.mp4"), None, ticket={"status_url": "https://evil.example/s", "response_url": "https://evil.example/r"})
            raise AssertionError("polled a host the provider does not own")
        except RuntimeError as e_:
            assert str(e_) == say("nothing_back"), e_      # refused at the door, not a poll that timed out
    finally:
        globals().update({"_post_json": _pj, "_get_json": _gj, "_download": _dl})
        time.sleep = _sl
    print("providers self-check OK")
