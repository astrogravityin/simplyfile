"""A screen's Tour Video script from its Guide me (2026-10-07): chip guide.<screen> -> tours/sf-<screen>.json, the way the
existing tours were made - the cover step waits for the page, each step presses its `open` (a stepper node, a tab) and then
spotlights its `target`. The tour's own settings (voice, viewport, blur, prod_base) are kept from the file already there.
selfcheck's guides_tours_check holds the two together. Run from the repo root:

    python tools/guide_tour.py myreturn taxwatch
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {"prod_base": "https://sf.valuestream.in", "voice": "en-IN-NeerjaNeural", "rate": "+0%", "viewport": {"width": 1280, "height": 720},
            "blur": ["#whoami", "#userpop .head"]}


def build(screen: str) -> dict:
    gp = ROOT / "chips" / f"guide.{screen.replace('-', '_')}.json"   # connect-ai -> guide.connect_ai
    g = json.loads((gp if gp.exists() else ROOT / "core" / "chips" / gp.name).read_text(encoding="utf-8"))   # a core walk (Agents)
    d = {p["name"]: p["default"] for p in g["params"]}
    sub = lambda s: str(s or "")  # noqa: E731 - {product} stays: make_tour fills it from chip edition.settings
    out = ROOT / "tours" / f"sf-{screen}.json"
    old = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
    head = {k: old.get(k, v) for k, v in DEFAULTS.items()}
    first = next((s["target"].split("|")[0] for s in d["steps"] if s.get("target")), "")
    steps = [{"chapter": sub(d["title"]), "say": sub(d["lede"]), "do": ([{"wait_for": first}] if first else []) + [{"wait": 1}]}]
    # 2026-10-10: a step whose actions were added to by hand in the tour (sf-clients' Start here: the demo firm has done every
    # step, so the card is opened from the name menu first) keeps them - as long as they still hold what the guide makes
    was = {x.get("chapter"): x.get("do") or [] for x in old.get("steps") or []}
    for s in d["steps"]:
        do = []
        if s.get("open"):
            do += [{"click": s["open"], "optional": True}, {"wait": 1.2}]
        if s.get("target"):
            do.append({"highlight_target": s["target"], "optional": True, "timeout": 5})
        kept = was.get(sub(s["title"])) or []
        if len(kept) > len(do) and all(a in kept for a in do):
            do = kept
        steps.append({"chapter": sub(s["title"]), "say": sub(s["say"]), "do": do})
    t = head | {"page_key": f"sf-{screen}", "title": sub(d["title"]), "start_url": f"/#/{screen}",
                "covers": [s["title"][:1].lower() + s["title"][1:] for s in d["steps"]], "steps": steps}
    out.write_bytes((json.dumps(t, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return t


if __name__ == "__main__":
    for sc in sys.argv[1:]:
        print(f"tours/sf-{sc}.json", len(build(sc)["steps"]), "steps")
