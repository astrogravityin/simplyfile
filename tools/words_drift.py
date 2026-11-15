"""Word drift: a screen's name is ONE word everywhere (W1.3, 2026-11-11 - scorecard B15: changing 'Organisation approvals' in
catalog.json alone left the guide, tour, ui chip and the Hindi / Telugu translations stale, and every guard stayed green).

    python tools/words_drift.py             every catalog.json label = its Guide me title, its tour title, its ui chip
                                            title, and a key in every translation chip
    python tools/words_drift.py --selftest

Which chip fields carry the name, the tour prefix, and the few screens whose page heading may differ from the menu word
(each with its reason) are in chip selfcheck.words (Chip Builder).
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def params(path: Path) -> dict:
    return {p["name"]: p.get("default") for p in json.loads(path.read_text(encoding="utf-8")).get("params", [])}


def chip_file(root: Path, name: str) -> Path | None:
    return next((p for p in (root / "chips" / f"{name}.json", root / "core" / "chips" / f"{name}.json") if p.is_file()), None)


def drift(root: Path = ROOT) -> list[str]:
    k = params(root / "chips" / "selfcheck.words.json")
    differs = {r["screen"] for r in k["ui_title_differs"]}
    langs = sorted((root / "chips").glob("lang.*.json")) + sorted((root / "core" / "chips").glob("lang.*.json"))
    bad = []
    for row in json.loads((root / "catalog.json").read_text(encoding="utf-8")):
        if "label" not in row:          # a flag-only row ({"id": "syscheck", "hidden": true}) sets a core screen, it names nothing
            continue
        sid, label = row["id"], row["label"]
        g = chip_file(root, f"guide.{sid.replace('-', '_')}")
        if g and params(g).get(k["guide_field"]) not in (None, label):
            bad.append(f"{sid}: Guide me ({g.name}) says {params(g)[k['guide_field']]!r}, the menu says {label!r}")
        t = root / "tours" / f"{k['tour_prefix']}-{sid}.json"
        if t.is_file() and json.loads(t.read_text(encoding="utf-8")).get(k["tour_field"]) != label:
            bad.append(f"{sid}: tour {t.name} says {json.loads(t.read_text(encoding='utf-8')).get(k['tour_field'])!r}, the menu says {label!r}")
        u = chip_file(root, f"ui.{sid}")
        title = params(u).get(k["ui_field"]) if u else None
        if isinstance(title, str) and sid not in differs and not html.unescape(title).startswith(label):
            bad.append(f"{sid}: page heading ({u.name} {k['ui_field']}) says {title!r}, the menu says {label!r}")
        for lf in langs:
            phrases = params(lf).get(k["lang_field"]) or {}
            if isinstance(phrases, dict) and label not in phrases:
                bad.append(f"{sid}: {lf.name} has no translation for {label!r} - the menu word changed and the translation was left behind")
    return bad


def selftest() -> None:
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        r = Path(t)
        for d in ("chips", "core/chips", "tours"):
            (r / d).mkdir(parents=True)
        shutil.copy(ROOT / "chips" / "selfcheck.words.json", r / "chips")
        k = params(r / "chips" / "selfcheck.words.json")
        def chip(name: str, **kv) -> None:
            (r / "chips" / f"{name}.json").write_text(json.dumps({"params": [{"name": a, "default": b} for a, b in kv.items()]}), encoding="utf-8")
        (r / "catalog.json").write_text(json.dumps([{"id": "approvals", "label": "Organisation approvals"}]), encoding="utf-8")
        chip("guide.approvals", **{k["guide_field"]: "Organisation approvals"})
        chip("ui.approvals", **{k["ui_field"]: "Organisation approvals"})
        chip("lang.hi", **{k["lang_field"]: {"Organisation approvals": "x"}})
        (r / "tours" / f"{k['tour_prefix']}-approvals.json").write_text(json.dumps({k["tour_field"]: "Organisation approvals"}), encoding="utf-8")
        assert drift(r) == [], drift(r)
        (r / "catalog.json").write_text(json.dumps([{"id": "approvals", "label": "Organisation reviews"}]), encoding="utf-8")   # the B15 drill
        found = drift(r)
        assert len(found) == 4 and all("Organisation reviews" in f for f in found), f"the menu word changed alone must fail 4 ways: {found}"
    print("word drift self-check OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit(0)
    found = drift()
    for f in found:
        print("drift:", f)
    n = len(json.loads((ROOT / "catalog.json").read_text(encoding="utf-8")))
    print(f"  words: {n} screens - menu word = Guide me = tour = page heading = translations; {len(found)} drifted")
    sys.exit(1 if found else 0)
