"""Showcase part 2 (C6-C15: ten more cases, then Firm analytics with 15) and part 3 (C16-C25: Import old returns, then
Firm analytics with 25) as narrated Tour Videos -> tmp/tour_video/showcase2.json, showcase3.json."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import runpy
import shutil
from pathlib import Path

ROOT = Path(_R + r"")
PACK = ROOT / "Requirements" / "Showcase - Demo CA Filing Firm"
DST = ROOT / "tools" / "tour_video" / "showcase"
FILES = {}
for folder in PACK.iterdir():
    n = folder.name.split(" ")[0]
    if folder.is_dir() and n[:1] in "CD" and n not in ("C1", "C2", "C3", "C4", "C5"):
        key = n.lower()
        (DST / key).mkdir(parents=True, exist_ok=True)
        for f in folder.iterdir():
            if f.suffix.lower() in {".xlsx", ".txt", ".json"}:
                shutil.copy2(f, DST / key / f.name)
                FILES.setdefault(key, []).append(f"showcase/{key}/{f.name}")


def file_of(key, part):
    hit = [f for f in FILES[key] if part in f.rsplit("/", 1)[-1]]
    assert len(hit) == 1, (key, part, hit)
    return hit[0]


O = lambda **a: {**a, "optional": True, "timeout": 6}   # noqa: E731
fill = lambda sel, text: {"fill": sel, "text": text}    # noqa: E731
click = lambda sel, **k: {"click": sel, **k}            # noqa: E731
AY, AY5 = "2026-27", "2025-26"


def new_client(c, extra=(), banks=(), partners=(), nri=False):
    do = [click("#cl-new"), fill(".modal #c-name", c["name"]), {"select": ".modal #c-status", "value": c["status"]}, fill(".modal #c-pan", c["pan"])]
    do += [fill(f".modal {s}", v) for s, v in extra]
    if nri:
        do.append(click(".modal #c-nri"))
    for i, b in enumerate(banks):
        do += [fill(f".modal #c-banks [data-bank]:nth-child({i + 1}) [data-f={f}]", v) for f, v in b.items()]
    for i, p in enumerate(partners):
        do.append(click(".modal #c-add-partner"))
        do += [fill(f".modal #c-partners [data-partner]:nth-child({i + 1}) [data-f={f}]", v) for f, v in p.items()]
    return do + [click(".modal [data-save]"), {"wait_for": f".cl-row:has-text('{c['name']}')"}]


def into_year(name, form, audit=False):
    do = [click(f".cl-row:has-text('{name}') [data-open]"), {"click": ".modal #y-add", "optional": True, "timeout": 3}, {"wait_for": ".modal #y-save"},
          {"select": ".modal #y-form", "value": form}]
    if audit:
        do.append(click(".modal #y-audit"))
    return do + [click(".modal #y-save"), {"wait_for": ".modal #y-save"}, {"wait": 1}, click(".modal [data-close]")]


def pick(screen, name, ay=None, sel=None):
    do = [{"goto": f"/#/{screen}"}, click(f".in-pick-row:has-text('{name}') [data-choose]")]
    if ay and ay != AY:
        do += [{"wait_for": sel}, {"select": sel, "value": ay}, {"wait": 1.5}]
    return do


def upload(button, path):
    return [click(button), {"upload": ".modal #rb-up-file", "files": [path]}, {"wait": 0.6}, click(".modal [data-save]"), {"wait": 2}]


def mapped(key, part, ay=AY, name=""):
    return [*pick("intake", name, ay, "#in-ay"), *upload("#in-up", file_of(key, part)),
            click(f".in-file[data-name*='{part}'] [data-map]"), {"wait_for": "#in-accept"}, {"wait": 1}, {"click": "#in-accept:not([disabled])", "optional": True, "timeout": 4}, {"wait": 2}]


def recon(key, name, ay=AY):
    return [*pick("recon", name, ay, "#rc-ay"), *upload("#rc-up", file_of(key, "26AS"))]


def comp(name, ay=AY):
    return [*pick("compute", name, ay, "#cc-ay"), {"wait_for": ".cc-comp"}]


def sign_and_file(ack, on=None, itru=False):
    do = [click("#cc-sign"), click(".modal [data-yes]"), {"wait_for": "#cc-file:not([disabled])"}, fill("#cc-ack", ack)]
    if on:
        do.append(fill("#cc-on", on))
    if itru:
        do.append(click("#cc-itru"))
    return do + [click("#cc-file"), click(".modal [data-yes]"), {"wait_for": ".cc-filed"}, {"wait": 1}]


def clients_page(ay=AY):
    return [{"goto": "/#/clients"}, {"wait_for": "#cl-new"}, {"select": "#cl-ay", "value": ay}, {"wait": 1.5}]


def tour(key, title, steps):
    t = {"page_key": key, "title": title, "start_url": "/#/clients", "prod_base": "https://sf.valuestream.in", "voice": "en-IN-NeerjaNeural",
         "rate": "+0%", "viewport": {"width": 1440, "height": 900}, "type_emails": True, "locale": "en-IN",
         "blur": ["#whoami", "#userpop .head", ".fi-pw", ".fi-card:has(#fi-pan)", ".fi-hero code", ".fi-team tbody tr:first-child", ".fi-team .muted",
                  "#c-email", "#c-phone", "#tp-email", "#fi-email", "#fi-phone", "#ii-email", "#ii-phone"],
         "steps": steps}
    out = ROOT / "tmp" / "tour_video" / f"{key}.json"
    out.write_text(json.dumps(t, indent=1, ensure_ascii=False), encoding="utf-8")
    errs = runpy.run_path(str(ROOT / "tools" / "tour_video" / "make_tour.py"), run_name="x")["validate_tour"](t)
    print(key, len(steps), "steps", errs or "valid")


def S(chapter, say, *do):
    return {**({"chapter": chapter} if chapter else {}), "say": say, "do": list(do), "hold": 0.6}


def bank(b, br, t, a, i):
    return [{"bank": b, "branch": br, "type": t, "account": a, "ifsc": i}]


# ===================================== part 2: ten more cases, then analytics with 15 =====================================
P2 = [S("Ten more cases", "Part two of the SimplyFile showcase: ten more situations a practice meets every season - last year's returns and how they are put right, "
        "and this year's harder cases. Every client is made up for this demo.", *clients_page())]
lak = {"name": "Lakshmi Devi", "status": "individual", "pan": "CLDPD3381F"}
P2 += [S("Case 6 - a belated return for last year", "Lakshmi Devi filed her return for assessment year 2025-26 in November 2025 - after the 31st of July due date. "
         "Choose the year first; a new client starts in the year on the screen.", *clients_page(AY5),
         *new_client(lak, [("#c-email", "lakshmi.devi@example.com"), ("#c-phone", "9866012345"), ("#c-dob", "1972-08-19"), ("#c-father", "Ranganath Rao"),
                           ("#c-address", "3-6-145, Himayatnagar, Hyderabad 500029")], bank("Union Bank of India", "Himayatnagar", "Savings", "520101234567890", "UBIN0815870"))),
       S(None, "Her statement and 26AS go in as usual.", *mapped("c6", "Income statement", AY5, lak["name"]), *recon("c6", lak["name"], AY5)),
       S(None, "Filed on the 20th of November 2025: SimplyFile calls it a belated return under section 139(4), and works out 234A and 234B to the day she filed.",
         *comp(lak["name"], AY5), O(highlight="#cc-int"), *sign_and_file("234567890123451", "2025-11-20"), O(highlight=".cc-filed"))]
sur = {"name": "Suresh Reddy", "status": "individual", "pan": "BSRPR2290K"}
P2 += [S("Case 7 - a revised return", "Suresh Reddy, a trader, filed in July 2026. Later his A I S showed fixed-deposit interest he had not reported.", *clients_page(),
         *new_client(sur, [("#c-email", "suresh.reddy@example.com"), ("#c-phone", "9849112345"), ("#c-dob", "1981-01-30"), ("#c-father", "Narayana Reddy"),
                           ("#c-address", "Plot 21, Kavuri Hills, Madhapur, Hyderabad 500081")], bank("Axis Bank", "Madhapur", "Current", "917020012345678", "UTIB0001234")),
         *mapped("c7", "as filed", AY, sur["name"]), *recon("c7", sur["name"])),
       S(None, "The original return, filed on the 25th of July 2026.", *comp(sur["name"]), *sign_and_file("678901234567801", "2026-07-25")),
       S(None, "Before the 31st of December he may revise. Start a revised return and add the missed interest as its own statement.",
         click("[data-act=revise]"), click(".modal [data-yes]"), {"wait": 2}, *mapped("c7", "FD interest missed", AY, sur["name"])),
       S(None, "Sign off and file again: a revised return under section 139(5). The original stays in the history, marked superseded.",
         *comp(sur["name"]), *sign_and_file("678901234567802"), O(highlight=".cc-hist"))]
anj = {"name": "Anjali Sharma", "status": "individual", "pan": "DASPS7712M"}
P2 += [S("Case 8 - an ITR-U that is not allowed", "Anjali Sharma filed in July 2025. After the 31st of December she found municipal tax she had never claimed.", *clients_page(AY5),
         *new_client(anj, [("#c-email", "anjali.sharma@example.com"), ("#c-phone", "9811012345"), ("#c-dob", "1985-05-05"), ("#c-father", "Rakesh Sharma"),
                           ("#c-address", "C-14, Sector 50, Noida 201301")], bank("Punjab National Bank", "Sector 50 Noida", "Savings", "0123000100123456", "PUNB0012300")),
         *mapped("c8", "as filed", AY5, anj["name"]), *recon("c8", anj["name"], AY5), *comp(anj["name"], AY5), *sign_and_file("789012345678901", "2025-07-30")),
       S(None, "Only an updated return is possible now - and an ITR-U can only raise tax. Claiming the deduction would lower it, so SimplyFile says no, and why.",
         click("[data-act=revise]"), click(".modal [data-yes]"), {"wait": 2}, *mapped("c8", "Municipal tax", AY5, anj["name"]), *comp(anj["name"], AY5),
         O(highlight=".cc-itru"), {"wait": 2}),
       S(None, "Discard the revision. The original return stands, as filed.", click("[data-act=discard]"), click(".modal [data-yes]"), {"wait": 2}, O(highlight=".cc-hist"))]
vij = {"name": "Vijay Kumar", "status": "individual", "pan": "AVKPK5520D"}
P2 += [S("Case 9 - old regime or new?", "Vijay Kumar has a business and two lakh fifty thousand of deductions under 80C, 80D and 80CCD(1B). Which regime is better?", *clients_page(),
         *new_client(vij, [("#c-email", "vijay.kumar@example.com"), ("#c-phone", "9840212345"), ("#c-dob", "1979-12-12"), ("#c-father", "Sampath Kumar"),
                           ("#c-address", "45, 2nd Cross, Jayanagar 4th Block, Bengaluru 560011")], bank("HDFC Bank", "Jayanagar", "Current", "50200011223344", "HDFC0000047")),
         *mapped("c9", "Income statement", AY, vij["name"]), *recon("c9", vij["name"])),
       S(None, "Switch the regime and both computations are there: the old regime, with the deductions, is two lakh twenty-six thousand two hundred - "
         "the new regime is one lakh twenty-four thousand eight hundred. The new regime saves him over a lakh.",
         *comp(vij["name"]), {"select": "#cc-regime", "value": "old"}, {"wait": 2}, O(highlight=".cc-comp"), {"wait": 2}, {"select": "#cc-regime", "value": "new"}, {"wait": 2},
         O(highlight=".cc-comp"))]
har = {"name": "Dr Harish Menon", "status": "individual", "pan": "AHMPM9034L"}
P2 += [S("Case 10 - surcharge above a crore", "Dr Harish Menon earns one point two crore from his practice, with a tax audit.", *clients_page(),
         *new_client(har, [("#c-email", "harish.menon@example.com"), ("#c-phone", "9847012345"), ("#c-dob", "1968-03-21"), ("#c-father", "Krishnan Menon"),
                           ("#c-address", "Menon Clinic, MG Road, Kochi 682016")], bank("Federal Bank", "MG Road Kochi", "Current", "10120200012345", "FDRL0001012")),
         *into_year(har["name"], "ITR-3", audit=True), *mapped("c10", "Income statement", AY, har["name"]), *recon("c10", har["name"])),
       S(None, "Surcharge at fifteen percent, with the marginal-relief check: tax thirty-nine lakh eighty-two thousand. TDS and four advance-tax instalments leave a small refund.",
         *comp(har["name"]), O(highlight=".cc-comp"), O(highlight=".cc-wf"))]
arj = {"name": "Arjun Pillai", "status": "individual", "pan": "BAPPP6611N"}
P2 += [S("Case 11 - a non-resident", "Arjun Pillai lives in Dubai and earns rent and N R O interest in India, taxed at thirty percent at source. Tick non-resident.", *clients_page(),
         *new_client(arj, [("#c-email", "arjun.pillai@example.com"), ("#c-phone", "9895012345"), ("#c-dob", "1983-09-09"), ("#c-father", "Gopalan Pillai"),
                           ("#c-address", "Flat 9B, Marina Heights, Dubai Marina, Dubai, UAE")], bank("South Indian Bank", "Thrissur NRI", "NRO Savings", "0123053000012345", "SIBL0000123"), nri=True),
         *mapped("c11", "Income statement", AY, arj["name"]), *recon("c11", arj["name"])),
       S(None, "A non-resident gets no rebate under 87A, so there is a little tax - nine thousand two hundred and sixty - and over two lakh of excess TDS comes back as a refund, with 244A interest.",
         *comp(arj["name"]), O(highlight=".cc-comp"), O(highlight=".cc-bal"))]
grn = {"name": "Greenfield Agritech LLP", "status": "llp", "pan": "AAKFG3307Q"}
P2 += [S("Case 12 - an LLP filing late", "Greenfield Agritech is an L L P without audit. Its due date was the 31st of August 2026; it filed on the 10th of September.", *clients_page(),
         *new_client(grn, [("#c-relation", "Rohit Varma (designated partner)"), ("#c-email", "accounts@greenfieldagri.example.com"), ("#c-phone", "9848512345"),
                           ("#c-dob", "2019-06-14"), ("#c-father", "Prasad Varma"), ("#c-signer", "AQRPV3344H"), ("#c-gst", "36AAKFG3307Q1ZP"),
                           ("#c-address", "Survey 112, Shamshabad, Rangareddy 501218")], bank("ICICI Bank", "Shamshabad", "Current", "063405001234", "ICIC0000634"),
                     [{"name": "Rohit Varma", "pan": "AQRPV3344H", "share": "60"}, {"name": "Neha Varma", "pan": "AQRPV5566J", "share": "40"}]),
         *into_year(grn["name"], "ITR-5"), *mapped("c12", "Income statement", AY, grn["name"]), *recon("c12", grn["name"])),
       S(None, "Taxed at thirty percent like a firm. Filed late, it is a belated return with 234A, B and C worked out to the filing date.",
         *comp(grn["name"]), *sign_and_file("890123456789012", "2026-09-10"), O(highlight=".cc-filed"))]
pra = {"name": "Prakash Joshi", "status": "individual", "pan": "BPJPJ4450R"}
P2 += [S("Case 13 - a home loan under the old regime", "Prakash Joshi pays three lakh fifty thousand of interest on the loan for the home he lives in.", *clients_page(),
         *new_client(pra, [("#c-email", "prakash.joshi@example.com"), ("#c-phone", "9822012345"), ("#c-dob", "1976-07-07"), ("#c-father", "Madhav Joshi"),
                           ("#c-address", "B-402, Gokul Residency, Kothrud, Pune 411038")], bank("Bank of Maharashtra", "Kothrud", "Savings", "60123456789", "MAHB0000456")),
         *mapped("c13", "Income statement", AY, pra["name"]), *recon("c13", pra["name"])),
       S(None, "Under the old regime the house-property loss is capped at two lakh. With 80C his taxable income is eight lakh fifty thousand, and tax eighty-five thousand eight hundred.",
         *comp(pra["name"]), {"select": "#cc-regime", "value": "old"}, {"wait": 2}, O(highlight=".cc-comp"))]
fat = {"name": "Fathima Begum", "status": "individual", "pan": "CFBPB2208H"}
P2 += [S("Case 14 - a mismatch nobody explained", "Fathima Begum's books claim eight thousand of TDS that her 26AS does not show.", *clients_page(),
         *new_client(fat, [("#c-email", "fathima.begum@example.com"), ("#c-phone", "9849312345"), ("#c-dob", "1990-10-10"), ("#c-father", "Abdul Rahim"),
                           ("#c-address", "18-2-45, Charminar Road, Hyderabad 500002")], bank("Canara Bank", "Charminar", "Savings", "1234101012345", "CNRB0001234")),
         *mapped("c14", "Income statement", AY, fat["name"]), *recon("c14", fat["name"]), O(highlight=".rc-f.sev-red")),
       S(None, "Left unexplained, the red keeps the year in Reconciling - the return cannot be signed off until someone looks into it.",
         *comp(fat["name"]), O(highlight=".cc-warn"))]
gop = {"name": "Gopal Krishna", "status": "individual", "pan": "AGKPK7781S"}
P2 += [S("Case 15 - undoing a wrong filing", "Gopal Krishna filed on time for assessment year 2025-26 - but the acknowledgement number was typed wrong.", *clients_page(AY5),
         *new_client(gop, [("#c-email", "gopal.krishna@example.com"), ("#c-phone", "9440012345"), ("#c-dob", "1964-04-04"), ("#c-father", "Venkata Krishna"),
                           ("#c-address", "12-1-34, Brodipet, Guntur 522002")], bank("Andhra Pragathi Grameena Bank", "Brodipet", "Savings", "91234567890", "APGB0001234")),
         *mapped("c15", "Income statement", AY5, gop["name"]), *recon("c15", gop["name"], AY5), *comp(gop["name"], AY5), *sign_and_file("901234567890000", "2025-07-20")),
       S(None, "Undo 'filed' with a reason, then file again with the right number. Nothing is deleted - both entries stay in the history.",
         click("[data-act=withdraw]"), fill(".modal #cc-why", "Acknowledgement number typed wrong - 0000 instead of 1234"), click(".modal [data-yes]"), {"wait": 2},
         *sign_and_file("901234567891234", "2025-07-20"), O(highlight=".cc-hist"))]
P2 += [S("Firm analytics - fifteen clients", "Firm analytics now shows the firm's season across all fifteen clients: returns filed and on time, tax handled, refunds secured, "
         "and the interest clients paid.", {"goto": "/#/analytics"}, {"wait_for": ".an-kpis"}, O(highlight=".an-kpis")),
       S(None, "The deadline radar lists every return still open, overdue first.", O(highlight=".an-card")),
       S(None, "And the growth opportunities: advance-tax planning for those who paid 234B and C, refunds that show too much TDS, late filers, revised returns, "
         "open mismatches - and last year's clients not yet carried into this year.", {"scroll_to": ".an-leads"}, O(highlight=".an-leads"), {"wait": 3}),
       S("Thank you", "That is part two. Part three shows how last years' returns come into SimplyFile in a minute each.", {"wait": 2})]
tour("showcase2", "SimplyFile showcase, part 2: ten more cases", P2)


# ===================================== part 3: import old returns, then analytics with 25 =====================================
def imp(fname, who=None, other=None, uncheck_now=False, ack="", on="", refused=False):
    do = [{"goto": "/#/clients"}, {"click": ".modal [data-yes]", "optional": True, "timeout": 3}, {"wait_for": "#cl-new"}, {"goto": "/#/itrimport"}, {"wait_for": "#ii-file"}, {"upload": "#ii-file", "files": [file_of("d", fname)]}, click("#ii-read"), {"wait_for": ".ii-sum"}, {"wait": 1}]
    if who == "other":
        do += [click("[name=ii-who][value=other]"), {"select": "#ii-other", "value": other}]
    if uncheck_now:
        do.append(click("#ii-now"))
    do += [O(highlight=".ii-card"), click("#ii-next"), fill("#ii-ack", ack), fill("#ii-on", on), click("#ii-go"), {"wait": 2}]
    if not refused:
        do += [{"wait_for": ".ii-done"}, O(highlight=".ii-dl")]
    return do


P3 = [S("Importing last years' returns", "Part three: a firm's history. Every client's past returns - the department's own JSON files - come into SimplyFile in a minute each. "
        "Here are ten returns from the last three years.", {"goto": "/#/itrimport"}, {"wait_for": "#ii-file"}, O(highlight=".ii-steps"))]
P3 += [S("Case 16 - matched by PAN", "Shree Ganesh Agarwal HUF's return for 2025-26. SimplyFile reads the form, the year and every figure, and finds the client with the same PAN.",
         *imp("01 ", ack="512345678901234", on="2025-10-28")),
       S("Case 17 - three years of history", "Kiran Kumar Rao's returns for 2023-24 and 2024-25 go in the same way. With this year's return, the firm now sees three years of his income.",
         *imp("02 ", ack="312345678901234", on="2023-07-24"), *imp("03 ", ack="412345678901234", on="2024-07-22")),
       S("Case 18 - a firm's ITR-5", "Sri Venkateswara Traders' ITR-5 for 2025-26 - a firm's return reads just as well.", *imp("04 ", ack="522345678901234", on="2025-10-30")),
       S("Case 19 - a new client from a return", "Lakshmi Narayana Textiles is not yet a client. Create the client straight from the return, start this year for them too - "
         "and download next year's statement with last year's figures beside every line, ready to fill.", *imp("05 ", ack="532345678901234", on="2025-07-29")),
       S("Case 20 - a client who stopped coming", "Ravi Teja filed with the firm for 2023-24 and not since. Import the return, and leave this year unstarted.",
         *imp("06 ", uncheck_now=True, ack="342345678901234", on="2023-07-26")),
       S("Case 21 - a revised return replaces the original", "Sunita Rao's original return for 2025-26, and then her revised return. The revised one takes the place of the original, "
         "which stays in the history as superseded.", *imp("07 ", uncheck_now=True, ack="552345678901234", on="2025-07-20"),
         *imp("08 ", ack="552345678909999", on="2025-11-20")),
       S("Case 22 - a belated return", "Mohammed Irfan's 2024-25 return was filed in November 2024 - the return itself says it was belated, and SimplyFile records it so.",
         *imp("09 ", uncheck_now=True, ack="462345678901234", on="2024-11-15")),
       S("Case 23 - a non-resident", "Deepa Krishnan lives in Singapore. Her return says non-resident, so her client record does too.", *imp("10 ", ack="562345678901234", on="2025-07-25")),
       S("Case 24 - the same return twice", "Importing the Agarwal return a second time is refused - nothing is recorded twice.",
         *imp("01 ", ack="512345678901234", on="2025-10-28", refused=True), O(highlight=".toast")),
       S("Case 25 - the wrong client", "And a return can never land on the wrong client: Mohammed Irfan's return, pointed at the Agarwal HUF, is refused because the PAN does not match.",
         *imp("09 ", who="other", other="Shree Ganesh Agarwal HUF", ack="462345678901234", on="2024-11-15", refused=True), O(highlight=".toast"))]
P3 += [S("Firm analytics - twenty-five clients", "Back in Firm analytics, the firm's whole history is in one place: returns on record across four assessment years.",
         {"goto": "/#/analytics"}, {"click": ".modal [data-yes]", "optional": True, "timeout": 3}, {"wait_for": ".an-kpis"}, O(highlight=".an-kpis")),
       S(None, "Year on year: clients, returns filed and income handled for each assessment year.", {"scroll_to": ".an-three"}, O(highlight=".an-three"), {"wait": 2}),
       S(None, "And new opportunities from the history: growing clients - income up by a quarter or more - who are ready for more services; "
         "shrinking clients to check in with early; and lapsed clients who filed with the firm before and could be called back.",
         {"scroll_to": ".an-leads"}, O(highlight=".an-leads"), {"wait": 3}),
       S("Thank you", "SimplyFile - from a client's past returns and this year's Excel to the department's JSON, with the whole practice in view. Thank you for watching.", {"wait": 2})]
tour("showcase3", "SimplyFile showcase, part 3: importing old returns", P3)
