"""Every word on every screen is a chip.

2026-09-18 owner: "chips and ops only, throughout". The server's sentences were already chips; the
screens' words were written into JavaScript. Now a screen's words are chip `ui.<screen>` - a record of
key -> text, editable in Ops & chips like any other - and a language may override any of them with chip
`ui.<screen>.<lang>` (e.g. ui.youtube.hi). A page asks for its words once and fills {placeholders} itself.

Words are not secrets (the sign-in page needs its own before anyone signs in), so this is open to all;
only chips named `ui.*` are ever served.
"""
from __future__ import annotations

import re

from fastapi import APIRouter

from core import engine

router = APIRouter()
_SCREEN = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_LANG = re.compile(r"^[a-z]{2,3}$")


def words(screen: str, lang: str = "") -> dict:
    """The words of one screen, in `lang` where a translation exists, else the chip's own words."""
    if not _SCREEN.match(screen or ""):
        return {}
    lib = engine.chips()
    base = engine.run(f"ui.{screen}") if f"ui.{screen}" in lib else {}
    if lang and _LANG.match(lang) and f"ui.{screen}.{lang}" in lib:
        base = dict(base) | {k: v for k, v in engine.run(f"ui.{screen}.{lang}").items() if v}
    return dict(base)


def page_settings(screen: str) -> dict:
    """2026-09-26: a page's own numbers, lists and maps (chip page.<screen>) - never in the page's code. Nothing secret."""
    if not _SCREEN.match(screen or ""):
        return {}
    return dict(engine.run(f"page.{screen}")) if f"page.{screen}" in engine.chips() else {}


@router.get("/api/core/words")
def api_words(screens: str = "", lang: str = ""):
    names = [s for s in screens.split(",")[:20] if _SCREEN.match(s)]
    got = {s: words(s, lang) for s in names}
    # 2026-10-03 owner: the work window read "I checked it" - which words are statements is chip work.statements;
    # a busy button saying one titles the window ww_busy_title. The page only looks the text up.
    return {"words": got, "settings": {s: page_settings(s) for s in names},
            "statements": sorted({x for s in names for x in engine.run("work.statements", {"words": got[s]}) or []})}


if __name__ == "__main__":  # ponytail: one runnable self-check
    assert words("../etc") == {} and words("") == {}, "only plain screen names are looked up"
    assert words("no_such_screen_here") == {}
    assert api_words("ab,b/..,cd")["words"].keys() == {"ab", "cd"}, "a name that is not a plain screen name is skipped"
    st_ = api_words("shell")["statements"]
    assert "Done" in st_ and not any(x.startswith(("Import", "Save", "Delete")) for x in st_), "statements by chip work.statements"
    print("core.words self-check OK")
