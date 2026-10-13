"""New filing's films (2026-10-11 owner: "every demo use case must have its own step-by-step video"): one Tour Video script per
worked example of chip wizard.cases -> tours/sf-case-<id>.json, and the screen's own walk tours/sf-wizard.json (its words exactly
chip guide.wizard's, as selfcheck's guides_tours_check wants). Each chapter is a Guide me step (chip guide.wizard titles); a case's
narration is its own (wizard.cases say), the guide's where the case has none. Every word comes from the chips; this only lays out
the clicks: the who-card (and the AY), the picks, the documents batch by batch, the popup's answers, Review, then on into the
return. Run from the repo root, then record (tools/showcase/record_cases.sh):

    .venv/Scripts/python.exe tools/make_case_tours.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HEAD = {"prod_base": "https://sf.valuestream.in", "voice": "en-IN-NeerjaNeural", "rate": "+0%", "viewport": {"width": 1280, "height": 720},
        "blur": ["#whoami", "#userpop .head"]}
CHOICE = {"residence", "pan_pick", "status"}
LANDS = {"myreturn": ".mr-rail-card", "audit": "#au-ay", "compute": "#cc-ay", "recon": "#rc-ay"}


def chip(cid):
    from core import engine  # noqa: PLC0415
    import store  # noqa: F401,PLC0415 - registers the portal's chips
    return engine.run(cid)


def raw(cid):
    """A chip's own knobs as written - {product} kept (make_tour fills it from edition.settings; selfcheck wants it unspelt)."""
    c = json.loads((ROOT / "chips" / f"{cid}.json").read_text(encoding="utf-8"))
    return {p["name"]: p["default"] for p in c["params"]}


def hl(sel):
    return {"highlight_target": sel, "optional": True, "timeout": 5}


def files(c, batch):
    return {"upload": "#wz-file", "files": [f"showcase/{c['folder']}/{f}" for f in batch]}


def answers(c):
    do = []
    for k, v in c["answers"].items():
        if k == "company":                                  # the company's popup: the option chosen, manufacturing ticked
            do.append({"select": "[data-co='option']", "value": v["option"]})
            if v.get("manufacturing") == "yes":
                do.append({"click": "[data-co='manufacturing']"})
            continue
        do.append({"click": f"[data-ask='{k}'][value='{v}']", "optional": True} if k in CHOICE else {"fill": f"[data-ask='{k}']", "text": v, "optional": True})
    return do


def case_tour(c, g, steps_by_title):
    say = c["say"]
    t = lambda title: steps_by_title[title]  # noqa: E731
    first = [{"wait_for": ".wz-start"}, {"wait": 1}]
    if c["ay"] != chip("clients.settings")["current_ay"]:
        first += [{"select": "#wz-ay", "value": c["ay"]}, {"wait": 0.6}]
    work = {r["id"] for r in chip("wizard.scenarios")["rows"] if r["group"] == "work"}
    flow = next(w for w in chip("wizard.settings")["who"] if w["id"] == c["who"])["flow"]
    order = (["business"] if flow == "myreturn" and work & set(c["picks"]) and "business" not in c["picks"] else []) + c["picks"]
    picks = []
    for p in order:
        picks += [{"click": f"[data-pick='{p}']"}, {"wait": 0.7}]
    b1, rest = c["batches"][0], c["batches"][1:]
    asked = bool(c["answers"]) or flow == "firm"          # a popup only where the documents leave something to ask
    popup = ([{"wait_for": ".wz-ask-modal", "timeout": 40}, {"wait": 1.5}] + answers(c) + [{"wait": 1}, {"click": ".wz-ask-modal [data-save]"}, {"wait": 3}]
             if asked else [{"wait": 1}]) + [hl(".wz-client")]
    later = []
    for b in rest:
        later += [files(c, b), {"wait": 2 + 1.5 * len(b)}]
    later += [{"wait": 1}, hl(".wz-prompts")]
    steps = [
        {"chapter": c["title"], "say": say["intro"], "do": first},
        {"chapter": t("Who it is for")["title"], "say": t("Who it is for")["say"], "do": [hl(".wz-who-groups"), {"click": f"[data-start='{c['who']}']"}, {"wait_for": ".wz-who"}, {"wait": 1}]},
        {"chapter": t("What applies")["title"], "say": say["what"], "do": picks + [hl(".wz-work|.wz-what")]},
        {"chapter": t("Which form")["title"], "say": t("Which form")["say"], "do": [hl(".wz-form")]},
        {"chapter": t("Documents you'll need")["title"], "say": t("Documents you'll need")["say"],
         "do": [{"click": "[data-go='docs']"}, {"wait_for": ".wz-docs"}, {"wait": 1}, hl(".wz-docs"), {"scroll": 420}]},
        {"chapter": t("Drop them in")["title"], "say": say["upload"],
         "do": [{"click": "[data-go='upload']"}, {"wait_for": "[data-drop='wz-file']"}, {"wait": 0.5}, files(c, b1), {"wait": 2 + 1.5 * len(b1)}]},
        {"chapter": t("The client, made for you")["title"], "say": say["client"], "do": popup},
    ]
    if rest or say.get("hints"):
        steps.append({"chapter": t("What the documents imply")["title"], "say": say.get("hints") or t("What the documents imply")["say"], "do": later})
    steps.append({"chapter": t("Review, then the return")["title"], "say": say["review"],
                  "do": [{"click": "[data-go='review']"}, {"wait_for": ".wz-review"}, {"wait": 1.5}, hl(".wz-go|.wz-review"), {"wait": 1},
                         {"click": "#wz-go"}, {"wait": 3}, {"wait_for": LANDS.get(c["opens"], ".card"), "timeout": 20, "optional": True}, {"wait": 2}]})
    steps += [{"chapter": m["chapter"], "say": m["say"], "do": m["do"]} for m in c.get("more", [])]   # 2026-10-13: what happens in My return after Review
    return HEAD | {"page_key": c["film"], "title": c["title"], "start_url": "/#/wizard", "covers": [s["chapter"][:1].lower() + s["chapter"][1:] for s in steps[1:]],
                   "steps": steps}


def screen_tour(g, c):
    """tours/sf-wizard.json: the guide's own words, walked with the salaried + gains case's documents."""
    by = {s["title"]: s for s in g["steps"]}
    do = {
        "Who it is for": [hl(".wz-who-groups|.wz-start")],
        "Worked examples": [hl(".wz-examples|.wz-start")],
        "Carry on later": [hl(".wz-resume|.wz-start")],
        "Four steps": [{"click": "[data-start='individual']"}, {"wait_for": ".wz-who"}, {"wait": 1}, hl(".wz-rail|.wz-start")],
        "What applies": [{"click": "[data-pick='employers']"}, {"wait": 0.8}, {"click": "[data-pick='shares']"}, {"wait": 0.8},
                         {"click": "[data-pick='property']"}, {"wait": 0.8}, hl(".wz-what|.wz-start")],
        "What kind of work": [{"click": "[data-pick='business']"}, {"wait": 1}, hl(".wz-work|.wz-what|.wz-start"), {"wait": 2},
                              {"click": "[data-pick='business']"}, {"wait": 0.8}],
        "Which form": [hl(".wz-form|.wz-start")],
        "Documents you'll need": [{"click": "[data-go='docs']"}, {"wait_for": ".wz-docs"}, {"wait": 1}, hl(".wz-docs|.wz-start")],
        "Drop them in": [{"click": "[data-go='upload']"}, {"wait_for": "[data-drop='wz-file']"}, {"wait": 0.5}, hl("[data-drop='wz-file']|.wz-start"),
                         {"wait": 2}, files(c, c["batches"][0]), {"wait_for": ".wz-ask-modal", "timeout": 30}],
        "The client, made for you": [{"wait": 2}] + answers(c) + [{"wait": 1}, {"click": ".wz-ask-modal [data-save]"}, {"wait": 3}, hl(".wz-client|.wz-start")],
        "What the documents imply": [files(c, c["batches"][1][:1]), {"wait": 4}, hl(".wz-prompts|.wz-start")],
        "Review, then the return": [{"click": "[data-go='review']"}, {"wait_for": ".wz-review"}, {"wait": 1}, hl(".wz-go|.wz-review|.wz-start")],
    }
    steps = [{"chapter": g["title"], "say": g["lede"], "do": [{"wait_for": ".wz-start"}, {"wait": 1}]}]
    steps += [{"chapter": s["title"], "say": s["say"], "do": do.get(s["title"], [hl(s.get("target", ".wz-start"))])} for s in g["steps"]]
    return HEAD | {"page_key": "sf-wizard", "title": g["title"], "start_url": "/#/wizard", "covers": [s["title"][:1].lower() + s["title"][1:] for s in g["steps"]],
                   "steps": steps}


def main():
    g = raw("guide.wizard")
    by = {s["title"]: s for s in g["steps"]}
    k = raw("wizard.cases")
    out = []
    for c in k["rows"]:
        p = ROOT / "tours" / f"{c['film']}.json"
        p.write_bytes((json.dumps(case_tour(c, g, by), indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        out.append(p.name)
    sal = next(c for c in k["rows"] if c["id"] == "salary_cg_property")
    (ROOT / "tours" / "sf-wizard.json").write_bytes((json.dumps(screen_tour(g, sal), indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print("wrote tours/sf-wizard.json and", len(out), "case tours:", ", ".join(out))


if __name__ == "__main__":
    main()
