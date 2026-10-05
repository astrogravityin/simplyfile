"""Showcase part 8 (audit phase 2) as a narrated Tour Video -> tmp/tour_video/showcase8.json.
Run after parts 1-2, pre6.py (last year's column) and pre8.py (two more earlier years): run_tours.sh record @pre6.py @pre8.py showcase8.
The GST returns are uploaded live from tools/tour_video/showcase/c3/gst (make_gst_demo.py)."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import runpy
from pathlib import Path

ROOT = Path(_R + r"")
GST = sorted(f"showcase/c3/gst/{f.name}" for f in (ROOT / "tools" / "tour_video" / "showcase" / "c3" / "gst").iterdir())
O = lambda **a: {**a, "optional": True, "timeout": 6}   # noqa: E731
click = lambda sel, **k: {"click": sel, **k}            # noqa: E731


def S(chapter, say, *do):
    return {**({"chapter": chapter} if chapter else {}), "say": say, "do": list(do), "hold": 0.6}


P8 = [S("Audit, part two", "Part eight: the audit, taken further. Each line against several earlier years, the G S T returns against the books, "
        "the Form 3 C D checklist in order of risk, and the statutory audit with the Accounting Standards.",
        {"goto": "/#/audit"}, {"wait_for": ".in-pick-row"}, click(".in-pick-row:has-text('Sri Venkateswara')"), {"wait_for": "#au-trend table"}),
      S("Against earlier years", "Sri Venkateswara Traders now has three earlier years beside this one - two from their own statements, "
        "and last year from the previous-year column. Each year is its own column.",
        {"scroll_to": "#au-trend"}, O(highlight="#au-src"), O(highlight="#au-trend thead")),
      S(None, "Rent was about three point one lakh for three years, and is six lakh now - while turnover grew eight percent. Up sharply on last "
        "year, and above its usual range: it has broken its own pattern.",
        O(highlight="#au-trend tr:has-text('Rent')")),
      S(None, "A line that grows with the business year after year is following its pattern, and is not flagged. One click raises the rent as "
        "an audit point.", click("#au-trend tr:has-text('Rent') [data-raise]"), {"wait": 1.5}),
      S("GST against the books", "Next, the G S T returns. Add the G S T R 3 B and G S T R 1 files from the G S T portal - the JSON, or the zip "
        "it downloads as.", {"scroll_to": "#au-gst-card"}, O(highlight="#au-gst-pick"),
        {"upload": "#au-gst-file", "files": GST}, {"wait_for": "#au-gst table"}, {"wait": 1}),
      S(None, "Month by month, G S T R 3 B against G S T R 1. In May, G S T R 1 is two and a half lakh higher; March's G S T R 3 B was never filed.",
        O(highlight="#au-gst tr:has-text('May')"), O(highlight="#au-gst tr:has-text('Mar')")),
      S(None, "And the year against the books: turnover in the books is about thirty five lakh higher than the G S T R 3 B - sales not declared, "
        "or income outside G S T. That too becomes an audit point.",
        O(highlight="#au-gst .au-verdict >> nth=0"), click("[data-gst-raise=more_in_books]"), {"wait": 1.5}),
      S("The riskiest first", "The Form 3 C D checklist, now in order of risk. Pick the line of business - a trader.",
        {"scroll_to": "#au-checks"}, {"select": "#au-sector", "value": "trading"}, {"wait": 1.5}),
      S(None, "Each clause shows high, medium or low, and why. Clause 22, payments to small suppliers, comes first: creditors jumped, and it "
        "often goes wrong in trading. Loans in cash, because unsecured loans tripled. Clause 21 b, payments without T D S, because rent and "
        "interest are flagged. As new statements come in, the order changes by itself.",
        O(highlight=".au-check >> nth=0"), O(highlight=".au-check:has-text('21(b)')")),
      S("Statutory audit", "For a firm, an L L P, an A O P or a proprietor: the statutory audit. An L L P sees whether its accounts must be audited. "
        "Every entity gets its level under the I C A I scheme - here level four, an M S M E, from turnover and borrowings.",
        {"scroll_to": "#au-stat-card"}, O(highlight="#au-stat .au-verdict")),
      S(None, "Then the Accounting Standards that apply at that level - some in full, some with relaxations - and the ones that do not apply at "
        "this level, kept apart. Each is worked through like a clause; an issue opens an audit point.",
        O(highlight="[data-as=as15]"), click(".au-off summary"), {"wait": 1}, O(highlight=".au-off")),
      S("Audit points", "Every point raised - from earlier years, from the G S T returns, from a clause or a standard - in one list, each with who "
        "answers it.", {"scroll_to": "#au-points"}, O(highlight="#au-points")),
      S("Thank you", "The limits, the flags, how far back to look, where each figure sits in a G S T return, how risky each clause is, and how each "
        "standard applies at each level are all SimplyFile's own rules, kept as chips - change one, and every client follows. Thank you for watching.",
        {"wait": 2})]

t = {"page_key": "showcase8", "title": "SimplyFile showcase, part 8: the audit, taken further", "start_url": "/#/audit",
     "prod_base": "https://sf.valuestream.in", "voice": "en-IN-NeerjaNeural", "rate": "+0%", "viewport": {"width": 1440, "height": 900},
     "type_emails": True, "locale": "en-IN", "blur": ["#whoami", "#userpop .head"], "steps": P8}
out = ROOT / "tmp" / "tour_video" / "showcase8.json"
out.write_text(json.dumps(t, indent=1, ensure_ascii=False), encoding="utf-8")
errs = runpy.run_path(str(ROOT / "tools" / "tour_video" / "make_tour.py"), run_name="x")["validate_tour"](t)
print("showcase8", len(P8), "steps", errs or "valid")
