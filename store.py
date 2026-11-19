"""This portal's own records: each person's AI key, their money left, and the receipt roll.

Everything generic — the JSON files, accounts, sessions, one-shot links — lives in core/store.py and
is re-exported here, so `store.users()` and `store.read()` keep working in every module.

Which key fields exist and what they say, how a key is shown masked, how long the receipt roll is and
when money is "low" are the chips `store.settings` / `store.funds_low`; which models are offered, the
default, the fall-back order and what a model id may look like are `store.models`; every sentence is
`store.messages`. Python reads and writes the files.
"""
from __future__ import annotations

import os

# The framework reads PORTAL_*; this portal was deployed with TV_*. Map once, before core loads, so
# no running install has to rename a single environment variable. (Infrastructure, not a decision.)
for _name in ("DATA", "BASE", "OWNER_EMAIL", "HTTPS", "SESSION_DAYS", "AUTH_PER_MINUTE", "GEOIP", "GEOIP_DB"):
    if os.getenv(f"TV_{_name}") is not None:
        os.environ.setdefault(f"PORTAL_{_name}", os.environ[f"TV_{_name}"])
os.environ.setdefault("PORTAL_COOKIE", "tv_session")          # sessions signed in before the move stay signed in

import re  # noqa: E402
from contextvars import ContextVar  # noqa: E402
from pathlib import Path  # noqa: E402

from core.store import *  # noqa: E402,F403 - the generic store IS this store
from core.store import _LOCK, SECRET_FILES  # noqa: E402 - underscore names are not star-exported
from core import engine  # noqa: E402

engine.register_dir(Path(__file__).resolve().parent / "chips")
# Which product this server is - Training & Video Portal or the studio - is chip edition.settings,
# picked by PORTAL_EDITION in the service file. Its name is the default until the owner renames it.
import edition  # noqa: E402

os.environ.setdefault("PORTAL_PRODUCT_NAME", edition.current()["product_name"])
SECRET_FILES.add("user_keys")
SECRET_FILES.add("keypool")                       # 2026-09-19 several keys per provider (providers.py)


# --- keys, per person ---------------------------------------------------------------------------
# The only key this portal needs is a Google Gemini key, used by "Draft with AI" in Video Narrator.
# Voices (edge-tts) and video muxing (ffmpeg) are free and need no key at all.
#
# A key belongs to the PERSON, never to the portal: everyone brings their own, spends their own
# money, and can never spend anyone else's. That is why every screen here needs a sign-in.

def _cfg() -> dict:
    return engine.run("store.settings")


def _models() -> dict:
    return engine.run("store.models")


def key_fields() -> dict:
    """The key form: each field's label, whether it is secret, what uses it, where to get it (and for the
    model, the choices offered — a free-text box was a trap: a typo saves fine and then Draft with AI fails
    days later with a message from Google about an unknown model)."""
    return _cfg()["key_fields"]


def default_keys() -> dict:
    cfg = _cfg()
    return {f: "" for f in cfg["key_fields"]} | {cfg["model_field"]: _models()["default_model"]}


def model_id_ok(text: str) -> bool:
    """What a model id can look like at all. Anything else is a typo, not a new model."""
    return engine.run("store.model_id_ok", {"model": text}) is True


def __getattr__(name: str):
    """`store.KEY_FIELDS`, `store.DEFAULT_KEYS` and `store.MODEL_PREFERENCE` still answer for callers written
    before the chips — read live from the chips."""
    if name == "KEY_FIELDS":
        return key_fields()
    if name == "DEFAULT_KEYS":
        return default_keys()
    if name == "MODEL_PREFERENCE":
        return tuple(_models()["preference"])
    raise AttributeError(name)


def keys_of(user_id: str) -> dict:
    """One person's keys. No environment fallback and no portal-wide key on purpose — a shared key
    would let one person spend another's balance without ever seeing it."""
    return default_keys() | (read("user_keys", {}).get(user_id) or {})  # noqa: F405


def save_keys_for(user_id: str, patch: dict, keep_blank_secrets: bool = True) -> None:
    """A blank secret means "keep the stored one": the browser never had the real value, so an empty
    box is ignorance, not an instruction to wipe it. Pass keep_blank_secrets=False to clear one.
    Whitespace inside a secret is dropped — keys get pasted with a stray space more often than not."""
    cfg = _cfg()
    fields, model_field = cfg["key_fields"], cfg["model_field"]
    with _LOCK:
        all_keys = read("user_keys", {})  # noqa: F405
        mine = all_keys.setdefault(user_id, {})
        for field, value in patch.items():
            if field not in fields:
                continue
            text = str(value or "")
            if fields[field]["secret"]:
                # Whitespace AND control characters go: some consoles and remote desktops paste
                # Ctrl+V as a literal SYN (0x16), and a key with one on the end is refused by Google
                # with a bare "400 Bad Request" that names nothing.
                text = "".join(ch for ch in text if ch.isprintable() and not ch.isspace())
                if not text and keep_blank_secrets:
                    continue
            text = text.strip()
            if field == model_field:
                # Empty means "use the default", never "use nothing". A malformed id is refused here
                # rather than surfacing as a confusing failure from Google on the next draft.
                if not text:
                    text = _models()["default_model"]
                elif not model_id_ok(text.lower()):
                    raise ValueError(engine.say("store.messages", "bad_model", model=text))
                else:
                    text = text.lower()
            mine[field] = text
        write("user_keys", all_keys)  # noqa: F405


def mask(value: str) -> str:
    """Never send a key back to the browser. The screen shows only that one is set, and its tail."""
    cfg = _cfg()
    v, dots, tail = str(value or ""), cfg["mask_dots"], cfg["mask_tail"]
    return f"{dots}{v[-tail:]}" if len(v) > cfg["mask_min_length"] else (dots if v else "")


# --- money left, per person ----------------------------------------------------------------------

def funds_for(user_id: str, provider: str | None = None) -> dict:
    provider = provider or _cfg()["default_provider"]
    f = (read("funds", {}).get(user_id) or {}).get(provider, {})  # noqa: F405
    loaded, spent = float(f.get("loaded_usd") or 0), float(f.get("spent_usd") or 0)
    return {"provider": provider, "loaded_usd": loaded, "spent_usd": round(spent, 4),
            "left_usd": round(loaded - spent, 4) if loaded else None,
            "low": engine.run("store.funds_low", {"loaded_usd": loaded, "spent_usd": spent}) is True}


def _fetch_json(url: str, timeout: float) -> dict:
    """One GET, JSON back. A test replaces this name so the suite never touches the network."""
    import json  # noqa: PLC0415
    from core import egress  # noqa: PLC0415
    with egress.fetch(url, timeout=timeout, purpose="funds") as r:
        return json.loads(r.read().decode("utf-8"))


def rates() -> dict:
    """Live rates per dollar from the feed in chip money.currencies, kept in store file `rates`:
    {per_usd: {code: rate}, at: feed's date, fetched_at, tried_at, error}. Asked again only when chip
    money.rates_due says so (once a day; a failed fetch waits retry_minutes and keeps the last good table).
    A blank feed_url = fixed rates only. The screen shows the feed's date, or why the last ask failed."""
    import time  # noqa: PLC0415
    m = engine.run("money.currencies")
    have = read("rates", {})  # noqa: F405
    if not m.get("feed_url"):
        return have
    now = time.time()
    due = engine.run("money.rates_due", {"hours_since_fetched": (now - float(have.get("fetched_at") or 0)) / 3600,
                                         "minutes_since_tried": (now - float(have.get("tried_at") or 0)) / 60,
                                         "refresh_hours": m["refresh_hours"], "retry_minutes": m["retry_minutes"]})
    if due is not True:
        return have
    try:
        got = _fetch_json(m["feed_url"], float(m["feed_timeout_s"]))
        table = got[m["feed_key"]]
        have = {"per_usd": {r["code"]: float(table[r["code"]]) for r in m["rows"] if r["code"] in table},
                "at": str(got.get(m["feed_at_key"], "")), "fetched_at": now, "tried_at": now, "error": ""}
    except Exception as e:  # noqa: BLE001 - the last good table stays; the reason is kept for the screen
        have = dict(have) | {"tried_at": now, "error": (str(e).strip().splitlines() or [type(e).__name__])[0][:200]}
    with _LOCK:
        write("rates", have)  # noqa: F405
    return have


def currency_of(user_id: str) -> dict:
    """The currency this person sees money in (chip money.currencies): their pick, else the default.
    per_usd is the feed's live rate when one is in, else the chip row's fixed one. The books stay in US
    dollars; this only changes how an amount is SHOWN and how a typed budget is read."""
    m = engine.run("money.currencies")
    rows = {r["code"]: r for r in m["rows"]}
    code = str(keys_of(user_id).get("currency") or "")
    row = dict(rows.get(code) or rows[m["default_code"]])
    live = rates()
    if row["code"] in (live.get("per_usd") or {}):
        row["per_usd"] = live["per_usd"][row["code"]]
    return row | {"rates_at": live.get("at", ""), "rates_error": live.get("error", ""),
                  "choices": [{"code": r["code"], "label": r["label"], "symbol": r["symbol"]} for r in m["rows"]]}


def save_currency(user_id: str, code: str) -> dict:
    m = engine.run("money.currencies")
    code = str(code or "").strip().upper()
    if code not in {r["code"] for r in m["rows"]}:
        raise ValueError(engine.say("money.currencies", "no_such", code=code))
    save_keys_for(user_id, {"currency": code})
    return currency_of(user_id)


def money_text(user_id: str, usd: float | None, extra: int = 2) -> str:
    """A dollar amount as this person sees it - symbol, their rate, their decimals (+extra for a cost).
    Every job-log line that names money goes through here, so the log matches the screens."""
    if usd is None:
        return "?"
    c = currency_of(user_id)
    places = int(c["decimals"]) + extra
    return f"{c['symbol']}{float(usd) * float(c['per_usd']):,.{places}f}"


def to_usd(user_id: str, amount: float) -> float:
    """A budget typed in the person's currency, in the dollars the books keep."""
    return float(amount or 0) / float(currency_of(user_id)["per_usd"])


def set_loaded(user_id: str, provider: str, amount: float) -> None:
    with _LOCK:
        all_funds = read("funds", {})  # noqa: F405
        all_funds.setdefault(user_id, {}).setdefault(provider, {})["loaded_usd"] = max(0.0, float(amount or 0))
        write("funds", all_funds)  # noqa: F405


# --- which key is paying for the work happening right now -----------------------------------------
# 2026-09-23 a key may be BORROWED (keyshare.py), so "who asked" and "whose money" are no longer the
# same person. providers hands out a key and stamps it here; spend() and log_run() read the stamp, so
# neither the fifteen call sites nor any future one has to know a key can belong to somebody else.
# A ContextVar is per thread, and a job runs its call and its booking in one thread.
IN_USE: ContextVar = ContextVar("key_in_use", default={})


_LAST_KEY: dict = {}                                     # (user, provider) -> the key that last did paid work
_WASTE: dict = {}                                        # (user, provider) -> dollars the portal threw away (receipt)
_WASTE_SPEND: dict = {}                                  # the same, for the wallet charge in spend()


def using_key(asked_by: str, key: dict | None) -> None:
    """providers: this key is about to do paid work for `asked_by`."""
    stamp = {"user_id": asked_by} | {k: v for k, v in (key or {}).items() if k != "secret"}
    IN_USE.set(stamp)
    if stamp.get("provider"):
        _LAST_KEY[(asked_by, stamp["provider"])] = stamp


def _in_use(user_id: str, provider: str) -> dict:
    """The stamped key, only when it is this person's call on this provider — a thread is reused, and a
    stale stamp must never bill the wrong account. 2026-09-28: a film's clips run in lane THREADS, so the job's own
    thread never saw the stamp and a borrowed key's film was never charged; the last key per person and provider
    answers then. ponytail: two jobs of one person on two keys of one provider at once bill the later key."""
    k = IN_USE.get() or {}
    if k.get("user_id") == user_id and k.get("provider") == provider:
        return k
    return _LAST_KEY.get((user_id, provider)) or {}


def waste(user_id: str, provider: str, usd: float | None) -> None:
    """The portal's own mistake cost this much (a picture the check threw away and drew again): never charged -
    the next store.log_run for this person and provider books it as given back."""
    if usd:
        with _LOCK:
            for d in (_WASTE, _WASTE_SPEND):
                d[(user_id, provider)] = d.get((user_id, provider), 0.0) + float(usd)


def spend(user_id: str, provider: str, amount: float | None) -> None:
    """Booked against whoever OWNS the key that did the work: spending on a borrowed key comes out of
    the lender's balance, which is the only balance the provider will actually charge."""
    if not amount:
        return
    k = _in_use(user_id, provider)
    payer = k.get("owner_id") or user_id
    if k.get("wallet"):                                  # 2026-09-28 managed credits: charged per step, as it is spent
        import wallet  # noqa: PLC0415 - wallet imports store
        with _LOCK:
            wasted = min(float(amount), _WASTE_SPEND.pop((user_id, provider), 0.0))
        pct = float(k.get("markup_pct") or 0)
        wallet.charge(user_id, engine.run("keyshare.price", {"base_usd": float(amount) - wasted, "markup_pct": pct}) or 0,
                      engine.run("keyshare.price", {"base_usd": wasted, "markup_pct": pct}) if wasted else 0)
    with _LOCK:
        all_funds = read("funds", {})  # noqa: F405
        row = all_funds.setdefault(payer, {}).setdefault(provider, {})
        row["spent_usd"] = round(float(row.get("spent_usd") or 0) + float(amount), 6)
        write("funds", all_funds)  # noqa: F405


def log_run(entry: dict) -> None:
    """Every paid or metered attempt, newest last, WITH the key that paid for it (own or borrowed),
    the mark-up in force AT THE TIME and the sitting it belongs to. The mark-up is frozen onto the row
    so raising it later never rewrites what somebody was already charged.
    ponytail: a capped JSON roll. `runs_kept` has to cover the longest gap between bills; move it to
    SQLite the day that stops fitting in memory."""
    keep = _cfg()["runs_kept"]
    user_id = str(entry.get("user_id") or "")
    k = _in_use(user_id, str(entry.get("provider") or ""))
    stamp = {}
    if k:
        pct = float(k.get("markup_pct") or 0)
        with _LOCK:
            wasted = min(float(entry.get("cost_usd") or 0), _WASTE.pop((user_id, str(entry.get("provider") or "")), 0.0))
        stamp = {"key_id": k.get("id"), "key_label": k.get("name"),
                 "key_owner_id": k.get("owner_id") or entry.get("user_id"),
                 "shared": bool(k.get("shared")), "markup_pct": pct,
                 "charged_usd": engine.run("keyshare.price", {"base_usd": float(entry.get("cost_usd") or 0) - wasted,
                                                              "markup_pct": pct}),
                 "refund_usd": engine.run("keyshare.price", {"base_usd": wasted, "markup_pct": pct}) if wasted else 0,
                 "wallet": bool(k.get("wallet")), "session_id": session_now(user_id)}
    with _LOCK:
        rows = read("runs", [])  # noqa: F405
        rows.append({"at": now()} | entry | stamp)  # noqa: F405
        write("runs", rows[-keep:])  # noqa: F405


def runs_of(user_id: str) -> list[dict]:
    """A person sees their own runs only — a receipt roll is nobody else's business."""
    # 2026-10-01: every Home card asked this - the runs file parsed once and shared (view), each caller its own list
    return [dict(r) for r in reversed(view("runs", []) or []) if r.get("user_id") == user_id]  # noqa: F405


def runs_touching(user_id: str) -> list[dict]:
    """Runs this person made OR paid for: a key's owner is billed for what a borrower spent, so they
    see the row. What they see OF it is chip keyshare.name_seen, not this function."""
    return [dict(r) for r in reversed(view("runs", []) or [])  # noqa: F405 - shared parse, each caller its own rows
            if r.get("user_id") == user_id or r.get("key_owner_id") == user_id]


if __name__ == "__main__":  # ponytail: one runnable self-check
    import sys
    assert mask("abcdefghijkl") == "••••••••ijkl"
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        import core.store as _cs
        _cs.DATA = Path(tmp)
        save_keys_for("u1", {"gemini_api_key": " AQ.abc def\x16\n"})
        assert keys_of("u1")["gemini_api_key"] == "AQ.abcdef", "pasted control characters never reach Google"
        try:
            save_keys_for("u1", {"gemini_model": "gemi dsf"})
            raise AssertionError("a malformed model id must be refused")
        except ValueError as e:
            assert '"gemi dsf" is not a model id' in str(e)
        save_keys_for("u1", {"gemini_model": ""})
        assert keys_of("u1")["gemini_model"] == "gemini-flash-latest", "blank means the default"
        set_loaded("u1", "gemini", 10)
        spend("u1", "gemini", 9.5)
        assert funds_for("u1")["low"] is True and funds_for("u1")["left_usd"] == 0.5
        set_loaded("u2", "gemini", 100)
        spend("u2", "gemini", 50)
        assert funds_for("u2")["low"] is False and funds_for("nobody")["low"] is False
        # 2026-09-19 live rates: fetched once, kept, a failure keeps the last table + its reason, never re-asked at once
        asked = []

        def fake_feed(url, timeout):
            asked.append(url)
            if len(asked) > 1:
                raise OSError("feed down")
            return {"rates": {"INR": 90.5, "EUR": 0.9}, "time_last_update_utc": "Sat, 19 Sep 2026 00:00:01 +0000"}
        me = sys.modules[__name__]
        real_feed = me._fetch_json
        me._fetch_json = fake_feed
        try:
            c = currency_of("u1")
            assert c["code"] == "USD" and c["per_usd"] == 1 and c["rates_at"].startswith("Sat, 19 Sep"), c
            assert save_currency("u1", "inr")["per_usd"] == 90.5, "the feed's rate, not the chip's fallback"
            assert money_text("u1", 1) == "₹90.5000" and to_usd("u1", 181) == 2.0
            assert len(asked) == 1, "one fetch a day, not one per screen"
            r = read("rates", {})  # noqa: F405
            r["fetched_at"] = r["tried_at"] = 0                      # a day later, the feed is down
            write("rates", r)  # noqa: F405
            c = currency_of("u1")
            assert c["per_usd"] == 90.5 and c["rates_error"] == "feed down" and len(asked) == 2, c
            assert currency_of("u1")["rates_error"] == "feed down" and len(asked) == 2, "a failed ask waits retry_minutes"
            try:
                save_currency("u1", "xyz")
                raise AssertionError("an unknown currency must be refused")
            except ValueError as e:
                assert "XYZ" in str(e)
        finally:
            me._fetch_json = real_feed
    assert mask("") == ""
    assert keys_of("nobody")["gemini_api_key"] == "", "a person with no key has no key"
    assert keys_of("nobody")["gemini_model"] == "gemini-flash-latest", "a default new keys can use"
    assert model_id_ok("gemini-2.5-flash") and not model_id_ok("gemi dsf")
    assert not model_id_ok("") and not model_id_ok("ab")
    me = sys.modules[__name__]
    assert me.KEY_FIELDS["gemini_model"]["choices"][0] == "gemini-flash-latest", "old callers still read KEY_FIELDS"
    assert me.MODEL_PREFERENCE[0] == "gemini-flash-latest" and me.DEFAULT_KEYS["gemini_api_key"] == ""
    with tempfile.TemporaryDirectory() as tmp2:
        _cs.DATA = Path(tmp2)
        # 2026-09-28 a film's clips run in lane threads: the key stamped THERE must still bill the job's log_run,
        # a wallet key is charged per step as it is spent, and a redrawn picture is given back, never charged
        import threading
        import wallet
        write(wallet.WALLETS, {"kid": {"added_usd": 10.0}})
        lent = {"id": "g1", "provider": "gemini", "owner_id": "boss", "shared": True, "wallet": True, "markup_pct": 50}

        def lane():
            using_key("kid", lent)
            waste("kid", "gemini", 0.04)
            spend("kid", "gemini", 0.08)
        t_ = threading.Thread(target=lane)
        t_.start()
        t_.join()
        wv = wallet.view("kid")
        assert abs(wv["charged_usd"] - 0.06) < 1e-9 and abs(wv["refunded_usd"] - 0.06) < 1e-9, ("0.04 kept x 1.5; 0.04 given back", wv)
        log_run({"what": "film", "user_id": "kid", "provider": "gemini", "cost_usd": 0.08})
        last = read("runs", [])[-1]
        assert last.get("key_owner_id") == "boss" and last.get("wallet") and abs(last["charged_usd"] - 0.06) < 1e-9, last
    print("store self-check OK")
