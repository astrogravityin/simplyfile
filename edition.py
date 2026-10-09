"""Which product this server is. In this folder only SimplyFile (chip edition.settings) - kept as the framework's hook.

2026-09-18 owner: "going forward all other features will be part of the studio, which is tv + new
features". One codebase, two editions. A server is told which it is by PORTAL_EDITION (a hosting fact,
set in its service file, like the port); what each edition is called and which screens it shows is chip
`edition.settings`. tv is frozen: a new screen is added to the catalog and to the studio's list only.
"""
from __future__ import annotations

import os

from core import engine


def settings() -> dict:
    return engine.run("edition.settings")


def current() -> dict:
    s = settings()
    want = (os.getenv("PORTAL_EDITION") or os.getenv("TV_EDITION") or s["default_edition"]).strip().lower()
    row = next((r for r in s["rows"] if r["id"] == want), None)
    if row is None:   # a service file naming an edition that does not exist must not start half-configured
        raise RuntimeError(f"PORTAL_EDITION={want!r} is not one of {[r['id'] for r in s['rows']]} (chip edition.settings)")
    return row


def ai_features() -> list[dict]:
    """This portal's features that call an AI model (chip ai.features; no chip = none)."""
    return list(engine.knobs("ai.features").get("features") or [])


def catalog(screens: list[dict]) -> list[dict]:
    """The catalog's screens this edition shows, in the edition's own order.
    2026-10-09 owner: the AI-key screens (Account & key, Buy a key, Keys for sale) are gone when the portal uses no AI, and
    the portal admin's alone when it does - chip ai.features lists the features; its key_screens the screens."""
    by_id = {s["id"]: s for s in screens}
    keyed = set(engine.knobs("ai.features").get("key_screens") or ["keys", "buykey", "keysales"])
    ai = bool(ai_features())
    return [by_id[i] | ({"admin": True} if i in keyed else {}) for i in current()["screens"] if i in by_id and (ai or i not in keyed)]


def door(host: str) -> dict | None:
    """2026-09-28 owner: "make the door standard as the other sites". Another address of the SAME edition (a second address on
    the studio) is a door, chip edition.settings rows[].doors: its own name, pitch and first screen - the same shell,
    sign-in card, menu and screens. Never a page of its own."""
    host = str(host or "").split(":")[0].strip().lower()
    return next((d for d in current().get("doors") or [] if host in d["hosts"]), None)


def menu_ids(host: str) -> set[str] | None:
    """The screens this address's menu and top search offer; None = every screen of the edition.
    A door's are ITS screens (e.g. home, watch, read...); the edition's own address leaves off its `site_hides`
    (2026-10-01 owner: "keep the door's screens out of the main menu" - they live on the door's address). The framework's admin
    screens, which no edition lists, stay for whoever may open them. Menu and search only: a hidden screen still opens
    from a link or a bell, and the server still asks access.may."""
    from core import access  # noqa: PLC0415
    d, own = door(host), current()["screens"]
    if d and d.get("screens"):
        return {s["id"] for s in access.CATALOG if s["id"] in d["screens"] or s["id"] not in own}
    hides = set(current().get("site_hides") or [])
    return {s["id"] for s in access.CATALOG if s["id"] not in hides} if hides and not d else None


def elsewhere(host: str) -> dict:
    """Where this address sends the screens its menu leaves off (chip edition.settings site_sends): {url, screens}, or
    {} - a door, or an address with nowhere named, keeps them. 2026-10-01 owner: "send door links to the door's address"."""
    h = str(host or "").split(":")[0].strip().lower()
    url = (current().get("site_sends") or {}).get(h, "")
    return {"url": url, "screens": list(current().get("site_hides") or [])} if url and not door(host) else {}


def bootstrap_extra(request, u) -> dict:
    d = door(request.headers.get("host") if request is not None else "")
    row = current() | {k: v for k, v in (d or {}).items() if k != "hosts"}
    from core import access  # noqa: PLC0415
    shown = menu_ids(request.headers.get("host") if request is not None else "")
    menu = {"catalog": [s for s in access.CATALOG if s["id"] in shown]} if shown is not None else {}
    away = elsewhere(request.headers.get("host") if request is not None else "")
    return ({"product_name": d["product_name"]} if d else {}) | menu | ({"elsewhere": away} if away else {}) | {"edition": {
        "id": row["id"], "brand_sub": row["brand_sub"], "landing": row["landing"],
        "words_prefix": row.get("words_prefix", ""), "tour": row.get("tour"), "selling": row.get("selling") or [],
        "jump_signin": bool(row.get("jump_signin")),
        # what uses an AI key here (chip ai.features labels) - Account & key says it; signed-in people only
        "ai_features": [f.get("label", "") for f in ai_features()] if u else [],
        # a door's "Launch Studio" (top right): the workshop's address as seen from THIS host (chip doors[].launch)
        "launch": ((d or {}).get("launch") or {}).get(str(request.headers.get("host") if request is not None else "").split(":")[0].lower(), "")}}


if __name__ == "__main__":  # ponytail: one runnable self-check - SimplyFile is the one edition here
    import store  # noqa: F401 - registers this portal's chips, as the app does
    keep = os.environ.pop("PORTAL_EDITION", None)
    try:
        e = current()                                                # 2026-10-05: boilerplate - any domain's default edition
        assert e["id"] == engine.run("edition.settings")["default_edition"] and e["landing"].startswith("#/")
        listed = e["screens"][:3]
        shown = [s["id"] for s in catalog([{"id": x} for x in [*reversed(listed), "no_such_screen"]])]
        assert shown == listed, shown                                 # the edition's order; a screen it does not list is absent
        assert door("no-such-host.example") is None
        real = ai_features
        try:   # AI-key screens: absent with no AI feature; admin-only (portal admin) with one
            for feats in ([], [{"id": "x"}]):
                globals()["ai_features"] = lambda f=feats: f
                got = {s["id"]: s for s in catalog([{"id": i} for i in [*listed, "keys"]] )} if "keys" in e["screens"] else None
                if got is not None:
                    assert ("keys" in got) == bool(feats) and (not feats or got["keys"].get("admin")), (feats, got)
        finally:
            globals()["ai_features"] = real
        os.environ["PORTAL_EDITION"] = "nonsense"
        try:
            current()
            raise AssertionError("an unknown edition must refuse to start")
        except RuntimeError:
            pass
    finally:
        os.environ.pop("PORTAL_EDITION", None)
        if keep is not None:
            os.environ["PORTAL_EDITION"] = keep
    print("edition self-check OK")
