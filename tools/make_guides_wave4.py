"""Guide me for My return and Tax rules, rewritten 2026-10-07 for what shipped on 6-7 October: start from documents, the
"already here" question, History with old versions, the sources panel, HUF, business (44AD / 44ADA / 44AE and own P&L ->
ITR-3 / ITR-4), capital gains, gifts, winnings and crypto, farm income, co-owned houses, more deductions, tax paid yourself,
residence, foreign income and assets, clubbing, s.89, ITR-U, and the JSON for ITR-1 / 2 / 3 / 4; Tax rules read-only for
users, the owner's Fetch -> Compare -> Apply, a re-check of this year, the reminder and the Rule book.
Writes chips guide.myreturn and guide.taxwatch (steps + their test case), then tours/sf-*.json from them (tools/guide_tour.py).
Targets are the pages' own selectors (static/page-myreturn.js, static/myreturn-wave3.js, static/page-rulewatch.js).
Run from the repo root:  python tools/make_guides_wave4.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import guide_tour  # noqa: E402

NODE = ".mr-node[data-step='{}']"
G, C, CH, R, F = (NODE.format(s) for s in ("gather", "check", "choose", "review", "file"))
card = lambda inner: f"section.card:has({inner})"  # noqa: E731 - the whole card around one of its own controls

MYRETURN = {
    "title": "My return",
    "lede": "Your own return - ITR-1, 2, 3 or 4, for yourself or a family HUF. Start from your documents: {product} reads them, "
            "checks them against each other, works out both regimes and makes the department's JSON.",
    "minutes": 7,
    "steps": [
        {"title": "Five steps", "say": "Gather, check, choose, review, file. Each step ticks itself off as it is done, and you can click any step to go back to it.",
         "target": ".mr-rail-card"},
        {"title": "Start from documents", "say": "No client to add first. Drop the pre-filled JSON or a return already filed, and the person - or the HUF - "
         "is made from it: PAN, name, date of birth. A CA firm sees its people here; you go straight to your own return.",
         "target": "#mr-new|.mr-pick|.mr-rail-card"},
        {"title": "Keep these handy", "say": "A checklist of what to have before you start. Each line ticks itself when the document is in.",
         "target": ".mr-ready", "open": G},
        {"title": "Where each document comes from", "say": "Who issues each document and what it gives your return: Form 16 from your employer; "
         "the AIS, TIS and 26AS from the department; a capital-gains statement from CAMS or your broker; your bank statement.",
         "target": "details.mr-how:has(.mr-src-table)", "open": G},
        {"title": "Drop in your documents", "say": "PDF, Excel, CSV or JSON: the pre-filled JSON, Form 16 from each employer, the AIS, TIS and 26AS, "
         "a CAMS or broker statement, a bank statement, last year's filed return.", "target": "[data-drop='mr-file']", "open": G},
        {"title": "Locked PDFs", "say": "An AIS or 26AS PDF opens with its password - your PAN in small letters and your date of birth. The eye shows what you typed.",
         "target": ".mr-pw", "open": G},
        {"title": "What each one gave", "say": "Every document shows what was read from it - salary, tax deducted, interest, each sale - and, if you do not "
         "have it yet, how to get it. Drop the same kind again and you are asked first: replace it, or keep both. A second Form 16 from the same "
         "employer is asked about too - a revised one replaces the first; one from another employer is a job change, and both count.",
         "target": ".mr-dgrid", "open": G},
        {"title": "History", "say": "Every figure you change and every document you replace is in History, with who and when. Old versions are kept, "
         "ready to download.", "target": "[data-history]"},
        {"title": "Your return at a glance", "say": "Total income, tax, and the refund due or the amount to pay - kept up to date with every document and every figure.",
         "target": ".mr-glance"},
        {"title": "Do the documents agree?", "say": "Form 16's tax deducted beside 26AS, and salary and interest beside the AIS. Two employers in a year? Each took off the standard "
         "deduction - the return takes it once, and the check says so. A gap is shown to you before the department finds it.", "target": ".mr-tmap|.mr-chk", "open": C},
        {"title": "New or old regime", "say": "Both regimes worked out in full, the cheaper one marked. Pick either - the other stays one click away.",
         "target": ".mr-rgs|.mr-regs", "open": CH},
        {"title": "From income to tax", "say": "Gross income, what is exempt, the deductions, the taxable income and the tax - step by step.",
         "target": ".mr-water", "open": CH},
        {"title": "Salary", "say": "Each employer's figures from Form 16, with the source beside them. Type over anything - your own figure is marked as yours.",
         "target": card("#mr-emp-add"), "open": R},
        {"title": "Residential status", "say": "Days in India this year and the years before decide resident, not ordinarily resident or non-resident - "
         "and so which income counts.", "target": card("#q-days_fy"), "open": R},
        {"title": "Salary arrears", "say": "Arrears for an earlier year: each year's income and regime, and the relief under section 89 worked out, with a "
         "reminder to file Form 10E - even for a year over fifty lakh, with that year's surcharge.", "target": card("#mr-ar-add"), "open": R},
        {"title": "Income from outside India", "say": "Foreign salary, interest or rent, by country, with the tax paid there - relief under the treaty, or section 91 without one.",
         "target": card("#mr-fi-add"), "open": R},
        {"title": "Foreign assets", "say": "A resident's bank accounts, shares and property abroad, accounts you can sign for, trusts and other income from outside India - for Schedule FA.", "target": card("#mr-fa-add"), "open": R},
        {"title": "Clubbing", "say": "Your spouse's or minor child's income that the law adds to yours - with the exemption for each child.",
         "target": card("#mr-cl-add"), "open": R},
        {"title": "House property", "say": "Self-occupied or let out, rent, municipal tax and loan interest. A co-owned house is taken by your share, and "
         "interest before the house was finished in five parts.", "target": card("#mr-house-add"), "open": R},
        {"title": "Business or profession", "say": "Presumptive income under 44AD, 44ADA or 44AE, or your own profit and loss. Receipts can come from your "
         "bank statement. Cash received and paid decide the tax-audit limit; left 44AD in the last five years, and it stays closed. GST turnover per "
         "GSTIN, typed or read from your GSTR-3B. The form follows: ITR-4, or ITR-3.", "target": card("#b-kind"), "open": R},
        {"title": "Other income", "say": "Savings and deposit interest, dividends, family pension - from the AIS, or typed.",
         "target": card("#e-other-savings"), "open": R},
        {"title": "Winnings and crypto", "say": "Lottery and online games, and crypto or other virtual digital assets - taxed at thirty percent, a crypto loss set off against nothing.",
         "target": card("#mr-vda-add"), "open": R},
        {"title": "Tax you paid yourself", "say": "Advance tax and self-assessment tax, with the BSR code and challan number - or read from the AIS.",
         "target": card("#mr-paid-add"), "open": R},
        {"title": "Capital gains", "say": "Every sale from a CAMS or broker statement, or typed: shares and funds with grandfathering, and a house or land "
         "with the cheaper of the two rates. Exemptions under 54, 54EC and 54F - more than one on a sale, each checked against its time limit. A CAMS "
         "or KFintech PDF is read too.", "target": card("#mr-cg-add"), "open": R},
        {"title": "Losses brought forward", "say": "Losses from earlier years, set off this year and carried on - or filled from last year's filed ITR-2 or ITR-3.",
         "target": card("#mr-loss-add"), "open": R},
        {"title": "Gifts", "say": "Gifts of money or property: from a relative or on your wedding they are free; from others, over fifty thousand in a year is income.",
         "target": card("#mr-gift-add"), "open": R},
        {"title": "Deductions", "say": "80C to 80G, and more for the old regime: 80DD, 80DDB, 80EE, 80EEA, 80EEB, 80GG and 80GGC, with the details each schedule asks for.",
         "target": card("#e-via-c80c"), "open": R},
        {"title": "A few questions", "say": "Contact details for the return, farm income, and for an HUF the Karta who signs it.",
         "target": card("#q-father"), "open": R},
        {"title": "Already filed?", "say": "Once filed, note the date and acknowledgement - and compare what was filed with what {product} worked out.",
         "target": card("#mr-filed-on"), "open": F},
        {"title": "File it", "say": "Download the department's JSON for ITR-1, 2, 3 or 4, checked against its schema, and upload it on the e-filing portal.",
         "target": "#mr-json|.mr-file", "open": F},
        {"title": "Updated return", "say": "Missed something in an earlier year? The updated return, ITR-U: the extra tax, interest and the additional "
         "tax worked out at that year's rates - capital gains, surcharge and interest for each instalment - and whether you can file one at all.", "target": card("[data-iurow]"), "open": F},
    ],
}

TAXWATCH = {
    "title": "Tax rules",
    "lede": "The year's tax figures - slabs, rebates, caps and due dates - in one place. Everyone sees what every return uses; the portal owner "
            "fetches each year's, compares and applies.",
    "minutes": 3,
    "steps": [
        {"title": "Live year", "say": "The figures every return on this portal uses today, and the year they are for. For everyone but the owner, this screen is read-only.",
         "target": "#tw-head"},
        {"title": "Which year", "say": "The next year, or this year again: the department publishes circulars all year, so a re-check can move a due date. "
         "A reminder shows when a re-check is due.", "target": "#tw-ay"},
        {"title": "Fetch", "say": "Pick Gemini or OpenAI and fetch: it searches official sources and proposes every figure in the same shape. It uses "
         "the owner's own AI key.", "target": "#tw-go|#tw-fetch"},
        {"title": "At a glance", "say": "How many figures there are, how many changed, how many are the same, and how many are not announced yet.",
         "target": ".sf-kpis"},
        {"title": "Compare", "say": "Each figure side by side - the live year's and the new one's, what changed marked, and the source page for each.",
         "target": "#tw-table"},
        {"title": "Only changes", "say": "Show only what changed.", "target": "#tw-only"},
        {"title": "Edit by hand", "say": "A figure the AI got wrong or could not find: type the right one. It is marked as edited.", "target": "[data-edit]"},
        {"title": "Apply", "say": "Tick what is right, then apply. The figures go into the rules with History; last year's slabs stay for past years.",
         "target": "#tw-apply"},
        {"title": "Changes it cannot apply", "say": "A new rule that is not a figure - a new fee, a new form - is listed here, to be built.",
         "target": "section.card:has(.tw-new)|#tw-table"},
        {"title": "Sources", "say": "The pages the AI read, to check for yourself.", "target": "section.card:has(.tw-pages)|#tw-table"},
        {"title": "Rule book", "say": "Every rule {product} works by, written out in one book.", "target": "#tw-head a.btn|#tw-head"},
    ],
}


def write(screen: str, v: dict) -> None:
    p = ROOT / "chips" / f"guide.{screen}.json"
    ch = json.loads(p.read_text(encoding="utf-8"))
    params = {x["name"]: x for x in ch["params"]}
    for k in ("title", "lede", "minutes", "steps"):
        params[k]["default"] = v[k]
    want = {k: params[k]["default"] for k in ("title", "lede", "icon", "minutes", "steps")}
    ch["test_cases"] = [{"args": {}, "expect_value": want}]
    ch["version"] = int(ch.get("version") or 1) + 1
    note = " 2026-10-07: rewritten for what shipped on 6-7 October (tools/make_guides_wave4.py)."
    if note not in ch.get("description_nl", ""):
        ch["description_nl"] = ch.get("description_nl", "") + note
    p.write_bytes((json.dumps(ch, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    t = guide_tour.build(screen)
    print(f"guide.{screen}: {len(v['steps'])} steps; tours/sf-{screen}.json {len(t['steps'])} steps")


if __name__ == "__main__":
    write("myreturn", MYRETURN)
    write("taxwatch", TAXWATCH)
