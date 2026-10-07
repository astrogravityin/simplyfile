"""Showcase parts 9-12 (2026-10-07) as narrated Tour Videos -> tmp/tour_video/showcase9.json .. showcase12.json:
  9  My return from documents - a self-filer drops in the pre-filled JSON, Form 16, a locked AIS, 26AS, a CAMS statement and a bank
     statement; the "already here" question; History with the old version; check; both regimes.     (TOUR_LOGIN=selfer)
 10  My return, the review and filing - capital gains (CAMS + a plot with the cheaper rate and 54EC), a co-owned flat, losses brought
     forward, gifts, winnings and crypto, tax paid, clubbing, s.89, farm income; ITR-2 JSON checked; ITR-U.  (selfer, after pre10.py)
 11  An HUF and a consultant, from a CA firm - start from documents, the Karta, 44ADA from the bank statement -> ITR-4, own P&L -> ITR-3.
 12  Tax rules - the owner's Compare and Apply on a saved, made-up draft (pre_taxwatch.py; no AI call).  (TOUR_LOGIN=admin)
Demo documents: python tools/showcase/make_myreturn_demo.py (tools/tour_video/showcase/self, self-again, huf, kavya). All made up."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import runpy
from pathlib import Path

ROOT = Path(_R)
O = lambda **a: {"optional": True, "timeout": 6, **a}   # noqa: E731
click = lambda sel, **k: {"click": sel, **k}            # noqa: E731
card = lambda inner: f"section.card:has({inner})"       # noqa: E731
node = lambda s: click(f".mr-node[data-step='{s}']")    # noqa: E731
SELF = "showcase/self/"
F = {"pre": SELF + "01 Pre-filled JSON - ZZDPK0042Q - AY 2026-27.json", "f16": SELF + "02 Form 16 - Demo Software - AY 2026-27.pdf",
     "ais": SELF + "03 AIS - ZZDPK0042Q - FY 2025-26.pdf", "26as": SELF + "04 26AS - ZZDPK0042Q - AY 2026-27.txt",
     "cams": SELF + "05 CAMS capital gains - ZZDPK0042Q - FY 2025-26.csv", "bank": SELF + "06 Bank statement - Demo Bank - FY 2025-26.csv",
     "again": "showcase/self-again/Form 16 - Demo Software - reissued.pdf", "huf": "showcase/huf/Pre-filled JSON - ZZDHF0045L - AY 2026-27.json",
     "kavya": "showcase/kavya/Pre-filled JSON - ZZDPC0044K - AY 2026-27.json", "kbank": "showcase/kavya/Bank statement - Demo Bank - Kavya - FY 2025-26.csv"}


def S(chapter, say, *do):
    return {**({"chapter": chapter} if chapter else {}), "say": say, "do": list(do), "hold": 0.6}


def up(f, wait=2.5, inp="#mr-file", btn="#mr-up"):
    return [{"upload": inp, "files": [F[f]]}, {"wait": 0.6}, click(btn), {"wait": wait}]


def typed(sel, text):   # a field saves when it is left; the page draws again - wait for it before the next one
    return [{"fill": sel, "text": text}, {"press": "Tab"}, {"wait": 1.6}]


P9 = [S("Your own return", "Part nine: your own return. Anil Kumar Demo - made up, like everyone in these films - is salaried and holds a few "
        "mutual funds. He signed up as an individual, was approved at once, and his one client is himself. He opens My return.",
        {"goto": "/#/myreturn"}, {"wait_for": ".mr-rail-card"}, {"wait": 1}),
      S("Five steps", "Five steps: gather, check, choose, review and file. Each ticks itself off as it is done.", O(highlight=".mr-rail-card")),
      S("Keep these handy", "First, a checklist of what to keep handy. Each line ticks itself as the document comes in.", O(highlight=".mr-ready")),
      S("Where each document comes from", "And where each document comes from: who issues it, and what it gives the return.",
        click("details.mr-how:has(.mr-src-table) > summary"), {"wait": 1}, O(highlight="details.mr-how:has(.mr-src-table)"),
        click("details.mr-how:has(.mr-src-table) > summary", optional=True)),
      S("The pre-filled JSON", "He starts with the pre-filled JSON from the e-filing portal. Drop it in, and read it.",
        {"scroll_to": "[data-drop='mr-file']"}, *up("pre", 1), {"wait_for": ".mr-dcard.is-in"}, {"wait": 1}),
      S("Form 16", "Then Form 16 from his employer, as a PDF.", {"scroll_to": "[data-drop='mr-file']"}, *up("f16")),
      S("A locked AIS", "The A I S PDF is locked the department's way: his P A N in small letters and his date of birth. He types it once - the eye "
        "shows what he typed.", {"scroll_to": "[data-drop='mr-file']"}, {"upload": "#mr-file", "files": [F["ais"]]},
        {"fill": "#mr-pw", "text": "zzdpk0042q15041988"}, click("#mr-pw-eye"), {"wait": 1}, click("#mr-up"), {"wait": 3}),
      S("26AS, CAMS and the bank", "The 26 A S; his C A M S capital-gains statement, as a C S V; and his bank statement.",
        {"scroll_to": "[data-drop='mr-file']"}, *up("26as", 2), *up("cams", 2), *up("bank", 2)),
      S("What each one gave", "Every document shows what was read from it: salary and tax deducted from Form 16, interest and dividends from the "
        "A I S, four sales from C A M S, and the interest in his bank statement.", {"scroll_to": ".mr-dgrid"}, O(highlight=".mr-dgrid"),
        O(highlight=".mr-dcard.is-in >> nth=4")),
      S("Already here?", "Then his employer sends Form 16 again. He drops it in - and is asked first: replace the one he has, or keep both. "
        "Nothing is overwritten without asking.", {"scroll_to": "[data-drop='mr-file']"}, {"upload": "#mr-file", "files": [F["again"]]},
        click("#mr-up"), {"wait_for": ".ask-modal"}, {"wait": 1}, O(highlight=".ask-modal .ask-choices"), {"wait": 1},
        click(".ask-modal [data-pick='replace']"), {"wait": 2.5}),
      S("History", "History keeps it all: each document added, the Form 16 replaced - and the old one kept, ready to download.",
        {"scroll_to": "[data-history]"}, click("[data-history]"), {"wait_for": ".modal:has(.ch-lede)"}, {"wait": 1.5},
        O(highlight=".modal:has(.ch-lede) .body"), {"wait": 1}, click(".modal:has(.ch-lede) [data-close]", optional=True)),
      S("At a glance", "At the top, his return at a glance: total income, tax, and the refund due - kept up to date with every document.",
        O(highlight=".mr-glance")),
      S("Do the documents agree?", "Check: Form 16's tax deducted beside the 26 A S, salary and interest beside the A I S. Here, everything agrees.",
        node("check"), {"wait": 1.5}, O(highlight=".mr-tmap"), O(highlight=".mr-chk >> nth=0")),
      S("New or old regime", "Choose: both regimes worked out in full, and the cheaper one marked.", node("choose"), {"wait": 1.5}, O(highlight=".mr-rgs"),
        O(highlight=".mr-regs")),
      S("From income to tax", "And from income to tax, step by step.", {"scroll_to": ".mr-water"}, O(highlight=".mr-water")),
      S(None, "Next, part ten: the review - capital gains, a plot sold, a flat he co-owns, gifts - and the return, ready to file.", {"wait": 1.5})]

P10 = [S("The review", "Part ten: the review. Every figure in Anil's return, where it came from - and anything he types over it, marked as his.",
         {"goto": "/#/myreturn"}, {"wait_for": ".mr-rail-card"}, node("review"), {"wait_for": card("#mr-emp-add")}, {"wait": 1}),
       S("Salary", "Salary from Form 16, with the source beside it.", O(highlight=card("#mr-emp-add"))),
       S("Residential status", "His residential status, from the days he was in India. A resident: all his income counts, wherever it arose.",
         {"scroll_to": card("#q-days_fy")}, O(highlight=card("#q-days_fy"))),
       S("Salary arrears", "Arrears for 2022-23 were paid to him this year. That year's income and regime give the relief under section 89 - "
         "with a reminder to file Form 10 E.", {"scroll_to": card("#mr-ar-add")}, O(highlight=card("#mr-ar-add"))),
       S("Abroad and clubbing", "Income and assets outside India have their own cards. And his minor son's interest is added to his income, less "
         "the exemption for each child.", {"scroll_to": card("#mr-fi-add")}, O(highlight=card("#mr-fi-add")), {"scroll_to": card("#mr-cl-add")},
         O(highlight=card("#mr-cl-add"))),
       S("A co-owned flat", "A flat he owns half of, with his wife, let out: rent, municipal tax and loan interest, each taken by his fifty percent share.",
         {"scroll_to": card("#mr-house-add")}, O(highlight=card("#mr-house-add"))),
       S("Winnings and crypto", "Online-game winnings and a crypto sale: taxed at thirty percent, whatever his slab.",
         {"scroll_to": card("#mr-vda-add")}, O(highlight=card("#mr-vda-add"))),
       S("Tax he paid", "Self-assessment tax he paid himself, with the B S R code and challan number.", {"scroll_to": card("#mr-paid-add")},
         O(highlight=card("#mr-paid-add"))),
       S("Capital gains", "Capital gains: the four sales read from the C A M S statement - one grandfathered to January 2018 - and a plot he typed.",
         {"scroll_to": card("#mr-cg-add")}, O(highlight=card("#mr-cg-add"))),
       S("The plot", "The plot was bought in 2010. Twelve and a half percent without indexation, or twenty percent with it: SimplyFile works out "
         "both and takes the cheaper. Twenty lakh went into 54 E C bonds, so that much is exempt.",
         {"scroll_to": ".mr-cg[data-cg='0']"}, O(highlight=".mr-cg[data-cg='0']")),
       S("Losses brought forward", "A short-term loss from 2024-25, set off against this year's gains.", {"scroll_to": card("#mr-loss-add")},
         O(highlight=card("#mr-loss-add"))),
       S("Gifts", "Two gifts: two lakh from an uncle - a relative, so it is free - and seventy-five thousand from a friend: over fifty thousand "
         "in the year, so it is income.", {"scroll_to": card("#mr-gift-add")}, O(highlight=card("#mr-gift-add"))),
       S("Deductions", "Deductions from Form 16 - and more for the old regime, 80 D D to 80 G G C, with what each schedule asks for.",
         {"scroll_to": card("#e-via-c80c")}, O(highlight=card("#e-via-c80c"))),
       S("Farm income", "A few questions last: his contact details, and his share of farm income - forty thousand. It is exempt, but it is "
         "shown in the return.", {"scroll_to": "#q-agri"}, *typed("#q-agri", "40000"), O(highlight=card("#q-father"))),
       S("ITR-2", "File: with capital gains, his form is I T R 2.", node("file"), {"wait_for": "#mr-json"}, {"wait": 1}, O(highlight=".mr-form")),
       S("Checked against the schema", "The department's JSON, checked against its own schema - valid. He downloads it and uploads it on the "
         "e-filing portal: SimplyFile never files for him.", O(highlight="#mr-schema.mr-ok", timeout=12), O(highlight="#mr-json")),
       S("Already filed, and ITR-U", "Once filed, he notes the acknowledgement. And for an earlier year he missed something in, the updated "
         "return - I T R U - is worked out here too.", {"scroll_to": card("#mr-filed-on")}, O(highlight=card("#mr-filed-on")),
         {"scroll_to": card("[data-iurow]")}, O(highlight=card("[data-iurow]"))),
       S(None, "Next, part eleven: the same screen for a CA firm's families and consultants.", {"wait": 1.5})]

P11 = [S("Families and consultants", "Part eleven: My return at a CA firm, for an H U F and for a consultant. Pick a person - or start from a document.",
         {"goto": "/#/myreturn"}, {"wait_for": "#mr-new"}, {"wait": 1}, O(highlight=".mr-pick")),
       S("Start from documents", "No client to add first. The family H U F's pre-filled JSON goes in, and the H U F is made from it - its P A N, "
         "name and the day it was formed.", {"scroll_to": "[data-drop='mr-new']"}, O(highlight=card("#mr-new")),
         *up("huf", 1, "#mr-new", "#mr-new-up"), {"wait_for": ".mr-rail-card"}, {"wait": 1.5}),
       S("What it gave", "Deposit interest and the tax the bank deducted, read. An H U F never files I T R 1 and gets no 87 A rebate: its form is I T R 2.",
         {"scroll_to": ".mr-dgrid"}, O(highlight=".mr-dcard.is-in"), {"scroll_to": "header.pagehead"}, O(highlight="header.pagehead .tag")),
       S("The Karta", "The return of an H U F is signed by its Karta: his name and P A N go here.", node("review"),
         {"wait_for": "#q-karta_name"}, {"scroll_to": "#q-karta_name"}, *typed("#q-karta_name", "Demo Karta"), *typed("#q-karta_pan", "ZZDPK0046M"),
         *typed("#q-father", "Demo Grandfather"), O(highlight=".mr-who >> nth=0")),
       S("Both regimes", "Both regimes for the H U F, the cheaper one marked.", node("choose"), {"wait": 1.5}, O(highlight=".mr-rgs")),
       S("A consultant", "Next, Kavya: a consultant with no Form 16 - fees from her clients, with tax deducted under 194 J. Her pre-filled JSON "
         "makes her too.", {"goto": "/#/myreturn"}, {"wait_for": "#mr-new"}, {"scroll_to": "[data-drop='mr-new']"},
         *up("kavya", 1, "#mr-new", "#mr-new-up"), {"wait_for": ".mr-rail-card"}, {"wait": 1.5}),
       S("Her bank statement", "Her bank statement: fifteen lakh ninety thousand of receipts, sixty thousand in cash - interest and her own "
         "transfers kept apart.", {"scroll_to": "[data-drop='mr-file']"}, *up("kbank", 3), {"scroll_to": ".mr-dgrid"},
         O(highlight=".mr-dcard.is-in >> nth=1")),
       S("Presumptive income", "On review, her work: a profession under 44 A D A. One click takes the receipts from the bank statement, and half "
         "of them is her income.", node("review"), {"wait_for": "#b-kind"}, {"scroll_to": "#b-kind"}, {"select": "#b-kind", "value": "44ADA"},
         {"wait": 2}, click("#mr-biz-bank"), {"wait": 2}, O(highlight=card("#b-kind"))),
       S("ITR-4", "Her nature of work, and her father's name for the return. The form follows: I T R 4, Sugam.",
         {"select": "#b-code", "value": "14001"}, {"wait": 2}, {"scroll_to": "#q-father"}, *typed("#q-father", "Demo Father"),
         {"scroll_to": "header.pagehead"}, O(highlight="header.pagehead .tag")),
       S("Her own profit and loss", "If she keeps her own accounts instead - receipts, expenses and profit typed - it is I T R 3.",
         {"scroll_to": "#b-kind"}, {"select": "#b-kind", "value": "profession"}, {"wait": 2}, {"scroll_to": "#b-expenses"},
         *typed("#b-expenses", "620000"), O(highlight=card("#b-kind"))),
       S("ITR-3, checked", "File: I T R 3, made from My return and checked against the department's schema.", node("file"), {"wait_for": ".mr-form"},
         {"wait": 1}, O(highlight=".mr-form"), O(highlight="#mr-schema.mr-ok", timeout=12)),
       S(None, "Last, part twelve: the tax rules themselves.", {"wait": 1.5})]

P12 = [S("Tax rules", "Part twelve: tax rules. Every slab, rebate, cap and due date the portal works with, in one place - read-only for everyone "
         "but the portal owner. Here is the owner.", {"goto": "/#/taxwatch"}, {"wait_for": "#tw-head"}, {"wait": 1}, O(highlight=".tw-live")),
       S("A reminder", "Not checked for thirty days: the department may have published something since. A reminder - never a call made by itself.",
         O(highlight="#tw-head > p >> nth=0")),
       S("Fetch", "Pick the year - the next one, or this year again - and an A I: Gemini or OpenAI, both searching the web, with the owner's own "
         "key. For this film the answer was saved beforehand, and made up: no A I is called.", O(highlight="#tw-fetch")),
       S("At a glance", "Four figures changed, thirty-four the same, and three not announced yet.", O(highlight=".sf-kpis")),
       S("Compare", "Side by side, this year's and the next: the new regime's slabs, the standard deduction, the 80 C cap and the due date - each "
         "change marked, with its source.", {"scroll_to": "#tw-table"}, O(highlight="#tw-table tr.s-changed >> nth=0"),
         O(highlight="#tw-table tr.s-changed >> nth=1")),
       S("Only changes", "Only the changes.", click("#tw-only"), {"wait": 1.2}, O(highlight="#tw-table")),
       S("Not announced", "Surcharge is not announced yet: it stays as it is until it is.", click("#tw-only"), {"wait": 1.2},
         O(highlight="#tw-table tr.s-unknown >> nth=0")),
       S("Not a figure", "A change that is not a figure - a new fee - is listed to be built, never guessed into a rule. And the pages it read, "
         "here made up.", {"scroll_to": "section.card:has(.tw-new)"}, O(highlight="section.card:has(.tw-new)"), O(highlight="section.card:has(.tw-pages)")),
       S("Apply", "Tick what is right and apply. The figures go into the rules through the same builder as every chip - with History - and "
         "last year's slabs stay for past years.", {"scroll_to": "#tw-apply"}, O(highlight="#tw-apply"), click("#tw-do"),
         {"wait_for": ".modal.confirm"}, {"wait": 1.2}, click(".modal.confirm [data-yes]"), {"wait": 3.5}),
       S("The new year is live", "The new year is now live: every return on the portal - a CA firm's or your own - works with its figures.",
         {"scroll_to": "#tw-head"}, O(highlight=".tw-live")),
       S("Rule book", "And the rule book: every rule SimplyFile works by, written out in one place.", O(highlight="#tw-head a.btn")),
       S("Thank you", "Your own return from your documents, a firm's families and consultants, and the year's rules kept up to date - all "
         "SimplyFile's own rules, kept as chips. Thank you for watching.", {"wait": 2})]

BASE = {"prod_base": "https://sf.valuestream.in", "voice": "en-IN-NeerjaNeural", "rate": "+0%", "viewport": {"width": 1440, "height": 900},
        "type_emails": True, "locale": "en-IN", "blur": ["#whoami", "#userpop .head"]}
PARTS = [("showcase9", "SimplyFile showcase, part 9: your own return, from your documents", "/#/myreturn", P9),
         ("showcase10", "SimplyFile showcase, part 10: the review, and the return filed", "/#/myreturn", P10),
         ("showcase11", "SimplyFile showcase, part 11: an HUF and a consultant", "/#/myreturn", P11),
         ("showcase12", "SimplyFile showcase, part 12: tax rules", "/#/taxwatch", P12)]
validate = runpy.run_path(str(ROOT / "tools" / "tour_video" / "make_tour.py"), run_name="x")["validate_tour"]
for key, title, start, steps in PARTS:
    t = {"page_key": key, "title": title, "start_url": start, **BASE, "steps": steps}
    (ROOT / "tmp" / "tour_video" / f"{key}.json").write_text(json.dumps(t, indent=1, ensure_ascii=False), encoding="utf-8")
    print(key, len(steps), "steps", validate(t) or "valid")
