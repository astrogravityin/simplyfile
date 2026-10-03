"""Wallet - managed credits (2026-09-28 owner: "We will make key available for them"). Teachers and kids never make
an API key: the portal owner lends theirs, and every run a person makes on a lent key draws on ONE balance.

The owner adds credit by hand (the person pays by UPI or bank - no gateway yet). Adding credit lends the owner's
default key for every provider to that person as a WALLET share (keyshare grant `wallet: True`); keyshare.limit_block
asks this module whether such a share may still spend. store.log_run charges the wallet with the marked-up price of
each run, less what the portal wasted (a picture the check threw away and drew again - store.waste).

  wallets  {user_id: {added_usd, charged_usd, refunded_usd, cap_usd (None = chip default), days: {date: usd}, adds: [...]}}

Every number and sentence is a chip: wallet.settings, wallet.block, wallet.messages.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException

import store
from core import engine, lists

WALLETS = "wallets"


def settings() -> dict:
    return engine.run("wallet.settings")


def say(key: str, **values) -> str:
    return engine.say("wallet.messages", key, **values)


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _all() -> dict:
    return store.read(WALLETS, {}) or {}


def _row(uid: str) -> dict:
    return _all().get(uid) or {}


def view(uid: str, r: dict | None = None, k: dict | None = None) -> dict:
    """What this person has: added, charged, given back, left, today's use and cap. None when they have no wallet.
    `r`/`k` = their row and the settings when the caller already read them (a list of thousands reads each once)."""
    r = _row(uid) if r is None else r
    if not r:
        return {}
    k = k or settings()
    cap = k["day_cap_usd"] if r.get("cap_usd") is None else r["cap_usd"]
    left = round(float(r.get("added_usd") or 0) - float(r.get("charged_usd") or 0), 6)
    today = round(float((r.get("days") or {}).get(_today()) or 0), 6)
    return {"added_usd": float(r.get("added_usd") or 0), "charged_usd": float(r.get("charged_usd") or 0),
            "refunded_usd": float(r.get("refunded_usd") or 0), "left_usd": left, "today_usd": today, "cap_usd": float(cap or 0),
            "low": 0 < left <= float(k["low_at_usd"]), "adds": (r.get("adds") or [])[-int(k["adds_shown"]):]}


def block(uid: str) -> str:
    """Blank while this person's wallet may spend; otherwise the sentence saying why not (chip wallet.block)."""
    v = view(uid)
    why = engine.run("wallet.block", {"left_usd": v.get("left_usd", 0), "today_usd": v.get("today_usd", 0),
                                      "day_cap_usd": v.get("cap_usd", 0)})
    return say(why, cap=store.money_text(uid, v.get("cap_usd"), 0)) if why else ""


def charge(uid: str, charged_usd: float, refunded_usd: float = 0.0) -> None:
    """store.log_run: one run on a wallet key - what it was charged, and what the portal gave back (not charged)."""
    if not charged_usd and not refunded_usd:
        return
    with store._LOCK:                                    # noqa: SLF001
        allw = _all()
        r = allw.setdefault(uid, {})
        r["charged_usd"] = round(float(r.get("charged_usd") or 0) + float(charged_usd or 0), 6)
        r["refunded_usd"] = round(float(r.get("refunded_usd") or 0) + float(refunded_usd or 0), 6)
        days = r.setdefault("days", {})
        days[_today()] = round(float(days.get(_today()) or 0) + float(charged_usd or 0), 6)
        for d in sorted(days)[:-7]:                      # ponytail: a week of days is all a daily cap needs
            days.pop(d)
        store.write(WALLETS, allw)


def _owner(user: dict) -> None:
    if (user or {}).get("role") != "owner":
        raise HTTPException(403, say("only_owner"))


def add(owner: dict, email: str, amount_usd: float, note: str = "") -> dict:
    """The owner adds credit someone paid for, and lends them the owner's default key for every provider."""
    import keyshare                                      # noqa: PLC0415 - keyshare asks this module back
    import providers                                     # noqa: PLC0415
    _owner(owner)
    k = settings()
    person = store.find_user(str(email or "").strip())
    if not person:
        raise HTTPException(404, say("no_person", email=email))
    try:
        amount = float(amount_usd)
    except (TypeError, ValueError):
        amount = 0.0
    if not 0 < amount <= float(k["add_max_usd"]):
        raise HTTPException(400, say("bad_amount", max=store.money_text(owner["id"], k["add_max_usd"], 0)))
    keys = {}
    for kk in providers.own_keys(owner["id"]):          # the default first, so the first per provider is the one lent
        keys.setdefault(kk["provider"], kk)
    if not keys:
        raise HTTPException(400, say("no_keys"))
    for kk in keys.values():
        g = keyshare.live_grant(owner["id"], kk["id"], person["id"])
        if not g:
            g = keyshare.share(owner["id"], kk["id"], person["email"], owner.get("name", ""), {"markup_pct": k["markup_pct"]})
        keyshare.mark_wallet(g["id"])
    with store._LOCK:                                    # noqa: SLF001
        allw = _all()
        r = allw.setdefault(person["id"], {})
        r["added_usd"] = round(float(r.get("added_usd") or 0) + amount, 6)
        r.setdefault("adds", []).append({"at": store.now(), "usd": amount, "by": owner["id"],
                                         "note": " ".join(str(note or "").split())[:int(k["note_max"])]})
        store.write(WALLETS, allw)
    return {"wallet": view(person["id"]), "message": say("added", amount=store.money_text(owner["id"], amount, 0), email=person["email"],
                                                         left=store.money_text(owner["id"], view(person["id"])["left_usd"], 0))}


def set_cap(owner: dict, email: str, cap_usd) -> dict:
    """The owner changes one person's daily cap (0 = none; blank = the chip's default)."""
    _owner(owner)
    person = store.find_user(str(email or "").strip())
    if not person or person["id"] not in _all():
        raise HTTPException(404, say("no_person", email=email))
    cap = None if cap_usd in (None, "") else max(0.0, float(cap_usd))
    with store._LOCK:                                    # noqa: SLF001
        allw = _all()
        allw[person["id"]]["cap_usd"] = cap
        store.write(WALLETS, allw)
    return {"wallet": view(person["id"]), "message": say("cap_set", email=person["email"], cap=store.money_text(owner["id"], cap, 0))
            if cap else say("cap_off", email=person["email"])}


def everyone(owner: dict, args: dict | None = None) -> list[dict]:
    """The owner's list: every wallet with its person - list wallets (core/lists.py) pages it."""
    _owner(owner)
    people = {u["id"]: u for u in store.users()}
    k = settings()
    return [{"user_id": uid, "email": (people.get(uid) or {}).get("email", uid), "name": (people.get(uid) or {}).get("name", "")}
            | {a: b for a, b in view(uid, r, k).items() if a != "adds"} for uid, r in _all().items()]


lists.source("wallets", everyone)


if __name__ == "__main__":  # ponytail: one runnable self-check - throwaway data, no network
    import tempfile
    from pathlib import Path

    from core import store as cstore
    cstore.DATA = Path(tempfile.mkdtemp())
    assert view("u1") == {} and block("u1"), "no wallet = may not spend on a wallet key"
    with store._LOCK:                                    # noqa: SLF001
        store.write(WALLETS, {"u1": {"added_usd": 15.0}})
    assert block("u1") == "" and view("u1")["left_usd"] == 15.0
    charge("u1", 2.0, refunded_usd=0.4)
    v = view("u1")
    assert v["left_usd"] == 13.0 and v["refunded_usd"] == 0.4 and v["today_usd"] == 2.0, v
    charge("u1", float(settings()["day_cap_usd"]))
    assert "limit" in block("u1"), "over today's cap stops the wallet"
    charge("u1", 11.0)
    assert view("u1")["left_usd"] < 0 and "used up" in block("u1")
    try:
        add({"id": "x", "role": "member"}, "a@b.c", 5)
        raise AssertionError("a member added credit")
    except HTTPException as e:
        assert e.status_code == 403
    # end to end: adding credit lends the owner's key; the borrower's pool sees it as a wallet key; empty = blocked
    import providers
    store.write("users", [{"id": "boss", "email": "boss@x.org", "role": "owner", "name": "Boss"},
                          {"id": "kid", "email": "kid@x.org", "role": "member", "name": "Kid"}])
    store.save_keys_for("boss", {"gemini_api_key": "AIzaTESTKEY0000000000"})
    boss = store.users()[0]
    add(boss, "kid@x.org", 2)
    lent = [k for k in providers.pool("kid", "gemini") if k.get("shared")]
    assert lent and lent[0]["wallet"] and not lent[0]["blocked"] and lent[0]["markup_pct"] == settings()["markup_pct"], lent
    add(boss, "kid@x.org", 1)
    assert len([k for k in providers.pool("kid", "gemini") if k.get("shared")]) == 1, "a second top-up grows the one balance"
    assert view("kid")["left_usd"] == 3.0
    charge("kid", 3.0)
    lent = [k for k in providers.pool("kid", "gemini") if k.get("shared")]
    assert lent[0]["blocked"] and providers.no_key_text("kid", "gemini") == say("empty"), providers.no_key_text("kid", "gemini")
    print("wallet self-check OK")
