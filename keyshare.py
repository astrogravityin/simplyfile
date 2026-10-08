"""Lending a key: one person's key used by another, with every run it paid for on the record.

2026-09-23 owner: "User can share their key with some other user and revoke the key also ... We need
to track how much spent was done by user 2 on user 1's key 1 ... User 1 can push the usage bill to
User 2 ... we need to track when access was given when it was revoked ... user 1 should not see
entire name of the video. User 2 can see to cross verify ... Key Label can be modified by user 2."

Shapes:
  key_grants.json  one row per lending, never deleted - it keeps the day it began and the day it
                   ended, and the borrower's own name for the key.
  key_bills.json   one row per bill pushed, with the totals frozen at the moment it was pushed.
  runs             the receipt roll (store.log_run) now stamps WHICH key paid for each run.

Nothing here decides anything. Who may lend to whom (keyshare.may_share), how much of a run's name a
viewer is shown (keyshare.name_seen), what a share's state is called (keyshare.grant_state), how a
bill is grouped (keyshare.bill_view) and every limit and sentence (keyshare.settings /
keyshare.messages) are chips. This file keeps records and asks.
"""
from __future__ import annotations

from fastapi import HTTPException

import store
from core import engine, lists, ops

GRANTS = "key_grants"
BILLS = "key_bills"


def settings() -> dict:
    return engine.run("keyshare.settings")


def limits_cfg() -> dict:
    return engine.run("keyshare.limits")


def charged(base_usd, markup_pct) -> float:
    """What a borrower pays for a run that really cost `base_usd`. Chip keyshare.price owns the sum."""
    return engine.run("keyshare.price", {"base_usd": base_usd or 0, "markup_pct": markup_pct or 0}) or 0.0


def say(key: str, **values) -> str:
    return engine.say("keyshare.messages", key, **values)


# --- the lending record ---------------------------------------------------------------------------

def grants() -> list[dict]:
    return list(store.read(GRANTS, []) or [])


def _write(rows: list[dict]) -> None:
    store.write(GRANTS, rows)


def state_of(g: dict) -> str:
    return engine.run("keyshare.grant_state", {"revoked": bool(g.get("revoked_at")),
                                               "ended_by_owner": g.get("revoked_by") == g.get("owner_id")})


def _live(g: dict) -> bool:
    return not g.get("revoked_at")


def lent_by(owner_id: str, key_id: str = "", live_only: bool = False) -> list[dict]:
    """Every lending this person made — the whole history unless asked for the live ones."""
    return [g for g in grants() if g["owner_id"] == owner_id
            and (not key_id or g["key_id"] == key_id) and (_live(g) or not live_only)]


def held_by(holder_id: str, live_only: bool = True) -> list[dict]:
    return [g for g in grants() if g["holder_id"] == holder_id and (_live(g) or not live_only)]


def _grant(grant_id: str) -> dict:
    g = next((x for x in grants() if x["id"] == grant_id), None)
    if not g:
        raise HTTPException(404, say("no_grant"))
    return g


def _terms(body: dict, current: dict | None = None) -> dict:
    """The lender's terms, checked against the chips: a mark-up per cent and three rolling caps
    (0 = no cap). Anything not given keeps what the share already had."""
    s, lim = settings(), limits_cfg()
    old = current or {}
    out = {}
    if "markup_pct" in body or not current:
        pct = _number(body.get("markup_pct"), old.get("markup_pct") or 0)
        if pct < 0 or pct > float(s["markup_max_pct"]):
            raise HTTPException(400, say("bad_markup", max=s["markup_max_pct"]))
        out["markup_pct"] = pct
    for w in lim["windows"]:
        field = f"cap_{w}_usd"
        if field in body or not current:
            cap = _number(body.get(field), old.get(field) or 0)
            if cap < 0 or cap > float(lim["cap_max_usd"]):
                raise HTTPException(400, say("bad_cap", max=lim["cap_max_usd"]))
            out[field] = cap
    return out


def _number(value, fallback: float) -> float:
    if value in (None, ""):
        return float(fallback)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _cutoff(hours: float) -> str:
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415
    return (datetime.now(timezone.utc) - timedelta(hours=float(hours))).isoformat(timespec="seconds")


def window_spend(g: dict) -> dict:
    """What this borrower has been CHARGED on this key inside each rolling window, beside the cap.
    The charged price is the one capped: it is the number the borrower sees and is billed."""
    lim = limits_cfg()
    rows = [r for r in store.runs_touching(g["owner_id"])
            if r.get("key_id") == g["key_id"] and r.get("user_id") == g["holder_id"]]
    out = {}
    for w in lim["windows"]:
        hours = float(lim.get(f"{w}_hours") or 0)
        since = _cutoff(hours) if hours else str(g.get("granted_at") or "")
        spent = sum(float(r.get("charged_usd") or 0) for r in rows if str(r.get("at") or "") >= since)
        cap = float(g.get(f"cap_{w}_usd") or 0)
        out[w] = {"spent": round(spent, 6), "cap": cap, "hours": hours, "left": round(cap - spent, 6) if cap else None,
                  "pct": round(spent / cap * 100, 1) if cap else None,
                  "warn": bool(cap) and spent >= cap * float(lim["warn_at_pct"]) / 100}
    return out


def limit_block(g: dict) -> str:
    """Blank while the borrower may still spend; otherwise the sentence saying which cap stopped them."""
    if g.get("wallet"):                                  # 2026-09-28 a wallet share spends the person's ONE balance
        import wallet  # noqa: PLC0415
        return wallet.block(g["holder_id"])
    use = window_spend(g)
    ok = engine.run("keyshare.within_limit", {
        f"{k}_{w}": (use[w]["spent"] if k == "spent" else use[w]["cap"])
        for w in use for k in ("spent", "cap")})
    if ok is True:
        return ""
    for w, u in use.items():
        if u["cap"] and u["spent"] >= u["cap"]:
            return say(f"over_limit_{w}", spent=round(u["spent"], 4), cap=u["cap"], hours=u["hours"])
    return say("over_limit_day", spent=0, cap=0, hours=0)


def warn_line(g: dict, viewer_id: str = "") -> str:
    """Blank while there is plenty left; otherwise the sentence telling the borrower to buy more.
    Bought credit never refills, so its warning is the one that matters - chip keyshare.limits
    warn_at_pct (80) means "warn once only a fifth is left"."""
    who = viewer_id or g.get("holder_id") or ""
    label = g.get("holder_label") or g.get("label_at_grant") or ""
    use = window_spend(g)
    total = use.get("total") or {}
    if total.get("cap") and total.get("warn") and (total.get("left") or 0) > 0:
        return say("credit_low", left=store.money_text(who, total["left"], 0),
                   bought=store.money_text(who, total["cap"], 0), label=label)
    for w, u in use.items():
        if w != "total" and u.get("cap") and u.get("warn") and (u.get("left") or 0) > 0:
            return say("cap_low", label=label, window=w, left=store.money_text(who, u["left"], 0),
                       cap=store.money_text(who, u["cap"], 0))
    return ""


def add_credit(owner_id: str, grant_id: str, amount_usd: float) -> dict:
    """Top up credit somebody already bought, on the share they already hold. A second share on the
    same key would be a second key in their list and a second thing to keep track of - the credit is
    the thing being bought, so it is the credit that grows."""
    g = _grant(grant_id)
    if g["owner_id"] != owner_id:
        raise HTTPException(403, say("not_your_grant"))
    added = _number(amount_usd, 0)
    with store._LOCK:                                    # noqa: SLF001
        rows = grants()
        for r in rows:
            if r["id"] == grant_id:
                r["cap_total_usd"] = round(float(r.get("cap_total_usd") or 0) + added, 6)
                r["topped_up_at"] = store.now()
                g = r
        _write(rows)
    left = window_spend(g)["total"]
    return g | {"message": say("credit_added", amount=store.money_text(g["holder_id"], added, 0),
                               label=g.get("holder_label") or g.get("label_at_grant") or "",
                               total=store.money_text(g["holder_id"], left["cap"], 0),
                               left=store.money_text(g["holder_id"], left["left"], 0))}


def mark_wallet(grant_id: str) -> None:
    """This share draws on the borrower's wallet (wallet.add), not on a credit of its own."""
    with store._LOCK:                                    # noqa: SLF001
        rows = grants()
        for r in rows:
            if r["id"] == grant_id:
                r["wallet"] = True
        _write(rows)


def live_grant(owner_id: str, key_id: str, holder_id: str) -> dict | None:
    """The share this person already holds on this key, if any - what a top-up grows."""
    return next((g for g in lent_by(owner_id, key_id, live_only=True) if g["holder_id"] == holder_id), None)


def set_terms(owner_id: str, grant_id: str, body: dict) -> dict:
    """The lender changes the mark-up or a cap on a live share. It applies from now on: what was
    already run keeps the mark-up frozen onto its own row."""
    g = _grant(grant_id)
    if g["owner_id"] != owner_id:
        raise HTTPException(403, say("not_your_grant"))
    patch = _terms(body, g)
    with store._LOCK:                                    # noqa: SLF001
        rows = grants()
        for r in rows:
            if r["id"] == grant_id:
                r.update(patch)
                g = r
        _write(rows)
    return g | {"message": say("limits_saved", label=g.get("label_at_grant") or g["key_id"],
                               summary=terms_text(g))}


def terms_text(g: dict) -> str:
    """"+20% · day: 5 · week: 20" — the share's terms in one line, every word from a chip."""
    lim = limits_cfg()
    pct = float(g.get("markup_pct") or 0)
    parts = [say("markup_none") if not pct else say("markup_some", pct=pct)]
    caps = [say("credit_line", cap=g["cap_total_usd"]) if w == "total" else say("cap_line", window=w, cap=g.get(f"cap_{w}_usd"))
            for w in lim["windows"] if float(g.get(f"cap_{w}_usd") or 0)]
    return " · ".join(parts + (caps or [say("no_limits")]))


def _person(email: str) -> dict | None:
    return store.find_user(str(email or "").strip())


def name_of(user_id: str) -> str:
    u = store.user_by_id(user_id)                    # 2026-10-01: indexed, not a scan of every account per row
    return str((u or {}).get("name") or (u or {}).get("username") or (u or {}).get("email") or say("someone"))


def email_of(user_id: str) -> str:
    u = store.user_by_id(user_id)                    # 2026-10-01: indexed, not a scan of every account per row
    return str((u or {}).get("email") or "")


# --- lend, take back, give back, rename -----------------------------------------------------------

def share(owner_id: str, key_id: str, email: str, who: str = "", terms: dict | None = None) -> dict:
    """Lend one of my keys to somebody with an account here. Their runs spend MY balance, and every
    one of them lands on my usage list."""
    import providers                                     # late: providers.pool asks this module back
    mine = next((k for k in providers.own_keys(owner_id) if k["id"] == key_id), None)
    borrowed = next((k for k in providers.pool_all(owner_id) if k["id"] == key_id and k.get("shared")), None)
    if borrowed:
        raise HTTPException(400, say("borrowed_not_lent_on"))
    if not mine:
        raise HTTPException(404, say("no_key"))
    person = _person(email)
    live = lent_by(owner_id, key_id, live_only=True)
    ok = engine.run("keyshare.may_share", {
        "is_owner": True, "key_is_borrowed": False,
        "same_person": bool(person) and person["id"] == owner_id,
        "person_exists": bool(person),
        "already_has_it": any(g["holder_id"] == (person or {}).get("id") for g in live),
        "holders_now": len(live), "holders_max": settings()["keys_shared_max"]})
    if ok is not True:
        if not person:
            raise HTTPException(404, say("no_such_person", email=email))
        if person["id"] == owner_id:
            raise HTTPException(400, say("not_yourself"))
        if any(g["holder_id"] == person["id"] for g in live):
            raise HTTPException(400, say("already_shared", email=person["email"]))
        raise HTTPException(400, say("too_many_holders", max=settings()["keys_shared_max"]))
    row = {"id": store.new_id(), "key_id": key_id, "owner_id": owner_id, "provider": mine["provider"],
           "holder_id": person["id"], "holder_email": person["email"], "holder_label": "",
           "label_at_grant": mine.get("name") or "", "granted_at": store.now(), "granted_by": who or owner_id,
           "revoked_at": "", "revoked_by": "", "revoked_by_name": ""} | _terms(terms or {})
    with store._LOCK:                                    # noqa: SLF001 - the store's own write lock
        _write(grants() + [row])
    return row | {"state": state_of(row),
                  "message": say("shared_ok", email=person["email"], label=mine.get("name") or key_id)}


def revoke(user_id: str, grant_id: str, who: str = "") -> dict:
    """The owner takes a key back, or the borrower gives it back. Both end the same share; the record
    keeps WHICH of them ended it and when."""
    g = _grant(grant_id)
    if user_id not in (g["owner_id"], g["holder_id"]):
        raise HTTPException(403, say("not_your_grant"))
    if _live(g):
        with store._LOCK:                                # noqa: SLF001
            rows = grants()
            for r in rows:
                if r["id"] == grant_id:
                    r.update({"revoked_at": store.now(), "revoked_by": user_id, "revoked_by_name": who or name_of(user_id)})
                    g = r
            _write(rows)
    label = g.get("holder_label") or g.get("label_at_grant") or g["key_id"]
    message = (say("revoked_ok", email=g["holder_email"], label=label) if user_id == g["owner_id"]
               else say("returned_ok", label=label))
    return g | {"state": state_of(g), "message": message}


def relabel(holder_id: str, grant_id: str, name: str) -> dict:
    """The borrower's OWN name for a borrowed key — usually the lender's name, so a key list of five
    borrowed keys is readable. The owner's own label is untouched."""
    text = str(name or "").strip()[: int(settings()["holder_label_max"])]
    if not text:
        raise HTTPException(400, say("label_needed"))
    g = _grant(grant_id)
    if g["holder_id"] != holder_id:
        raise HTTPException(403, say("not_your_grant"))
    with store._LOCK:                                    # noqa: SLF001
        rows = grants()
        for r in rows:
            if r["id"] == grant_id:
                r["holder_label"] = text
                g = r
        _write(rows)
    return g | {"message": say("relabelled_ok", label=text)}


def borrowed(holder_id: str, pid: str) -> list[dict]:
    """The keys lent TO this person for one provider, in providers.pool's own shape. A key the owner
    has since deleted simply is not here any more — no tombstone, no error."""
    import providers                                     # late: this is called FROM providers.pool
    out = []
    for g in held_by(holder_id):
        if g["provider"] != pid:
            continue
        src = next((k for k in providers.own_keys(g["owner_id"], pid) if k["id"] == g["key_id"]), None)
        if not src:
            continue
        stop = limit_block(g)
        low = "" if stop else warn_line(g, holder_id)
        out.append(dict(src, is_default=False, shared=True, grant_id=g["id"], owner_id=g["owner_id"],
                        owner_name=name_of(g["owner_id"]), markup_pct=float(g.get("markup_pct") or 0), wallet=bool(g.get("wallet")),
                        blocked=bool(stop), blocked_reason=stop, low=bool(low), low_reason=low,
                        name=g.get("holder_label") or say("borrowed_from", owner=name_of(g["owner_id"]))))
    return out


def borrowed_all(holder_id: str) -> list[dict]:
    """Every key lent to this person, whatever the provider."""
    import providers                                     # late
    return [k for r in providers.rows() if r.get("key_field") for k in borrowed(holder_id, r["id"])]


# 2026-09-28 owner: "Lend - it goes beyond 10 we are gone": what I lent is list keys_lent (core/lists.py) - searched,
# sorted and paged on the server; only the page's rows get their terms and spend windows (the costly part).
def _lent_rows(user: dict, args: dict) -> list[dict]:
    names = {u["id"]: u.get("name") or u.get("email") or "" for u in store.users()}
    return [g | {"state": state_of(g), "holder_name": names.get(g["holder_id"], "")}
            for g in lent_by(user["id"], str(args.get("key_id") or ""), live_only=str(args.get("all") or "") != "1")]


def _lent_fill(user: dict, rows: list[dict], args: dict) -> list[dict]:
    return [g | {"terms": terms_text(g), "use": window_spend(g) if g["state"] == "active" else {}} for g in rows]


lists.source("keys_lent", _lent_rows, _lent_fill)


def _held_rows(user: dict, args: dict) -> list[dict]:
    people = {u["id"]: u for u in store.users()}
    return [g | {"state": state_of(g), "owner_name": (people.get(g["owner_id"]) or {}).get("name") or "",
                 "owner_email": (people.get(g["owner_id"]) or {}).get("email") or ""} for g in held_by(user["id"])]


def _held_fill(user: dict, rows: list[dict], args: dict) -> list[dict]:
    """The costly part of a borrowed key - its spend windows, stop and warning, the borrower's own prices - per page."""
    return [g | {"terms": terms_text(g), "use": window_spend(g), "blocked_reason": limit_block(g), "low_reason": warn_line(g, user["id"]),
                 # a borrower is quoted THEIR price (mark-up in), never the provider's own
                 "rates": rate_card(user["id"], float(g.get("markup_pct") or 0))} for g in rows]


lists.source("keys_held", _held_rows, _held_fill)


def shares_view(user_id: str) -> dict:
    """What the Account & key screen shows about lending: how many people hold each of my keys (the people
    themselves are list keys_lent, one page at a time) and what I hold. Never a secret, never a hint of one."""
    counts: dict[str, int] = {}
    for g in lent_by(user_id, live_only=True):
        counts[g["key_id"]] = counts.get(g["key_id"], 0) + 1
    mine = held_by(user_id)
    s = settings()
    return {"lent_counts": counts, "lent_total": sum(counts.values()), "held_n": len(mine), "max_holders": s["keys_shared_max"],
            "label_max": s["holder_label_max"], "markup_max": s["markup_max_pct"],
            "cap_max": limits_cfg()["cap_max_usd"], "windows": limits_cfg()["windows"]}


# --- what a minute of video will cost the borrower --------------------------------------------------

def rate_card(user_id: str, markup_pct: float = 0.0) -> dict:
    """What a borrower is told before they take a key: roughly what a minute of video, a still and a
    thousand words will cost THEM, mark-up already in, with the disclaimer that it is an estimate.
    Every number comes from providers.models; every sentence and assumption from keyshare.rate_card."""
    import providers                                     # late: providers.pool asks this module back
    c = engine.run("keyshare.rate_card")
    cash = lambda usd: store.money_text(user_id, charged(usd, markup_pct), int(c["decimals_extra"]))  # noqa: E731 - their currency, their price
    lines = []
    for kind in c["kinds"]:
        pick = providers.choice(user_id, kind) if kind in providers.kinds() else {}
        m = providers.model_row(kind, str(pick.get("model") or "")) or next(iter(providers.model_rows(kind)), None)
        if not m:
            continue
        label = m.get("label") or m.get("id")
        if kind == "video" and m.get("usd_per_second_low") is not None:
            secs = float(c["seconds_per_minute"])
            lines.append(ops.template(c["video_line"], {
                "low": cash(float(m["usd_per_second_low"]) * secs),
                "high": cash(float(m["usd_per_second_high"]) * secs), "model": label}))
        elif kind == "image" and m.get("usd_per_image") is not None:
            lines.append(ops.template(c["image_line"], {
                "usd": cash(float(m["usd_per_image"])), "model": label}))
        elif kind == "text" and m.get("out") is not None:
            # a price per million tokens -> a price for this many written words
            per_word = float(m["out"]) / 1_000_000 * 1000 / float(c["words_per_1k_tokens"])
            lines.append(ops.template(c["text_line"], {
                "usd": cash(per_word * float(c["text_words"])), "model": label}))
    return {"lines": lines, "markup_pct": markup_pct,
            "markup_line": ops.template(c["with_markup"], {"pct": markup_pct}) if markup_pct else c["at_cost"],
            "disclaimer": c["disclaimer"]}


# --- usage: every run, own key or borrowed ---------------------------------------------------------

def usage_row(r: dict, viewer_id: str, portal: str, labels: dict) -> dict:
    """One line of the usage table, as THIS viewer may see it."""
    s = settings()
    owner = r.get("key_owner_id") or r.get("user_id") or ""
    return {
        "at": r.get("at"),
        "portal": portal,
        "key_id": r.get("key_id"),
        "key_label": labels.get((owner, r.get("key_id")), r.get("key_label") or ""),
        "own": owner == r.get("user_id"),
        "mine": r.get("user_id") == viewer_id,
        "owner_name": name_of(owner) if owner else "",
        "owner_id": owner,
        "used_by": name_of(str(r.get("user_id") or "")),
        "user_id": r.get("user_id"),
        "activity": engine.run("keyshare.name_seen", {
            "name": r.get("what") or "", "is_mine": r.get("user_id") == viewer_id,
            "chars": s["owner_sees_chars"], "tail": s["owner_sees_tail"]}),
        "seconds": r.get("elapsed_s"),
        "provider": r.get("provider"),
        "model": r.get("model"),
        # What THIS viewer is shown as the cost. The borrower is shown - and billed - the charged
        # price; the lender sees that too, and beside it what the provider really took from them.
        "cost_usd": _charged_of(r),
        "base_usd": r.get("cost_usd") if r.get("key_owner_id") == viewer_id else None,
        "markup_pct": r.get("markup_pct") or 0,
        "session_id": r.get("session_id") or "",
        "free": bool(r.get("free")),
        # a failure that cost money is still a run somebody is billed for, so it keeps its reason -
        # but only for the person who made it; a lender is owed the money, not the story.
        "error": r.get("error") if r.get("user_id") == viewer_id else "",
        "tokens_in": r.get("tokens_in") if r.get("user_id") == viewer_id else None,
        "tokens_out": r.get("tokens_out") if r.get("user_id") == viewer_id else None,
    }


def _charged_of(r: dict) -> float | None:
    """What the run was charged at. Rows written before mark-ups existed were charged at cost."""
    if r.get("charged_usd") is not None:
        return r["charged_usd"]
    return r.get("cost_usd")


def _labels(viewer_id: str) -> dict:
    """(owner_id, key_id) → the name THIS viewer calls that key: their own label for their own keys,
    their own label for a borrowed one, the lender's label otherwise."""
    import providers
    out = {}
    for k in providers.own_keys(viewer_id):
        out[(viewer_id, k["id"])] = k.get("name") or ""
    for g in held_by(viewer_id, live_only=False):
        out[(g["owner_id"], g["key_id"])] = g.get("holder_label") or g.get("label_at_grant") or ""
    return out


def usage(viewer_id: str, portal: str, q: str = "", page: int = 1, page_size: int | None = None) -> dict:
    """Every run this person made or paid for, one page of it. Runs on their own key are here too —
    the owner asked for tracking "across the board", not only for shared keys."""
    s = settings()
    labels = _labels(viewer_id)
    rows = [usage_row(r, viewer_id, portal, labels) for r in store.runs_touching(viewer_id)]
    return ops.rows_view(rows=rows, query=q, search_keys=s["usage_search_keys"],
                         sort_key=s["usage_sort_key"], sort_desc=s["usage_sort_desc"],
                         page=page, page_size=page_size or s["usage_page_size"],
                         max_page_size=s["usage_max_page_size"])


# --- bills ------------------------------------------------------------------------------------------

def bills() -> list[dict]:
    return list(store.read(BILLS, []) or [])


def _billed_to(key_id: str, holder_id: str) -> str:
    """The end of the last bill for this key and this person — a new bill starts there."""
    ends = [b["to_at"] for b in bills() if b["key_id"] == key_id and b["holder_id"] == holder_id]
    return max(ends) if ends else ""


def owing(owner_id: str) -> list[dict]:
    """What each borrower has run up on each of my keys since I last billed them. One line per key
    per person — chip keyshare.bill_view decides the grouping and the totals."""
    v = engine.run("keyshare.bill_view")
    v = dict(v, measures=dict(v["measures"], base_usd=["sum", "cost_usd"], charged_usd=["sum", "charged_usd"]))
    labels = _labels(owner_id)
    lent = lent_by(owner_id)
    prepaid = {(g["key_id"], g["holder_id"]) for g in lent if float(g.get("cap_total_usd") or 0)}
    # 2026-09-28 "tens of thousands": the last bill per key and person, each grant, each name - read ONCE, not per run
    billed: dict = {}
    for b in bills():
        kh = (b["key_id"], b["holder_id"])
        billed[kh] = max(billed.get(kh, ""), b["to_at"])
    grant_of = {(g["key_id"], g["holder_id"]): g for g in lent}
    people = {u["id"]: u for u in store.users()}
    mine = [dict(r, charged_usd=_charged_of(r)) for r in store.runs_touching(owner_id)
            if r.get("key_owner_id") == owner_id and r.get("user_id") != owner_id
            and (r.get("key_id"), r.get("user_id")) not in prepaid          # bought credit was paid for up front
            and r.get("at", "") > billed.get((str(r.get("key_id") or ""), str(r.get("user_id") or "")), "")]
    lines = ops.group_rows(rows=mine, key=v["group_by"], measures=v["measures"]) or []
    out = []
    for ln in lines:
        if (ln.get("charged_usd") or 0) < float(v["min_usd"]):
            continue
        key_id, holder_id = str(ln.get("key_id") or ""), str(ln.get("user_id") or "")
        g, who = grant_of.get((key_id, holder_id)) or {}, people.get(holder_id) or {}
        out.append(ln | {"key_label": labels.get((owner_id, key_id), ""),
                         "holder_name": who.get("name") or who.get("email") or "", "holder_email": who.get("email") or "",
                         "markup_pct": float(g.get("markup_pct") or 0), "terms": terms_text(g) if g else "",
                         "from_at": billed.get((key_id, holder_id), "")})
    return out


def report(owner_id: str, group: str = "", q: str = "", page: int = 1) -> dict:
    """The lender's report on every key they lent: per key, per key and person, or per key, person and
    sitting. Only the lender sees base_usd beside charged_usd."""
    v = engine.run("keyshare.report_view")
    s = settings()
    group = group if group in v["group_by"] else v["default_group"]
    labels = _labels(owner_id)
    rows = [dict(r, charged_usd=_charged_of(r)) for r in store.runs_touching(owner_id)
            if r.get("key_owner_id") == owner_id and r.get("user_id") != owner_id]
    lines = ops.group_rows(rows=rows, key=v["group_by"][group], measures=v["measures"]) or []
    out = []
    for ln in lines:
        key_id, holder_id = str(ln.get("key_id") or ""), str(ln.get("user_id") or "")
        g = next((x for x in lent_by(owner_id, key_id) if x["holder_id"] == holder_id), {})
        out.append(ln | {"key_label": labels.get((owner_id, key_id), ""),
                         "holder_name": name_of(holder_id) if holder_id else "",
                         "holder_email": email_of(holder_id) if holder_id else "",
                         "session_id": ln.get("session_id") or "",
                         "session_label": ln.get("session_id") or say("unknown_session"),
                         "markup_pct": float(g.get("markup_pct") or 0),
                         "terms": terms_text(g) if g else "", "state": state_of(g) if g else "",
                         "granted_at": g.get("granted_at", ""), "revoked_at": g.get("revoked_at", "")})
    view = ops.rows_view(rows=out, query=q, search_keys=["key_label", "holder_name", "holder_email", "session_id"],
                         sort_key=v["sort_key"], sort_desc=v["sort_desc"],
                         page=page, page_size=s["report_page_size"], max_page_size=s["usage_max_page_size"])
    return (view or {}) | {"group": group, "groups": list(v["group_by"]),
                           "totals": {"base_usd": round(sum(float(x.get("base_usd") or 0) for x in out), 6),
                                      "charged_usd": round(sum(float(x.get("charged_usd") or 0) for x in out), 6),
                                      "runs": sum(int(x.get("runs") or 0) for x in out)}}


def raise_bill(owner_id: str, holder_id: str, key_id: str, amount_usd: float, note: str = "",
               kind: str = "usage", base_usd: float | None = None, runs: int = 0,
               from_at: str = "", to_at: str = "", seconds: float = 0, markup_pct: float = 0) -> dict:
    """One bill, frozen. `kind` says where it came from: "usage" (what a borrower spent since the last
    bill) or "purchase" (credit bought up front — keysales). This portal raises the bill; no money
    moves through it, so a bill is settled by the two people and marked paid here."""
    labels = _labels(owner_id)
    row = {"id": store.new_id(), "kind": kind, "key_id": key_id, "key_label": labels.get((owner_id, key_id), ""),
           "owner_id": owner_id, "owner_name": name_of(owner_id), "holder_id": holder_id,
           "holder_email": email_of(holder_id), "holder_name": name_of(holder_id),
           "from_at": from_at, "to_at": to_at or store.now(), "runs": runs, "seconds": seconds,
           "cost_usd": round(float(amount_usd or 0), 6),
           "base_usd": round(float(amount_usd if base_usd is None else base_usd or 0), 6),
           "markup_pct": markup_pct, "note": str(note or "").strip()[: int(settings()["bill_note_max"])],
           "pushed_at": store.now(), "settled_at": "", "settled_note": ""}
    with store._LOCK:                                    # noqa: SLF001
        store.write(BILLS, (bills() + [row])[-int(settings()["bills_kept"]):])
    return row


def push_bill(owner_id: str, key_id: str, holder_id: str, note: str = "") -> dict:
    """Send the borrower what they have spent on my key. The totals are frozen here, so the bill still
    reads true after the receipt roll has rolled past those runs."""
    line = next((x for x in owing(owner_id) if x["key_id"] == key_id and x["user_id"] == holder_id), None)
    if not line:
        raise HTTPException(400, say("nothing_to_bill"))
    row = raise_bill(owner_id, holder_id, key_id,
                     amount_usd=line.get("charged_usd") or 0,                  # what the borrower owes
                     base_usd=line.get("base_usd") or 0,                       # what it really cost the lender
                     note=note, kind="usage", runs=line.get("runs") or 0,
                     from_at=line["from_at"], to_at=line.get("last_at") or store.now(),
                     seconds=line.get("seconds") or 0, markup_pct=line.get("markup_pct") or 0)
    return row | {"message": say("bill_pushed", amount=store.money_text(owner_id, row["cost_usd"]),
                                 email=row["holder_email"], runs=row["runs"], label=row["key_label"])}


def settle_bill(holder_id: str, bill_id: str, note: str = "") -> dict:
    b = next((x for x in bills() if x["id"] == bill_id), None)
    if not b:
        raise HTTPException(404, say("no_bill"))
    if b["holder_id"] != holder_id:
        raise HTTPException(403, say("bill_not_yours"))
    with store._LOCK:                                    # noqa: SLF001
        rows = bills()
        for r in rows:
            if r["id"] == bill_id:
                r.update({"settled_at": store.now(), "settled_note": str(note or "").strip()[: int(settings()["bill_note_max"])]})
                b = r
        store.write(BILLS, rows)
    return b | {"message": say("bill_acked")}


def bills_view(user_id: str) -> dict:
    """How many bills I sent and was sent, and how many lines are not billed yet - the bills themselves are lists
    keys_bills_sent / keys_bills_received / keys_owing (core/lists.py), one searched page at a time."""
    all_ = bills()
    return {"sent_n": sum(1 for b in all_ if b["owner_id"] == user_id),
            "received_n": sum(1 for b in all_ if b["holder_id"] == user_id), "owing_n": len(owing(user_id))}


lists.source("keys_bills_sent", lambda user, args: [b for b in bills() if b["owner_id"] == user["id"]])
lists.source("keys_bills_received", lambda user, args: [{k: v for k, v in b.items() if k != "base_usd"}
                                                        for b in bills() if b["holder_id"] == user["id"]])
lists.source("keys_owing", lambda user, args: owing(user["id"]))


if __name__ == "__main__":  # ponytail: one runnable self-check of lending, using, billing
    import tempfile
    from pathlib import Path
    import core.store as cs
    import providers
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        cs.DATA = Path(tmp)
        a = cs.add_user("a@x.com", "pw-aaaaaaaa", name="Anita")
        b = cs.add_user("b@x.com", "pw-bbbbbbbb", name="Bala")
        store.save_keys_for(a["id"], {"gemini_api_key": "AIza-anita-00000000000"})
        spare = providers.pool_add(a["id"], "gemini", "AIza-anita-spare-00000", "Spare")
        assert providers.pool(b["id"], "gemini") == [], "nothing is shared until somebody shares it"

        g = share(a["id"], spare["id"], "b@x.com", "Anita", {"markup_pct": 25, "cap_day_usd": 5})
        held = providers.pool(b["id"], "gemini")
        assert [k["shared"] for k in held] == [True] and held[0]["secret"] == "AIza-anita-spare-00000"
        assert providers.key_for(b["id"], "gemini") == "AIza-anita-spare-00000", "a borrowed key is a usable key"
        assert providers.pool_view(b["id"])["gemini"][0].get("secret") is None, "a borrowed secret is never sent out"
        try:
            share(a["id"], spare["id"], "b@x.com")
            raise AssertionError("the same key twice to the same person must be refused")
        except HTTPException as e:
            assert "already has" in e.detail
        try:
            share(b["id"], spare["id"], "a@x.com")
            raise AssertionError("a borrowed key is never lent on")
        except HTTPException:
            pass

        # b renames it for themselves; a's own label is untouched
        relabel(b["id"], g["id"], "Anita's Gemini")
        assert providers.pool(b["id"], "gemini")[0]["name"] == "Anita's Gemini"
        assert [k["name"] for k in providers.own_keys(a["id"], "gemini")] == ["Key 1", "Spare"]

        # b spends on it: a's balance moves, b's does not, and the run says whose key it was
        store.set_loaded(a["id"], "gemini", 10)
        store.set_loaded(b["id"], "gemini", 10)
        out, used = providers.call_with_keys(b["id"], "gemini", lambda s: "fine")
        assert used["shared"] and used["owner_id"] == a["id"]
        store.spend(b["id"], "gemini", 2.0)
        store.log_run({"what": "Draft: Diwali promo film", "who": "Bala", "user_id": b["id"],
                       "provider": "gemini", "model": "gemini-flash-latest", "cost_usd": 2.0, "elapsed_s": 31.5})
        assert store.funds_for(a["id"], "gemini")["spent_usd"] == 2.0, "the lender's balance pays"
        assert store.funds_for(b["id"], "gemini")["spent_usd"] == 0, "the borrower's own balance is untouched"

        seen_a = usage(a["id"], "Demo Portal")["rows"][0]
        seen_b = usage(b["id"], "Demo Portal")["rows"][0]
        assert seen_a["used_by"] == "Bala" and seen_a["own"] is False
        assert seen_a["activity"] == "Draft: Diwali …", ("the lender sees enough to recognise it, not the title", seen_a)
        assert seen_b["activity"] == "Draft: Diwali promo film", "the person who ran it sees it whole and can cross-check"
        assert seen_a["key_label"] == "Spare" and seen_b["key_label"] == "Anita's Gemini", "each side its own name"
        assert seen_a["seconds"] == 31.5 and seen_a["owner_name"] == "Anita"

        # --- the mark-up: the lender's balance moves by the REAL cost, the borrower is charged more ---
        assert store.funds_for(a["id"], "gemini")["spent_usd"] == 2.0, "a mark-up never touches the real balance"
        assert seen_b["cost_usd"] == 2.5 and seen_b.get("base_usd") is None, "the borrower sees the jacked price ONLY"
        assert seen_a["cost_usd"] == 2.5 and seen_a["base_usd"] == 2.0, "the lender sees both"
        assert seen_a["markup_pct"] == 25

        line = owing(a["id"])[0]
        assert line["runs"] == 1 and line["charged_usd"] == 2.5 and line["base_usd"] == 2.0
        assert line["holder_email"] == "b@x.com" and line["markup_pct"] == 25
        bill = push_bill(a["id"], spare["id"], b["id"], "September")
        assert bill["cost_usd"] == 2.5 and bill["base_usd"] == 2.0, "a bill is sent at the jacked price"
        got = lists.page("keys_bills_received", b, {})["rows"][0]
        assert got["id"] == bill["id"] and got["cost_usd"] == 2.5 and "base_usd" not in got, (
            "what the key really cost its owner is never sent to the borrower")
        assert owing(a["id"]) == [], "what is billed is not billed twice"
        try:
            push_bill(a["id"], spare["id"], b["id"])
            raise AssertionError("an empty bill must be refused")
        except HTTPException:
            pass
        settle_bill(b["id"], bill["id"], "paid by UPI")
        assert lists.page("keys_bills_sent", a, {})["rows"][0]["settled_at"], "the lender sees it settled"
        try:
            settle_bill(a["id"], bill["id"])
            raise AssertionError("only the person billed may settle it")
        except HTTPException:
            pass

        # --- the lender's caps: the key stops when a rolling window is spent ------------------------
        use = lists.page("keys_lent", a, {})["rows"][0]["use"]
        assert use["day"]["spent"] == 2.5 and use["day"]["cap"] == 5 and use["day"]["pct"] == 50
        assert use["week"]["cap"] == 0 and use["week"]["pct"] is None, "a cap of 0 is no cap"
        assert providers.candidates(b["id"], "gemini"), "half the day's cap spent: the key still works"
        store.using_key(b["id"], providers.pool(b["id"], "gemini")[0])
        store.log_run({"what": "Second film", "who": "Bala", "user_id": b["id"], "provider": "gemini",
                       "model": "gemini-flash-latest", "cost_usd": 2.0, "elapsed_s": 10})
        blocked = providers.pool(b["id"], "gemini")[0]
        assert blocked["blocked"] and "cap" in blocked["blocked_reason"], blocked.get("blocked_reason")
        assert providers.candidates(b["id"], "gemini") == [], "a spent cap takes the key out of the running"
        try:
            providers.call_with_keys(b["id"], "gemini", lambda s_: "fine")
            raise AssertionError("no usable key must be refused, not run anyway")
        except HTTPException:
            pass
        set_terms(a["id"], g["id"], {"cap_day_usd": 20})
        assert providers.candidates(b["id"], "gemini"), "raising the cap frees the key at once"
        assert providers.pool(a["id"], "gemini")[0]["name"] == "Key 1", "the lender's own keys are untouched"

        # a mark-up change applies from NOW: what already ran keeps the per cent frozen onto its row
        set_terms(a["id"], g["id"], {"markup_pct": 100})
        again = usage(a["id"], "Demo Portal")["rows"]
        assert sorted(r["cost_usd"] for r in again) == [2.5, 2.5], "old runs keep the mark-up they were charged at"

        # --- the lender's report: per key, per person, per sitting ----------------------------------
        rep = report(a["id"], "person")
        assert rep["rows"][0]["runs"] == 2 and rep["rows"][0]["charged_usd"] == 5.0 and rep["rows"][0]["base_usd"] == 4.0
        assert rep["rows"][0]["holder_name"] == "Bala" and rep["rows"][0]["terms"]
        assert rep["totals"] == {"base_usd": 4.0, "charged_usd": 5.0, "runs": 2}
        assert set(rep["groups"]) == {"key", "person", "session"}
        store.note_session(b["id"], "sitting-one")
        store.using_key(b["id"], providers.pool(b["id"], "gemini")[0])
        store.log_run({"what": "Third", "who": "Bala", "user_id": b["id"], "provider": "gemini",
                       "model": "gemini-flash-latest", "cost_usd": 1.0, "elapsed_s": 5})
        by_sitting = report(a["id"], "session")["rows"]
        assert len(by_sitting) == 2 and sorted(x["runs"] for x in by_sitting) == [1, 2], (
            "runs made in one sitting group together", by_sitting)
        assert [x for x in by_sitting if x["session_id"]][0]["charged_usd"] == 2.0, "100% mark-up from now on"

        # --- what a borrower is told BEFORE they take the key ---------------------------------------
        card = rate_card(b["id"], 100)
        at_cost = rate_card(b["id"], 0)
        assert card["lines"] and card["disclaimer"] and "estimate" in card["disclaimer"]
        assert "100" in card["markup_line"] and "own prices" in at_cost["markup_line"]
        assert lists.page("keys_held", b, {})["rows"][0]["rates"]["lines"], "the borrower's own section quotes their prices"

        # taking it back: gone at once, and the record says who ended it and when
        revoke(a["id"], g["id"], "Anita")
        assert providers.pool(b["id"], "gemini") == [], "a key taken back is gone at once"
        hist = lists.page("keys_lent", a, {"all": "1"})["rows"][0]
        assert hist["state"] == "revoked" and hist["granted_at"] and hist["revoked_at"]
        assert usage(a["id"], "Demo Portal")["total"] == 3, "the runs it paid for stay on the record"
        g2 = share(a["id"], spare["id"], "b@x.com")
        revoke(b["id"], g2["id"], "Bala")
        assert next(x for x in lists.page("keys_lent", a, {"all": "1"})["rows"] if x["id"] == g2["id"])["state"] == "returned", "the borrower giving it back reads differently"
    print("keyshare self-check OK")
