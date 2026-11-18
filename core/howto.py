"""How to Use, for the portal's OWN pages: each screen in the catalog carries training links —
a manual, a YouTube tour, a video file — shown as a "How to Use" button in the top bar.

One link is a button; several are a menu. Stored as {screen_id: [{label, url, type, active}]}.
Reading is open (the sign-in page has a How to Use too); editing needs the How to Use pages screen.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from core import engine, store
from core.access import CATALOG, screen

router = APIRouter()


def say(key: str, **values) -> str:
    return engine.say("howto.messages", key, **values)


def settings() -> dict:
    """Length limits, links per page and the link types: chip howto.settings."""
    return engine.run("howto.settings")


def extra_pages() -> list[dict]:
    """The way in is a page too, and the one a newcomer most needs help on."""
    return [{"id": "signin", "label": say("signin_page_label"), "group": say("signin_page_group")}]


def guess_type(url: str) -> str:
    return engine.run("howto.link_type", {"url": url})


def clean(link: dict) -> dict:
    k = settings()
    url = str(link.get("url") or "").strip()[:int(k["url_max"])]
    # http(s) or a path on this portal — never javascript:, data: or anything a click could run (chip howto.url_allowed).
    if engine.run("howto.url_allowed", {"url": url}) is not True:
        raise HTTPException(400, say("not_web_address", url=url[:int(k["url_shown_in_error"])]))
    label = str(link.get("label") or "").strip()[:int(k["label_max"])]
    if not label:
        raise HTTPException(400, say("needs_label"))
    t = link.get("type") if link.get("type") in k["types"] else guess_type(url)
    return {"label": label, "url": url, "type": t, "active": link.get("active") is not False}


def pages() -> list[dict]:
    return extra_pages() + [{k: s.get(k, "") for k in ("id", "label", "group")} for s in CATALOG if not s.get("bottom_bar")]   # the bar: no page


@router.get("/api/core/howto")
def public_links():
    return {"pages": {k: [l for l in v if l.get("active", True)] for k, v in store.read("howto", {}).items()}}


@router.get("/api/core/howto/all")
def all_links(_: dict = Depends(screen("howto-config"))):
    return {"pages": pages(), "links": store.read("howto", {})}


@router.put("/api/core/howto/{page_id}")
def save_links(page_id: str, body: dict = Body(...), _: dict = Depends(screen("howto-config"))):
    if page_id not in {p["id"] for p in pages()}:
        raise HTTPException(404, say("no_page"))
    links = [clean(l) for l in (body.get("links") or [])][:int(settings()["links_per_page"])]
    with store._LOCK:                                 # noqa: SLF001
        allv = store.read("howto", {})
        if links:
            allv[page_id] = links
        else:
            allv.pop(page_id, None)
        store.write("howto", allv)
    return {"links": links}


if __name__ == "__main__":  # ponytail: one runnable self-check of what a link may be
    assert guess_type("https://youtu.be/abc") == "youtube" and guess_type("/m/guide") == "doc"
    assert guess_type("https://x.io/a.webm?t=1") == "video" and guess_type("https://example.com") == "link"
    assert clean({"label": " Tour ", "url": "https://youtu.be/abc"}) == {"label": "Tour", "url": "https://youtu.be/abc",
                                                                         "type": "youtube", "active": True}
    for bad in ({"label": "x", "url": "javascript:alert(1)"}, {"label": "x", "url": "//evil.example"}, {"url": "/m/a"}):
        try:
            clean(bad)
            raise AssertionError(f"accepted {bad}")
        except HTTPException as e:
            assert e.status_code == 400
    print("core.howto self-check OK")
