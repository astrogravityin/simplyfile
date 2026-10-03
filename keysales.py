"""Selling credit on a key: an offer put up by the owner (or a sales person), a request to buy it,
and — once it is approved — a prepaid share plus a bill.

2026-09-23 owner: "User should see Buy Key menu ... The request will come to Portal Admin for now,
eventually we will have another role called Sales Person ... Before Request, PA/SP need to configure
the key which can be sold, here PA/SP can decide how much jackup they need to do. Only when PA/SP
configure then only Buy Key should be seen by other user otherwise that menu should not be visible
to them ... User will buy key for the cost say 10 USD, in that case no limit (daily, weekly or
monthly) will be there ... Currently money transaction/payment module not be there but only billing
module we should build."

Nothing is taken and nothing is paid here: an approval raises a BILL (keyshare) and hands over
credit. Money moves between the two people however they already do it.

Shapes:
  key_offers.json  one row per key a seller put up, with the mark-up they add.
  key_orders.json  one row per request to buy, never deleted - who asked, who answered, when.

Every decision is a chip: who may sell (keysales.may_sell, the Sales Person role is a row in its
list), who may buy what (keysales.may_buy), what a request's state is called (keysales.order_state),
every size and sentence (keysales.settings / keysales.messages).
"""
from __future__ import annotations

from fastapi import HTTPException

import keyshare
import store
from core import engine, lists

OFFERS = "key_offers"
ORDERS = "key_orders"


def settings() -> dict:
    return engine.run("keysales.settings")


def say(key: str, **values) -> str:
    return engine.say("keysales.messages", key, **values)


def may_sell(user: dict | None) -> bool:
    """Chip keysales.may_sell owns the list of roles. Adding a Sales Person is a chip edit."""
    return engine.run("keysales.may_sell", {"role": (user or {}).get("role", "member")}) is True


# --- offers: what is for sale ---------------------------------------------------------------------

def offers() -> list[dict]:
    return list(store.read(OFFERS, []) or [])


def _write_offers(rows: list[dict]) -> None:
    store.write(OFFERS, rows)


def _offer(offer_id: str) -> dict:
    o = next((x for x in offers() if x["id"] == offer_id), None)
    if not o:
        raise HTTPException(404, say("no_offer"))
    return o


def _key_of(o: dict) -> dict | None:
    import providers                                     # late: providers.pool asks keyshare back
    return next((k for k in providers.own_keys(o["seller_id"]) if k["id"] == o["key_id"]), None)


def is_live(o: dict) -> bool:
    """An offer is only real while it is switched on AND the key behind it still exists."""
    return bool(o.get("active")) and _key_of(o) is not None


def live_offers() -> list[dict]:
    return [o for o in offers() if is_live(o)]


def anything_to_buy(user: dict | None) -> bool:
    """core.access.register_available: no live offer this person could buy on = no Buy a key menu.
    A seller's own offer does not count — nobody buys their own key."""
    uid = (user or {}).get("id")
    return bool(uid) and any(o["seller_id"] != uid for o in live_offers())


def save_offer(seller: dict, body: dict) -> dict:
    """Put one of my keys up for sale, or change what I ask for it. The mark-up is the same field a
    lent key carries (keyshare) — a sale is a lending that was paid for up front."""
    if not may_sell(seller):
        raise HTTPException(403, say("not_a_seller"))
    s = settings()
    rows = offers()
    oid = str(body.get("id") or "")
    row = next((x for x in rows if x["id"] == oid), None) if oid else None
    if row and row["seller_id"] != seller["id"]:
        raise HTTPException(403, say("not_your_offer"))
    key_id = str(body.get("key_id") or (row or {}).get("key_id") or "")
    draft = dict(row or {}, seller_id=seller["id"], key_id=key_id)
    if not key_id or _key_of(draft) is None:
        raise HTTPException(400, say("offer_needs_key" if not key_id else "offer_key_gone"))
    if row is None and len([x for x in rows if x["seller_id"] == seller["id"]]) >= int(s["offers_max"]):
        raise HTTPException(400, say("too_many_offers", max=s["offers_max"]))
    key = _key_of(draft)
    terms = keyshare._terms(body, row)                   # noqa: SLF001 - the same mark-up rules as a lending
    patch = {"key_id": key_id, "provider": key["provider"], "markup_pct": terms.get("markup_pct", 0),
             "title": str(body.get("title") or key.get("name") or "").strip()[: int(s["title_max"])],
             "note": str(body.get("note") or "").strip()[: int(s["note_max"])],
             "active": bool(body.get("active", True)), "updated_at": store.now()}
    if row is None:
        row = {"id": store.new_id(), "seller_id": seller["id"], "created_at": store.now()} | patch
        rows.append(row)
    else:
        row.update(patch)
    with store._LOCK:                                    # noqa: SLF001
        _write_offers(rows)
    return view_offer(row, seller["id"]) | {
        "message": say("offer_saved" if row["active"] else "offer_off", title=row["title"],
                       terms=keyshare.terms_text(row))}


def delete_offer(seller: dict, offer_id: str) -> dict:
    """Off the shelf. Credit already bought is a share of its own and keeps working."""
    o = _offer(offer_id)
    if o["seller_id"] != seller["id"]:
        raise HTTPException(403, say("not_your_offer"))
    with store._LOCK:                                    # noqa: SLF001
        _write_offers([x for x in offers() if x["id"] != offer_id])
    return {"ok": True, "message": say("offer_deleted", title=o.get("title") or "")}


def view_offer(o: dict, viewer_id: str) -> dict:
    """What a buyer may see of an offer: the seller, the terms, and what it will cost THEM. Never the
    key's hint, never its secret, never the seller's own cost."""
    pct = float(o.get("markup_pct") or 0)
    return {"id": o["id"], "title": o.get("title") or "", "note": o.get("note") or "",
            "provider": o.get("provider"), "active": bool(o.get("active")), "live": is_live(o),
            "markup_pct": pct, "seller_id": o["seller_id"], "seller_name": keyshare.name_of(o["seller_id"]),
            "seller_line": say("sold_by", seller=keyshare.name_of(o["seller_id"])),
            "terms": keyshare.terms_text(o), "key_id": o["key_id"] if o["seller_id"] == viewer_id else "",
            "rates": keyshare.rate_card(viewer_id, pct)}


# --- requests to buy ------------------------------------------------------------------------------

def orders() -> list[dict]:
    return list(store.read(ORDERS, []) or [])


def _write_orders(rows: list[dict]) -> None:
    store.write(ORDERS, rows[-int(settings()["orders_kept"]):])


def state_of(o: dict) -> str:
    return engine.run("keysales.order_state", {"decided": bool(o.get("decided_at")),
                                               "approved": bool(o.get("grant_id")),
                                               "withdrawn": bool(o.get("withdrawn_at"))})


def _waiting(o: dict) -> bool:
    return state_of(o) == "requested"


def place_order(buyer: dict, offer_id: str, amount_usd, note: str = "") -> dict:
    """Ask the seller for credit. Nothing is charged and nothing changes until they say yes."""
    s = settings()
    o = _offer(offer_id)
    mine = [x for x in orders() if x["buyer_id"] == buyer["id"] and _waiting(x)]
    amount = keyshare._number(amount_usd, 0)             # noqa: SLF001
    ok = engine.run("keysales.may_buy", {
        "offer_live": is_live(o), "is_seller": o["seller_id"] == buyer["id"],
        "already_waiting": any(x["offer_id"] == offer_id for x in mine),
        "open_orders": len(mine), "open_orders_max": s["open_orders_max"],
        "amount_usd": amount, "min_usd": s["pack_min_usd"], "max_usd": s["pack_max_usd"]})
    if ok is not True:
        if not (float(s["pack_min_usd"]) <= amount <= float(s["pack_max_usd"])):
            raise HTTPException(400, say("bad_amount", min=s["pack_min_usd"], max=s["pack_max_usd"]))
        if any(x["offer_id"] == offer_id for x in mine):
            raise HTTPException(400, say("already_waiting"))
        if len(mine) >= int(s["open_orders_max"]):
            raise HTTPException(400, say("too_many_orders", max=s["open_orders_max"]))
        raise HTTPException(400, say("cannot_buy"))
    row = {"id": store.new_id(), "offer_id": offer_id, "seller_id": o["seller_id"], "key_id": o["key_id"],
           "title": o.get("title") or "", "buyer_id": buyer["id"], "buyer_email": buyer["email"],
           "amount_usd": round(amount, 2), "markup_pct": float(o.get("markup_pct") or 0),
           "note": str(note or "").strip()[: int(s["note_max"])], "requested_at": store.now(),
           "decided_at": "", "decided_by": "", "reason": "", "withdrawn_at": "",
           "grant_id": "", "bill_id": ""}
    with store._LOCK:                                    # noqa: SLF001
        _write_orders(orders() + [row])
    return view_order(row, buyer["id"]) | {
        "message": say("order_placed", seller=keyshare.name_of(o["seller_id"]),
                       amount=store.money_text(buyer["id"], row["amount_usd"], 0), title=row["title"])}


def withdraw_order(buyer_id: str, order_id: str) -> dict:
    o = _order(order_id)
    if o["buyer_id"] != buyer_id:
        raise HTTPException(403, say("not_your_order"))
    if not _waiting(o):
        raise HTTPException(400, say("order_decided"))
    o = _patch(order_id, {"withdrawn_at": store.now()})
    return view_order(o, buyer_id) | {"message": say("order_withdrawn")}


def _order(order_id: str) -> dict:
    o = next((x for x in orders() if x["id"] == order_id), None)
    if not o:
        raise HTTPException(404, say("no_order"))
    return o


def _patch(order_id: str, patch: dict) -> dict:
    with store._LOCK:                                    # noqa: SLF001
        rows = orders()
        for r in rows:
            if r["id"] == order_id:
                r.update(patch)
                out = r
        _write_orders(rows)
    return out


def decide_order(seller: dict, order_id: str, approve: bool, reason: str = "") -> dict:
    """The seller answers. A yes hands over the credit as a prepaid share — the mark-up the offer
    named, NO day/week/month cap, and the amount bought as the only ceiling — and raises the bill for
    it. This portal bills; it does not take the money."""
    if not may_sell(seller):
        raise HTTPException(403, say("not_a_seller"))
    o = _order(order_id)
    if o["seller_id"] != seller["id"]:
        raise HTTPException(403, say("not_your_order"))
    if not _waiting(o):
        raise HTTPException(400, say("order_decided"))
    s = settings()
    patch = {"decided_at": store.now(), "decided_by": seller["id"],
             "reason": str(reason or "").strip()[: int(s["note_max"])]}
    if not approve:
        o = _patch(order_id, patch)
        return view_order(o, seller["id"]) | {"message": say("rejected_ok", buyer=keyshare.name_of(o["buyer_id"]))}
    # Buying again is a TOP-UP, not a second key: credit is what was bought, so credit is what grows.
    held = keyshare.live_grant(seller["id"], o["key_id"], o["buyer_id"])
    grant = (keyshare.add_credit(seller["id"], held["id"], o["amount_usd"]) if held
             else keyshare.share(seller["id"], o["key_id"], o["buyer_email"], keyshare.name_of(seller["id"]),
                                 {"markup_pct": o["markup_pct"], "cap_day_usd": 0, "cap_week_usd": 0,
                                  "cap_month_usd": 0, "cap_total_usd": o["amount_usd"]}))
    bill = keyshare.raise_bill(seller["id"], o["buyer_id"], o["key_id"], o["amount_usd"],
                               say("bill_for_credit",
                                   amount=store.money_text(o["buyer_id"], o["amount_usd"], 0),
                                   title=o["title"]), kind="purchase")
    o = _patch(order_id, patch | {"grant_id": grant["id"], "bill_id": bill["id"]})
    return view_order(o, seller["id"]) | {
        "message": say("approved_ok", buyer=keyshare.name_of(o["buyer_id"]), title=o["title"],
                       amount=store.money_text(o["buyer_id"], o["amount_usd"], 0))}


def view_order(o: dict, viewer_id: str) -> dict:
    g = next((x for x in keyshare.grants() if x["id"] == o.get("grant_id")), None)
    left = keyshare.window_spend(g)["total"] if g else {}
    warn = keyshare.warn_line(g, viewer_id) if g and not g.get("revoked_at") else ""
    stop = keyshare.limit_block(g) if g and not g.get("revoked_at") else ""
    return o | {"state": state_of(o), "seller_name": keyshare.name_of(o["seller_id"]),
                "buyer_name": keyshare.name_of(o["buyer_id"]),
                "mine": o["buyer_id"] == viewer_id,
                "credit": {"bought": left.get("cap"), "left": left.get("left"),
                           "low": bool(warn), "warn": warn, "spent_out": bool(stop), "stopped": stop,
                           "line": say("credit_left", bought=store.money_text(viewer_id, left.get("cap"), 0),
                                       left=store.money_text(viewer_id, left.get("left"), 0))} if left else {}}


# --- what each screen asks for ---------------------------------------------------------------------

def shop(user: dict) -> dict:
    """Buy a key: what is on sale (never my own), what I asked for, and what I must be told."""
    s = settings()
    # Credit that is nearly gone, or gone: the reason this screen was opened. One row per key, newest
    # order first - a top-up on the same key is the same credit, so it is named once.
    low, seen = [], set()
    for k in keyshare.borrowed_all(user["id"]):
        if (k.get("low") or k.get("blocked")) and k["grant_id"] not in seen:
            seen.add(k["grant_id"])
            low.append({"grant_id": k["grant_id"], "label": k["name"], "owner_name": k.get("owner_name", ""),
                        "stopped": bool(k.get("blocked")),
                        "message": k.get("blocked_reason") or k.get("low_reason") or "",
                        "offer_id": next((o["id"] for o in live_offers()
                                          if o["key_id"] == k["id"] and o["seller_id"] == k["owner_id"]), "")})
    # 2026-10-01 (Phase 3): every seller's offer was sent whole - list.buy_offers pages it; here only how many
    return {"offers_n": sum(1 for o in live_offers() if o["seller_id"] != user["id"]),
            "orders_n": sum(1 for o in orders() if o["buyer_id"] == user["id"]), "low_credit": low,
            "packs": s["packs_usd"], "custom_ok": s["custom_ok"],
            "min_usd": s["pack_min_usd"], "max_usd": s["pack_max_usd"],
            "buy_note": s["buy_note"], "billing_only": s["billing_only"],
            # the same sentence a quote carries, said once for the whole screen as well - a price a
            # buyer acts on is never shown without what moves it (chip keyshare.rate_card)
            "disclaimer": engine.run("keyshare.rate_card")["disclaimer"]}


def desk(seller: dict) -> dict:
    """Keys for sale: my offers, the requests waiting on them, and the ones I already answered."""
    if not may_sell(seller):
        raise HTTPException(403, say("not_a_seller"))
    import providers                                     # late
    mine = [o for o in orders() if o["seller_id"] == seller["id"]]
    s = settings()
    return {"offers": [view_offer(o, seller["id"]) for o in offers() if o["seller_id"] == seller["id"]],
            "keys": [{"id": k["id"], "name": k["name"], "provider": k["provider"], "hint": k["hint"]}
                     for k in providers.own_keys(seller["id"])],
            "waiting_n": sum(1 for o in mine if _waiting(o)), "answered_n": sum(1 for o in mine if not _waiting(o)),
            "markup_max": keyshare.settings()["markup_max_pct"],
            "title_max": s["title_max"], "note_max": s["note_max"], "billing_only": s["billing_only"]}


# 2026-09-28 owner "tens of thousands": requests are lists sales_waiting / sales_answered (the seller) and buy_orders
# (the buyer) - one searched page; only that page's rows get their credit line (view_order reads grants and runs).
def _named(rows: list[dict]) -> list[dict]:
    people = {u["id"]: u for u in store.users()}
    return [o | {"buyer_name": (people.get(o["buyer_id"]) or {}).get("name") or "",
                 "seller_name": (people.get(o["seller_id"]) or {}).get("name") or ""} for o in rows]


def _sales(waiting: bool):
    def rows(user: dict, args: dict) -> list[dict]:
        if not may_sell(user):
            raise HTTPException(403, say("not_a_seller"))
        return _named([o for o in reversed(orders()) if o["seller_id"] == user["id"] and _waiting(o) == waiting])
    return rows


def _offer_rows(user: dict, args: dict) -> list[dict]:
    """Live offers of OTHER sellers, light enough to search (title, seller); `pick` = one offer."""
    pick = str(args.get("pick") or "")
    return [{"id": o["id"], "title": o.get("title") or "", "seller_name": keyshare.name_of(o["seller_id"]), "_raw": o}
            for o in live_offers() if o["seller_id"] != user["id"] and (not pick or o["id"] == pick)]


lists.source("buy_offers", _offer_rows, lambda user, rows, args: [view_offer(r["_raw"], user["id"]) for r in rows])
lists.source("sales_waiting", _sales(True), lambda user, rows, args: [view_order(o, user["id"]) for o in rows])
lists.source("sales_answered", _sales(False), lambda user, rows, args: [view_order(o, user["id"]) for o in rows])
lists.source("buy_orders", lambda user, args: _named([o for o in reversed(orders()) if o["buyer_id"] == user["id"]]),
             lambda user, rows, args: [view_order(o, user["id"]) for o in rows])


if __name__ == "__main__":  # ponytail: one runnable self-check of offer -> request -> credit -> bill
    import tempfile
    from pathlib import Path
    import core.store as cs
    import providers
    from core import access
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        cs.DATA = Path(tmp)
        access.load(Path(__file__).resolve().parent / "catalog.json")
        access.register_available("buykey", anything_to_buy)   # app.py does the same on boot
        sel = cs.add_user("sell@x.com", "pw-sellerrr", name="Sella", role="owner")
        buy = cs.add_user("buy@x.com", "pw-buyerrrr", name="Buya")
        store.save_keys_for(sel["id"], {"gemini_api_key": "AIza-sella-0000000000"})
        key = providers.own_keys(sel["id"])[0]
        assert not anything_to_buy(buy), "no offer = nothing to buy = no menu"
        assert access.decide(buy, "buykey")["allowed"] is False, "the screen is refused before it exists"

        o = save_offer(sel, {"key_id": key["id"], "title": "Gemini credit", "markup_pct": 20})
        assert o["markup_pct"] == 20 and o["live"] and "20" in o["terms"]
        assert o["key_id"] == key["id"] and o["rates"]["lines"], "a buyer is quoted before they ask"
        assert shop(buy)["disclaimer"] == o["rates"]["disclaimer"], (
            "the screen and the quote say the same thing about what moves a price")
        assert anything_to_buy(buy) and not anything_to_buy(sel), "nobody buys their own key"
        assert access.decide(buy, "buykey")["allowed"] is True

        try:
            save_offer(buy, {"key_id": key["id"]})
            raise AssertionError("only a seller puts a key up for sale")
        except HTTPException as e:
            assert e.status_code == 403
        assert engine.run("keysales.may_sell", {"role": "member"}) is False

        # the buyer asks for $10
        try:
            place_order(buy, o["id"], 0.2)
            raise AssertionError("an amount the shop does not sell is refused")
        except HTTPException:
            pass
        order = place_order(buy, o["id"], 10, "for the October films")
        assert order["state"] == "requested" and order["amount_usd"] == 10
        assert not providers.pool(buy["id"], "gemini"), "asking hands over nothing"
        try:
            place_order(buy, o["id"], 10)
            raise AssertionError("a second request on the same offer is refused")
        except HTTPException:
            pass
        assert desk(sel)["waiting_n"] == 1 and lists.page("sales_waiting", sel, {})["total"] == 1

        # the seller says yes: prepaid credit, no rolling caps, and a bill
        done = decide_order(sel, order["id"], True)
        assert done["state"] == "approved" and done["credit"]["bought"] == 10 and done["credit"]["left"] == 10
        k = providers.pool(buy["id"], "gemini")[0]
        assert k["shared"] and k["markup_pct"] == 20 and not k["blocked"]
        g = keyshare.held_by(buy["id"])[0]
        assert (g["cap_day_usd"], g["cap_week_usd"], g["cap_month_usd"]) == (0, 0, 0), "bought credit has no rolling cap"
        assert g["cap_total_usd"] == 10
        bill = lists.page("keys_bills_received", buy, {})["rows"][0]
        assert bill["kind"] == "purchase" and bill["cost_usd"] == 10 and "base_usd" not in bill
        assert lists.page("keys_bills_sent", sel, {})["rows"][0]["kind"] == "purchase"

        # spending it: charged at +20%, and the key stops the moment the credit runs out
        store.using_key(buy["id"], providers.pool(buy["id"], "gemini")[0])
        store.log_run({"what": "A film", "who": "Buya", "user_id": buy["id"], "provider": "gemini",
                       "model": "gemini-flash-latest", "cost_usd": 4.0, "elapsed_s": 20})
        assert keyshare.window_spend(g)["total"]["spent"] == 4.8, "charged at the offer's mark-up"
        assert not providers.pool(buy["id"], "gemini")[0]["blocked"]
        assert keyshare.owing(sel["id"]) == [], "prepaid credit is never billed a second time as usage"
        store.using_key(buy["id"], providers.pool(buy["id"], "gemini")[0])
        store.log_run({"what": "Another", "who": "Buya", "user_id": buy["id"], "provider": "gemini",
                       "model": "gemini-flash-latest", "cost_usd": 4.4, "elapsed_s": 20})
        spent = providers.pool(buy["id"], "gemini")[0]
        assert spent["blocked"] and "credit" in spent["blocked_reason"], spent.get("blocked_reason")
        assert providers.candidates(buy["id"], "gemini") == []

        # --- the warning at a fifth left, and buying more ------------------------------------------
        # $10 bought, $8.80 charged so far: under a fifth left, so the buyer is TOLD, not just stopped.
        g = keyshare.held_by(buy["id"])[0]
        assert keyshare.window_spend(g)["total"]["spent"] == 10.08, keyshare.window_spend(g)["total"]
        top = shop(buy)
        assert top["low_credit"] and top["low_credit"][0]["stopped"], "a spent-out key leads the screen"
        assert "credit" in top["low_credit"][0]["message"]
        assert lists.page("buy_orders", buy, {})["rows"][0]["credit"]["spent_out"] is True

        # buying again on the SAME key tops the credit up; it is not a second key in the list
        more = place_order(buy, o["id"], 10)
        decide_order(sel, more["id"], True)
        assert len(providers.pool(buy["id"], "gemini")) == 1, "a top-up is the same key, not a second one"
        assert len(keyshare.held_by(buy["id"])) == 1
        g = keyshare.held_by(buy["id"])[0]
        assert g["cap_total_usd"] == 20 and g["topped_up_at"], "the credit grew"
        k3 = providers.pool(buy["id"], "gemini")[0]
        assert not k3["blocked"] and not k3["low"], "topped up: working again and not low"
        assert providers.candidates(buy["id"], "gemini"), "the key works again"
        assert lists.page("keys_bills_received", buy, {})["total"] == 2, "each purchase is its own bill"
        assert not shop(buy)["low_credit"], "nothing to warn about any more"

        # spend down to the last fifth: warned, still working
        store.using_key(buy["id"], providers.pool(buy["id"], "gemini")[0])
        store.log_run({"what": "Third", "who": "Buya", "user_id": buy["id"], "provider": "gemini",
                       "model": "gemini-flash-latest", "cost_usd": 6.0, "elapsed_s": 30})
        use = keyshare.window_spend(keyshare.held_by(buy["id"])[0])["total"]
        assert use["spent"] == 17.28 and use["left"] == 2.72 and use["warn"] is True, use
        warned = providers.pool(buy["id"], "gemini")[0]
        assert warned["low"] and not warned["blocked"], "warned at a fifth left, NOT stopped"
        assert "Buy more" in warned["low_reason"] and "$2.72" in warned["low_reason"], warned["low_reason"]
        assert providers.candidates(buy["id"], "gemini"), "a warning never stops the key"
        assert shop(buy)["low_credit"][0]["stopped"] is False
        assert lists.page("keys_held", buy, {})["rows"][0]["low_reason"], "the Shared keys card says it too"

        # switching the offer off hides the menu again; credit already bought keeps working
        save_offer(sel, {"id": o["id"], "active": False})
        assert not anything_to_buy(buy) and keyshare.held_by(buy["id"]), "an offer off is not a key taken back"
        delete_offer(sel, o["id"])
        assert keyshare.held_by(buy["id"]), "deleting the offer never touches credit somebody paid for"

        # a no is a no, and it is on the record
        o2 = save_offer(sel, {"key_id": key["id"], "title": "Second", "markup_pct": 0})
        again = place_order(buy, o2["id"], 5)
        said_no = decide_order(sel, again["id"], False, "not this month")
        assert said_no["state"] == "rejected" and said_no["reason"] == "not this month"
        assert len(keyshare.held_by(buy["id"])) == 1, "a refusal hands over nothing"
    print("keysales self-check OK")
