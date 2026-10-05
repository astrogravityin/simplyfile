"""Showcase part 6 (Tax audit) as a narrated Tour Video -> tmp/tour_video/showcase6.json.
Run after parts 1-2 and pre6.py (Sri Venkateswara Traders' books with last year's column): rehearse_all.sh ... @pre6.py showcase6."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import runpy
from pathlib import Path

ROOT = Path(_R + r"")
O = lambda **a: {**a, "optional": True, "timeout": 6}   # noqa: E731
fill = lambda sel, text: {"fill": sel, "text": text}    # noqa: E731
click = lambda sel, **k: {"click": sel, **k}            # noqa: E731


def S(chapter, say, *do):
    return {**({"chapter": chapter} if chapter else {}), "say": say, "do": list(do), "hold": 0.6}


P6 = [S("Tax audit", "Part six: the tax audit. For a client under section 44 A B, SimplyFile works through Form 3 C D with the auditor - "
        "whether an audit is needed, what moved since last year, the clauses that apply to this client, and the points still open.",
        {"goto": "/#/audit"}, {"wait_for": ".in-pick-row"}, O(highlight=".card")),
      S("Is an audit needed?", "Sri Venkateswara Traders, a partnership firm. From the books already mapped in Intake, the turnover is three point two crore - "
        "above the one crore limit, so a tax audit is needed.",
        click(".in-pick-row:has-text('Sri Venkateswara')"), {"wait_for": "#au-need .au-verdict"}, O(highlight="#au-need")),
      S(None, "What the books cannot show, the firm answers. If cash receipts and cash payments are each within five percent, the limit becomes ten crore - "
        "and the answer changes at once.", click("[data-fact=cash_ok]"), {"wait": 1.5}, O(highlight="#au-need .au-verdict")),
      S(None, "Here they are not, so the audit stays - and the year is marked as a tax audit, which also moves the due date to the thirty first of October.",
        click("[data-fact=cash_ok]"), {"wait": 1.5}, O(click="#au-mark"), {"wait": 1.2}, O(highlight="#au-need")),
      S("This year against last", "Every mapped line of the profit and loss account and the balance sheet, this year against last. Last year comes from "
        "last year's statements, last year's filed return, or - as here - the previous-year column in this year's accounts.",
        {"scroll_to": "#au-trend"}, O(highlight="#au-src")),
      S(None, "The lines worth a look are flagged: rent nearly doubled and interest doubled, salaries and travel up sharply, unsecured loans tripled, "
        "creditors up two thirds - while sales grew about eight percent. And a donation that was there last year is gone.",
        O(highlight="#au-trend")),
      S(None, "One click turns a flag into an audit point. Rent up eighty nine percent - is the new lease on record, and was TDS deducted?",
        click("#au-trend tr:has-text('Rent') [data-raise]"), {"wait": 1.5}, {"scroll_to": "#au-points"}, O(highlight="#au-points")),
      S(None, "Every line is a search away - say, the loans.", {"scroll_to": "#au-trend"}, click("#au-flagged"), fill("#au-q", "loans"),
        {"wait": 1}, O(highlight="#au-trend"), fill("#au-q", ""), click("#au-flagged")),
      S("Form 3CD checklist", "The Form 3 C D checklist - only the clauses that apply to this client. A firm gets clause nine, partners and their shares; "
        "rent and interest bring clause twenty one b, payments without TDS; loans bring clause thirty one, loans taken or repaid in cash.",
        {"scroll_to": "#au-checks"}, O(highlight="#au-checks")),
      S(None, "Each clause is marked as it is worked through, with a note.",
        fill("[data-check=c9] [data-note]", "Deed dated 1 April 2021 - shares unchanged this year"), {"select": "[data-check=c9] [data-state]", "value": "done"},
        {"wait": 1.2}, O(highlight="[data-check=c9]")),
      S(None, "Marking a clause as an issue opens an audit point by itself.",
        fill("[data-check=c21b] [data-note]", "Rent to a partner's relative - TDS under 194-I deducted late in two months"),
        {"select": "[data-check=c21b] [data-state]", "value": "issue"}, {"wait": 1.5}, O(highlight="[data-check=c21b]")),
      S("Audit points", "Audit points: what still needs an answer before the report is signed - from the year-on-year flags, from the checklist, or added by hand, "
        "each with the person who answers it.",
        {"scroll_to": "#au-points"}, fill("#au-pt", "Confirmations from the five largest creditors"), {"select": "#au-owner", "value": "Ravi Kumar"},
        click("#au-add"), {"wait": 1.5}, O(highlight="#au-points")),
      S(None, "A tax preparer may raise points; a reviewer, the auditor, a partner or the firm admin clears them - and every point keeps who raised it and when.",
        click(".au-point:has-text('Rent') [data-flip]"), {"wait": 1.5}, O(highlight="#au-points")),
      S("Thank you", "The tax audit: the limits, the flags, the 3 C D clauses and who may clear a point are all SimplyFile's own rules, kept as chips - "
        "change a limit when the law changes, and every client follows. Thank you for watching.", {"wait": 2})]

t = {"page_key": "showcase6", "title": "SimplyFile showcase, part 6: the tax audit", "start_url": "/#/audit",
     "prod_base": "https://sf.valuestream.in", "voice": "en-IN-NeerjaNeural", "rate": "+0%", "viewport": {"width": 1440, "height": 900},
     "type_emails": True, "locale": "en-IN", "blur": ["#whoami", "#userpop .head"], "steps": P6}
out = ROOT / "tmp" / "tour_video" / "showcase6.json"
out.write_text(json.dumps(t, indent=1, ensure_ascii=False), encoding="utf-8")
errs = runpy.run_path(str(ROOT / "tools" / "tour_video" / "make_tour.py"), run_name="x")["validate_tour"](t)
print("showcase6", len(P6), "steps", errs or "valid")
