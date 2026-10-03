"""Screen guide: a step-by-step tour of one screen, drawn over the live page — a spotlight on each part,
a card with the narration and a picture, and an optional spoken voice (the browser's own, free).

Every word, every step, every spotlight and every picture is a chip:
    guide.<screen>     one screen's tour: title, lede, minutes, steps (rows: title, say, target, art)
    guide.settings     the voice, the pace, which pictures exist
    guide.check        what a tour / an imported Guide me script must satisfy (rows over op doc_problems)
    ui.guide           the card's own buttons and labels (core/words.py)
A new screen gets a tour by adding one chip — no code. The top bar shows "Guide me" only where one exists.

Reading is open to anyone signed in (a tour is words, not data); a step never carries a person's content.
"""
from __future__ import annotations

import re
from pathlib import Path

import json

from fastapi import APIRouter, Body, Depends, HTTPException

from core import auth, engine
from core.access import screen as screen_guard

router = APIRouter()
_SCREEN = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
#: what a step may hold; anything else in a row is dropped before it reaches a browser
STEP_KEYS = ("title", "say", "target", "art", "place", "open")


def say(key: str, **values) -> str:
    return engine.say("guide.messages", key, **values)


def screens() -> list[str]:
    """Every screen with a live tour: the chips named guide.<screen> (guide.settings / guide.messages are not tours)."""
    skip = set(engine.run("guide.settings")["not_tours"])
    return sorted(c[6:] for c, v in engine.chips().items()
                  if c.startswith("guide.") and c[6:] not in skip and v.get("status") != "inactive")


def tour(screen: str) -> dict:
    cid = f"guide.{screen.replace('-', '_')}"
    if not _SCREEN.match(screen.replace("-", "_")) or cid not in engine.chips() or screen in engine.run("guide.settings")["not_tours"]:
        raise HTTPException(404, say("no_tour"))
    t = engine.run(cid)
    steps = [{k: s.get(k) for k in STEP_KEYS if s.get(k) not in (None, "")} for s in (t.get("steps") or []) if s.get("say")]
    return {"screen": screen, "title": t.get("title", ""), "lede": t.get("lede", ""), "minutes": t.get("minutes"), "icon": t.get("icon", ""),
            "steps": steps, "settings": engine.run("guide.settings") | (t.get("voice") or {})}


def bootstrap_extra(request, u) -> dict:
    """Which screens have a tour, so the top bar can show Guide me without a second call."""
    return {"guides": [s.replace("_", "-") for s in screens()]} if u else {}


@router.get("/api/core/guide/{screen}")
def api_tour(screen: str, _: dict = Depends(auth.signed_in)):
    return tour(screen)


# --- How to Use pages -> Guide me: import a Guide me script onto a screen, set its voice, or take it off -----------
# 2026-09-28 owner: "come back to the module, How to Use - Configure: Import Guide me, hooked to that page; change the
# voice and save; then the Guide me button is available". An import PUBLISHES chip guide.<screen> into the data layer
# exactly as Ops & chips would (history snapshot, version + 1) - so an imported tour is still a chip, editable there.

def _chip_id(scr: str) -> str:
    return f"guide.{scr.replace('-', '_')}"


def _page_ids() -> set[str]:
    from core.access import CATALOG  # noqa: PLC0415 - the catalog is loaded after this module
    return {s["id"] for s in CATALOG}


def admin_view(scr: str) -> dict:
    """What How to Use pages shows for one screen: its tour (if any), where it came from, and its voice."""
    if scr not in _page_ids():
        raise HTTPException(404, say("no_tour"))
    chip = engine.chips().get(_chip_id(scr))
    has = bool(chip) and chip.get("status") != "inactive"
    t = engine.run(_chip_id(scr)) if has else {}
    return {"screen": scr, "has": has, "source": (chip or {}).get("_source", ""), "shipped": bool((chip or {}).get("_shipped")),
            "title": t.get("title", ""), "steps": len(t.get("steps") or []), "voice": t.get("voice") or {},
            "settings": engine.run("guide.settings")}


def _publish(chip: dict, u: dict, action: str) -> None:
    from core import builder  # noqa: PLC0415 - builder imports the whole framework; only an admin write needs it
    lib = engine.with_drafts([chip])
    bad = engine.problems(chip, lib)
    failing = [r for r in engine.run_tests(chip, lib) if not r["ok"]]
    if bad or failing:
        raise HTTPException(422, {"message": say("chip_refused"), "problems": bad + [str(r.get("error") or r["got"]) for r in failing]})
    old = engine.chips().get(chip["chip_id"]) or {}
    out = builder._clean(chip) | {"version": int(old.get("version") or 0) + 1, "status": "published",  # noqa: SLF001
                                  "updated_by": u["email"], "updated_at": builder.store.now()}
    builder._write(builder.root() / "chips" / f"{chip['chip_id']}.json", out)  # noqa: SLF001
    builder._snapshot("chips", out, u, action)  # noqa: SLF001
    builder.refresh("chips")
    engine.refresh()


def _with_param(chip: dict, name: str, typ: str, value, label: str) -> dict:
    """The chip with knob `name` set to `value` (added, with its field in the record and in every test's answer)."""
    chip = json.loads(json.dumps(chip))
    row = next((p for p in chip.get("params") or [] if p["name"] == name), None)
    if row is None:
        chip.setdefault("params", []).append({"name": name, "type": typ, "default": value, "label": label})
        chip.setdefault("expr", {"vop": "record", "fields": {}}).setdefault("fields", {})[name] = f"${name}"
    else:
        row["default"] = value
    for tc in chip.get("test_cases") or []:      # a test that leaves this knob out now expects its new default
        if isinstance(tc.get("expect_value"), dict) and name not in (tc.get("args") or {}):
            tc["expect_value"][name] = value
    return chip


def _base(scr: str) -> dict:
    """The chip an import is written into: the screen's own, else a copy of the guide.settings `chip_template` tour."""
    lib = engine.chips()
    own = lib.get(_chip_id(scr))
    if own:
        return own
    tpl = json.loads(json.dumps(lib[_chip_id(engine.run("guide.settings")["chip_template"])]))
    return tpl | {"chip_id": _chip_id(scr), "label": say("chip_label", screen=scr), "aliases": [f"{scr} guide", "guide me"]}


def parse(body: dict) -> dict:
    """The script from a request: {script: {...}} or {script_text: "..."}; too big or not JSON -> 400 in plain words."""
    st = engine.run("guide.settings")
    text = body.get("script_text")
    if isinstance(text, str):
        if len(text.encode("utf-8")) > int(st["import_max_kb"]) * 1024:
            raise HTTPException(400, say("too_big", kb=st["import_max_kb"]))
        try:
            script = json.loads(text)
        except ValueError:
            raise HTTPException(400, say("not_json")) from None
    else:
        script = body.get("script")
    if not isinstance(script, dict):
        raise HTTPException(400, say("not_json"))
    return script


def import_script(scr: str, script: dict, u: dict) -> dict:
    if scr not in _page_ids():
        raise HTTPException(404, say("no_tour"))
    st = engine.run("guide.settings")
    problems = check(script, script=True, sets={"portals": st["accept_portals"], "pages": [scr, scr.replace("-", "_")]})
    if problems:
        raise HTTPException(422, {"message": say("script_refused", n=len(problems)), "problems": problems})
    chip = _base(scr)
    keep = {"title": "text", "lede": "long", "icon": "text", "minutes": "number", "steps": "rows"}
    for name, typ in keep.items():
        if name in script:
            chip = _with_param(chip, name, typ, script[name] if name != "steps" else
                               [{k: s[k] for k in STEP_KEYS if k in s} for s in script["steps"]], say(f"knob_{name}"))
    if isinstance(script.get("voice"), dict):
        chip = _with_param(chip, "voice", "record", {k: v for k, v in script["voice"].items() if k in st["voice_keys"]}, say("knob_voice"))
    _publish(chip, u, "import")
    return admin_view(scr)


def save_voice(scr: str, voice: dict, u: dict) -> dict:
    view = admin_view(scr)
    if not view["has"]:
        raise HTTPException(404, say("no_tour"))
    st = engine.run("guide.settings")
    voice = {k: v for k, v in (voice or {}).items() if k in st["voice_keys"]}
    problems = check(tour(scr) | {"voice": voice})
    if problems:
        raise HTTPException(422, {"message": say("script_refused", n=len(problems)), "problems": problems})
    _publish(_with_param(engine.chips()[_chip_id(scr)], "voice", "record", voice, say("knob_voice")), u, "voice")
    return admin_view(scr)


def remove_import(scr: str, u: dict) -> dict:
    """Take an imported tour off: the data-layer chip goes (history kept), so the shipped tour - or none - is back."""
    from core import builder  # noqa: PLC0415
    chip = engine.chips().get(_chip_id(scr))
    if not chip or chip.get("_source") != "data":
        raise HTTPException(404, say("nothing_imported"))
    builder._snapshot("chips", builder._clean(chip), u, "remove")  # noqa: SLF001
    (builder.root() / "chips" / f"{chip['chip_id']}.json").unlink(missing_ok=True)
    builder.refresh("chips")
    engine.refresh()
    return admin_view(scr)


@router.get("/api/core/guide-admin/{scr}")
def api_admin_view(scr: str, _: dict = Depends(screen_guard("howto-config"))):
    return admin_view(scr)


@router.put("/api/core/guide-admin/{scr}/script")
def api_import(scr: str, body: dict = Body(...), u: dict = Depends(screen_guard("howto-config"))):
    return import_script(scr, parse(body), u)


@router.put("/api/core/guide-admin/{scr}/voice")
def api_voice(scr: str, body: dict = Body(...), u: dict = Depends(screen_guard("howto-config"))):
    return save_voice(scr, body.get("voice") or {}, u)


@router.delete("/api/core/guide-admin/{scr}")
def api_remove(scr: str, u: dict = Depends(screen_guard("howto-config"))):
    return remove_import(scr, u)


def icon_names() -> list[str]:
    """The icon names the portal can draw (keys of PATHS in core/static/icons.js) - a fact, gathered."""
    text = (Path(__file__).resolve().parent / "static" / "icons.js").read_text(encoding="utf-8")
    body = text[text.index("PATHS"):]
    return sorted(set(re.findall(r"^\s*'?([a-z][\w-]*)'?\s*:", body[: body.index("};")], re.M)))


def check(doc: dict, script: bool = False, sets: dict | None = None) -> list[str]:
    """Plain sentences for everything wrong with a tour (or, script=True, an imported Guide me script).
    Every rule is a row of chip guide.check; this only gathers what the portal knows and words the answer."""
    known = {"art_kinds": engine.run("guide.settings")["art_kinds"], "icons": icon_names()} | (sets or {})
    rows = engine.run("guide.check", {"doc": doc, "script": script, "sets": known}) or []
    out = []
    for r in rows:
        line = say(r["say"], n=(r["index"] + 1) if "index" in r else "")
        if line not in out:
            out.append(line)
    return out


if __name__ == "__main__":  # ponytail: one runnable self-check - every tour chip passes chip guide.check
    import sys
    engine.register_dir(Path(__file__).resolve().parent.parent / "chips")
    bad = [f"{s}: {line}" for s in screens() for line in check(tour(s))]
    try:
        tour("../etc")
        bad.append("a path was looked up as a screen")
    except HTTPException:
        pass
    if bad:
        sys.exit("core.guide self-check FAILED:\n  " + "\n  ".join(bad))
    print(f"core.guide self-check OK ({len(screens())} tours)")
