"""00 RECORDING SCRIPT - the showcase run sheet, its figures taken from showcase_expected.json (the portal's own answers)."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
import json
import re
from pathlib import Path

ROOT = Path(_R + r"")
OUT = ROOT / "Requirements" / "Showcase - Demo CA Filing Firm"
X = json.loads(Path(__file__).with_name("showcase_expected.json").read_text(encoding="utf-8"))
style = re.search(r"<style>.*?</style>", (ROOT / "Requirements/Demo E2E - Shree Ganesh Agarwal HUF/00 START HERE - End to end test.html")
                  .read_text(encoding="utf-8"), re.S).group(0)


def inr(n):
    n = round(float(n or 0))
    s, neg = str(abs(int(n))), n < 0
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        s = head + "," + tail
    return ("-" if neg else "") + "₹" + s


def card(n, title, where, body):
    return f'<div class="card step"><div class="num">{n}</div><div><h2>{title}</h2><span class="where">{where}</span>\n{body}\n</div></div>'


def table(rows, head=("Field", "Type")):
    return "<table><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>" + "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</table>"


c1, c2, c3, c4, c5 = (X[k] for k in ("c1", "c2", "c3", "c4", "c5"))
k1, k2, k3, k4 = c1["compute"], c2["compute"], c3["compute"], c4["compute"]
k5o, k5 = c5["compute_original"], c5["compute_updated"]
I = lambda k: f"234A {inr(k['interest']['a'])} · 234B {inr(k['interest']['b'])} · 234C {inr(k['interest']['c'])}"  # noqa: E731
BAL = lambda k: f"{'Refund' if k['balance']['kind'] == 'refund' else 'Payable'} {inr(k['balance']['amount'])}"  # noqa: E731

parts = []
parts.append(f"""<h1>SimplyFile showcase: Demo CA Filing Firm</h1>
<p class="lede">A recording run sheet: set up the firm on <b>sf.valuestream.in</b>, approve it, bring in the team, and take five <b>fictional</b>
clients through every scenario the portal has. Every client name, PAN, TAN, account and amount below is made up; the figures in
"You should see" are the portal's own answers from a rehearsal run of exactly these steps.</p>
<div class="card"><h2>Before you record</h2>
<ul class="files">
<li><b>Real details only for the firm itself</b> (step 1): take PAN, TAN, GSTIN, FRN, membership no., address and mobile from your uncle. Everything else in this sheet is fictional.</li>
<li><b>Hide what is real</b>: record in a window you control and blur the firm's details card and the name/email in the top-right menu (e.g. OBS Studio with a blur filter, or crop those areas in the editor). The Tour Video screen's own recordings already blur the signed-in name.</li>
<li><b>The papers</b> in <code>A Firm papers - placeholders</code> are plain PDFs stamped <span class="bad">DEMO PLACEHOLDER</span> - not identity documents. Use them only to show the upload; afterwards use <b>Replace</b> on each with the real paper.</li>
<li>Team e-mails use <code>@example.com</code> (no mail goes anywhere). Each person's one-time password is shown on screen once - note it if you want to sign in as them.</li>
<li>Browser zoom 90% keeps whole cards on screen; one client per take keeps the edit simple.</li></ul></div>""")

parts.append(card(1, "Sign up and set up the firm", "Sign up → My firm → CA firm",
                  table([("Firm / account name", "Demo CA Filing Firm (as on the PAN card)"), ("PAN", "the firm's PAN - 4th letter F (P if a proprietorship)"),
                         ("TAN", "10 characters, e.g. HYDP12345E"), ("GSTIN", "15 characters; it must carry the PAN"),
                         ("ICAI FRN", "6 digits + region letter, e.g. 012345S"), ("CA membership no.", "6 digits"),
                         ("Owner / partner in charge", "your uncle's name"), ("Aadhaar - last 4 digits", "only 4 digits (a full number is refused)"),
                         ("Mobile linked to PAN / GST", "his mobile (he gives you the sign-up OTP)"), ("Email · Address", "the firm's")], ("Field", "What to give"))
                  + "<ol class=\"do\"><li>Upload the five PDFs from <code>A Firm papers - placeholders</code> into their slots (1 Aadhaar, 2 PAN card, 3 TAN letter, 4 GST, 5 ICAI).</li>"
                  "<li>Tick the confirmation, <b>Save</b>, then <b>Send for approval</b>.</li></ol>"
                  "<p class=\"good\">You should see: the strip Details ✓ Papers ✓ Sent, the banner \"Waiting for approval\" and the Filing menu still shut.</p>"))
parts.append(card(2, "Approve the firm", "Portal admin → Firm approvals",
                  "<ol class=\"do\"><li>Sign in as the portal admin → <b>Firm approvals</b>: Demo CA Filing Firm waits with its review clock.</li>"
                  "<li><b>Open</b> → read the details and View each paper → <b>Approve</b>.</li></ol>"
                  "<p class=\"good\">You should see (signed in as the firm again): the shield green \"Approved\", and Clients &amp; years, Intake &amp; map, Reconcile, Compute &amp; close in the menu.</p>"))
parts.append(card(3, "Bring in the team", "My firm → Team → Add a person",
                  table([("Kavitha Menon", "kavitha.partner@example.com", "Partner"), ("Anand Murthy", "anand.reviewer@example.com", "Reviewer"),
                         ("Ravi Kumar", "ravi.preparer@example.com", "Tax preparer")], ("Name", "Email", "Role"))
                  + "<p class=\"good\">Each shows its one-time password once. Optional take: sign in as Ravi (preparer) - he maps and computes, but has no Sign off or File button.</p>"))

m1 = c1["map"]
parts.append(card(4, "C1 · Shree Ganesh Agarwal HUF - the full road (ITR-3, tax audit)", "Clients &amp; years · Intake &amp; map · Reconcile · Compute &amp; close",
                  "<p>Folder <code>C1 Shree Ganesh Agarwal HUF (ITR-3, tax audit)</code>. Type the master from <code>01 Client master…txt</code>, plus: date of birth / formation "
                  "<code>1998-04-15</code>, father's name of the signatory <code>Ram Prasad Agarwal</code>, PAN of the signatory <code>ABCPA1234D</code>. Year 2026-27: ITR-3, tick Tax audit.</p>"
                  "<ol class=\"do\"><li>Intake: upload <code>02 …xlsx</code> → <b>Accept all suggestions</b> → the one row left (<i>Add: Disallowance u/s 40(a)(ia)</i>) gets <code>ITR3 BP</code>. "
                  f"Show the heading totals: <b>TOTAL INCOME STATEMENT {inr(20736500)} · Adds up</b>.</li>"
                  f"<li>Upload <code>10 Client books…xlsx</code>: {c1['books_upload']['rows']} rows, all tagged. Upload <code>02</code> again to show <b>Replace it?</b> (choose Cancel).</li>"
                  f"<li>Reconcile: upload <code>03</code>, <code>04</code>, <code>05</code> → {c1['recon']['summary']['red']} red, {c1['recon']['summary']['amber']} amber, {c1['recon']['summary']['ok']} agree. "
                  "Clients &amp; years shows <b>3 Reconciling</b>. Explain the red Lakshmi Finance finding → the year moves to <b>4 Review</b> by itself.</li>"
                  f"<li>Compute: total income <b>{inr(k1['income'])}</b>, tax <b>{inr(k1['tax']['total'])}</b> (surcharge with marginal relief), {I(k1)}, <b class=\"ok\">{BAL(k1)}</b>; "
                  "244A: none (refund under 10% of tax).</li>"
                  "<li>Files: <b>ITR-3 JSON</b> → \"Fits the CBDT schema\", balance sheet tallies at ₹3,77,50,000, P&amp;L profit = business income; <b>Form 3CB-3CD JSON</b> → fits, with "
                  "<b>your firm</b> as auditor.</li>"
                  "<li>Sign off → ack <code>456789012345678</code>, date filed today → <b>original u/s 139(1)</b> (due 31 Oct with audit). Then <b>Start a revised return</b> → <b>Discard the revision</b> "
                  "to show the history.</li></ol>"))
parts.append(card(5, "C2 · Ramesh Iyer - senior citizen, late return", "Clients &amp; years · Intake &amp; map · Reconcile · Compute &amp; close",
                  table([("Name · Status · PAN", "Ramesh Iyer · Individual · <code>BXRPI5821K</code>"), ("Date of birth", "<code>1958-06-10</code> (60+ in the year)"),
                         ("Father's name", "Venkatesan Iyer"), ("Email · Mobile", "ramesh.iyer@example.com · 9840012345"),
                         ("Address", "14, Kutchery Road, Mylapore, Chennai 600004"), ("Bank", "Indian Bank · Mylapore · Savings · 6012345678 · IDIB000M053"),
                         ("Year 2026-27", "ITR-3, no audit")])
                  + "<ol class=\"do\"><li>Upload the income statement → every row suggested → Accept all. Upload the 26AS → all agree.</li>"
                  f"<li>Compute: income <b>{inr(k2['income'])}</b>, tax <b>{inr(k2['tax']['total'])}</b>, TDS {inr(k2['tds'])}, self-assessment tax {inr(k2['paid'])} (paid 20 Sep 2026, after the 31 Aug due date).</li>"
                  f"<li>Interest: <b>{I(k2)}</b> - the line <i>\"No 234B / 234C: resident senior citizen with no business income\"</i>; only 234A for the late return. <b>{BAL(k2)}</b>.</li></ol>"))
parts.append(card(6, "C3 · Sri Venkateswara Traders - a firm: ITR-5, 3CB-3CD, short advance tax", "Clients &amp; years · Intake &amp; map · Reconcile · Compute &amp; close",
                  table([("Name · Status · PAN", "Sri Venkateswara Traders · Firm · <code>AAFFS4721M</code>"), ("GSTIN", "<code>36AAFFS4721M1ZK</code>"),
                         ("Date of formation", "<code>2012-04-01</code>"), ("Partners", "Venkata Rao <code>ABCPV1234E</code> 50% · Srinivas Rao <code>ABCPS5678F</code> 50%"),
                         ("Signatory", "S/o Narasimha Rao · PAN <code>ABCPV1234E</code>"), ("Email · Mobile", "accounts@svtraders.example.com · 9848012345"),
                         ("Address", "12-2-718, Mehdipatnam, Hyderabad 500028"), ("Bank", "State Bank of India · Mehdipatnam · Current · 38123456789 · SBIN0020071"),
                         ("Year 2026-27", "ITR-5, tick Tax audit")])
                  + "<ol class=\"do\"><li>Upload <i>IT Stmt, Dep, Loans, 40A(2)(b)</i> → Accept all: income rows, TDS, advance tax, depreciation (3CD 18), loans (3CD 31(a)/(b)), the s.40A(2)(b) rent (3CD 23).</li>"
                  "<li>Upload <i>Trading, P&amp;L and Balance Sheet</i> - <b>no SF Ref column</b>: every row is suggested as <code>ITR5 PL …</code> / <code>ITR5 BS …</code> → Accept all.</li>"
                  f"<li>Reconcile the 26AS → all agree. Compute: income <b>{inr(k3['income'])}</b>, firm rate 30% + cess = <b>{inr(k3['tax']['total'])}</b>; advance tax {inr(k3['paid'])} is under 90% → "
                  f"<b>{I(k3)}</b>; <b class=\"bad\">{BAL(k3)}</b>.</li>"
                  "<li>Files: ITR-5 JSON fits (partners' capital in Part A-BS, balance sheet tallies, P&amp;L = business income); Form 3CB-3CD JSON fits - depreciation blocks coded, two loans, one repayment, "
                  "the 40A(2)(b) rent, and your firm as auditor. Tick <b>Transfer pricing (3CEB)</b> on the year to show the due date move to 30 Nov; untick.</li></ol>"))
parts.append(card(7, "C4 · Kiran Kumar Rao - professional: 87A rebate, refund and 244A interest", "Clients &amp; years · Intake &amp; map · Reconcile · Compute &amp; close",
                  table([("Name · Status · PAN", "Kiran Kumar Rao · Individual · <code>BKRPR4417H</code>"), ("Date of birth · Father", "<code>1988-11-23</code> · Mohan Rao"),
                         ("Email · Mobile", "kiran.rao@example.com · 9849912345"), ("Address", "Flat 402, Aditya Enclave, Kondapur, Hyderabad 500084"),
                         ("Bank", "ICICI Bank · Kondapur · Savings · 123401234567 · ICIC0001234"), ("Year 2026-27", "ITR-3, no audit")])
                  + f"<ol class=\"do\"><li>Upload the statement and 26AS → Accept all; 2 TDS lines (194J) agree.</li>"
                  f"<li>Compute: income <b>{inr(k4['income'])}</b>, rebate u/s 87A wipes the tax → <b>{inr(k4['tax']['total'])}</b>; <b class=\"ok\">{BAL(k4)}</b>.</li>"
                  "<li>Sign off → ack <code>567890123456789</code>, <b>Date filed 2026-08-20</b> → original (on time, due 31 Aug). Then <b>Refund received on 2026-10-01</b>.</li>"
                  f"<li>The refund line shows <b>244A interest {inr(k4['refund_interest']['interest'])}</b> - 0.5% a month from 1 April (the return was on time).</li></ol>"))
parts.append(card(8, "C5 · Meera Nair - AY 2025-26: the original, then an updated return (ITR-U)", "Clients &amp; years · Intake &amp; map · Reconcile · Compute &amp; close",
                  table([("Name · Status · PAN", "Meera Nair · Individual · <code>AYMPN6630Q</code>"), ("Date of birth · Father", "<code>1979-02-14</code> · Gopinath Nair"),
                         ("Email · Mobile", "meera.nair@example.com · 9845012345"), ("Address", "22, Indiranagar 2nd Stage, Bengaluru 560038"),
                         ("Bank", "Canara Bank · Indiranagar · Savings · 0412101234567 · CNRB0000412"), ("Year", "<b>2025-26</b> (pick it in the year box), ITR-3")])
                  + "<ol class=\"do\"><li>Upload <i>Income statement AY 2025-26 (as filed in July 2025)</i> and the 26AS → Accept all; all agree.</li>"
                  f"<li>Compute (AY 2025-26 slabs): income {inr(k5o['income'])}, tax {inr(k5o['tax']['total'])}, {BAL(k5o)}. Sign off → ack <code>345678901234567</code>, "
                  "<b>Date filed 2025-07-28</b> → original.</li>"
                  "<li>The FD interest from Federal Bank was missed. <b>Start an updated return (ITR-U)</b> (the revision window closed on 31 Dec 2025).</li>"
                  f"<li>Upload <i>Income missed in the original return</i> → Accept. Compute: income <b>{inr(k5['income'])}</b>, tax {inr(k5['tax']['total'])}, {I(k5)}, {BAL(k5)}.</li>"
                  f"<li>The ITR-U box: further tax and interest <b>{inr(k5['itr_u']['extra'])}</b> → <b>additional tax u/s 140B @ {k5['itr_u']['pct']}% = {inr(k5['itr_u']['additional'])}</b>. "
                  "Filing without ticking the confirmation (no search, survey, assessment…) is refused; tick it, sign off, ack <code>345678901234999</code> → <b>updated u/s 139(8A)</b>; "
                  "the history shows the original as <i>Revised</i>.</li></ol>"
                  "<p class=\"tip\">The ITR JSON check lists 2 points here (assessment year, due date): the department's schema in SimplyFile is the AY 2026-27 one. An AY 2025-26 updated "
                  "return is prepared in the department's ITR-U utility from these figures.</p>"))
parts.append("""<div class="card"><h2>The Tour Videos</h2>
<p>Every screen has a narrated tour made from its Guide me walk: My firm, Firm approvals, Clients &amp; years, Intake &amp; map, Reconcile, Compute &amp; close.
Signed in as the portal owner on sf.valuestream.in, open <b>Tour Video</b> and press record on each - the recordings blur the signed-in name by themselves.
Share them with the recording of this run.</p></div>""")
html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SimplyFile showcase</title>{style}</head>
<body><div class="wrap">
{''.join(parts)}
</div></body></html>"""
(OUT / "00 RECORDING SCRIPT - SimplyFile showcase.html").write_text(html, encoding="utf-8")
print("written")
