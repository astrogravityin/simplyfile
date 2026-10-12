"""2026-10-11 owner (after a client demo: "the flow is not intuitive"): New filing - a guided wizard in front of My return.
The person says what they are filing, is told which documents it needs, uploads them; each is identified by the existing
readers, the client is made from them, a popup asks only what is missing or does not agree, and the documents' own hints
ask for more ("your AIS shows fund sales - upload the CAMS statement"). Then into My return at the right step.

2026-10-11 later (owner: "the start screen offers only A client and A family HUF; it must cover every filing SimplyFy supports"):
who = an individual (salaried / pensioner / investor / professional / business owner), an HUF, a partnership firm, an LLP, an
AOP / BOI - and a company and a trust shown as "not yet" (one chip switch each: wizard.settings who[].supported; the company's
path - documents, route to the firm flow - is defined already). "What kind of work" for a business: trading, manufacturing,
services, profession, farming, GST, presumptive or books, tax audit, partners' pay, stock, depreciation. A firm / LLP / AOP / BOI
goes to the firm flow (the client made from the GST certificate, the deed's partners in the popup, the books into Intake & map,
26AS / AIS into Reconcile, GSTR-3B JSON into the tax audit). Worked examples: chip wizard.cases (one per path, each a film).

Writes / updates the chips (every case worked out and checked). Re-runnable; a chip whose content is the same is left alone.
Run from D:/Simplyfile:  .venv/Scripts/python.exe tools/make_wizard_chips.py
New chips: wizard.settings, wizard.scenarios, wizard.docs, wizard.doc_need, wizard.offered, wizard.form, wizard.pan_kind,
wizard.asks, wizard.prompts, wizard.next_step, wizard.who_state, wizard.work_open, wizard.entity_sniff, wizard.constitution,
wizard.route, wizard.firm_next, wizard.cases, myreturn.sniff, ui.wizard, guide.wizard.
Changed: start.steps (the first work step is the wizard), firm.roles (the wizard's grant), edition.settings (its screen),
chat.faq (questions about it), guide.myreturn and guide.clients (a step pointing to it)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "chips"
NOTE = "2026-10-11: "
sys.path.insert(0, str(ROOT))


def run_chip(cid, args):
    from core import engine  # noqa: PLC0415
    import store  # noqa: F401,PLC0415 - registers the portal's chips
    engine.refresh()
    return engine.run(cid, args)


def write(c):
    (CH / f"{c['chip_id']}.json").write_bytes((json.dumps(c, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def same_but_version(a, b):
    a, b = dict(a), dict(b)
    for x in (a, b):
        for k in ("version", "description_nl", "test_cases"):
            x.pop(k, None)
    return a == b


def save(c, note=""):
    """Write the chip (version + 1 when its content changed), then work out / check every test case."""
    path = CH / f"{c['chip_id']}.json"
    before = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if before and same_but_version(before, c):
        print("same", c["chip_id"])
        return
    c["version"] = (before or {}).get("version", 0) + 1
    if before and note and note not in before.get("description_nl", ""):
        c["description_nl"] = before.get("description_nl", "") + " " + NOTE + note
    elif not before:
        c["description_nl"] = NOTE + note
    else:
        c["description_nl"] = before.get("description_nl", "")
    write(c)
    for t in c["test_cases"]:
        if t.get("fill"):
            t.pop("fill")
            t["expect_value"] = run_chip(c["chip_id"], t["args"])
        got = run_chip(c["chip_id"], t["args"])
        assert got == t["expect_value"], (c["chip_id"], t["args"], got, t["expect_value"])
    write(c)
    print("wrote", c["chip_id"], "v", c["version"])


def kind_of(v):
    return "text" if isinstance(v, str) else "boolean" if isinstance(v, bool) else "number" if isinstance(v, (int, float)) else "json"


def record_chip(cid, label, knobs, note, returns="record"):
    """An accessor chip that hands its knobs back as one record; its no-args test is what it answers."""
    return {"chip_id": cid, "kind": "accessor", "set": cid.split(".")[0], "label": label, "aliases": [label.lower()],
            "params": [{"name": k, "type": "long" if isinstance(v, str) and len(v) > 60 else kind_of(v), "default": v, "label": k} for k, v in knobs.items()],
            "expr": {"vop": "record", "fields": {k: f"${k}" for k in knobs}}, "returns": returns, "status": "published",
            "test_cases": [{"args": {}, "fill": True}], "_note": note}


def value_chip(cid, label, params, expr, cases, note, kind="accessor", returns="any"):
    return {"chip_id": cid, "kind": kind, "set": cid.split(".")[0], "label": label, "aliases": [label.lower()],
            "params": [{"name": n, "type": kind_of(d), "default": d, "label": lab} for n, d, lab in params],
            "expr": expr, "returns": returns, "status": "published",
            "test_cases": [{"args": a, "expect_value": e} for a, e in cases], "_note": note}


def put(c):
    note = c.pop("_note", "")
    save(c, note)


def V(op, **kw):
    return {"vop": op, **kw}


def T(op, **kw):
    return {"op": op, **kw}


def HAS(x, lst="$picked"):
    return T("in_set", value=x, set=lst)


def ALL(*items):
    return T("all", items=list(items))


def ANY(*items):
    return T("any", items=list(items))


def NOT(item):
    return T("not", item=item)


def EQ(a, b):
    return T("eq", left=a, right=b)


def NE(a, b):
    return T("ne", left=a, right=b)


def GT(a, b):
    return T("gt", left=a, right=b)


def LE(a, b):
    return T("le", left=a, right=b)


def LT(a, b):
    return T("lt", left=a, right=b)


def IF(cond, then, other=""):
    return {"vop": "choose", "cases": [{"when": cond, "then": then}], "else": other}


def CHOOSE(cases, other):
    return {"vop": "choose", "cases": [{"when": w, "then": t} for w, t in cases], "else": other}


def COUNT(x):
    return V("count", items=x)


def ids_when(pairs):
    """The ids whose condition holds, in order - a list of choose-or-blank, blanks dropped."""
    return V("compact", values=[IF(cond, i) for i, cond in pairs])


# --- the content: who, what applies, the documents --------------------------------------------------------------------------

ENT = ["firm", "llp", "aop", "company", "trust"]          # the who-cards that go to the firm flow (ITR-5 / 6 / 7)
PEOPLE = ["self", "individual", "huf"]
NOT_SAL = ["huf"] + ENT                                    # no salary, second employer or arrears

# who: status = the client status made (statuses: any of these, the PAN's 4th letter picks - an AOP or a BOI); flow = where the
# return is made (myreturn = My return, firm = Clients & years -> Intake & map -> Reconcile -> Compute & close -> Tax audit);
# supported = false shows the card as "not yet" (its note), and nothing can be started on it. Flipping a company to true (once
# clients.settings has a company status and ITR-6) is the one edit: its documents and route below are already there.
WHO = [
    {"id": "self", "status": "individual", "statuses": ["individual"], "for": "self", "flow": "myreturn", "group": "people", "supported": True,
     "art": "self", "label": "Myself", "sub": "My own return", "form": "", "note": "", "instead": ""},
    {"id": "individual", "status": "individual", "statuses": ["individual"], "for": "firm", "flow": "myreturn", "group": "people", "supported": True,
     "art": "person", "label": "An individual", "sub": "Salaried, pensioner, investor, professional or business owner", "form": "", "note": "", "instead": ""},
    {"id": "huf", "status": "huf", "statuses": ["huf"], "for": "firm", "flow": "myreturn", "group": "people", "supported": True,
     "art": "family", "label": "A family HUF", "sub": "A Hindu undivided family, signed by its Karta", "form": "", "note": "", "instead": ""},
    {"id": "firm", "status": "firm", "statuses": ["firm"], "for": "firm", "flow": "firm", "group": "business", "supported": True,
     "art": "firm", "label": "A partnership firm", "sub": "Partners and a deed - trading, making goods or services, often GST and a tax audit", "form": "ITR-5", "note": "", "instead": ""},
    {"id": "llp", "status": "llp", "statuses": ["llp"], "for": "firm", "flow": "firm", "group": "business", "supported": True,
     "art": "llp", "label": "An LLP", "sub": "A limited liability partnership - its agreement and designated partners", "form": "ITR-5", "note": "", "instead": ""},
    {"id": "aop", "status": "aop", "statuses": ["aop", "boi"], "for": "firm", "flow": "firm", "group": "business", "supported": True,
     "art": "aop", "label": "An AOP or BOI", "sub": "An association of persons or a body of individuals - a society, a joint venture", "form": "ITR-5", "note": "", "instead": ""},
    {"id": "company", "status": "company", "statuses": ["company"], "for": "firm", "flow": "firm", "group": "business", "supported": True,
     "art": "company", "label": "A company", "sub": "Private or public limited - its CIN, tax option (115BAA, 115BAB or normal with MAT), directors",
     "form": "ITR-6", "note": "", "instead": "individual"},
    {"id": "trust", "status": "trust", "statuses": ["trust"], "for": "firm", "flow": "firm", "group": "business", "supported": False,
     "art": "trust", "label": "A trust", "sub": "A charitable or religious trust or institution", "form": "ITR-7", "note": "ny_trust", "instead": "individual"},
]


def row(i, art, label, sub, sec, not_for=(), implies=(), group="income", only_for=(), excludes=()):
    return {"id": i, "group": group, "art": art, "label": label, "sub": sub, "sec": sec, "not_for": list(not_for), "only_for": list(only_for),
            "implies": list(implies), "excludes": list(excludes)}


WHAT = [
    row("salary", "salary", "Salary or pension", "From an employer, with a Form 16", "s.15-17", NOT_SAL),
    row("employers", "employers", "Changed jobs in the year", "More than one employer - a Form 16 from each", "s.192", NOT_SAL, ["salary"]),
    row("house", "house", "A house", "Lived in with a home loan, or let out on rent", "s.22-24", ENT),
    row("interest", "interest", "Interest and dividends", "Savings, deposits, dividends, a tax refund's interest", "s.56", ENT),
    row("shares", "shares", "Shares or mutual funds sold", "Equity, debt and fund units - CAMS, KFintech or a broker", "s.111A, 112, 112A", ENT),
    row("property", "property", "Sold land or a house", "The sale, the buyer's TDS, and the exemption for reinvesting", "s.50C, 54, 54EC, 54F", ENT),
    row("vda", "vda", "Crypto or other virtual assets", "Each transfer, at a flat 30%", "s.115BBH", ENT),
    row("business", "business", "A business or profession", "Consultant, freelancer, shop or trade - presumptive or own figures, with GST", "s.44AD, 44ADA, 44AE", ENT),
    row("foreign", "foreign", "Foreign income or assets", "Accounts, shares or RSUs abroad; tax paid outside India", "Schedule FA, s.90, 91", ENT),
    row("nri", "nri", "Lived outside India", "Non-resident or not ordinarily resident - the days in India decide", "s.6", ENT),
    row("arrears", "arrears", "Salary arrears of earlier years", "Relief so arrears are not taxed at this year's higher slab", "s.89, Form 10E", NOT_SAL, ["salary"]),
    row("losses", "losses", "Losses from last year", "Capital, house or business losses carried forward in last year's return", "s.70-80"),
    row("revise", "revise", "Revising, or an updated return", "Correcting a return filed, or adding income an earlier year left out", "s.139(5), 139(8A)"),
    # what kind of work - for a business, and for a person or HUF with one (it brings "A business or profession" with it)
    row("trading", "trading", "Trading", "Buying and selling goods - a shop, a wholesaler, a distributor", "Trading account", (), ["business"], "work"),
    row("manufacturing", "factory", "Manufacturing", "Making goods - raw material in, finished goods out", "Manufacturing account", (), ["business"], "work"),
    row("services", "services", "Services", "Contracts, agency, IT, repairs, transport", "s.194C, 194J", (), ["business"], "work"),
    row("profession", "profession", "A profession", "Doctor, lawyer, CA, architect, engineer, consultant", "s.44AA, 44ADA", (), ["business"], "work"),
    row("agriculture", "farm", "Farming", "Agricultural income - exempt, but it counts for the rate", "s.10(1)", (), [], "work"),
    row("gst", "gst", "Registered for GST", "A GSTIN, with GSTR-1 and GSTR-3B each month or quarter", "GST", (), ["business"], "work"),
    row("presumptive", "presumptive", "Small turnover - tax on a fixed share", "Up to 3 crore of business (mostly by bank) or 75 lakh of fees: 6-8% or 50% is the income",
        "s.44AD, 44ADA", ["llp", "aop", "company", "trust"], ["business"], "work", (), ["books", "audit"]),
    row("books", "books", "Full books of account", "Profit and loss and a balance sheet - from Tally or the accountant", "s.44AA", (), ["business"], "work", (), ["presumptive"]),
    row("audit", "audit", "Tax audit", "Turnover above 1 crore (10 crore mostly by bank), or 50 lakh of fees - Form 3CD", "s.44AB, Form 3CA / 3CB-3CD",
        (), ["business", "books"], "work", (), ["presumptive"]),
    row("partners_pay", "partners", "Partners' salary and interest", "Remuneration and interest on capital, within the deed and the limits", "s.40(b)",
        (), [], "work", ["firm", "llp"]),
    row("stock", "stock", "Stock and inventory", "Opening and closing stock, valued at cost or market", "s.145A, Form 3CD cl.14", (), ["business"], "work"),
    row("depreciation", "machine", "Machines, vehicles, buildings", "Depreciation by block of assets", "s.32", (), ["business"], "work"),
]
MR, FF, BOTH = ["myreturn"], ["firm"], ["myreturn", "firm"]


def doc(i, kind, req, opt, label, what, where, flows=BOTH):
    return {"id": i, "kind": kind, "flows": flows, "required_for": req, "optional_for": opt, "label": label, "what": what, "where": where}


DOCS = [
    doc("ais", "ais", ["any"], [], "AIS - Annual Information Statement",
        "Everything reported on the PAN: salary, interest, dividends, sales of shares, funds and property, tax paid.",
        "incometax.gov.in > Services > Annual Information Statement (AIS) > download the PDF. Its password: the PAN in small letters and the date of birth (DDMMYYYY).", MR),
    doc("ais_e", "ais", [], ["any"], "AIS of the business (CSV)", "Receipts, interest and TDS reported on the business's PAN - set beside the books in Reconcile.",
        "incometax.gov.in (signed in as the business) > Services > Annual Information Statement (AIS) > download as CSV.", FF),
    doc("26as", "26as", ["any"], [], "Form 26AS", "Every TDS and TCS credited to the PAN, and the tax paid - as the department holds it.",
        "incometax.gov.in > e-File > Income Tax Returns > View Form 26AS > TRACES > Export as text (or PDF)."),
    doc("prefill", "prefill", [], ["any"], "Pre-filled JSON", "Who you are, salary, TDS, taxes paid and bank accounts in one file - the quickest start.",
        "incometax.gov.in > e-File > Income Tax Returns > Download Pre-Filled Data > AY {ay}.", MR),
    doc("form16", "form16", ["salary", "employers", "arrears"], [], "Form 16 from each employer",
        "Part A: TDS by quarter (from TRACES). Part B: salary, exempt allowances and deductions.", "Your employer's HR or payroll portal - due by 15 June.", MR),
    doc("cg", "cg", ["shares"], [], "Capital-gains statement", "Each sale: units, dates, cost, sale value and the 31 January 2018 value.",
        "CAMS (camsonline.com) or KFintech (kfintech.com) > Capital gains statement for FY {fy}; your broker's back office > Tax P&L.", MR),
    doc("sale_deed", "", ["property"], [], "Sale deed and purchase papers",
        "Sale price, stamp-duty value, the buyer's PAN and TDS, what the property cost, a new house or bonds bought.",
        "The registered deed from the sub-registrar; the buyer's Form 16B for the TDS. Entered on Review.", MR),
    doc("home_loan", "", [], ["house"], "Home-loan interest certificate; rent received",
        "Interest paid (s.24(b)), principal (80C), and for a house let out the rent and municipal tax.", "Your lender's portal or branch; the rent agreement. Entered on Review.", MR),
    doc("bank", "bank", [], ["business", "interest", "firm", "llp", "aop"], "Bank statement", "Receipts with no TDS, cash deposits, interest the AIS may not show.",
        "Net banking > Statements > the financial year, as Excel, CSV or PDF."),
    doc("gst", "gst", [], ["gst"], "GSTR-3B summary", "The GST turnover per GSTIN - set beside the receipts.",
        "gst.gov.in > Services > Returns > View filed returns > GSTR-3B for each month (or the year's summary).", MR),
    doc("vda_report", "", ["vda"], [], "Your exchange's tax report", "Each crypto transfer: what it cost, what it sold for, the dates.",
        "The exchange's tax or P&L report. Entered on Review.", MR),
    doc("foreign_docs", "", ["foreign"], [], "Foreign account and holding statements",
        "Peak and closing balance, income and tax paid abroad - for the calendar year {cy}.",
        "The foreign bank, broker or employer's stock plan. Entered on Review (Schedule FA); Form 67 for the credit.", MR),
    doc("travel", "", ["nri"], [], "Days in India", "Days in India this year and the years before decide residence.",
        "Passport stamps or the immigration record. Entered on Review.", MR),
    doc("form10e", "", ["arrears"], [], "Arrears by year (Form 10E)", "Which years the arrears belong to, and each year's income.",
        "Your employer; Form 10E is filed on incometax.gov.in before the return.", MR),
    doc("filed_prev", "filed_prev", ["losses"], ["revise"], "Last year's return (JSON)", "Its Schedule CFL - the losses still to carry forward.",
        "incometax.gov.in > e-File > Income Tax Returns > View Filed Returns > the year before > Download JSON.", MR),
    doc("filed", "filed", ["revise"], [], "The return being revised (JSON)", "Compared figure by figure with the one you are making now.",
        "incometax.gov.in > e-File > Income Tax Returns > View Filed Returns > AY {ay} > Download JSON.", MR),
    doc("proofs", "", [], ["salary", "house", "interest", "self"], "Deduction proofs",
        "80C (PPF, ELSS, LIC, tuition), 80D health cover, NPS, donations - old regime only, except the employer's NPS.", "Each provider's statement. Entered on Review.", MR),
    # the firm flow: a partnership firm, an LLP, an AOP / BOI (and a company or a trust, once they are open)
    doc("gst_cert", "gst_cert", ["gst"], ["firm", "llp", "aop", "company"], "GST registration certificate (REG-06)",
        "The GSTIN, the legal name and the constitution - the client is made from it.",
        "gst.gov.in > Services > User Services > View / Download Certificates.", FF),
    doc("deed", "deed", ["firm", "llp", "partners_pay", "trust"], ["aop"], "Partnership deed, LLP agreement or trust deed",
        "Who the partners (or members) are, their shares, and the salary and interest the deed allows (s.40(b)).",
        "The firm's own signed copy; for an LLP the agreement filed with the MCA (Form 3).", FF),
    doc("books", "books", ["books", "audit", "company"], ["firm", "llp", "aop", "trust"], "Financial statements or trial balance (Excel)",
        "Trading or manufacturing account, profit and loss, balance sheet - each row tagged in Intake & map.",
        "Tally > Display > Statements of accounts > export to Excel; or the accountant's final accounts.", FF),
    doc("gst_json", "gst_json", [], ["gst"], "GSTR-3B and GSTR-1 (JSON)", "Each month's returns from the GST portal - the tax audit sets them against the books.",
        "gst.gov.in > Returns > View e-filed returns > Download JSON for each month (or the zip of them).", FF),
    doc("stock_list", "", ["stock"], [], "Closing stock list and valuation", "Quantity and value of raw material, work in progress and finished goods on 31 March.",
        "The stock register; tagged with the books in Intake & map.", FF),
    doc("asset_register", "", ["depreciation"], [], "Fixed-asset register", "Each block's opening value, additions (with dates), sales and depreciation.",
        "A sheet in the books' Excel - tagged in Intake & map (Form 3CD clause 18).", FF),
    doc("itr_prev", "itr_prev", ["losses"], ["firm", "llp", "aop", "company"], "Last year's return (ITR-5 JSON)",
        "Last year's figures and losses - brought in on Import old returns.",
        "incometax.gov.in (signed in as the business) > e-File > Income Tax Returns > View Filed Returns > Download JSON.", FF),
    doc("coi", "coi", ["company"], [], "Certificate of incorporation", "The CIN, the date of incorporation and the directors - the company is made from it.",
        "MCA21 > View company master data / public documents; the company's own copy.", FF),
    doc("comp_income", "books", ["company"], [], "Computation of income (Excel)", "The CA's computation - with the Form 29B book-profit rows for MAT.",
        "The tax working for the year, exported to Excel - tagged in Intake & map.", FF),
    doc("asset_schedule", "books", ["company"], [], "Fixed-asset schedule (Excel)", "Each block's opening value, additions (the 180-day split), sales and depreciation.",
        "The depreciation schedule as per the Income-tax Rules - tagged in Intake & map.", FF),
]
ASKS = [   # what the popup may ask - its input and where the answer goes (client / return / the wizard itself)
    {"id": "pan_pick", "input": "choice", "to": "wizard"},
    {"id": "pan", "input": "pan", "to": "client"},
    {"id": "status", "input": "choice", "to": "wizard"},
    {"id": "name", "input": "text", "to": "client"},
    {"id": "huf_name", "input": "text", "to": "client"},
    {"id": "dob", "input": "date", "to": "client"},
    {"id": "karta_name", "input": "text", "to": "return"},
    {"id": "karta_pan", "input": "pan", "to": "return"},
    {"id": "residence", "input": "choice", "to": "return"},
    {"id": "partners", "input": "partners", "to": "client"},
    {"id": "gstin", "input": "gstin", "to": "client"},
    {"id": "company", "input": "company", "to": "client"},
]
PROMPTS = [   # what a document implies - upload this kind, or enter it at that My return step / firm screen
    {"id": "form16_more", "kind": "form16", "step": "gather", "screen": "myreturn"},
    {"id": "cams", "kind": "cg", "step": "gather", "screen": "myreturn"},
    {"id": "property", "kind": "", "step": "review", "screen": "myreturn"},
    {"id": "vda", "kind": "", "step": "review", "screen": "myreturn"},
    {"id": "business", "kind": "", "step": "check", "screen": "myreturn"},
    {"id": "gst", "kind": "gst", "step": "gather", "screen": "myreturn"},
    {"id": "last_itr", "kind": "filed_prev", "step": "gather", "screen": "myreturn"},
    {"id": "foreign", "kind": "", "step": "review", "screen": "myreturn"},
    {"id": "arrears", "kind": "", "step": "review", "screen": "myreturn"},
    {"id": "books", "kind": "books", "step": "", "screen": "intake"},
    {"id": "gst_json", "kind": "gst_json", "step": "", "screen": "audit"},
    {"id": "deed", "kind": "deed", "step": "", "screen": "clients"},
    {"id": "stock", "kind": "", "step": "", "screen": "intake"},
    {"id": "dep", "kind": "", "step": "", "screen": "intake"},
    {"id": "itr_prev", "kind": "", "step": "", "screen": "itrimport"},
    {"id": "audit_3cd", "kind": "", "step": "", "screen": "audit"},
]


def chips():
    put(record_chip("wizard.settings", "New filing: the wizard's steps, who a return may be for, its limits, the popup's fields and the prompts", {
        "steps": ["what", "docs", "upload", "review"],
        "who": WHO,
        "files_max": 30,
        "sessions_max": 30,
        "asks": ASKS,
        "prompts": PROMPTS,
        "kept_kinds": ["prefill", "ais", "26as", "form16", "cg", "gst", "bank", "filed", "filed_prev"],
        "typed_kinds": [""],
        "self_mode": "self",
        "firm_mode": "firm",
        "firm_flow": "firm",
        "work_kinds": [r["id"] for r in WHAT if r["group"] == "work"],
        "firm_kinds": ["gst_cert", "deed", "books", "gst_json", "itr_prev"],
        "partners_max": 20,
    }, "the wizard's own knobs - steps, who (Myself for a self-filer's desk; an individual, an HUF, a partnership firm, an LLP, an AOP / BOI for a "
       "firm; a company and a trust shown as not yet - supported false is the one switch), at most 30 files and 30 open filings, the popup's "
       "fields (which input, where the answer goes) and the prompts (upload a kind, or enter it at a My return step or a firm screen)."))
    put(record_chip("wizard.scenarios", "New filing: what may apply to a return - in plain words, the section small", {"rows": WHAT},
                    "every card on 'What applies this year?' and 'What kind of work?' - its words (the list IS the content, as myreturn.checklist), "
                    "the section beneath, who it is not (or only) for (an HUF has no salary, partners' pay only a firm or an LLP), what it brings "
                    "with it (a second employer means salary, a tax audit means books) and what it rules out (presumptive or books)."))
    put(record_chip("wizard.docs", "New filing: the documents each kind of return needs - what each is, and where to get it", {"rows": DOCS},
                    "the checklist of 'Documents you'll need': each document's reader kind (blank = typed later), the flows it belongs to (My return, "
                    "the firm flow), the picks and who it is needed or good to have for ('any' = every return), what it is and where to get it "
                    "({ay} {fy} {cy} filled from the year)."))
    put(value_chip("wizard.doc_need", "New filing: is a document needed, good to have, or not asked for these picks",
                   [("required_for", [], "picks it is needed for (any = every return)"), ("optional_for", [], "picks it is good to have for"),
                    ("picked", [], "what was picked, and who"), ("flows", BOTH, "the flows it belongs to"), ("flow", "myreturn", "this return's flow")],
                   CHOOSE([(NOT(HAS("$flow", "$flows")), ""),
                           (ANY(HAS("any", "$required_for"), LT(COUNT(V("missing", want="$required_for", have="$picked")), COUNT("$required_for"))), "required"),
                           (ANY(HAS("any", "$optional_for"), LT(COUNT(V("missing", want="$optional_for", have="$picked")), COUNT("$optional_for"))), "optional")], ""),
                   [({"required_for": ["any"], "optional_for": [], "picked": []}, "required"),
                    ({"required_for": ["salary", "employers"], "optional_for": [], "picked": ["house", "salary"]}, "required"),
                    ({"required_for": ["salary"], "optional_for": ["house"], "picked": ["house"]}, "optional"),
                    ({"required_for": ["shares"], "optional_for": [], "picked": ["salary"]}, ""),
                    ({"required_for": [], "optional_for": ["any"], "picked": []}, "optional"),
                    ({"required_for": ["salary"], "optional_for": [], "picked": ["salary"], "flows": ["myreturn"], "flow": "firm"}, ""),
                    ({"required_for": ["gst"], "optional_for": ["firm"], "picked": ["trading", "firm"], "flows": ["firm"], "flow": "firm"}, "optional"),
                    ({"required_for": ["gst"], "optional_for": ["firm"], "picked": ["gst", "firm"], "flows": ["firm"], "flow": "firm"}, "required")],
                   "a document of another flow is not shown (a Form 16 for a firm); else it is needed when a pick it is needed for was made (or it "
                   "is needed for every return), else good to have the same way, else not shown."))
    put(value_chip("wizard.offered", "New filing: is a card offered to this person / for this return",
                   [("who", "", "who the return is for, or the person's mode (self / firm)"), ("not_for", [], "never for these"),
                    ("only_for", [], "only for these (empty = anyone)")],
                   ALL(NOT(HAS("$who", "$not_for")), ANY(EQ(COUNT("$only_for"), 0), HAS("$who", "$only_for"))),
                   [({"who": "huf", "not_for": ["huf"], "only_for": []}, False), ({"who": "individual", "not_for": ["huf"], "only_for": []}, True),
                    ({"who": "self", "not_for": [], "only_for": ["self"]}, True), ({"who": "firm", "not_for": [], "only_for": ["self"]}, False),
                    ({"who": "firm", "not_for": [], "only_for": []}, True), ({"who": "aop", "not_for": [], "only_for": ["firm", "llp"]}, False),
                    ({"who": "llp", "not_for": ["llp", "aop"], "only_for": []}, False)],
                   "an HUF is offered no salary, second employer or arrears; Myself only on a self-filer's desk, everyone else only in a firm; "
                   "partners' pay only for a firm or an LLP; presumptive taxation not for an LLP or an AOP.",
                   kind="predicate", returns="boolean"))
    put(value_chip("wizard.who_state", "New filing: is a who-card open, or shown as not yet",
                   [("supported", True, "the card's switch (wizard.settings who[].supported)"), ("status_known", True, "clients.settings has its status")],
                   CHOOSE([(ALL(EQ("$supported", True), EQ("$status_known", True)), "open")], "not_yet"),
                   [({"supported": True, "status_known": True}, "open"), ({"supported": False, "status_known": True}, "not_yet"),
                    ({"supported": True, "status_known": False}, "not_yet"), ({"supported": False, "status_known": False}, "not_yet")],
                   "a card opens only when it is switched on AND the client register knows its status (a company needs clients.settings' company "
                   "status and ITR-6): switched on too early, it still says not yet - never a dead end."))
    put(value_chip("wizard.work_open", "New filing: does 'What kind of work?' show",
                   [("flow", "myreturn", "the return's flow"), ("picked", [], "what was picked")],
                   ANY(EQ("$flow", "firm"), HAS("business")),
                   [({"flow": "firm", "picked": []}, True), ({"flow": "myreturn", "picked": ["salary"]}, False),
                    ({"flow": "myreturn", "picked": ["business", "salary"]}, True)],
                   "always for a business (the firm flow); for a person or an HUF once 'A business or profession' is picked.",
                   kind="predicate", returns="boolean"))
    biz = ANY(HAS("business"), HAS("trading"), HAS("manufacturing"), HAS("services"), HAS("profession"))
    put(value_chip("wizard.form", "New filing: the form the picks point to, and why - from myreturn.form, or the business's form",
                   [("picked", [], "what applies"), ("who", "individual", "who the return is for"), ("flow", "myreturn", "the return's flow"),
                    ("entity_form", "ITR-5", "the business's form (wizard.settings who[].form)")],
                   CHOOSE([(EQ("$flow", "firm"), V("record", fields={"form": "$entity_form", "why": CHOOSE([(HAS("audit"), "why_e_audit"), (HAS("presumptive"), "why_e_44ad")], "why_e_books"),
                                                                     "from": "wizard"}))],
                          {"chip": "myreturn.form", "args": {"resident": NOT(HAS("nri")), "houses": IF(HAS("house"), 1, 0),
                                                             "other_cg": ANY(HAS("shares"), HAS("property")), "foreign": HAS("foreign"),
                                                             "loss_cf": HAS("losses"), "business": biz, "huf": EQ("$who", "huf"),
                                                             "special": HAS("vda"), "books": ANY(HAS("books"), HAS("audit")), "over_limit": HAS("audit"),
                                                             "agri": IF(HAS("agriculture"), 100000, 0)}}),
                   [({"picked": ["salary"], "who": "individual"}, {"form": "ITR-1", "why": "why_simple"}),
                    ({"picked": ["salary", "shares"], "who": "individual"}, {"form": "ITR-2", "why": "why_cg"}),
                    ({"picked": ["interest", "shares"], "who": "huf"}, {"form": "ITR-2", "why": "why_cg"}), ({"picked": ["interest"], "who": "huf"}, {"form": "ITR-2", "why": "why_huf"}),
                    ({"picked": ["business"], "who": "self"}, {"form": "ITR-4", "why": "why_presumptive"}),
                    ({"picked": ["business", "shares"], "who": "individual"}, {"form": "ITR-3", "why": "why_biz_more"}),
                    ({"picked": ["salary", "nri"], "who": "individual"}, {"form": "ITR-2", "why": "why_nonres"}),
                    ({"picked": ["vda"], "who": "individual"}, {"form": "ITR-2", "why": "why_special"}),
                    ({"picked": ["trading", "business", "presumptive", "gst"], "who": "individual"}, {"form": "ITR-4", "why": "why_presumptive"}),
                    ({"picked": ["trading", "business", "books"], "who": "individual"}, {"form": "ITR-3", "why": "why_biz_books"}),
                    ({"picked": ["profession", "business", "books", "audit"], "who": "individual"}, {"form": "ITR-3", "why": "why_biz_limit"}),
                    ({"picked": ["trading", "gst", "books", "audit"], "who": "firm", "flow": "firm", "entity_form": "ITR-5"}, {"form": "ITR-5", "why": "why_e_audit", "from": "wizard"}),
                    ({"picked": ["trading", "presumptive"], "who": "firm", "flow": "firm", "entity_form": "ITR-5"}, {"form": "ITR-5", "why": "why_e_44ad", "from": "wizard"}),
                    ({"picked": ["services", "books"], "who": "llp", "flow": "firm", "entity_form": "ITR-5"}, {"form": "ITR-5", "why": "why_e_books", "from": "wizard"}),
                    ({"picked": [], "who": "company", "flow": "firm", "entity_form": "ITR-6"}, {"form": "ITR-6", "why": "why_e_books", "from": "wizard"})],
                   "no second form engine: a person's or an HUF's picks become myreturn.form's facts (a house = one house, shares or a property "
                   "sale = a capital gain, NRI = not resident, the kind of work = a business, books or a tax audit = ITR-3 ...); a business has "
                   "its card's form (ITR-5) with the reason - a tax audit, presumptive, or the books.", returns="record"))
    put(value_chip("wizard.pan_kind", "New filing: does a PAN fit the return chosen (its 4th letter: P a person, H an HUF, F a firm or LLP ...)",
                   [("pan", "", "the PAN"), ("letter", "", "its 4th letter"), ("wants", [], "the letters the chosen return takes"),
                    ("found_status", "", "the status a GST certificate's constitution names"), ("want_statuses", [], "the statuses the chosen card takes")],
                   CHOOSE([(EQ("$pan", ""), "none"), (NOT({"chip": "clients.shape_ok", "args": {"kind": "pan", "value": "$pan"}}), "bad"),
                           (NOT(HAS("$letter", "$wants")), "clash"),
                           (ALL(NE("$found_status", ""), NOT(HAS("$found_status", "$want_statuses"))), "clash")], "ok"),
                   [({"pan": "", "letter": "", "wants": ["P"]}, "none"), ({"pan": "ZZDP1", "letter": "P", "wants": ["P"]}, "bad"),
                    ({"pan": "ZZDHW0046M", "letter": "H", "wants": ["P"]}, "clash"), ({"pan": "ZZDPR0047N", "letter": "P", "wants": ["P"]}, "ok"),
                    ({"pan": "ZZDAR0059L", "letter": "A", "wants": ["A", "B"]}, "ok"),
                    ({"pan": "ZZDFP0058K", "letter": "F", "wants": ["F"], "found_status": "llp", "want_statuses": ["firm"]}, "clash"),
                    ({"pan": "ZZDFP0058K", "letter": "F", "wants": ["F"], "found_status": "llp", "want_statuses": ["llp"]}, "ok")],
                   "a PAN's 4th letter says whose it is (clients.settings statuses pan_letter) - an AOP card takes A or B; a GST certificate's "
                   "constitution (a partnership firm or an LLP share the letter F) must fit the card too. One that does not is asked about."))
    base = {"client": False, "files": 1, "pans": 1, "name": "X", "dob": "2000-01-01", "who": "individual", "karta_name": "", "karta_pan": "",
            "clash": False, "nri": False, "resident": "", "partners_need": False, "gstin_need": False, "company_need": False}
    put(value_chip("wizard.asks", "New filing: what the popup asks - only what the documents did not give, or gave two ways",
                   [(k, v, k) for k, v in base.items()],
                   ids_when([("pan_pick", ALL(NOT("$client"), GT("$pans", 1))),
                             ("pan", ALL(NOT("$client"), GT("$files", 0), EQ("$pans", 0))),
                             ("status", EQ("$clash", True)),
                             ("name", ALL(NOT("$client"), GT("$files", 0), LE("$pans", 1), EQ("$name", ""), NE("$who", "huf"))),
                             ("huf_name", ALL(NOT("$client"), GT("$files", 0), LE("$pans", 1), EQ("$name", ""), EQ("$who", "huf"))),
                             ("dob", ALL(GT("$files", 0), HAS("$who", ["self", "individual"]), EQ("$dob", ""))),
                             ("karta_name", ALL(GT("$files", 0), EQ("$who", "huf"), EQ("$karta_name", ""))),
                             ("karta_pan", ALL(GT("$files", 0), EQ("$who", "huf"), EQ("$karta_pan", ""))),
                             ("residence", ALL(EQ("$nri", True), EQ("$resident", ""))),
                             ("partners", ALL(GT("$files", 0), EQ("$partners_need", True))),
                             ("gstin", ALL(GT("$files", 0), EQ("$gstin_need", True))),
                             ("company", ALL(GT("$files", 0), EQ("$company_need", True)))]),
                   [(base, []),
                    (base | {"pans": 0, "name": "", "dob": ""}, ["pan", "name", "dob"]),
                    (base | {"pans": 2}, ["pan_pick"]),
                    (base | {"name": "", "dob": ""}, ["name", "dob"]),
                    (base | {"client": True, "name": "", "who": "huf", "dob": ""}, ["karta_name", "karta_pan"]),
                    (base | {"name": "", "who": "huf", "dob": ""}, ["huf_name", "karta_name", "karta_pan"]),
                    (base | {"clash": True}, ["status"]),
                    (base | {"nri": True}, ["residence"]),
                    (base | {"files": 0, "pans": 0, "name": "", "dob": ""}, []),
                    (base | {"client": True, "who": "self", "dob": ""}, ["dob"]),
                    (base | {"who": "firm", "dob": "", "partners_need": True}, ["partners"]),
                    (base | {"who": "llp", "dob": "", "name": "", "partners_need": True, "gstin_need": True}, ["name", "partners", "gstin"]),
                    (base | {"who": "aop", "dob": "", "files": 0, "partners_need": True}, []),
                    (base | {"who": "company", "dob": "", "company_need": True}, ["company"])],
                   "the popup's questions: two PANs found (whose return?), none found, a PAN (or a GST certificate's constitution) that is not the "
                   "return chosen, no name, an HUF's name and Karta, a date of birth (it opens a locked AIS and decides the senior limits), "
                   "residence when NRI was picked, a business's partners or members (filled in from its deed), its GSTIN when GST was picked and no "
                   "document gave one, a company's CIN, incorporation, tax option, manufacturing and directors (filled in from its certificate of "
                   "incorporation) - nothing before a document is in.", returns="list"))
    pbase = {"sales": 0, "cg_docs": 0, "ia": 0, "property_rows": 0, "tans_missing": 0, "vda_seen": 0, "vda_rows": 0, "fees": 0, "business": False,
             "gst_docs": 0, "losses": False, "prev_docs": 0, "foreign": False, "fa_rows": 0, "arrears": False, "arrear_rows": 0,
             "flow": "myreturn", "books_docs": 0, "gst_pick": False, "gst_json_docs": 0, "has_partners": False, "deed_docs": 0, "stock_pick": False,
             "dep_pick": False, "prev5_docs": 0, "audit_pick": False}
    firm = EQ("$flow", "firm")
    put(value_chip("wizard.prompts", "New filing: what the documents imply - further documents or figures to give",
                   [(k, v, k) for k, v in pbase.items()],
                   ids_when([("form16_more", GT("$tans_missing", 0)),
                             ("cams", ALL(GT("$sales", 0), EQ("$cg_docs", 0))),
                             ("property", ALL(GT("$ia", 0), EQ("$property_rows", 0))),
                             ("vda", ALL(GT("$vda_seen", 0), EQ("$vda_rows", 0))),
                             ("business", ALL(GT("$fees", 0), NOT("$business"), NOT(firm))),
                             ("gst", ALL(EQ("$business", True), EQ("$gst_docs", 0), NOT(firm))),
                             ("last_itr", ALL(EQ("$losses", True), EQ("$prev_docs", 0))),
                             ("foreign", ALL(EQ("$foreign", True), EQ("$fa_rows", 0))),
                             ("arrears", ALL(EQ("$arrears", True), EQ("$arrear_rows", 0))),
                             ("books", ALL(firm, EQ("$books_docs", 0))),
                             ("gst_json", ALL(firm, EQ("$gst_pick", True), EQ("$gst_json_docs", 0))),
                             ("deed", ALL(firm, EQ("$has_partners", True), EQ("$deed_docs", 0))),
                             ("stock", ALL(firm, EQ("$stock_pick", True))),
                             ("dep", ALL(firm, EQ("$dep_pick", True))),
                             ("itr_prev", ALL(firm, GT("$prev5_docs", 0))),
                             ("audit_3cd", ALL(firm, EQ("$audit_pick", True)))]),
                   [(pbase, []),
                    (pbase | {"sales": 320000}, ["cams"]), (pbase | {"sales": 320000, "cg_docs": 1}, []),
                    (pbase | {"ia": 1}, ["property"]), (pbase | {"ia": 1, "property_rows": 1}, []),
                    (pbase | {"tans_missing": 1}, ["form16_more"]),
                    (pbase | {"vda_seen": 90000}, ["vda"]),
                    (pbase | {"fees": 1500000}, ["business"]), (pbase | {"fees": 1500000, "business": True}, ["gst"]),
                    (pbase | {"losses": True}, ["last_itr"]), (pbase | {"foreign": True, "arrears": True}, ["foreign", "arrears"]),
                    (pbase | {"flow": "firm", "fees": 900000}, ["books"]),
                    (pbase | {"flow": "firm", "books_docs": 1, "gst_pick": True, "has_partners": True}, ["gst_json", "deed"]),
                    (pbase | {"flow": "firm", "books_docs": 2, "gst_pick": True, "gst_json_docs": 12, "has_partners": True, "deed_docs": 1, "stock_pick": True,
                              "dep_pick": True, "prev5_docs": 1, "audit_pick": True}, ["stock", "dep", "itr_prev", "audit_3cd"])],
                   "AIS fund or share sales with no capital-gains statement; 194IA TDS (26AS / AIS) with no property sale entered; a salary TAN "
                   "with no Form 16; 194S crypto with no transfer entered; 194J / 194C fees with no business; a business with no GSTR-3B; losses "
                   "picked with no last year's return; foreign or arrears picked with nothing entered. A business (the firm flow): no books yet, "
                   "GST with no GSTR-3B JSON, partners with no deed, stock and depreciation to tag, last year's ITR-5 to import, the tax audit's "
                   "Form 3CD to work through.", returns="list"))
    put(value_chip("wizard.next_step", "New filing: the My return step to open at the end",
                   [("required_missing", 0, "needed documents not in"), ("typed", 0, "prompts to enter on Review"), ("red", 0, "red checks")],
                   CHOOSE([(GT("$required_missing", 0), "gather"), (GT("$typed", 0), "review"), (GT("$red", 0), "check")], "choose"),
                   [({"required_missing": 1, "typed": 1, "red": 1}, "gather"), ({"required_missing": 0, "typed": 2, "red": 1}, "review"),
                    ({"required_missing": 0, "typed": 0, "red": 1}, "check"), ({"required_missing": 0, "typed": 0, "red": 0}, "choose")],
                   "never a dead end: a needed document still missing opens Gather, figures to type open Review, a red check opens Check, else "
                   "Choose (the two regimes)."))
    put(value_chip("wizard.biz_kind", "New filing: the business kind My return starts with, from the kind of work picked",
                   [("picked", [], "what was picked")],
                   CHOOSE([(ALL(HAS("profession"), ANY(HAS("books"), HAS("audit"))), "profession"), (ANY(HAS("books"), HAS("audit")), "business"),
                           (HAS("profession"), "44ADA"), (ANY(HAS("presumptive"), HAS("trading"), HAS("manufacturing"), HAS("services")), "44AD")], ""),
                   [({"picked": ["profession", "presumptive", "business"]}, "44ADA"), ({"picked": ["trading", "gst", "presumptive", "business"]}, "44AD"),
                    ({"picked": ["trading", "books", "business"]}, "business"), ({"picked": ["profession", "audit", "books", "business"]}, "profession"),
                    ({"picked": ["business"]}, ""), ({"picked": ["salary"]}, "")],
                   "a person's or an HUF's kind of work becomes My return's business kind (myreturn.settings biz_kinds) once the client is "
                   "known and none is set: a profession on the presumptive basis 44ADA, a trade or service 44AD, full books or a tax audit "
                   "their own profit and loss (profession / business, ITR-3); just 'a business' leaves it to choose on Check."))
    put(value_chip("wizard.firm_next", "New filing: the firm-flow screen to open at the end (a firm, an LLP, an AOP / BOI)",
                   [("books", 0, "books files in Intake & map"), ("untagged", 0, "rows with no SF Ref yet"), ("portal", 0, "26AS / AIS / TIS in Reconcile"),
                    ("audit", False, "a tax audit was picked")],
                   CHOOSE([(EQ("$books", 0), "intake"), (GT("$untagged", 0), "intake"), (EQ("$portal", 0), "recon"), (EQ("$audit", True), "audit")], "compute"),
                   [({"books": 0, "untagged": 0, "portal": 1, "audit": True}, "intake"), ({"books": 2, "untagged": 14, "portal": 1, "audit": True}, "intake"),
                    ({"books": 2, "untagged": 0, "portal": 0, "audit": True}, "recon"), ({"books": 2, "untagged": 0, "portal": 1, "audit": True}, "audit"),
                    ({"books": 2, "untagged": 0, "portal": 1, "audit": False}, "compute")],
                   "the firm flow in the order the work happens: no books, or rows still to tag -> Intake & map; no 26AS / AIS -> Reconcile; a tax "
                   "audit -> Tax audit; else Compute & close. Never a dead end."))
    put(record_chip("wizard.entity_sniff", "New filing: what a business's document is, and who it names - read from its text", {
        "kinds": [
            {"id": "gst_cert", "words": ["form gst reg-06", "registration certificate"], "all": True},
            {"id": "coi", "words": ["certificate of incorporation"], "all": True},
            {"id": "deed", "words": ["deed of partnership", "partnership deed", "limited liability partnership agreement", "llp agreement",
                                     "agreement of association", "trust deed", "memorandum of association"], "all": False},
            {"id": "books", "words": ["profit and loss", "balance sheet", "trial balance", "total income statement", "manufacturing account",
                                      "trading account"], "all": False},
        ],
        "gstin": r"\b(\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z])\b",
        "gstin_pan_from": 2, "gstin_pan_to": 12,
        "legal_name": [r"Legal Name(?: of Business)?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9 .&'()/-]{2,120}?)\s*(?:\n|$|Trade Name)"],
        "constitution": r"Constitution of Business\s*[:\-]?\s*([A-Za-z ]{3,60}?)\s*(?:\n|$|Address)",
        "deed_name": [r"(?:M/s\.?|firm name\s*[:\-])\s*([A-Z][A-Za-z0-9 .&'-]{2,100}?)\s*(?:\(|,|\n|$)",
                      r"(?:LLP|association|trust) (?:name|known as)\s*[:\-]?\s*([A-Z][A-Za-z0-9 .&'-]{2,100}?)\s*(?:\(|,|\n|$)"],
        "partner": r"(?:Partner|Member|Trustee)\s*\d+\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,80}?),\s*PAN\s*([A-Z]{5}\d{4}[A-Z]),\s*(?:profit )?share\s*(\d{1,3}(?:\.\d+)?)\s*%",
        "pan": [r"\bPAN\s*(?:of the (?:firm|assessee|LLP|company))?\s*[:\-]?\s*([A-Z]{5}\d{4}[A-Z])\b"],
        "book_name": r"\A\s*([A-Z][A-Z0-9 .&'()-]{2,100}?)\s*\n",
        "cin": r"\b([LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})\b",
        "coi_name": [r"certify that\s+([A-Z][A-Za-z0-9 .&'()-]{2,120}?)\s+is incorporated"],
        "incorporated": r"Date of incorporation\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})",
        "director": r"Director\s*\d+\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,80}?),\s*DIN\s*(\d{8}),\s*PAN\s*([A-Z]{5}\d{4}[A-Z])",
        "itr_roots": {"ITR5": "ITR-5", "ITR6": "ITR-6", "ITR7": "ITR-7"},
        "head_chars": 8000,
    }, "the new filing wizard's identification of a business's papers: a GST certificate (REG-06 - GSTIN, legal name, constitution of "
       "business; the PAN is the GSTIN's 3rd-12th characters), a partnership deed / LLP agreement / trust deed (the firm's name, each "
       "partner's name, PAN and share), the books (trading / manufacturing account, P&L, balance sheet - the name on the first line, the "
       "PAN after 'PAN :'), a certificate of incorporation (the CIN, the company's name, the date, each director's name, DIN and PAN), last "
       "year's ITR-5 / 6 / 7 JSON. A GSTR-3B / GSTR-1 JSON is the tax audit's reader (audit.read_gst); 26AS, AIS and "
       "a bank statement My return's readers."))
    CONST = [{"pattern": r"(?i)limited liability partnership|\bLLP\b", "name": "llp"}, {"pattern": r"(?i)partnership", "name": "firm"},
             {"pattern": r"(?i)association of persons|society|club", "name": "aop"}, {"pattern": r"(?i)body of individuals", "name": "boi"},
             {"pattern": r"(?i)(private|public) limited company|company", "name": "company"}, {"pattern": r"(?i)trust", "name": "trust"},
             {"pattern": r"(?i)hindu undivided family", "name": "huf"}, {"pattern": r"(?i)proprietorship", "name": "individual"}]
    put(value_chip("wizard.constitution", "New filing: the client status a GST certificate's 'Constitution of Business' names",
                   [("text", "", "the constitution, as the certificate says it"), ("rows", CONST, "pattern -> status, the first that matches")],
                   V("first_matching", text="$text", rows="$rows", pattern_field="pattern", value_field="name", default=""),
                   [({"text": "Partnership"}, "firm"), ({"text": "Limited Liability Partnership"}, "llp"), ({"text": "Society/ Club/ Trust/ AOP"}, "aop"),
                    ({"text": "Private Limited Company"}, "company"), ({"text": "Proprietorship"}, "individual"), ({"text": "Something else"}, "")],
                   "the GST portal's constitution words -> the client status (an LLP before a partnership, a society or club an AOP); none matching "
                   "= nothing said, and the card's own status stands."))
    put(record_chip("wizard.route", "New filing: where each read document goes in the firm flow", {
        "dest": {"coi": "client", "books": "intake", "bank": "intake", "26as": "recon", "ais": "recon", "tis": "recon", "gst_json": "gst", "gst_cert": "client",
                 "deed": "client", "itr_prev": "keep", "gst": "keep", "filed": "keep", "filed_prev": "keep", "prefill": "keep", "form16": "keep", "cg": "keep"},
        "dest_default": "keep",
        "screen": {"intake": "intake", "recon": "recon", "gst": "audit", "client": "clients", "keep": ""},
    }, "the firm flow's readers: the books and a bank statement into Intake & map (each row tagged), 26AS / AIS / TIS into Reconcile, GSTR-3B / "
       "GSTR-1 JSON into the tax audit's GST check, the GST certificate and the deed onto the client itself; last year's ITR-5 is kept here "
       "and brought in on Import old returns (it needs the acknowledgement number)."))


# --- the worked examples (one per path) - the demo seed plays each through the wizard; each is a film -------------------------

def case(i, who, title, line, folder, batches, picks, client, form, opens, says, ay="2026-27", answers=None):
    return {"id": i, "who": who, "ay": ay, "title": title, "line": line, "folder": folder, "batches": batches, "picks": picks,
            "client": client, "form": form, "opens": opens, "answers": answers or {}, "say": says, "film": f"sf-case-{i.replace('_', '-')}"}


CASES = [
    case("salaried", "individual", "Salaried, one employer - ITR-1",
         "Priya Demo Salaried: her pre-filled JSON, one Form 16 and the 26AS - the client made from them, nothing asked, ITR-1.",
         "case-salaried", [["1 Pre-filled JSON - ZZDPS0052D - AY 2026-27.json", "2 Form 16 - Demo Retail - AY 2026-27.pdf", "3 26AS - ZZDPS0052D - AY 2026-27.txt",
                            "4 AIS - ZZDPS0052D - FY 2025-26.csv"]],
         ["salary", "interest"], "PRIYA DEMO SALARIED", "ITR-1", "myreturn",
         {"intro": "A salaried client with one employer: start a new filing, pick An individual, and let the documents do the typing.",
          "what": "Salary from one employer, and some bank interest - two cards. The likely form says ITR-1, with its reason.",
          "upload": "Her pre-filled JSON, the Form 16 and the 26AS, dropped in together. Each is read for what it is.",
          "client": "The pre-filled JSON names her - PAN, name, date of birth - so the client is made and nothing is asked.",
          "review": "Review: what was understood, nothing missing - one button into My return, at the right step."}),
    case("two_jobs", "individual", "Two employers in the year",
         "Arun Demo Twojobs changed jobs: the 26AS shows a second employer's TAN, the wizard asks for that Form 16.",
         "case-two-jobs", [["1 26AS - ZZDPT0053E - AY 2026-27.txt", "2 Form 16 - Demo Foods - AY 2026-27.pdf"], ["3 Form 16 - Demo Logistics - AY 2026-27.pdf", "4 AIS - ZZDPT0053E - FY 2025-26.csv"]],
         ["employers"], "ARUN DEMO TWOJOBS", "ITR-1", "myreturn",
         {"intro": "A client who changed jobs in the year - two employers, two Form 16s.",
          "what": "Changed jobs in the year brings Salary with it. The form follows: still ITR-1.",
          "upload": "The 26AS and the first Form 16 go in. The 26AS names him, and shows two employers' TANs.",
          "client": "The client is made from the 26AS. The popup asks only his date of birth.",
          "hints": "The second employer's TAN has no Form 16 here - the hint says so. Its Form 16 goes in, and the hint is gone.",
          "review": "Both Form 16s in, nothing missing - into My return, where the two employers' standard deduction is checked."},
         answers={"dob": "1990-07-21"}),
    case("salary_cg_property", "individual", "Salary, funds sold and a plot sold",
         "Ravi Demo Salaried: two employers, a fund sale the AIS shows, a plot sold with 194IA TDS - CAMS and the deed figures asked for. ITR-2.",
         "wizard-sal", [["1 Form 16 - Demo Analytics - AY 2026-27.pdf", "2 AIS - ZZDPR0047N - FY 2025-26.pdf"],
                        ["3 26AS - ZZDPR0047N - AY 2026-27.txt", "4 Form 16 - Demo Cloud Services - AY 2026-27.pdf", "5 CAMS capital gains - ZZDPR0047N - FY 2025-26.pdf"]],
         ["employers", "shares", "property"], "Ravi Demo Salaried", "ITR-2", "myreturn",
         {"intro": "Salary, mutual funds sold and a plot sold - the documents point to everything else.",
          "what": "Two employers, shares or funds sold, land sold - the form becomes ITR-2, for the capital gains.",
          "upload": "His Form 16 and the AIS go in first. The Form 16 names his PAN but not his name, and the AIS is locked.",
          "client": "The popup asks his name and date of birth. With the date, the locked AIS opens by itself.",
          "hints": "The AIS shows fund sales - upload the CAMS statement. The 26AS shows 194IA TDS on a plot - enter the sale. Another employer's TAN - its Form 16.",
          "review": "Every needed document in; the plot's sale figures wait in My return's Review."},
         answers={"name": "Ravi Demo Salaried", "dob": "1986-02-11"}),
    case("pensioner", "individual", "A pensioner with interest",
         "Savitri Demo Pensioner, 69: a bank pension, deposit interest - the senior-citizen limits from her date of birth. ITR-1.",
         "case-pensioner", [["1 Form 16 - Demo Bank pension - AY 2026-27.pdf", "2 26AS - ZZDPP0054F - AY 2026-27.txt", "3 AIS - ZZDPP0054F - FY 2025-26.csv"]],
         ["salary", "interest"], "SAVITRI DEMO PENSIONER", "ITR-1", "myreturn",
         {"intro": "A retired client: a pension from the bank and interest on deposits.",
          "what": "A pension is salary - pick Salary or pension, and Interest and dividends. ITR-1.",
          "upload": "The pension Form 16, the 26AS and the AIS - all three read.",
          "client": "The client is made from the 26AS; her date of birth is asked once - it decides the senior-citizen limits and 80TTB.",
          "review": "Into My return: the interest under 80TTB, the senior slab in the old regime, both regimes compared."},
         answers={"dob": "1956-08-14"}),
    case("consultant", "individual", "A consultant on 44ADA",
         "Neha Demo Consultant: fees with 194J TDS and a bank statement - presumptive income at 50%, ITR-4.",
         "case-consultant", [["1 Pre-filled JSON - ZZDPN0055G - AY 2026-27.json", "2 Bank statement - Demo Bank - Neha - FY 2025-26.csv",
                              "3 26AS - ZZDPN0055G - AY 2026-27.txt", "4 AIS - ZZDPN0055G - FY 2025-26.csv"]],
         ["profession", "presumptive"], "NEHA DEMO CONSULTANT", "ITR-4", "myreturn",
         {"intro": "A consultant with no employer: fees from clients, with TDS under 194J.",
          "what": "A business or profession, then the kind of work: a profession, on the presumptive basis - section 44ADA, half the fees as income. ITR-4.",
          "upload": "Her pre-filled JSON and the bank statement. The 194J fees and the receipts are read.",
          "client": "The pre-filled JSON names her - the client is made, nothing asked.",
          "review": "Into My return: the fees, 50% as income, the bank receipts set beside them."}),
    case("trader", "individual", "A small trader on 44AD, with GST",
         "Ramu Demo Kirana runs a shop: his GSTR-3B summary and bank statement - 6% of digital turnover as income, ITR-4.",
         "case-trader", [["1 Pre-filled JSON - ZZDPK0056H - AY 2026-27.json", "2 GSTR-3B summary - ZZDPK0056H - FY 2025-26.csv", "3 Bank statement - Demo Bank - Ramu - FY 2025-26.csv",
                          "4 26AS - ZZDPK0056H - AY 2026-27.txt", "5 AIS - ZZDPK0056H - FY 2025-26.csv"]],
         ["trading", "gst", "presumptive"], "RAMU DEMO KIRANA", "ITR-4", "myreturn",
         {"intro": "A shopkeeper with a GST number and a small turnover.",
          "what": "Trading, registered for GST, and the small-turnover card - section 44AD. ITR-4 follows.",
          "upload": "The pre-filled JSON, the GSTR-3B summary and the bank statement.",
          "client": "The client is made from the pre-filled JSON.",
          "review": "Into My return: the GST turnover beside the receipts, 6% and 8% of each part as income."}),
    case("huf", "huf", "An HUF with a house and capital gains",
         "Demo Verma HUF: deposits, a let-out flat and a fund sale; the 26AS names the HUF, the popup asks for the Karta. ITR-2.",
         "wizard-huf", [["1 26AS - ZZDHW0046M - AY 2026-27.txt", "2 AIS - ZZDHW0046M - FY 2025-26.csv"], ["3 CAMS capital gains - ZZDHW0046M - FY 2025-26.pdf"]],
         ["house", "interest", "shares"], "DEMO VERMA HUF", "ITR-2", "myreturn",
         {"intro": "A Hindu undivided family: deposits, a flat let out, and mutual funds sold.",
          "what": "A family HUF - no salary cards for it. A house, interest, shares or funds sold: ITR-2.",
          "upload": "The 26AS and the AIS go in; the 26AS names the HUF, its PAN's fourth letter is H.",
          "client": "The client is made. The popup asks only for the Karta - name and PAN.",
          "hints": "The AIS shows a fund sale - upload the CAMS statement. In it goes; the hint is answered.",
          "review": "Into My return for the HUF: the rent, the fund sale and the deposits - signed by the Karta."},
         answers={"karta_name": "Mohan Demo Verma", "karta_pan": "ZZDPV0046K"}),
    case("firm_trading", "firm", "A trading firm with GST and a tax audit",
         "Demo Balaji Traders: its GST certificate makes the client, the deed's partners fill the popup, the books go to Intake & map, 26AS to Reconcile, GSTR-3B to the tax audit. ITR-5 with 3CD.",
         "case-firm-trading", [["1 GST certificate - Demo Balaji Traders.pdf", "2 Partnership deed - Demo Balaji Traders.pdf"],
                               ["3 26AS - ZZDFB0057J - AY 2026-27.txt", "4 Demo Balaji Traders - Trading, P&L and Balance Sheet AY 2026-27.xlsx",
                                "5 Demo Balaji Traders - IT Stmt, Dep, Loans AY 2026-27.xlsx", "6 GSTR-3B - 36ZZDFB0057J1Z3 - FY 2025-26.zip",
                                "7 ITR-5 AY 2025-26 - Demo Balaji Traders - ZZDFB0057J.json"]],
         ["trading", "gst", "audit", "partners_pay", "stock", "depreciation"], "DEMO BALAJI TRADERS", "ITR-5", "audit",
         {"intro": "A partnership firm that trades, with a GST number and a turnover that needs a tax audit.",
          "what": "A partnership firm, then the kind of work: trading, GST, a tax audit, partners' salary and interest, stock, depreciation. ITR-5, with Form 3CD.",
          "upload": "The GST certificate and the partnership deed first. The certificate gives the GSTIN, the legal name and the constitution.",
          "client": "The client is made from the certificate - a partnership firm, its GSTIN on it. The popup shows the deed's partners and shares, to confirm.",
          "hints": "Then the 26AS, the books, the GSTR-3B returns and last year's ITR-5. Each goes where the firm's work happens: the books to Intake & map, the 26AS to Reconcile, the GST returns to the tax audit.",
          "review": "Review: the books came with their SF Refs and the 26AS is in, so the next screen is the Tax audit - Form 3CD by risk, then Compute & close."}),
    case("firm_mfg", "firm", "A manufacturing firm with stock and depreciation",
         "Lakshmi Narayana Textiles, already a client: its GST certificate finds it; the manufacturing account, stock and depreciation go to Intake & map. ITR-5 with 3CD.",
         "case-firm-mfg", [["1 GST certificate - Lakshmi Narayana Textiles.pdf", "2 Partnership deed - Lakshmi Narayana Textiles.pdf"],
                           ["3 26AS - AAGFL5512K - AY 2026-27.txt", "4 Lakshmi Narayana Textiles - Manufacturing, P&L and Balance Sheet AY 2026-27.xlsx",
                            "5 GSTR-3B - 36AAGFL5512K1Z2 - FY 2025-26.zip"]],
         ["manufacturing", "gst", "audit", "stock", "depreciation"], "Lakshmi Narayana Textiles", "ITR-5", "audit",
         {"intro": "A firm that makes cloth: raw material in, finished goods out, machines that depreciate.",
          "what": "Manufacturing, GST, a tax audit, stock and inventory, machines - the documents list follows from them.",
          "upload": "The GST certificate names a firm already in the register - the documents go to its return.",
          "client": "Lakshmi Narayana Textiles is found by its PAN. Its partners come from the deed, confirmed in the popup.",
          "hints": "The manufacturing account goes to Intake & map. Closing stock and the depreciation schedule are tagged there.",
          "review": "This year's filing, which waited in Collecting, now has its books, 26AS and GST returns - on to the Tax audit."}),
    case("llp_services", "llp", "An LLP in services",
         "Demo Pixel Works LLP: an IT services LLP - its GST certificate says Limited Liability Partnership; fees with 194J in the 26AS. ITR-5.",
         "case-llp", [["1 GST certificate - Demo Pixel Works LLP.pdf", "2 LLP agreement - Demo Pixel Works LLP.pdf"],
                      ["3 26AS - ZZDFP0058K - AY 2026-27.txt", "4 Demo Pixel Works LLP - Income statement AY 2026-27.xlsx"]],
         ["services", "gst", "books"], "DEMO PIXEL WORKS LLP", "ITR-5", "compute",
         {"intro": "A limited liability partnership selling IT services.",
          "what": "An LLP: services, GST, full books. No presumptive card - an LLP cannot use 44AD. ITR-5.",
          "upload": "The GST certificate and the LLP agreement. The constitution says Limited Liability Partnership - it fits the card.",
          "client": "The client is made as an LLP; the designated partners come from the agreement.",
          "hints": "Then the 26AS - clients' fees with 194J TDS - and the income statement.",
          "review": "No tax audit, the books tagged, the 26AS in - straight on to Compute & close, with the fees set against the 26AS."}),
    case("aop", "aop", "An association of persons",
         "Demo Residents Welfare Association: an AOP (its PAN's 4th letter A) - interest on deposits, members from its agreement. ITR-5.",
         "case-aop", [["1 Agreement of association - Demo Residents Welfare Association.pdf", "2 26AS - ZZDAR0059L - AY 2026-27.txt",
                       "3 Demo Residents Welfare Association - Income statement AY 2026-27.xlsx"]],
         ["services", "books"], "DEMO RESIDENTS WELFARE ASSOCIATION", "ITR-5", "compute",
         {"intro": "A residents' welfare association - an association of persons.",
          "what": "An AOP or BOI: the PAN's fourth letter decides which. Services and books. ITR-5.",
          "upload": "The agreement of association, the 26AS and the income statement.",
          "client": "The 26AS names the association; its PAN says AOP. The members come from the agreement.",
          "review": "On to Compute & close - the AOP's tax worked out at its own rates."}),
    case("company_trading", "company", "A trading company on 115BAA",
         "Zenith Demo Traders Private Limited: its certificate of incorporation makes the client (CIN, date, directors), the popup takes the "
         "option - 115BAA, 22% with no MAT - the final accounts, computation and asset schedule go to Intake & map. ITR-6.",
         "case-company-trading", [["00 Certificate of incorporation - Zenith Demo Traders.pdf", "00 GST certificate - Zenith Demo Traders.pdf"],
                                  ["01 Final accounts - Zenith Demo Traders FY 2025-26.xlsx", "02 Computation of income - Zenith Demo Traders AY 2026-27.xlsx",
                                   "03 Fixed asset schedule - Zenith Demo Traders FY 2025-26.xlsx", "04 26AS - ZZDCZ0061K - AY 2026-27.txt"]],
         ["trading", "gst", "audit", "stock", "depreciation"], "ZENITH DEMO TRADERS PRIVATE LIMITED", "ITR-6", "audit",
         {"intro": "A private limited company that trades - its return is ITR-6.",
          "what": "A company, then the kind of work: trading, GST, a tax audit, stock, depreciation. ITR-6, with Form 3CD.",
          "upload": "The certificate of incorporation and the GST certificate first: the CIN, the date, the directors, the GSTIN.",
          "client": "The popup shows what the certificate said, and asks the tax option - section 115BAA, 22% with no MAT - and whether it manufactures. Saved: the company is made.",
          "hints": "Then the final accounts, the computation of income, the fixed-asset schedule and the 26AS - into Intake & map and Reconcile.",
          "review": "Review, then the Tax audit; Compute & close works out the 115BAA tax and fills the ITR-6."},
         answers={"company": {"option": "115BAA", "manufacturing": "no"}}),
    case("company_mfg", "company", "A manufacturing company with MAT",
         "Kaveri Demo Fabricators Private Limited: normal provisions, losses brought forward, so MAT under 115JB is the tax - its "
         "certificate makes the client, its books go to Intake & map. ITR-6.",
         "case-company-mfg", [["00 Certificate of incorporation - Kaveri Demo Fabricators.pdf"],
                              ["01 Final accounts - Kaveri Demo Fabricators FY 2025-26.xlsx", "02 Computation of income - Kaveri Demo Fabricators AY 2026-27.xlsx",
                               "03 Fixed asset schedule - Kaveri Demo Fabricators FY 2025-26.xlsx", "04 26AS - ZZDCK0062L - AY 2026-27.txt"]],
         ["manufacturing", "audit", "stock", "depreciation"], "KAVERI DEMO FABRICATORS PRIVATE LIMITED", "ITR-6", "audit",
         {"intro": "A private limited company that makes things - normal provisions, so the minimum alternate tax may be the tax.",
          "what": "A company: manufacturing, a tax audit, stock, machines that depreciate. ITR-6, with Form 3CD.",
          "upload": "The certificate of incorporation: the CIN, the date of incorporation and both directors.",
          "client": "The popup takes the option - normal provisions - and ticks that it manufactures, for the additional depreciation. Saved: the company is made.",
          "hints": "The final accounts, the computation with the book-profit rows for MAT, the asset schedule and the 26AS go in.",
          "review": "Review, then the Tax audit; Compute & close sets the normal tax against MAT under 115JB - MAT is the tax this year, and a credit for later."},
         answers={"company": {"option": "normal", "manufacturing": "yes"}}),
    case("nri", "individual", "A non-resident with Indian income",
         "Kiran Demo Abroad lives outside India: NRO interest and rent from a flat - residence asked in the popup. ITR-2.",
         "case-nri", [["1 26AS - ZZDPA0060M - AY 2026-27.txt", "2 AIS - ZZDPA0060M - FY 2025-26.csv"]],
         ["nri", "interest", "house"], "KIRAN DEMO ABROAD", "ITR-2", "myreturn",
         {"intro": "A client who lives abroad, with income in India.",
          "what": "Lived outside India, interest, a house let out. Not resident: ITR-1 is not for him - ITR-2.",
          "upload": "The 26AS and the AIS - interest on the NRO account, rent from the tenant.",
          "client": "The client is made from the 26AS. The popup asks his date of birth, and whether he was resident.",
          "review": "Into My return: the days in India decide residence; the rent and interest at the non-resident's rates."},
         answers={"dob": "1984-03-09", "residence": "no"}),
    case("updated_return", "individual", "An updated return (ITR-U)",
         "Meena Demo Updated left out deposit interest last year: the return she filed and the AIS for AY 2025-26 - the updated return under 139(8A).",
         "case-itru", [["1 ITR-1 AY 2025-26 filed - ZZDPU0061N.json", "2 AIS - ZZDPU0061N - FY 2024-25.csv", "3 26AS - ZZDPU0061N - AY 2025-26.txt",
                         "4 Form 16 - Demo Insurance Brokers - AY 2025-26.pdf"]],
         ["salary", "revise", "interest"], "MEENA DEMO UPDATED", "ITR-1", "myreturn",
         {"intro": "Income left out of last year's return - an updated return, with the additional tax.",
          "what": "The assessment year is last year. Salary, interest, and Revising, or an updated return - the return filed is needed.",
          "upload": "The return she filed, as JSON, that year's AIS and 26AS, and her Form 16: the deposit interest she missed is in the AIS.",
          "client": "The filed return names her - the client is made, nothing asked.",
          "review": "Into My return for AY 2025-26: every figure set beside the return filed, the updated return's extra tax worked out."},
         ay="2025-26"),
]


def cases_chip():
    put(record_chip("wizard.cases", "New filing: the worked examples - one per path, each with its documents and its film", {
        "rows": CASES, "folder_root": "tools/tour_video/showcase", "film_dir": "static/showcase", "film_ext": ".mp4",
    }, "every path the wizard takes, worked through with made-up documents (ZZ... PANs, @demo.example, Demo ... names): who, the AY, what "
       "was picked, the documents in upload order (each batch, then the popup's answers), the client it makes or finds, the form, where "
       "it opens - and the narration of its film (tours/sf-case-<id>.json, tools/make_case_tours.py). The demo seed plays each through "
       "the wizard (tools/showcase/pre_cases.py), so every case is there after the nightly reset."))
    put(record_chip("showcase.case_films", "Landing page: the worked examples' films - their group in Watch", {
        "group": {"id": "cases", "title": "Every filing, step by step",
                  "line": "One worked example for each kind of return - a salaried ITR-1 to a company's ITR-6 with Form 3CD - from the first card to the return."},
        "tags": ["new filing", "worked example"], "topics": ["new filing"], "before": "screens",
        "play_counts": {"Clients": "36", "In review": "8", "Tax audits": "7"}, "play_sub_from": "\d+ clients", "play_sub_to": "36 clients",
        "play_try": "Carry on any of New filing's 15 worked examples - from a salaried ITR-1 to a company's ITR-6 with Form 3CD",
    }, "the Watch section's group for New filing's worked examples (chip wizard.cases, one film each; tools/showcase/case_films.py "
       "writes the chapters into showcase.page, before the screen tours, and leaves every other group as it is) - and Try it live's counts "
       "(36 clients, 8 in review, 7 tax audits once the worked examples and the two companies are in the demo) with one more thing to try."))


UI = {
    "title": "New filing", "eyebrow": "Guided filing",
    "lede": "Say who the return is for, see the documents it needs, drop them in - {product} reads each one, makes the client and asks only for what is missing.",
    "s_what": "What you're filing", "s_docs": "Documents", "s_upload": "Upload", "s_review": "Review",
    "start_h": "What are you filing today?", "start_cta": "Start a new filing",
    "start_p": "Pick who the return is for. Four short steps: nothing is filed for you, and you see every figure before the department's JSON is made.",
    "start_points": "Tell it what applies - in plain words|See the documents and where to get each|Drop them in - the client is made from them|Open the return at the right step",
    "who_people": "People", "who_business": "Businesses", "start_ay": "Assessment year",
    "ny_tag": "Not yet", "ny_h": "{label} - not in New filing yet",
    "ny_company": "A company's return (ITR-6) is made from Clients & years for now - add the company there, then Intake & map. The guided way in comes next; a director's own return starts here.",
    "ny_trust": "Trust returns (ITR-7) are not in {product} yet. Meanwhile file the trustees' or the settlor's own returns here.",
    "ny_instead": "Start an individual's return instead", "ny_clients": "Back to Clients & years", "ny_close": "Close",
    "examples_h": "Worked examples", "examples_p": "One for each kind of return - watch it start to finish, with made-up documents.",
    "watch": "Watch how", "watch_n": "{n} {n:example|examples}", "watch_h": "Watch how: {label}", "watch_none": "No film for this yet.",
    "watch_play": "Play", "watch_form": "Form", "watch_opens": "Opens", "case_film": "Film",
    "resume_h": "Carry on where you left off", "resume_row": "{n} {n:document|documents} · last touched {when}", "resume_open": "Carry on",
    "resume_none": "Nothing waiting - every filing you started is finished or discarded.",
    "discard": "Discard", "discard_title": "Discard this filing?",
    "discard_body": "The wizard's progress is dropped. The client and every document already in its return stay where they are.",
    "who_h": "Who is this return for?", "what_h": "What applies this year?",
    "what_p": "Pick everything that fits - you can change it later. Not sure? Upload the documents: they say what else applies.",
    "work_h": "What kind of work?", "work_p": "The business in plain words - it decides the documents, the form and whether a tax audit and Form 3CD are needed.",
    "not_for": "Not for {who}", "picked_n": "{n} picked",
    "form_h": "Likely form", "form_note": "The documents' amounts settle it in My return - 112A gains up to 1.25 lakh still fit ITR-1, for one.",
    "form_note_firm": "A business files ITR-5 from its books; the tax audit's Form 3CD goes with it when the turnover needs one.",
    "why_e_audit": "{form} with a tax audit: Form 3CA or 3CB with 3CD - the audit report by 30 September, the return by 31 October.",
    "why_e_44ad": "{form} with the income on the presumptive basis (44AD / 44ADA) - no full books below the limits.",
    "why_e_books": "{form} from the books: trading or manufacturing account, profit and loss and the balance sheet, tagged in Intake & map.",
    "ay": "Assessment year", "go_docs": "See the documents", "go_upload": "Upload the documents", "go_review": "Review", "back": "Back",
    "docs_h": "Documents you'll need", "docs_p": "From what you picked. Each says what it is and where to get it; what you type in waits for later.",
    "g_required": "Needed", "g_optional": "Good to have", "g_typed": "Typed in later",
    "where": "Where to get it", "have_n": "{n} in", "missing": "Not in yet", "typed_tag": "Type in",
    "up_h": "Drop every document in",
    "up_p": "PDF, JSON, CSV, Excel or a zip - several at once. Each is identified by what it is, never by its file name.",
    "drop": "Drop documents here, or browse", "drop_hint": "Form 16, AIS, 26AS, pre-filled JSON, CAMS or KFintech, GSTR-3B, last year's ITR",
    "drop_hint_firm": "GST certificate, partnership deed or LLP agreement, books in Excel, 26AS, AIS, GSTR-3B JSON, last year's ITR-5",
    "pw": "Password of a locked PDF (if it is not PAN + date of birth)", "pw_ph": "Leave blank for the usual one",
    "reading": "Reading {name}", "read_n": "{n} {n:document|documents} read",
    "cards_h": "What each document said", "cards_none": "Nothing uploaded yet - the cards appear here as each file is read.",
    "st_in": "Read - in the return", "st_held": "Read - waits for the client", "st_other": "Not recognised", "st_other_pan": "Another person's",
    "st_locked": "Locked", "st_kept": "Read - kept here", "st_already": "Already there",
    "to_intake": "Into Intake & map", "to_recon": "Into Reconcile", "to_gst": "Into the tax audit's GST check", "to_client": "Onto the client",
    "to_keep": "Kept with this filing", "to_myreturn": "Into My return",
    "other_p": "Not a document {product} reads. It is kept here, not added to the return - remove it, or upload the right one.",
    "other_pan_p": "This names PAN {pan}, not {mine} - it was not added to this return.",
    "locked_p": "Locked: type its password above and upload it again - or give the date of birth when asked, and it is opened again.",
    "already_p": "The same file is there already - nothing added twice.",
    "remove": "Remove", "remove_title": "Remove this document?",
    "remove_body": "It comes out of this filing and out of the return. The file itself is kept in History.",
    "f_pan": "PAN", "f_name": "Name", "f_ay": "AY", "f_kind": "Read as", "f_gstin": "GSTIN", "f_constitution": "Constitution", "f_partners": "Partners",
    "f_sheets": "Sheets", "f_periods": "GST returns", "f_rows": "Rows", "f_entries": "Entries", "f_form": "Form",
    "client_h": "The client", "client_wait": "Not known yet - the first document with a PAN makes the client.",
    "client_new": "Made from the documents", "client_found": "Already in your register - the documents go to their return",
    "client_self": "Your own profile", "client_partners": "{n} {n:partner|partners}",
    "prompts_h": "The documents point to more", "prompts_none": "Nothing more implied so far.",
    "pr_upload": "Upload it", "pr_enter": "Enter it in My return", "pr_open": "Open {screen}",
    "pr_form16_more": "TAN {tans} paid salary and has no Form 16 here - upload that employer's Form 16.",
    "pr_cams": "The AIS shows {amount} of share or mutual-fund sales - upload the CAMS / KFintech (or broker) capital-gains statement.",
    "pr_property": "26AS shows TDS under section 194IA on a property sale of {amount} - enter the sale (deed figures, cost, any exemption) in My return.",
    "pr_vda": "The AIS shows {amount} of crypto sold (194S) - enter each transfer in My return.",
    "pr_business": "{amount} of fees came with TDS under {sections} - add the business or profession.",
    "pr_gst": "A business: upload the GSTR-3B summary, so the GST turnover sits beside the receipts.",
    "pr_last_itr": "Losses from last year: upload last year's ITR JSON - its Schedule CFL is read.",
    "pr_foreign": "Foreign income or assets: enter each account and holding in My return (Schedule FA).",
    "pr_arrears": "Salary arrears: enter each earlier year's arrears in My return - the relief is worked out.",
    "pr_books": "No books yet: upload the financial statements or the trial balance in Excel - each row is tagged in Intake & map.",
    "pr_gst_json": "Registered for GST: upload the GSTR-3B (and GSTR-1) JSON - the tax audit sets the GST turnover against the books.",
    "pr_deed": "Partners: upload the partnership deed or LLP agreement - the partners, their shares and the pay it allows (s.40(b)).",
    "pr_stock": "Stock: the closing stock and its valuation are tagged with the books in Intake & map (Form 3CD clause 14).",
    "pr_dep": "Depreciation: tag the fixed-asset sheet in Intake & map - the blocks, additions and rates (s.32, Form 3CD clause 18).",
    "pr_itr_prev": "Last year's ITR-5 is here: bring it in on Import old returns with its acknowledgement number - it becomes last year's figures.",
    "pr_audit_3cd": "A tax audit: the Tax audit screen walks Form 3CD by risk, with the GST check and this year against last.",
    "scr_intake": "Intake & map", "scr_recon": "Reconcile", "scr_audit": "Tax audit", "scr_compute": "Compute & close", "scr_itrimport": "Import old returns",
    "scr_clients": "Clients & years", "scr_myreturn": "My return",
    "ask_h": "A few details the documents did not give", "ask_eyebrow": "Only what is missing",
    "ask_p": "Everything else came from the documents. Change any of it later on the client or in its return.",
    "ask_save": "Save and carry on", "ask_later": "Later",
    "a_pan_pick": "Whose return is this?", "a_pan_pick_hint": "The documents name more than one PAN.",
    "a_pan": "PAN", "a_pan_hint": "No document named one. The 4th letter is P for a person, H for an HUF, F for a firm or LLP, A for an AOP.",
    "a_status": "This PAN is not the return chosen", "a_status_hint": "The documents say {kind} (PAN {pan}) - you chose {chosen}.",
    "a_status_switch": "File it as {kind}",
    "a_name": "Name, as on the PAN", "a_huf_name": "The HUF's name", "a_huf_name_hint": "As on its PAN - for example, Demo Verma HUF.",
    "a_dob": "Date of birth", "a_dob_hint": "It opens a locked AIS (PAN + date of birth) and decides the senior-citizen limits.",
    "a_karta_name": "Karta's name", "a_karta_pan": "Karta's PAN", "a_karta_pan_hint": "An individual's PAN - its 4th letter is P.",
    "a_residence": "Resident in India in FY {fy}?", "res_yes": "Resident", "res_no": "Not resident", "res_later": "Work it out from the days",
    "a_partners": "Partners or members", "a_partners_hint": "Name, PAN and profit share of each - as the deed says. Filled in from the deed when one is in.",
    "a_p_name": "Name", "a_p_pan": "PAN", "a_p_share": "Share %", "a_p_add": "Add a partner", "a_p_remove": "Remove this partner",
    "a_company": "The company", "a_company_hint": "From its certificate of incorporation - check them; the rest (shareholders, the option's Form 10-IC) waits on Clients & years.",
    "a_cin": "CIN", "a_incorporated": "Date of incorporation", "a_option": "Tax option", "a_manufacturing": "It manufactures or produces goods",
    "a_directors": "Directors", "a_d_name": "Name", "a_d_din": "DIN", "a_d_pan": "PAN", "a_d_add": "Add a director",
    "f_cin": "CIN", "f_directors": "Directors", "dk_coi": "Certificate of incorporation",
    "a_gstin": "GSTIN", "a_gstin_hint": "15 characters - the state code, the PAN, then three more. On the GST certificate.",
    "k_individual": "an individual", "k_huf": "an HUF", "k_firm": "a partnership firm", "k_llp": "an LLP", "k_aop": "an AOP", "k_boi": "a BOI",
    "k_company": "a company", "k_trust": "a trust",
    "dk_prefill": "Pre-filled JSON", "dk_ais": "AIS", "dk_26as": "26AS", "dk_form16": "Form 16", "dk_cg": "Capital-gains statement", "dk_gst": "GSTR-3B summary",
    "dk_bank": "Bank statement", "dk_filed": "The return filed", "dk_filed_prev": "Last year's return", "dk_tis": "TIS", "dk_other": "Other document",
    "dk_gst_cert": "GST certificate", "dk_deed": "Deed or agreement", "dk_books": "Books of account", "dk_gst_json": "GST returns (JSON)",
    "dk_itr_prev": "Last year's return",
    "rv_h": "What {product} understood", "rv_who": "Return for", "rv_form": "Form", "rv_docs": "Documents",
    "rv_gaps_h": "Still missing", "rv_gaps_none": "Every needed document is in.",
    "rv_open": "Continue in My return", "rv_opens_at": "Opens at {step}", "rv_open_firm": "Continue in {screen}", "rv_opens_firm": "Then Reconcile, the tax audit and Compute & close",
    "rv_need_client": "Upload a document with the PAN, or give it when asked - the return opens once the client is known.",
    "rv_checks": "{n} {n:check needs|checks need} a look", "rv_checks_none": "The documents agree with each other so far.",
    "rv_prompts": "{n} {n:hint|hints} from the documents",
    "saved": "Saved", "made_client": "{name} - client made from the documents", "found_client": "{name} - already a client; the documents go to their return",
    "hero_h": "What are you filing today?",
    "hero_p": "Pick who the return is for - a person, an HUF, a firm, an LLP, an AOP or a company. Drop the documents in: {product} makes the client and fills the return.",
    "hero_btn": "Start a new filing", "hero_resume": "{n} {n:filing|filings} waiting", "mr_new": "Start a new filing", "hero_all": "All filings and examples",
    "bad_who": "Pick who this return is for.", "bad_pick": "{id} does not apply to this return.", "no_wizard": "That filing is not here.",
    "not_yet": "{who}: not in New filing yet.",
    "too_many": "At most {n} documents in one filing.", "too_many_open": "At most {n} filings can wait at once - finish or discard one first.",
    "bad_pan": "{pan} is not a PAN - five letters, four digits, a letter.", "bad_gstin": "{gstin} is not a GSTIN - 15 characters, the PAN inside.",
    "pan_letter": "PAN {pan}: its 4th letter is {letter} - {want} for {kind}.", "need_name": "The name is needed.",
    "bad_answer": "{field} is not a question here.", "bad_choice": "{value} is not one of the choices.", "self_other": "Your desk files only your own return.",
    "too_many_partners": "At most {n} partners.", "done": "Opening the return",
}

GUIDE_STEPS = [
    {"title": "Who it is for", "say": "A person, an HUF, a partnership firm, an LLP, an AOP or BOI, or a company - each card starts its own filing. A trust says Not yet, with what to do meanwhile.",
     "target": ".wz-start-who|.wz-who|.wz-start"},
    {"title": "Worked examples", "say": "One worked example for each kind of return, with made-up documents: Watch how plays it start to finish.",
     "target": ".wz-examples|.wz-start"},
    {"title": "Carry on later", "say": "Every filing not finished waits here. Carry on opens it where you left off; Discard drops the wizard's progress, never the client or the return.",
     "target": ".wz-resume|.wz-start"},
    {"title": "Four steps", "say": "What you're filing, the documents, the upload, the review. Progress is saved as you go - leave, and carry on later.",
     "target": ".wz-rail|.wz-start"},
    {"title": "What applies", "say": "Salary, a second employer, a house, shares and funds, a property sale, crypto, a business, foreign income, days abroad, arrears, last year's losses, a revised return - in plain words, the section small beneath.",
     "target": ".wz-what|.wz-start"},
    {"title": "What kind of work", "say": "For a business: trading, manufacturing, services, a profession or farming; GST or not; a small turnover on the presumptive basis or full books; a tax audit with Form 3CD; partners' salary and interest; stock; depreciation.",
     "target": ".wz-work|.wz-what|.wz-start"},
    {"title": "Which form", "say": "The form follows from the picks, with its reason in one line - ITR-1, 2, 3 or 4 for a person or an HUF, ITR-5 for a firm, an LLP or an AOP, ITR-6 for a company.",
     "target": ".wz-form|.wz-start"},
    {"title": "Documents you'll need", "say": "Needed, good to have, and what you type in - each with what it is and where to get it: TRACES, the AIS, your employer, CAMS or KFintech, the GST portal, the firm's deed and its books.",
     "target": ".wz-docs|.wz-start", "open": ".wz-node[data-step='docs']"},
    {"title": "Drop them in", "say": "Several at once. Each file is identified by what it is - a Form 16, an AIS, a GST certificate, a deed, the books - with its PAN, name and year; a file it cannot read says so.",
     "target": "[data-drop='wz-file']|.wz-start", "open": ".wz-node[data-step='upload']"},
    {"title": "The client, made for you", "say": "The first document with a PAN makes the client, or finds the one already in your register. A popup asks only what is missing or does not agree: whose PAN, a date of birth, an HUF's Karta, a firm's partners from its deed, residence.",
     "target": ".wz-client|.wz-start", "open": ".wz-node[data-step='upload']"},
    {"title": "What the documents imply", "say": "Fund sales in the AIS - upload the CAMS statement. Another employer's TAN - that Form 16. A firm with GST - its GSTR-3B. Each hint goes once it is answered.",
     "target": ".wz-prompts|.wz-start", "open": ".wz-node[data-step='upload']"},
    {"title": "Review, then the return", "say": "What was understood, what is still missing, and one button on: My return at the right step for a person, Intake & map or the next firm screen for a business - never a dead end.",
     "target": ".wz-go|.wz-review|.wz-start", "open": ".wz-node[data-step='review']"},
]


def words_chip(cid, label, words, note):
    c = record_chip(cid, label, words, note)
    for p in c["params"]:
        p["type"] = "long" if len(p["default"]) > 60 else "text"
    return c


def ui_and_guide():
    put(words_chip("ui.wizard", "New filing screen words", UI, "every word of the New filing wizard (static/page-wizard.js) and its hero on Clients & years / My return."))
    g = record_chip("guide.wizard", "Guide me: New filing", {
        "title": "New filing", "icon": "spark", "minutes": 4, "steps": GUIDE_STEPS,
        "lede": "The guided way in: say who the return is for, see the documents it needs, drop them in - {product} reads each one, makes the client and asks only for what is missing."},
        "the New filing walk - who (people and businesses, the not-yet cards), the worked examples, resume, the four steps, what applies, "
        "the kind of work, the form, the documents, the upload, the client made from them, the hints, the review; tours/sf-wizard.json says "
        "the same (tools/guide_tour.py wizard).")
    g["set"] = "guide"
    g["expr"]["fields"] = {k: f"${k}" for k in ("title", "lede", "icon", "minutes", "steps")}
    put(g)


# --- the chips that change ------------------------------------------------------------------------------------------------

def load(cid):
    return json.loads((CH / f"{cid}.json").read_text(encoding="utf-8"))


def knob(c, name):
    return next(p for p in c["params"] if p["name"] == name)


def refresh_tests(c):
    """No-args tests answer what the chip now answers; a test with args keeps its expectation (checked by save)."""
    for t in c["test_cases"]:
        if not t.get("args"):
            t["fill"] = True


FAQ = [
    {"id": "wizard_start", "q": "How do I start a new filing?", "words": "start new filing wizard guided step by step walk me through filing where to begin first return new return from documents",
     "a": "New filing (the first screen under Filing, and the cards at the top of Clients & years): pick who the return is for - a person, an HUF, a firm, an LLP or an AOP - say what applies, see the documents it needs, drop them in. Each is read, the client is made from the PAN and name found, and a popup asks only for what is missing. Then the return opens at the right step.",
     "roles": [], "go": "#/wizard", "live": ""},
    {"id": "wizard_docs", "q": "Which documents do I need for my return?", "words": "which documents need for my return checklist form 16 ais 26as cams what to collect papers for return tax documents list",
     "a": "New filing lists them from what applies: the AIS and 26AS always, Form 16 from each employer, a CAMS / KFintech statement for funds sold, the GSTR-3B for a business, last year's ITR for losses - each with where to get it.",
     "roles": [], "go": "#/wizard", "live": ""},
    {"id": "wizard_resume", "q": "Can I leave a new filing and carry on later?", "words": "carry on later resume continue saved progress left off come back unfinished half done filing wizard",
     "a": "Yes. The wizard saves each step on the server. Open New filing: every filing not finished waits under Carry on where you left off. Discard drops only the wizard's progress - the client and the return stay.",
     "roles": [], "go": "#/wizard", "live": ""},
    {"id": "wizard_unknown", "q": "Why does a file say Not recognised?", "words": "not recognised unrecognised unknown file wrong document cannot identify file type which document is this",
     "a": "It is not one of the documents the wizard reads (pre-filled JSON, AIS, 26AS, Form 16, a CAMS / KFintech or broker statement, GSTR-3B, a bank statement, a filed ITR JSON; for a business also the GST certificate, the deed or LLP agreement, the books in Excel and the GST returns' JSON). It stays on the card, out of the return - remove it, or upload the right file. A locked PDF says Locked instead.",
     "roles": [], "go": "#/wizard", "live": ""},
    {"id": "wizard_client", "q": "Does the wizard make the client from the documents?", "words": "make client from documents automatically created client pan name from form 16 ais popup asks missing details karta",
     "a": "Yes - the first document with a PAN makes the client (or finds the one already in your register). Only what no document gave is asked in a popup: the name, date of birth, an HUF's name and Karta, a firm's partners, which PAN when two are found, residence.",
     "roles": [], "go": "#/wizard", "live": ""},
    {"id": "wizard_firm", "q": "How do I file a partnership firm's return?", "words": "partnership firm return itr-5 itr5 file firm return partners deed gst certificate trading firm new firm client how to file a firm",
     "a": "New filing > A partnership firm: pick the kind of work (trading, manufacturing, services, GST, a tax audit, partners' pay, stock, depreciation), then drop in the GST certificate, the deed, the books in Excel, the 26AS and the GSTR-3B JSON. The certificate makes the client (GSTIN, name, partnership), the popup shows the deed's partners to confirm, the books go to Intake & map, the 26AS to Reconcile, the GST returns to the tax audit. ITR-5, with Form 3CD when audited.",
     "roles": [], "go": "#/wizard", "live": ""},
    {"id": "wizard_llp", "q": "Can I file an LLP's return?", "words": "llp limited liability partnership return itr-5 llp agreement designated partners file llp",
     "a": "Yes - New filing > An LLP. Its GST certificate's constitution (Limited Liability Partnership) must fit the card; the designated partners come from the LLP agreement. An LLP cannot use the presumptive 44AD, so its books go to Intake & map. ITR-5.",
     "roles": [], "go": "#/wizard", "live": ""},
    {"id": "wizard_aop", "q": "What about an AOP, BOI or a society?", "words": "aop boi association of persons body of individuals society residents welfare association club joint venture return",
     "a": "New filing > An AOP or BOI: the PAN's fourth letter decides which (A an AOP, B a BOI). The members come from its agreement, the books go to Intake & map, the 26AS to Reconcile. ITR-5.",
     "roles": [], "go": "#/wizard", "live": ""},
    {"id": "wizard_company", "q": "Can I file a trust's return?", "words": "trust itr-7 itr7 charitable trust religious trust society trust return not yet company itr-6 itr6",
     "a": "Not yet: trusts (ITR-7) show on New filing as Not yet - meanwhile file the trustees' own returns, one press away on the card. A company's return (ITR-6) starts at New filing > A company: its certificate of incorporation makes the client (CIN, date, directors), the popup asks the tax option (115BAA, 115BAB or normal with MAT) and whether it manufactures, and the books go to Intake & map.",
     "roles": [], "go": "#/wizard", "live": ""},
    {"id": "wizard_work", "q": "What is 'What kind of work' in New filing?", "words": "what kind of work trading manufacturing services profession farming presumptive 44ad 44ada books tax audit 44ab 3cd partners remuneration 40b stock depreciation",
     "a": "For a business (and a person with one): trading, manufacturing, services, a profession or farming; GST or not; a small turnover on the presumptive basis (44AD / 44ADA) or full books; a tax audit (44AB, Form 3CD); partners' salary and interest (40(b)); stock; depreciation. The picks decide the documents, the form and the hints.",
     "roles": [], "go": "#/wizard", "live": ""},
    {"id": "wizard_examples", "q": "Is there a worked example of each kind of return?", "words": "example worked example video watch how film demo case sample filing walkthrough each kind of return",
     "a": "Yes - New filing's Worked examples: a salaried ITR-1, two employers, salary with funds and a plot sold, a pensioner, a 44ADA consultant, a 44AD trader, an HUF, a trading firm with GST and a tax audit, a manufacturing firm, an LLP, an AOP, a trading company on 115BAA, a manufacturing company with MAT, a non-resident and an updated return. Watch how plays each start to finish; in the demo each is there to carry on.",
     "roles": [], "go": "#/wizard", "live": ""},
]


def changed():
    c = load("start.steps")
    rows = knob(c, "rows")["default"]
    for r in rows:
        if r["id"] == "client":
            r.update(label="Start a new filing", href="#/wizard",
                     say="Pick who the return is for and drop the documents in - the client is made from them, and only what is missing is asked.")
        if r["id"] == "my_docs":
            r.update(label="Start your filing", href="#/wizard",
                     say="Say what applies, drop in Form 16, the AIS and 26AS - My return fills in what it can.")
    scr = knob(c, "screens")["default"]
    if "wizard" not in scr:
        scr.insert(0, "wizard")
    refresh_tests(c)
    save(c, "the first work step is New filing (#/wizard): 'Start a new filing' for a firm, 'Start your filing' for a self-filer; the card shows on the wizard too.")

    c = load("firm.roles")
    for r in knob(c, "rows")["default"]:
        if r["id"] in ("firm_admin", "partner", "preparer", "self") and "wizard" not in r["grants"]:
            r["grants"].insert(r["grants"].index("myreturn") if "myreturn" in r["grants"] else 0, "wizard")
    refresh_tests(c)
    save(c, "the New filing wizard's grant - firm admin, partner, preparer (they add clients) and the self-filer.")

    c = load("edition.settings")
    for r in knob(c, "rows")["default"]:
        if r["id"] == "simplyfile" and "wizard" not in r["screens"]:
            r["screens"].insert(r["screens"].index("clients"), "wizard")
    refresh_tests(c)
    save(c, "New filing (wizard) in SimplyFy's menu, first in Filing.")

    c = load("chat.faq")
    rows = knob(c, "rows")["default"]
    have = {r["id"] for r in rows}
    at = next(i for i, r in enumerate(rows) if r["id"] == "start_steps") + 1
    for r in reversed(FAQ):
        if r["id"] not in have:
            rows.insert(at, r)
        else:
            rows[[x["id"] for x in rows].index(r["id"])] = r
    refresh_tests(c)
    save(c, "questions about the New filing wizard - how to start, which documents, carry on later, Not recognised, the client made from the documents; "
            "later the same day: a firm's, an LLP's, an AOP's return, a company or trust (not yet), the kind of work, the worked examples.")

    for gid, step, before in (
            ("guide.myreturn", {"title": "New filing", "say": "New here? Start a new filing: the wizard asks what you are filing, lists the documents, reads them, makes the client and opens this return at the right step.",
                                "target": "#mr-wizard|.mr-pick|.mr-rail-card"}, "Start from documents"),
            ("guide.clients", {"title": "Start a new filing", "say": "The quickest way in: pick who the return is for right here - a person, an HUF, a firm, an LLP or an AOP - and New filing lists the documents, reads them and makes the client.",
                               "target": "#cl-wizard|.cl-hero"}, "The register")):
        c = load(gid)
        steps = knob(c, "steps")["default"]
        old = next((s for s in steps if s["title"] == step["title"]), None)
        if old:
            old.update(step)
        else:
            i = next(n for n, s in enumerate(steps) if s["title"] == before)
            steps.insert(i + (1 if gid == "guide.clients" else 0), step)
        refresh_tests(c)
        save(c, "a step pointing to New filing (the wizard).")


if __name__ == "__main__":
    chips()
    cases_chip()
    ui_and_guide()
    changed()
