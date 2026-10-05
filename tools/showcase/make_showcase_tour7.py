"""Showcase part 7 (History - the change log) as a narrated Tour Video -> tmp/tour_video/showcase7.json.
Run after parts 1-2 (the firm, its team and fifteen clients, with Shree Ganesh Agarwal HUF's statement replaced once):
run_tours.sh record showcase:check showcase2:check showcase7."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import runpy
from pathlib import Path

ROOT = Path(_R + r"")
O = lambda **a: {**a, "optional": True, "timeout": 6}   # noqa: E731
fill = lambda sel, text: {"fill": sel, "text": text}    # noqa: E731
click = lambda sel, **k: {"click": sel, **k}            # noqa: E731
TOP = ".backdrop >> nth=-1"                             # the dialog on top (History opens over the client's window)


def S(chapter, say, *do):
    return {**({"chapter": chapter} if chapter else {}), "say": say, "do": list(do), "hold": 0.6}


P7 = [S("History", "Part seven: History. Every change in SimplyFile is kept - what each field was, what it became, when, and who made it. "
        "Replaced documents are kept too, so any earlier version can be downloaded.",
        {"goto": "/#/clients"}, {"wait_for": ".cl-row:has-text('Ramesh Iyer')"}),
      S("A change to a client", "Ramesh Iyer's details. His father's name was entered with a spelling mistake, and he has a new mobile number.",
        click(".cl-row:has-text('Ramesh Iyer') [data-open]"), {"wait_for": ".modal #c-father"}, O(highlight=".modal #c-father")),
      S(None, "Correct them, and save.",
        fill(".modal #c-father", "Venkatesh Iyer"), fill(".modal #c-phone", "9840099999"), {"wait": 0.6},
        click(".modal [data-save]"), {"wait": 2}),
      S(None, "Open the client again, and press History.",
        click(".cl-row:has-text('Ramesh Iyer') [data-open]"), {"wait_for": ".modal [data-history]"}, O(highlight=".modal [data-history]"),
        click(".modal [data-history]"), {"wait_for": f"{TOP} >> .ch-ev"}),
      S(None, "One save is one entry: who made it, where and when, and every field it changed - what it was, struck through, and what it is now.",
        O(highlight=f"{TOP} >> .ch-ev >> nth=0")),
      S(None, "Below it, everything since the client was added, newest first - grouped by day.",
        {"scroll_to": f"{TOP} >> .ch-ev >> nth=-1"}, O(highlight=f"{TOP} >> .ch-ev >> nth=-1")),
      S(None, "Details and Documents can be seen apart, and any field, value or person can be searched - say, the phone.",
        click(f"{TOP} >> [data-kind=info]"), {"wait": 1}, fill(f"{TOP} >> [data-q]", "phone"), {"wait": 1.5}, O(highlight=f"{TOP} >> [data-log]"),
        fill(f"{TOP} >> [data-q]", ""), click(f"{TOP} >> [data-kind='']"), {"wait": 1}, click(f"{TOP} >> [data-close]"), {"wait": 0.6},
        click(".modal [data-close]"), {"wait": 0.6}),
      S("Earlier versions of documents", "Shree Ganesh Agarwal H U F's statement was replaced in part one, when the corrected one came in. "
        "The first version was not thrown away.",
        click(".cl-row:has-text('Shree Ganesh Agarwal HUF') [data-open]"), {"wait_for": ".modal [data-history]"},
        click(".modal [data-history]"), {"wait_for": f"{TOP} >> .ch-ev"}, click(f"{TOP} >> [data-kind=doc]"), {"wait_for": f"{TOP} >> .ch-doc"}),
      S(None, "History shows the document replaced, version one by version two - and version one can be downloaded, exactly as it was "
        "first uploaded.", O(highlight=f"{TOP} >> .ch-dl >> nth=0")),
      S(None, "The same History button is on Intake and map, Reconcile, Compute and close, and the Tax audit - each showing this client's changes.",
        click(f"{TOP} >> [data-close]"), {"wait": 0.6}, click(".modal [data-close]"), {"wait": 0.6}),
      S("The firm's own history", "The firm has its own History, on My firm: the firm's details, and its team - people added, and every change "
        "of role.",
        {"goto": "/#/firm"}, {"wait_for": "[data-history]"}, O(highlight="[data-history]"), click("[data-history]"),
        {"wait_for": f"{TOP} >> .ch-ev"}, O(highlight=f"{TOP} >> [data-log]")),
      S(None, "So when someone asks who changed a role, or what a P A N used to be, the answer is one click away.",
        fill(f"{TOP} >> [data-q]", "role"), {"wait": 1.5}, O(highlight=f"{TOP} >> [data-log]"), fill(f"{TOP} >> [data-q]", ""), {"wait": 0.6},
        click(f"{TOP} >> [data-close]"), {"wait": 0.6}),
      S("Thank you", "History: every field, old and new, who and when, and every earlier document kept. What is logged, what each field "
        "is called, and how long it is kept are SimplyFile's own rules, kept as chips. Thank you for watching.", {"wait": 2})]

t = {"page_key": "showcase7", "title": "SimplyFile showcase, part 7: History", "start_url": "/#/clients",
     "prod_base": "https://sf.valuestream.in", "voice": "en-IN-NeerjaNeural", "rate": "+0%", "viewport": {"width": 1440, "height": 900},
     "type_emails": True, "locale": "en-IN", "blur": ["#whoami", "#userpop .head"], "steps": P7}
out = ROOT / "tmp" / "tour_video" / "showcase7.json"
out.write_text(json.dumps(t, indent=1, ensure_ascii=False), encoding="utf-8")
errs = runpy.run_path(str(ROOT / "tools" / "tour_video" / "make_tour.py"), run_name="x")["validate_tour"](t)
print("showcase7", len(P7), "steps", errs or "valid")
