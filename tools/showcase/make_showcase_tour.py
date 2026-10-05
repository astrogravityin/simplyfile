"""The showcase as ONE narrated Tour Video: the firm admin of Demo CA Filing Firm adds the team, then takes five fictional
clients through every scenario the portal has. Writes tmp/tour_video/showcase.json and copies the client files to
tools/tour_video/showcase/ (gitignored) - make_tour.py uploads only from under tools/tour_video/."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import shutil
from pathlib import Path

ROOT = Path(_R + r"")
PACK = ROOT / "Requirements" / "Showcase - Demo CA Filing Firm"
DST = ROOT / "tools" / "tour_video" / "showcase"
DST.mkdir(parents=True, exist_ok=True)   # never cleared: parts 2 and 3 keep their files here too
FILES = {}
for n, folder in enumerate(sorted(p for p in PACK.iterdir() if p.is_dir() and p.name.split(" ")[0] in {"C1", "C2", "C3", "C4", "C5"}), 1):
    for f in folder.iterdir():
        if f.suffix.lower() in {".xlsx", ".txt", ".csv"} and not f.name.startswith("01 "):
            (DST / f"c{n}").mkdir(exist_ok=True)
            shutil.copy2(f, DST / f"c{n}" / f.name)       # the original name: the screens show it
            FILES[(n, f.name)] = f"showcase/c{n}/{f.name}"


def file_of(n, part):
    hit = [v for (k, name), v in FILES.items() if k == n and part in name]
    assert len(hit) == 1, (n, part, hit)
    return hit[0]


O = lambda **a: {**a, "optional": True, "timeout": 6}   # noqa: E731  - a spotlight that may be missing
steps = []


def step(chapter, say, *do, hold=0.6):
    s = {"say": say, "do": list(do), "hold": hold}
    if chapter:
        s["chapter"] = chapter
    steps.append(s)


def fill(sel, text):
    return {"fill": sel, "text": text}


def click(sel, **k):
    return {"click": sel, **k}


def new_client(name, status, pan, extra, banks, partners=()):
    do = [click("#cl-new"), fill(".modal #c-name", name), {"select": ".modal #c-status", "value": status}, fill(".modal #c-pan", pan)]
    for sel, v in extra:
        do.append(fill(f".modal {sel}", v))
    for i, b in enumerate(banks):
        if i:
            do.append(click(".modal #c-add-bank"))
        for f, v in b.items():
            do.append(fill(f".modal #c-banks [data-bank]:nth-child({i + 1}) [data-f={f}]", v))
    for i, p in enumerate(partners):
        do.append(click(".modal #c-add-partner"))
        for f, v in p.items():
            do.append(fill(f".modal #c-partners [data-partner]:nth-child({i + 1}) [data-f={f}]", v))
    return do + [click(".modal [data-save]"), {"wait_for": f".cl-row:has-text('{name}')"}]


def into_year(name, form, audit=False, tp=False, assigned=""):
    do = [click(f".cl-row:has-text('{name}') [data-open]"), {"click": ".modal #y-add", "optional": True, "timeout": 3}, {"wait_for": ".modal #y-save"},
          {"select": ".modal #y-form", "value": form}]
    if audit:
        do.append(click(".modal #y-audit"))
    if tp:
        do.append(click(".modal #y-tp"))
    if assigned:
        do.append(fill(".modal #y-assigned", assigned))
    return do + [click(".modal #y-save"), {"wait_for": ".modal #y-save"}, {"wait": 1}, click(".modal [data-close]")]


def pick(screen, name, ay=None, sel=None):
    do = [{"goto": f"/#/{screen}"}, click(f".in-pick-row:has-text('{name}') [data-choose]")]
    if ay:
        do += [{"wait_for": sel}, {"select": sel, "value": ay}, {"wait": 1.5}]
    return do


def upload(button, path):
    return [click(button), {"upload": ".modal #rb-up-file", "files": [path]}, {"wait": 0.6}, click(".modal [data-save]"), {"wait": 2}]


def open_file(part):
    return [click(f".in-file[data-name*='{part}'] [data-map]"), {"wait_for": "#in-accept"}, {"wait": 1}]


def accept():
    return [click("#in-accept"), {"wait": 2}]


def sign_and_file(ack, on=None, itru=False):
    do = [click("#cc-sign"), click(".modal [data-yes]"), {"wait_for": "#cc-file:not([disabled])"}, fill("#cc-ack", ack)]
    if on:
        do.append(fill("#cc-on", on))
    if itru:
        do.append(click("#cc-itru"))
    return do + [click("#cc-file"), click(".modal [data-yes]"), {"wait_for": ".cc-filed"}, {"wait": 1}]


AY, AY5 = "2026-27", "2025-26"

# ---- the firm
step("Demo CA Filing Firm on SimplyFile",
     "Welcome to SimplyFile, the income-tax filing portal for CA firms. This is Demo C A Filing Firm, approved by the portal admin. "
     "Every client and figure you will see is made up for this demo.", {"wait": 1.5})
step("My firm", "My firm shows the firm's approval, its papers and its team. The shield is green: the firm is approved, so the Filing screens are open.",
     O(highlight=".fi-hero"), O(highlight=".fi-banner"))
team = [("Kavitha Menon", "kavitha.partner@example.com", "partner", "Kavitha joins as a partner: she can sign off, file and revise."),
        ("Anand Murthy", "anand.reviewer@example.com", "reviewer", "Anand is the reviewer: he reads everything and signs off the computation."),
        ("Ravi Kumar", "ravi.preparer@example.com", "preparer", "Ravi is the tax preparer: clients, mapping, reconciling and computing - no sign-off or filing.")]
for i, (nm, em, role, say) in enumerate(team):
    step("Building the team" if i == 0 else None, say, click("#fi-add"), fill(".modal #tp-name", nm), fill(".modal #tp-email", em),
         {"select": ".modal #tp-role", "value": role}, click(".modal [data-save]"), {"wait": 2},
         O(click=".modal [data-close]"), {"wait_for": f".fi-team tr:has-text('{nm}'), tr:has-text('{nm}')"})
step(None, "Each person gets a one-time password and sets their own at first sign-in. Their role decides which menus and buttons they see.", O(highlight=".fi-team"))

# ---- C1
step("Client 1 - Shree Ganesh Agarwal HUF",
     "Client one is a Hindu undivided family with a trading business and a tax audit: the full road from the client master to a filed return.",
     {"goto": "/#/clients"}, {"wait_for": "#cl-new"})
step(None, "A new client: name, status, PAN - its fourth letter must fit the status - email, phone, address and the bank account for the refund. "
     "Date of birth, the karta's father's name and PAN go into the return's verification.",
     *new_client("Shree Ganesh Agarwal HUF", "huf", "AAAHG4321K",
                 [("#c-relation", "Ganesh Prasad Agarwal"), ("#c-email", "ganesh.agarwal.huf@example.com"), ("#c-phone", "9800012345"),
                  ("#c-dob", "1998-04-15"), ("#c-father", "Ram Prasad Agarwal"), ("#c-signer", "ABCPA1234D"), ("#c-gst", "36AAAHG4321K1Z8"),
                  ("#c-address", "8-2-293/A, Road No. 12, Banjara Hills, Hyderabad 500034")],
                 [{"bank": "HDFC Bank", "branch": "Banjara Hills", "type": "Current", "account": "50200098765432", "ifsc": "HDFC0000123"}]))
step(None, "Into assessment year 2026-27 with ITR-3 and a tax audit, assigned to Ravi. The stage is not picked by anyone - it moves by itself.",
     *into_year("Shree Ganesh Agarwal HUF", "ITR-3", audit=True, assigned="Ravi Kumar"), O(highlight=".cl-row:has-text('Shree Ganesh') .cl-stage"))
step("Intake and mapping", "Intake: upload the client's statement - the income statement, depreciation and loans - straight from Excel.",
     *pick("intake", "Shree Ganesh Agarwal HUF"), *upload("#in-up", file_of(1, "02 ")))
step(None, "Every row is grouped under the statement's own headings. Each heading adds up the way the statement means it, and is checked against the statement's own total.",
     *open_file("IT Stmt"), O(highlight=".mp-group-h"), {"wait": 1})
step(None, "SimplyFile has already suggested an SF Ref for almost every row. Accept them all in one click.", *accept())
step(None, "One row needs a person: the disallowance under section forty a, i a. It goes to business income - type ITR3 BP and save.",
     fill(".mp-row:has-text('40(a)') [data-ref]", "ITR3 BP"), click("#in-save"), {"wait": 2}, O(highlight=".mp-group-h"))
step(None, "The client's final accounts next: trading, profit and loss, and the balance sheet. Their own SF Ref column tags every row.",
     click("#in-back"), {"wait_for": "#in-up"}, *upload("#in-up", file_of(1, "10 ")), *open_file("Balance Sheet"), {"wait": 2})
step(None, "Uploading the same statement again does not fail: SimplyFile offers to replace it, keeps the refs on rows that did not change, and keeps the old version.",
     click("#in-back"), {"wait_for": "#in-up"}, click("#in-up"), {"upload": ".modal #rb-up-file", "files": [file_of(1, "02 ")]}, {"wait": 0.6},
     click(".modal [data-save]"), {"wait": 1.5}, O(highlight=".modal"), {"wait": 1.5}, click(".modal [data-yes]"), {"wait": 2})
step("Reconcile with 26AS, AIS and TIS", "Reconcile: bring in the 26AS, AIS and TIS downloaded from the income-tax portal.",
     *pick("recon", "Shree Ganesh Agarwal HUF"), *upload("#rc-up", file_of(1, "03 ")), *upload("#rc-up", file_of(1, "04 ")), *upload("#rc-up", file_of(1, "05 ")))
step(None, "Books against the portal, deductor by deductor. One red: Lakshmi Finance shows thirty-six thousand of TDS, the books claim forty thousand.",
     O(highlight="#rc-hero"), O(highlight=".rc-f.sev-red"))
step(None, "Explain it - the client confirmed the credit as per 26AS - and the year moves on to review by itself.",
     click(".rc-f.sev-red [data-explain]"), fill(".modal #rc-note", "Checked with the client: claim restricted to the 26AS credit of Rs 36,000."),
     click(".modal [data-save]"), {"wait": 2}, O(highlight="#rc-hero"))
step("Compute and close", "Compute: each head adds its mapped rows. Tax, surcharge and cess, under the regime you pick.",
     *pick("compute", "Shree Ganesh Agarwal HUF"), {"wait_for": ".cc-comp"}, O(highlight=".cc-steps"), O(highlight=".cc-comp"))
step(None, "Interest under 234 A, B and C is worked out from the 26AS challans by date - here nil, the advance tax covered every instalment. "
     "The refund is sixty-six thousand three hundred and sixty rupees.", O(highlight="#cc-int"), O(highlight=".cc-bal"), O(highlight=".cc-wf"))
step(None, "The files for filing: the computation in Excel, the ITR-3 JSON in the income-tax department's own format, and the Form 3CB-3CD JSON - "
     "each checked against the CBDT schema before you download. The balance sheet tallies and the profit matches business income.",
     O(highlight=".cc-dl"), {"wait": 2}, O(highlight="#cc-itr-check"), O(highlight="#cc-3cd-check"))
step(None, "The reviewer signs off, then the acknowledgement number and the date filed. Filed on time, it is an original return under 139 one, and the year locks.",
     *sign_and_file("456789012345678"), O(highlight=".cc-close"))
step(None, "Found a mistake after filing? Start a revised return. Changed your mind? Discard the revision - the filed return stands. Nothing filed is ever deleted.",
     click("[data-act=revise]"), click(".modal [data-yes]"), {"wait": 2}, O(highlight=".cc-close"), {"wait": 1.5},
     click("[data-act=discard]"), click(".modal [data-yes]"), {"wait": 2}, O(highlight=".cc-hist"))

# ---- C2
step("Client 2 - Ramesh Iyer, senior citizen",
     "Client two, Ramesh Iyer, was born in 1958: a resident senior citizen with no business income, filing late.",
     {"goto": "/#/clients"}, {"wait_for": "#cl-new"},
     *new_client("Ramesh Iyer", "individual", "BXRPI5821K",
                 [("#c-email", "ramesh.iyer@example.com"), ("#c-phone", "9840012345"), ("#c-dob", "1958-06-10"), ("#c-father", "Venkatesan Iyer"),
                  ("#c-address", "14, Kutchery Road, Mylapore, Chennai 600004")],
                 [{"bank": "Indian Bank", "branch": "Mylapore", "type": "Savings", "account": "6012345678", "ifsc": "IDIB000M053"}]),
     *into_year("Ramesh Iyer", "ITR-3"))
step(None, "His income statement and 26AS - every row suggested, accepted in one click.",
     *pick("intake", "Ramesh Iyer"), *upload("#in-up", file_of(2, "Income statement")), *open_file("Income statement"), *accept(),
     *pick("recon", "Ramesh Iyer"), *upload("#rc-up", file_of(2, "26AS")))
step(None, "A senior citizen with no business income pays no advance tax, so no interest under 234 B or C. Filing after the 31st of July due date still "
     "costs 234 A: five hundred and seventy-one rupees, worked out to the day.",
     *pick("compute", "Ramesh Iyer"), {"wait_for": ".cc-comp"}, O(highlight="#cc-int"), O(highlight=".cc-bal"), O(highlight=".cc-dates"))

# ---- C3
step("Client 3 - Sri Venkateswara Traders, a firm",
     "Client three is a partnership firm: ITR-5 with a tax audit and Form 3CEB for transfer pricing. Its partners go in the client master.",
     {"goto": "/#/clients"}, {"wait_for": "#cl-new"},
     *new_client("Sri Venkateswara Traders", "firm", "AAFFS4721M",
                 [("#c-relation", "Venkata Rao (managing partner)"), ("#c-email", "accounts@svtraders.example.com"), ("#c-phone", "9848012345"),
                  ("#c-dob", "2012-04-01"), ("#c-father", "Narasimha Rao"), ("#c-signer", "ABCPV1234E"), ("#c-gst", "36AAFFS4721M1ZK"),
                  ("#c-address", "12-2-718, Mehdipatnam, Hyderabad 500028")],
                 [{"bank": "State Bank of India", "branch": "Mehdipatnam", "type": "Current", "account": "38123456789", "ifsc": "SBIN0020071"}],
                 [{"name": "Venkata Rao", "pan": "ABCPV1234E", "share": "50"}, {"name": "Srinivas Rao", "pan": "ABCPS5678F", "share": "50"}]),
     *into_year("Sri Venkateswara Traders", "ITR-5", audit=True, tp=True))
step(None, "Its statement and its final accounts. These accounts have no SF Ref column at all - SimplyFile reads the words under the P and L and "
     "balance sheet headings and suggests every ref.",
     *pick("intake", "Sri Venkateswara Traders"), *upload("#in-up", file_of(3, "IT Stmt")), *open_file("IT Stmt"), *accept(),
     click("#in-back"), {"wait_for": "#in-up"}, *upload("#in-up", file_of(3, "Balance Sheet")), *open_file("Balance Sheet"), {"wait": 1.5}, *accept())
step(None, "26AS in, everything agrees.", *pick("recon", "Sri Venkateswara Traders"), *upload("#rc-up", file_of(3, "26AS")), O(highlight="#rc-hero"))
step(None, "Advance tax fell short, so 234 B and 234 C apply: twenty-two thousand three hundred and seventy-two, and fourteen thousand one hundred and thirteen. "
     "With Form 3CEB the due date is the 30th of November.",
     *pick("compute", "Sri Venkateswara Traders"), {"wait_for": ".cc-comp"}, O(highlight="#cc-int"), O(highlight=".cc-bal"), O(highlight=".cc-dates"))
step(None, "The ITR-5 JSON and the 3CB-3CD JSON, both checked against the department's schema - our firm named as the auditor.",
     O(highlight=".cc-dl"), {"wait": 2}, O(highlight="#cc-3cd-check"))

# ---- C4
step("Client 4 - Kiran Kumar Rao, professional",
     "Client four, Kiran Kumar Rao, is a professional whose clients deducted TDS under 194 J.",
     {"goto": "/#/clients"}, {"wait_for": "#cl-new"},
     *new_client("Kiran Kumar Rao", "individual", "BKRPR4417H",
                 [("#c-email", "kiran.rao@example.com"), ("#c-phone", "9849912345"), ("#c-dob", "1988-11-23"), ("#c-father", "Mohan Rao"),
                  ("#c-address", "Flat 402, Aditya Enclave, Kondapur, Hyderabad 500084")],
                 [{"bank": "ICICI Bank", "branch": "Kondapur", "type": "Savings", "account": "123401234567", "ifsc": "ICIC0001234"}]),
     *into_year("Kiran Kumar Rao", "ITR-3"),
     *pick("intake", "Kiran Kumar Rao"), *upload("#in-up", file_of(4, "Income statement")), *open_file("Income statement"), *accept(),
     *pick("recon", "Kiran Kumar Rao"), *upload("#rc-up", file_of(4, "26AS")))
step(None, "The 87 A rebate brings his tax to nil, so all the TDS comes back: a refund of one lakh eighty thousand.",
     *pick("compute", "Kiran Kumar Rao"), {"wait_for": ".cc-comp"}, O(highlight=".cc-bal"), O(highlight=".cc-wf"))
step(None, "Filed on the 20th of August, within the new 31st of August due date for business returns.", *sign_and_file("567890123456789", "2026-08-20"))
step(None, "The refund was paid on the 1st of October. Interest under 244 A at half a percent a month: six thousand three hundred rupees.",
     fill("#cc-refon", "2026-10-01"), {"wait": 2}, O(highlight=".cc-bal"), O(highlight="#cc-refon"))

# ---- C5
step("Client 5 - Meera Nair, updated return",
     "Client five, Meera Nair, filed her return for assessment year 2025-26 in July 2025. Later she found income she had missed.",
     {"goto": "/#/clients"}, {"wait_for": "#cl-new"}, {"select": "#cl-ay", "value": AY5}, {"wait": 1.5},
     *new_client("Meera Nair", "individual", "AYMPN6630Q",
                 [("#c-email", "meera.nair@example.com"), ("#c-phone", "9845012345"), ("#c-dob", "1979-02-14"), ("#c-father", "Gopinath Nair"),
                  ("#c-address", "22, Indiranagar 2nd Stage, Bengaluru 560038")],
                 [{"bank": "Canara Bank", "branch": "Indiranagar", "type": "Savings", "account": "0412101234567", "ifsc": "CNRB0000412"}]),
     *into_year("Meera Nair", "ITR-3"))
step(None, "First the return as she filed it, with its 26AS.",
     *pick("intake", "Meera Nair", AY5, "#in-ay"), *upload("#in-up", file_of(5, "as filed")), *open_file("as filed"), *accept(),
     *pick("recon", "Meera Nair", AY5, "#rc-ay"), *upload("#rc-up", file_of(5, "26AS")))
step(None, "Recorded as filed on the 28th of July 2025: an original return.",
     *pick("compute", "Meera Nair", AY5, "#cc-ay"), {"wait_for": ".cc-comp"}, *sign_and_file("345678901234567", "2025-07-28"))
step(None, "The 31st of December has passed, so a revised return is no longer allowed - SimplyFile offers an updated return, ITR-U, instead.",
     O(highlight=".cc-dates"), click("[data-act=revise]"), {"wait": 1}, O(highlight=".modal"), {"wait": 1.5}, click(".modal [data-yes]"), {"wait": 2})
step(None, "The missed income goes in like any other statement.",
     *pick("intake", "Meera Nair", AY5, "#in-ay"), *upload("#in-up", file_of(5, "missed")), *open_file("missed"), *accept())
step(None, "The updated return: two lakh sixty thousand six hundred and ninety-three of further tax, and under section 140 B an additional "
     "twenty-five percent - sixty-five thousand one hundred and seventy-three. Confirm it, sign off, and file.",
     *pick("compute", "Meera Nair", AY5, "#cc-ay"), {"wait_for": ".cc-itru"}, O(highlight=".cc-itru"), {"wait": 2},
     *sign_and_file("345678901234999", itru=True), O(highlight=".cc-hist"))

# ---- close
step("Clients and years", "Back in Clients and years, every client shows where it stands, and the pipeline counts them by stage.",
     {"goto": "/#/clients"}, {"wait_for": "#cl-kpis"}, {"select": "#cl-ay", "value": AY}, {"wait": 1.5}, O(highlight="#cl-kpis"), O(highlight="#cl-list"))
step("Guide me", "Lost on any screen? Guide me walks you through it, step by step. SimplyFile - from the client's Excel to the department's JSON, "
     "for your whole firm. Thank you for watching.", O(highlight="button:has-text('Guide me')"), {"wait": 2})

tour = {"page_key": "showcase", "title": "SimplyFile showcase", "start_url": "/#/firm", "prod_base": "https://sf.valuestream.in",
        "voice": "en-IN-NeerjaNeural", "rate": "+0%", "viewport": {"width": 1440, "height": 900},
        "blur": ["#whoami", "#userpop .head", ".fi-pw", ".fi-card:has(#fi-pan)", ".fi-hero code", ".fi-team tbody tr:first-child", ".fi-team .muted", "#c-email", "#c-phone", "#tp-email", "#fi-email", "#fi-phone"], "type_emails": True, "locale": "en-IN",
        "covers": ["firm and team", "clients", "intake and mapping", "replace", "reconcile", "234A/B/C", "244A", "ITR and 3CD JSON",
                   "filing, revise, discard", "ITR-U"], "steps": steps}
out = ROOT / "tmp" / "tour_video" / "showcase.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(tour, indent=1, ensure_ascii=False), encoding="utf-8")
import runpy  # noqa: E402
mt = runpy.run_path(str(ROOT / "tools" / "tour_video" / "make_tour.py"), run_name="x")
errs = mt["validate_tour"](tour)
print("steps", len(steps), "| files", len(FILES), "| errors", errs or "none")
