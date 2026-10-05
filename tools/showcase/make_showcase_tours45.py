"""Showcase part 4 (Delegations) and part 5 (Chip Chat) as narrated Tour Videos -> tmp/tour_video/showcase4.json, showcase5.json.
Run after parts 1-2 have put the firm, team and clients in place (rehearse_all.sh ... @pre4.py showcase4 showcase5)."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import runpy
from pathlib import Path

ROOT = Path(_R + r"")
O = lambda **a: {**a, "optional": True, "timeout": 6}   # noqa: E731
fill = lambda sel, text: {"fill": sel, "text": text}    # noqa: E731
click = lambda sel, **k: {"click": sel, **k}            # noqa: E731


def tour(key, title, steps, start="/#/delegate"):
    t = {"page_key": key, "title": title, "start_url": start, "prod_base": "https://sf.valuestream.in", "voice": "en-IN-NeerjaNeural",
         "rate": "+0%", "viewport": {"width": 1440, "height": 900}, "type_emails": True, "locale": "en-IN",
         "blur": ["#whoami", "#userpop .head", ".fi-pw", "#c-email", "#c-phone"], "steps": steps}
    out = ROOT / "tmp" / "tour_video" / f"{key}.json"
    out.write_text(json.dumps(t, indent=1, ensure_ascii=False), encoding="utf-8")
    errs = runpy.run_path(str(ROOT / "tools" / "tour_video" / "make_tour.py"), run_name="x")["validate_tour"](t)
    print(key, len(steps), "steps", errs or "valid")


def S(chapter, say, *do):
    return {**({"chapter": chapter} if chapter else {}), "say": say, "do": list(do), "hold": 0.6}


def lend(to, scope, clients, grants, until, note, ay=None):
    do = [{"goto": "/#/delegate"}, {"wait_for": "#dl-new"}, click("#dl-new"), {"wait_for": ".modal #dl-to"}, {"select": ".modal #dl-to", "value": to},
          click(f".modal .dl-kind:has-text('{scope}')")]
    do += [click(f".modal .dl-clients label:has-text('{c}')") for c in clients]
    if ay:
        do.append({"select": ".modal #dl-ay", "value": ay})
    do += [click(f".modal .dl-grants label:has-text('{g}')") for g in grants]
    return do + [fill(".modal #dl-until", until), fill(".modal #dl-note", note), O(highlight=".modal .body"), click(".modal #dl-save"),
                 {"wait_for": f"tr:has-text('{note[:30]}')"}]


P4 = [S("Delegations", "Part four: delegations. In a CA firm people go on leave, fall ill, or need help at the deadline. Instead of sharing a password, "
        "SimplyFile lets a person lend some of their own powers to a colleague - for one filing, one client, some clients or all clients for a year - and for set dates.",
        {"goto": "/#/delegate"}, {"wait_for": "#dl-new"}, O(highlight=".page-head, .ph, h1")),
      S(None, "The firm admin sees every delegation in the firm. Kavitha, a partner, is away next week, so she has already lent Anand the right to file "
        "every return of assessment year 2026-27 until she is back.", O(scroll_to="section:has-text('Everyone in the firm')"), O(highlight="section:has-text('Everyone in the firm')"), {"wait": 1}),
      S("One filing", "Now Demo Partner lends Ravi, a tax preparer, the sign-off for one filing: Shree Ganesh Agarwal HUF, 2026-27. A preparer cannot sign off on his own - "
        "this lets him, for this one client and year, until the end of the month.",
        *lend("Ravi", "One filing", ["Agarwal"], ["Sign off a computation"], "2026-10-31", "Agarwal HUF - please sign off, I am travelling", ay="2026-27")),
      S("Some clients for a year", "Next: some clients for a year. Ravi may also mark the returns filed for Ramesh Iyer and Meera Nair this year.",
        *lend("Ravi", "Some clients for a year", ["Ramesh Iyer", "Meera Nair"], ["Mark a return filed"], "2026-12-31", "File Ramesh and Meera once signed off", ay="2026-27")),
      S("What it covers", "Only what Demo Partner may do himself can be lent. Ravi can now sign off the Agarwal HUF for 2026-27 - but not another client, and not another year. "
        "Everything he does through it is recorded as Ravi, for Demo Partner - so the firm always knows who did what, and for whom.",
        O(highlight="section:has-text('Lent by me')"), {"wait": 1}),
      S("Take it back", "A delegation ends by itself on its date - or can be taken back at once.",
        click("section:has-text('Lent by me') tr:has-text('File Ramesh') [data-revoke]"), {"wait_for": ".modal [data-yes]"}, click(".modal [data-yes]"),
        {"wait_for": "section:has-text('Lent by me') tr:has-text('File Ramesh') .sv-pill:has-text('Taken back')"},
        O(highlight="section:has-text('Lent by me')"), {"wait": 1}),
      S("Portal level", "The portal owner can delegate too: day-to-day portal work - firm approvals, portal analytics, server and sites - to a deputy, for set dates. "
        "People and access, the rule builders and setup stay with the owner alone.", {"wait": 2}),
      S("Thank you", "Delegations in SimplyFile: powers lent, never passwords shared - scoped, dated, recorded and revocable. Thank you for watching.", {"wait": 2})]
tour("showcase4", "SimplyFile showcase, part 4: delegations", P4)


def ask(q):
    return [fill("[data-q]", q), {"press": "Enter"}, {"wait": 1.6}, O(highlight=".cx-log .cx-chips:last-child")]


P5 = [S("The tool bar", "Part five: Chip Chat and the tool bar. At the bottom right of every screen: Chip Chat, screen capture, screen recording, voice typing, "
        "Notes and Issues. It folds away sideways or upwards with the arrow.", {"goto": "/#/clients"}, {"wait_for": ".pd [data-dock-chip-chat]"}, O(highlight=".pd")),
      S("Chip Chat", "Chip Chat is the firm's own expert on call. It knows more than ten thousand questions - how SimplyFile works, tax with real numbers, "
        "due dates, kinds of return, roles and permissions - and it answers from SimplyFile's own rules and your firm's own data, for your role. "
        "No AI guesswork, and no data leaving the firm.", click(".pd [data-dock-chip-chat]"), {"wait_for": "[data-q]"}, O(highlight=".cx-head")),
      S(None, "Under the ask box, a fresh set of example questions every time - some from your own work - and a new hint in the box.",
        O(highlight=".cx-examples"), {"wait": 1}),
      S("Your own work", "Which returns are overdue? Worked out live from the firm's clients - each line opens the client. And after every answer: what to ask next.",
        *ask("Which returns are overdue?")),
      S(None, "Where does a client stand? Just name them.", *ask("Where does Kiran stand?")),
      S("Tax, worked out", "Tax questions with numbers are worked out by the same rules as the computation: eighteen and a half lakh for an HUF, old regime, 2025-26.",
        *ask("How much tax on 18.5 lakh for an HUF under the old regime for AY 2025-26?")),
      S(None, "Twelve lakh for a resident individual in the new regime: the 87A rebate takes the tax to nil.", *ask("tax on 12 lakh")),
      S("Dates and kinds of return", "Due dates for any form and year, and what a return filed on a given day would be: ITR 3 on the 15th of November 2026 is belated.",
        *ask("If I file ITR-3 on 15/11/2026 what kind of return is it?")),
      S(None, "An updated return, two lakh of extra tax, fifteen months after the year ended: 140 B adds fifty percent.",
        *ask("ITR-U additional tax on extra tax of 2 lakh filed 15 months after the year ended")),
      S("Roles", "Who may do what: a tax preparer cannot sign off - and Chip Chat says how it can be lent to him.", *ask("Can a tax preparer sign off?")),
      S("Surprise me", "And Surprise me: a good question, different for each person, every hour and every press.", click("[data-surprise]"), {"wait": 1.8},
        O(highlight=".cx-log .cx-chips:last-child")),
      S("Training it", "When Chip Chat does not know, it says so and keeps the question - the firm and the role, never the person's name.",
        *ask("What are the office hours?")),
      S(None, "The firm admin trains it on the Train tab: every question asked, what Chip Chat said, and a Teach box - point it at the right answer, "
        "or write the firm's own.", click("[data-tab=train]"), {"wait_for": ".cx-table"}, O(highlight=".cx-tbar")),
      S(None, "The firm's own answer to office hours - taught once, for everyone in the firm.",
        {"select": "[data-filter]", "value": "unanswered"}, {"wait": 1.5}, {"wait_for": "tr:has-text('office hours')"},
        fill("tr:has-text('office hours') [data-own]", "Monday to Saturday, 9:30 to 6:30. Sundays closed."),
        click("tr:has-text('office hours') [data-teach]"), {"wait": 1.5}, O(highlight=".cx-train .cx-card:last-child")),
      S(None, "Ask again - and the firm's answer comes.", click("[data-tab=chat]"), *ask("office hours?")),
      S("Notes", "Notes: private notes for each person, opened from the tool bar - search on the left, the note on the right, with bold, lists, "
        "highlight and text colours, pictures pasted or taken with screen capture, and voice notes kept with the words written down. "
        "The microphone is on as Notes opens: what you say is typed in.",
        click(".modal [data-close]"), click(".pd [data-dock-tool=notes]"), {"wait_for": "[data-editor]"}, click("[data-new]"),
        fill("[data-name]", "Agarwal HUF - to ask"),
        fill("[data-editor]", "To ask Ganesh: the FD interest certificate and the rent receipts, before sign-off."),
        {"press": "Control+a"}, click("[data-tools] .as-swatch"), {"press": "End"},
        click("[data-save]"), {"wait_for": ".as-row:has-text('Agarwal HUF')"}, O(highlight=".modal .as-split")),
      S("Issues", "Issues: anything wrong or missing goes to the portal admin - a header, the details, several pictures and voice notes. "
        "Each issue shows its status and the admin's reply, and the flag shows a badge when a reply is waiting.",
        click(".modal [data-close]"), O(click=".modal [data-yes]"), click(".pd [data-dock-tool=issue]"), {"wait_for": "[data-title]"},
        fill("[data-title]", "Add a Form 26AS download button"), fill("[data-text]", "It would save a trip to TRACES for every client."),
        O(highlight=".modal [data-issue-new]"), click("[data-send]"), {"wait_for": ".as-row-btn:has-text('26AS')"}, click(".as-row-btn:has-text('26AS')"),
        {"wait_for": "[data-issue-detail]"}, O(highlight=".modal .as-split")),
      S(None, "Screen capture snips part of the screen - to copy, download, keep in a note or report as an issue. Screen recording makes a video for "
        "the team. Voice typing writes what you say into the box you are in.", click(".modal [data-close]"), O(highlight=".pd"), {"wait": 1}),
      S("Thank you", "Chip Chat and the tool bar: more than ten thousand questions answered from SimplyFile's own rules and your own data - by firm and by "
        "role, and trained by the firm. Thank you for watching.", {"wait": 2})]
tour("showcase5", "SimplyFile showcase, part 5: Chip Chat and the tool bar", P5, start="/#/clients")
