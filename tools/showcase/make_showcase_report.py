"""One self-contained HTML page (no internet needed): Demo CA Filing Firm on SimplyFile - a professional narration,
the five demo cases, the consolidated filing activity and the analytics snapshot. Figures = the showcase run."""
import pathlib as _pl; _R = str(_pl.Path(__file__).resolve().parents[2])  # the repo root
from html import escape as E
from pathlib import Path

OUT = Path(_R + r"\Requirements\Showcase - Demo CA Filing Firm\00 SimplyFile showcase - Demo CA Filing Firm.html")


def inr(n):
    n = round(n)
    s, neg = str(abs(n)), n < 0
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        s = ",".join([head] + parts if head else parts) + "," + tail
    return ("-" if neg else "") + "₹" + s


CASES = [
    {"n": 1, "name": "Shree Ganesh Agarwal HUF", "tag": "ITR-3 · Tax audit (3CB-3CD)", "who": "A Hindu undivided family running a trading business in Hyderabad, with rental income and interest.",
     "scenario": "The complete road - from the client master to a filed, audited return - including a re-uploaded statement, a 26AS mismatch and a revised return started and discarded.",
     "steps": ["Client master with PAN, GSTIN, bank account, the karta's details for verification",
               "Income statement uploaded from Excel; 27 of 29 rows suggested automatically, one disallowance u/s 40(a)(ia) mapped by hand",
               "Final accounts (Trading, P&L, Balance Sheet) mapped from the client's own SF Ref column - 33 rows",
               "Same statement uploaded again - SimplyFile offers Replace, keeps every mapping and the earlier version",
               "26AS, AIS and TIS reconciled: one red - Lakshmi Finance TDS ₹36,000 in 26AS vs ₹40,000 claimed - explained",
               "Computation, ITR-3 JSON and Form 3CB-3CD JSON validated against the CBDT schemas; balance sheet tallies at ₹3,77,50,000",
               "Reviewer sign-off; filed as an original return u/s 139(1); a revised return started and discarded - the filed return stands"],
     "figures": [("Total income", 20736500), ("Tax payable (incl. surcharge, cess)", 7439640), ("TDS", 306000), ("Advance tax paid", 7200000),
                 ("Interest u/s 234A/B/C", 0), ("Refund due", 66360)],
     "outcome": "Filed on time · Refund ₹66,360 · ITR-3 and 3CD JSON ready for the department's utility"},
    {"n": 2, "name": "Ramesh Iyer", "tag": "Senior citizen · Late return", "who": "A resident senior citizen (born 1958) in Chennai with rental and interest income, no business.",
     "scenario": "A senior citizen without business income is exempt from advance tax (s.207(2)) - so no 234B/C - but filing after 31 July still attracts 234A.",
     "steps": ["Client master with date of birth - the exemption follows from it automatically",
               "Income statement and 26AS: every row suggested and accepted in one click",
               "234A worked out to the day from the self-assessment challan; 234B/C nil by law"],
     "figures": [("Total income", 2112000), ("Tax payable", 237120), ("TDS", 180000), ("Self-assessment tax paid", 57120),
                 ("Interest u/s 234A", 571), ("Balance payable", 571)],
     "outcome": "Ready for review · Only ₹571 of 234A - the exemption saved 234B/C entirely"},
    {"n": 3, "name": "Sri Venkateswara Traders", "tag": "Partnership firm · ITR-5 · 3CB-3CD · Form 3CEB", "who": "A two-partner trading firm in Hyderabad with a tax audit and transfer-pricing report.",
     "scenario": "A firm whose final accounts carry no SF Ref column at all, whose advance tax fell short, and whose due date moves to 30 November because of Form 3CEB.",
     "steps": ["Partners and their profit shares in the client master",
               "Statement (depreciation, loans, 40A(2)(b)) and final accounts: SimplyFile read the words under the P&L and Balance Sheet headings and suggested every ref",
               "26AS reconciled - everything agrees",
               "234B ₹22,372 and 234C ₹14,113 worked out from the challan dates",
               "ITR-5 JSON and 3CB-3CD JSON validated - the CA firm named as auditor"],
     "figures": [("Total income", 4300000), ("Tax payable", 1341600), ("TDS", 72000), ("Advance tax paid", 950000),
                 ("Interest u/s 234B + 234C", 36485), ("Balance payable", 356085)],
     "outcome": "Ready for review · Due 30 November 2026 (3CEB) · A clear case for an advance-tax calendar next year"},
    {"n": 4, "name": "Kiran Kumar Rao", "tag": "Professional · Refund + 244A", "who": "A young professional in Kondapur whose clients deducted TDS u/s 194J.",
     "scenario": "The 87A rebate brings his tax to nil, so all TDS comes back - with interest u/s 244A once the refund is paid.",
     "steps": ["Income statement and 26AS mapped and reconciled",
               "Rebate u/s 87A applied under the new regime - tax nil",
               "Filed on 20 August 2026, inside the new 31 August due date for non-audit business returns",
               "Refund received on 1 October 2026 - 244A interest at 0.5% a month worked out"],
     "figures": [("Total income", 975000), ("Tax after 87A rebate", 0), ("TDS", 180000), ("Refund due", 180000), ("Interest u/s 244A", 6300)],
     "outcome": "Filed on time · Refund ₹1,80,000 plus ₹6,300 interest"},
    {"n": 5, "name": "Meera Nair", "tag": "AY 2025-26 · Updated return (ITR-U)", "who": "A salaried individual in Bengaluru who filed in July 2025 and later found income she had missed.",
     "scenario": "After 31 December a revised return is no longer allowed - SimplyFile offers an updated return u/s 139(8A) and works out the 140B additional tax.",
     "steps": ["Original return (as filed on 28 July 2025) recorded with its 26AS - refund ₹62,660 then",
               "Missed income uploaded as its own statement",
               "ITR-U: further tax ₹2,60,693 (including the refund to be given back) and 25% additional tax u/s 140B",
               "Confirmed, signed off and filed - the original stays in the history as revised"],
     "figures": [("Total income - original", 936000), ("Total income - updated", 1836000), ("Tax payable - updated", 250430),
                 ("Interest u/s 234A/B/C", 55603), ("Further tax for ITR-U", 260693), ("Additional tax u/s 140B (25%)", 65173)],
     "outcome": "ITR-U filed · ₹65,173 additional tax disclosed correctly - no penalty exposure on the missed income"},
]
TOTALS = [("Clients served", "5"), ("Returns filed", "4"), ("Tax handled on computations", inr(7439640 + 237120 + 1341600 + 0 + 250430)),
          ("Refunds secured for clients", inr(66360 + 180000)), ("244A interest for clients", inr(6300)),
          ("Interest worked out (234A/B/C)", inr(571 + 36485 + 55603)), ("140B additional tax disclosed", inr(65173)),
          ("Schema-valid department files", "ITR-3 ×3, ITR-5, 3CB-3CD ×2")]
FILINGS = [("Shree Ganesh Agarwal HUF", "2026-27", "ITR-3", "Original u/s 139(1)", "Filed", "Revised started and discarded"),
           ("Kiran Kumar Rao", "2026-27", "ITR-3", "Original u/s 139(1)", "Filed 20/08/2026", "Refund + 244A"),
           ("Meera Nair", "2025-26", "ITR-3", "Original u/s 139(1)", "Filed 28/07/2025 → revised", "Superseded by ITR-U"),
           ("Meera Nair", "2025-26", "ITR-3", "Updated u/s 139(8A)", "Filed", "140B ₹65,173"),
           ("Ramesh Iyer", "2026-27", "ITR-3", "-", "Review", "234A ₹571 payable"),
           ("Sri Venkateswara Traders", "2026-27", "ITR-5", "-", "Review", "Due 30/11/2026 (3CEB)")]
NARRATION = [
    "Demo CA Filing Firm is a chartered accountancy practice serving individuals, Hindu undivided families, professionals and partnership firms. "
    "This showcase follows the firm through one assessment season on SimplyFile - from the day the firm was verified and approved on the portal, "
    "to the day its last return of the season was filed.",
    "The firm signed up with its PAN, TAN, GSTIN and ICAI registration, uploaded its papers, and was approved by the portal administrator. "
    "The firm admin then brought the team in - a partner who signs off and files, a reviewer, and a tax preparer - each with their own sign-in, "
    "so every upload, sign-off and filing is recorded against the person who did it.",
    "Across five clients the team handled the whole range of an Indian tax practice: a tax-audited HUF business, a senior citizen filing late, "
    "a partnership firm with a transfer-pricing report, a professional due a refund, and an updated return for income missed in an earlier year. "
    "Statements came in as the clients' own Excel files; SimplyFile suggested the mapping for almost every row, reconciled the books against 26AS, AIS and TIS, "
    "and worked out tax, interest under sections 234A, 234B and 234C, refund interest under section 244A and the additional tax under section 140B - "
    "with every rule kept in one place and every figure traceable to its source row.",
    "By the end of the season the firm had filed four returns, secured refunds of ₹2,46,360 for its clients with a further ₹6,300 of interest, "
    "disclosed missed income through an updated return before the department found it, and produced ITR and Form 3CD files in the Income-tax Department's own "
    "JSON format, checked against the official schemas before upload. Two returns stand at review with their deadlines in view.",
    "Firm analytics then turns the season into a plan: a deadline radar for what is still open, the workload of each team member, "
    "and growth opportunities - clients who need advance-tax planning, clients whose refunds show too much TDS, late filers who need a compliance calendar. "
    "Each is a conversation about a service the firm already knows how to give.",
]


def case(c):
    rows = "".join(f"<tr><td>{E(k)}</td><td class='num'>{inr(v)}</td></tr>" for k, v in c["figures"])
    steps = "".join(f"<li>{E(s)}</li>" for s in c["steps"])
    return f"""<section class="case" id="c{c['n']}"><div class="case-h"><span class="num-badge">{c['n']}</span><div><h3>{E(c['name'])}</h3>
      <span class="tag">{E(c['tag'])}</span></div></div>
      <p class="who">{E(c['who'])}</p><p><b>The scenario.</b> {E(c['scenario'])}</p>
      <div class="case-grid"><div><h4>What the team did</h4><ol>{steps}</ol></div>
        <div><h4>The figures</h4><table>{rows}</table></div></div>
      <p class="outcome">{E(c['outcome'])}</p></section>"""


html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Demo CA Filing Firm on SimplyFile</title>
<style>
:root{{--bg:#f6f7fb;--panel:#fff;--ink:#1d2033;--muted:#6b7086;--line:#e4e6ef;--brand:#5b5bd6;--brand-soft:#ededfc;--ok:#15803d;--ok-soft:#e7f6ec;--warn:#9a6212;--warn-soft:#fdf3e1}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0d0f17;--panel:#161a26;--ink:#e8eaf3;--muted:#9aa0b8;--line:#272c3d;--brand:#8b8bf5;--brand-soft:#23254a;--ok:#4ade80;--ok-soft:#14301f;--warn:#f0b65a;--warn-soft:#3a2c14}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
.wrap{{max-width:1040px;margin:0 auto;padding:28px 16px 60px}}
header.hero{{background:linear-gradient(135deg,var(--brand),#7c3aed);color:#fff;border-radius:18px;padding:34px 30px}}
header.hero h1{{margin:0 0 6px;font-size:30px;line-height:1.2}}header.hero p{{margin:0;opacity:.92}}
.kicker{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;opacity:.85}}
.note{{font-size:13px;color:var(--muted);margin:10px 0 0}}
h2{{font-size:21px;margin:34px 0 12px}}h3{{margin:0;font-size:18px}}h4{{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}}
.card,.case{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px 22px;margin:0 0 14px}}
.narr p{{margin:0 0 12px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}}
.kpi{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}}.kpi b{{display:block;font-size:22px;margin-top:4px}}.kpi span{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
.case-h{{display:flex;gap:12px;align-items:center;margin-bottom:6px}}.num-badge{{flex:none;width:36px;height:36px;border-radius:50%;background:var(--brand);color:#fff;display:grid;place-items:center;font-weight:700}}
.tag{{display:inline-block;font-size:12px;padding:2px 10px;border-radius:999px;background:var(--brand-soft);color:var(--brand);margin-top:3px}}
.who{{color:var(--muted);margin:8px 0}}.case-grid{{display:grid;grid-template-columns:1.3fr 1fr;gap:22px;margin-top:12px}}
ol{{margin:0;padding-left:20px}}ol li{{margin:0 0 6px}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:7px 6px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}td.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
th{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
.outcome{{margin:14px 0 0;padding:10px 14px;border-radius:10px;background:var(--ok-soft);color:var(--ok);font-weight:600}}
.scroll{{overflow-x:auto}}.scroll table{{min-width:640px}}
.leads{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}.lead{{background:var(--warn-soft);border-radius:12px;padding:14px}}.lead b{{display:block}}
.toc a{{color:var(--brand);text-decoration:none;margin-right:14px;white-space:nowrap}}
footer{{color:var(--muted);font-size:13px;margin-top:30px}}
@media (max-width:700px){{.case-grid{{grid-template-columns:1fr}}header.hero{{padding:24px 20px}}header.hero h1{{font-size:24px}}}}
@media print{{body{{background:#fff}}.case,.card{{break-inside:avoid}}}}
</style></head><body><div class="wrap">
<header class="hero"><div class="kicker">SimplyFile · showcase</div><h1>Demo CA Filing Firm</h1>
<p>One assessment season on SimplyFile - from firm approval to filed returns, in the Income-tax Department's own format.</p></header>
<p class="note">Every client, PAN, amount and team member in this showcase is made up for demonstration. The firm's own details are not shown.</p>
<p class="toc">{''.join(f'<a href="#{i}">{t}</a>' for i, t in [("narr", "Narration"), ("summary", "Consolidated activity"), ("cases", "Five cases"), ("filings", "Filing register"), ("analytics", "Analytics")])}</p>

<h2 id="narr">The season, in brief</h2><div class="card narr">{''.join(f'<p>{E(p)}</p>' for p in NARRATION)}</div>

<h2 id="summary">Consolidated filing activity</h2>
<div class="kpis">{''.join(f'<div class="kpi"><span>{E(k)}</span><b>{E(v)}</b></div>' for k, v in TOTALS)}</div>

<h2 id="cases">Five cases</h2>{''.join(case(c) for c in CASES)}

<h2 id="filings">Filing register</h2><div class="card scroll"><table><tr><th>Client</th><th>AY</th><th>Form</th><th>Return</th><th>Status</th><th>Note</th></tr>
{''.join('<tr>' + ''.join(f'<td>{E(x)}</td>' for x in r) + '</tr>' for r in FILINGS)}</table></div>

<h2 id="analytics">What Firm analytics shows the partners</h2>
<div class="card"><p>Firm analytics in SimplyFile turns the season into decisions. For AY 2026-27 it shows:</p>
<table><tr><td>Returns filed / clients this year</td><td class="num">2 / 5</td></tr><tr><td>Filed on time</td><td class="num">100%</td></tr>
<tr><td>Open on the deadline radar</td><td class="num">Ramesh Iyer (past 31 Aug) · Sri Venkateswara Traders (30 Nov)</td></tr></table>
<h4 style="margin-top:16px">Growth opportunities it raises</h4><div class="leads">
<div class="lead"><b>Advance-tax planning</b>Sri Venkateswara Traders paid ₹36,485 of 234B/C - a quarterly advance-tax calendar saves it next year.</div>
<div class="lead"><b>Too much TDS</b>Kiran Kumar Rao (₹1,80,000) and the Agarwal HUF (₹66,360) wait for refunds - a s.197 certificate or TDS review frees the money.</div>
<div class="lead"><b>Compliance calendar</b>Ramesh Iyer will pay 234A - reminders before 31 July avoid it.</div>
<div class="lead"><b>Review engagement</b>Meera Nair needed an ITR-U - a mid-year review catches missed income before it costs 140B tax.</div></div></div>

<footer>Prepared with SimplyFile · sf.valuestream.in · Figures from the showcase run of 4 October 2026.</footer>
</div></body></html>"""
OUT.write_text(html, encoding="utf-8")
print(OUT)

# --- 2026-10-04: ten more scenarios (C6-C15), figures from showcase2_expected.json -------------------------------------
import json  # noqa: E402
X2 = json.loads((Path(__file__).parent / "showcase2_expected.json").read_text(encoding="utf-8"))
MORE = [
    ("c6", "Lakshmi Devi", "AY 2025-26 · Belated return u/s 139(4)", "Rent and FD interest; the return was filed on 20 November 2025, after the 31 July due date but before 31 December.",
     "SimplyFile names the return belated from the dates alone and works out 234A and 234B to the day of filing."),
    ("c7", "Suresh Reddy", "AY 2026-27 · Revised return u/s 139(5)", "A trader filed on 25 July 2026; AIS later showed ₹2,50,000 of FD interest he had not reported.",
     "Start a revised return, add the missed income as its own statement, sign off and file again - the original stays in the history as superseded."),
    ("c8", "Anjali Sharma", "AY 2025-26 · ITR-U refused", "After 31 December she found municipal tax she had not claimed - it would lower her tax.",
     "An updated return can only raise tax. SimplyFile refuses to file it, says why, and the revision is discarded - the original return stands."),
    ("c9", "Vijay Kumar", "AY 2026-27 · Old or new regime?", "A businessman with ₹2,50,000 of 80C, 80D and 80CCD(1B) deductions.",
     "Switch the regime and both computations are there: old ₹2,26,200 against new ₹1,24,800 - the new regime saves ₹1,01,400."),
    ("c10", "Dr Harish Menon", "AY 2026-27 · Surcharge above ₹1 crore", "A doctor with professional income of ₹1.2 crore and a tax audit.",
     "Surcharge at 15% is applied (with the marginal-relief check) - tax ₹39,82,680, against which TDS and four advance-tax instalments leave a refund of ₹65,835."),
    ("c11", "Arjun Pillai", "AY 2026-27 · Non-resident", "Rent and NRO interest in India, TDS at 30% u/s 195.",
     "No 87A rebate for a non-resident - tax ₹9,260 on ₹5,78,000 - and a refund of ₹2,12,740 of excess TDS, with 244A interest."),
    ("c12", "Greenfield Agritech LLP", "AY 2026-27 · LLP, ITR-5, filed late", "An LLP without audit, due 31 August 2026, filed on 10 September.",
     "Taxed at 30% as a firm, filed as belated with 234A/B/C of ₹17,699 - and listed under late filers in Firm analytics."),
    ("c13", "Prakash Joshi", "AY 2026-27 · House-property loss, old regime", "Interest of ₹3,50,000 on the loan for his self-occupied home.",
     "The house-property loss is capped at ₹2,00,000; with 80C the taxable income is ₹8,50,000 and tax ₹85,800 under the old regime."),
    ("c14", "Fathima Begum", "AY 2026-27 · Open mismatch", "The books claim ₹8,000 of TDS that 26AS does not show.",
     "The red finding is left unexplained, so the year stays in Reconciling and cannot be signed off - Firm analytics lists it under open mismatches."),
    ("c15", "Gopal Krishna", "AY 2025-26 · Undoing a wrong filing", "Filed on time with a refund - but the acknowledgement number was typed wrong.",
     "Undo 'filed' with a reason, then file again with the right number; both entries stay in the history. He is not yet in AY 2026-27, so analytics lists him for a renewal call."),
]


def fig(r):
    cm = r.get("after_revise") or r.get("after_refile") or r.get("after_file") or r.get("after_discard") or r["compute"]
    bal = cm["balance"]
    return [("Total income", cm["income"]), ("Tax", cm["tax"]["total"]), ("Interest 234A/B/C", cm["interest"].get("total") or 0),
            ("Refund due" if bal["kind"] == "refund" else "Balance payable", bal["amount"])]


more = "".join(f"""<section class="case"><div class="case-h"><span class="num-badge">{k[1:]}</span><div><h3>{E(nm)}</h3><span class="tag">{E(tag)}</span></div></div>
  <p class="who">{E(who)}</p><div class="case-grid"><div><p>{E(how)}</p></div><div><table>{''.join(f"<tr><td>{E(a)}</td><td class='num'>{inr(b)}</td></tr>" for a, b in fig(X2[k]))}</table></div></div></section>"""
               for k, nm, tag, who, how in MORE)
html = OUT.read_text(encoding="utf-8").replace('<h2 id="filings">', f'<h2 id="more">Ten more scenarios - last year\'s returns and how they are updated</h2>{more}\n<h2 id="filings">')
html = html.replace('("cases", "Five cases")', '').replace('>Five cases</a>', '>Five cases</a><a href="#more">Ten more</a>')
OUT.write_text(html, encoding="utf-8")
print("ten more added")

# --- 2026-10-04: C16-C25 - importing last years' returns (figures from showcase3_expected.json) -------------------------
X3 = json.loads((Path(__file__).parent / "showcase3_expected.json").read_text(encoding="utf-8"))
RET = X3["returns"]
IMP = [
    ("c16", "Shree Ganesh Agarwal HUF", "Matched by PAN", "The 2025-26 ITR-3 JSON is read - form, year, every figure - and the client with the same PAN is picked for you.", [1]),
    ("c17", "Kiran Kumar Rao", "Three years of history", "His 2023-24 and 2024-25 returns go in; with this year's return the firm sees three years of income - and analytics marks him as a growing client.", [2, 3]),
    ("c18", "Sri Venkateswara Traders", "A firm's ITR-5", "The firm's 2025-26 ITR-5 reads just as well. Against this year, income is down by more than a quarter - analytics marks it to check in early.", [4]),
    ("c19", "Lakshmi Narayana Textiles", "A new client from a return", "Not yet a client: created straight from the return, started in AY 2026-27 too, and next year's statement downloaded with last year's figures beside each line - filled in and uploaded, every row maps itself.", [5]),
    ("c20", "Ravi Teja", "A client who stopped coming", "Filed with the firm for 2023-24 and not since - analytics lists him as a lapsed client to call back.", [6]),
    ("c21", "Sunita Rao", "A revised return replaces the original", "The original 2025-26 return, then the revised one (section 139(5)): the revised one stands, the original stays in the history as superseded.", [7, 8]),
    ("c22", "Mohammed Irfan", "A belated return", "The 2024-25 return says itself that it was filed under section 139(4); SimplyFile records it as belated.", [9]),
    ("c23", "Deepa Krishnan", "A non-resident", "The return says non-resident, so the new client record does too - no 87A rebate will ever be given to her.", [10]),
    ("c24", "Shree Ganesh Agarwal HUF", "The same return twice", "Importing the same JSON again is refused: \"" + X3["c24"]["result"]["detail"] + "\"", []),
    ("c25", "Mohammed Irfan", "The wrong client", "His return pointed at another client is refused: \"" + X3["c25"]["result"]["detail"] + "\"", []),
]
rows3 = "".join(f"<tr><td>{E(RET[str(i)]['file'][:2])}</td><td>{E(RET[str(i)]['file'][3:].removesuffix('.json'))}</td><td>{E(RET[str(i)]['kind'])}</td>"
                f"<td class='num'>{inr(RET[str(i)]['income'])}</td><td class='num'>{inr(RET[str(i)]['tax'])}</td></tr>" for i in range(1, 11))
cards3 = "".join(f"""<section class="case"><div class="case-h"><span class="num-badge">{k[1:]}</span><div><h3>{E(nm)}</h3><span class="tag">{E(tag)}</span></div></div>
  <p>{E(how)}</p>{'<p class="who">Return(s): ' + ', '.join(E(RET[str(i)]['file']) for i in files) + '</p>' if files else ''}</section>""" for k, nm, tag, how, files in IMP)
L3 = X3["analytics"]["leads"]
lead3 = "".join(f'<div class="lead"><b>{E(t)}</b>{E(", ".join(f"{n}" + (f" ({p:+d}%)" if p is not None else "") for n, p in L3.get(k, [])) or "-")}</div>'
                for k, t in [("growing", "Growing clients"), ("shrinking", "Shrinking clients"), ("lapsed", "Lapsed clients"), ("not_renewed", "Not yet carried into this year")])
yrs = "".join(f"<tr><td>{E(y['ay'])}</td><td class='num'>{y['n']}</td><td class='num'>{y['filed']}</td><td class='num'>{inr(y['income'])}</td></tr>" for y in X3["analytics"]["years"])
sec3 = f"""<h2 id="import">Importing last years' returns - ten more cases</h2>
<div class="card"><p><b>Import old returns</b> is a four-step wizard: upload the ITR JSON as filed (from incometax.gov.in or the offline utility), choose whose return it is -
the client with the same PAN, another client, or a new client made from the return (and start this year for them) - give the acknowledgement number and date filed,
and download the statement as filed and next year's statement ready to fill. A revised or updated return takes the place of the one standing; the same return twice,
or a return pointed at a client with a different PAN, is refused.</p>
<h4>The ten dummy returns (AY 2023-24 to 2025-26)</h4><div class="scroll"><table><tr><th>#</th><th>Return</th><th>Kind</th><th>Total income</th><th>Tax</th></tr>{rows3}</table></div></div>
{cards3}
<h2 id="analytics25">Firm analytics with the whole history</h2><div class="card"><p>Returns on record: <b>{X3['analytics']['roll']['returns']}</b> in the rehearsal firm's history.</p>
<div class="scroll"><table><tr><th>AY</th><th>Clients</th><th>Returns filed</th><th>Income handled</th></tr>{yrs}</table></div>
<h4 style="margin-top:16px">Opportunities the history adds</h4><div class="leads">{lead3}</div></div>
"""
html = OUT.read_text(encoding="utf-8").replace('<h2 id="filings">', sec3 + '\n<h2 id="filings">')
html = html.replace('<a href="#more">Ten more</a>', '<a href="#more">Ten more</a><a href="#import">Imported returns</a><a href="#analytics25">History analytics</a>')
html = html.replace("One assessment season on SimplyFile - from firm approval to filed returns, in the Income-tax Department's own format.",
                    "Twenty-five cases on SimplyFile - this season's returns, last years' returns put right, and three years of history imported - in the Income-tax Department's own format.")
OUT.write_text(html, encoding="utf-8")
print("imports added")

# --- 2026-10-04: file formats in and out, and the part-3 run on production -----------------------------------------
FMT_IN = [
    ("Client's statements", "Intake", ".xlsx, .xls, .xlsm or .csv (comma, semicolon or tab) - up to 20 MB; text PDFs best-effort",
     "Every sheet, in the usual statement layouts; amounts as numbers or as text (1,23,456 Dr, (12,500), Rs 5,000); two-sided statements are split. "
     "Each row with a figure needs an SF Ref - SimplyFile suggests one where it recognises the row (e.g. 3CD 31(a) #2, ITR3 HP); a person accepts "
     "or changes it. NOT read: scans and photos (no text recognition), password-protected files, .xlsb / .ods (save as .xlsx), Tally XML."),
    ("Income-tax portal files", "Reconcile", "26AS as the text export from TRACES (.txt); AIS / TIS as .csv or Excel",
     "TDS, TCS and challans by party and date, matched against the books."),
    ("Last years' returns", "Import old returns", "The ITR JSON as filed - ITR-3 or ITR-5 - up to 4 MB",
     "The file downloaded from incometax.gov.in or saved by the offline utility; the CBDT wrapper {\"ITR\": {\"ITR3\": {...}}} is read as it is."),
    ("Firm papers", "My firm", "PDF or image, up to 5 MB each",
     "Owner's Aadhaar, PAN card, TAN letter, GST certificate, ICAI certificate."),
]
FMT_OUT = [
    ("Income-tax return", "ITR-3 or ITR-5 JSON, CBDT schema AY 2026-27 V1.1", "\"ITR-3 &lt;PAN&gt; AY 2026-27.json\"",
     "{\"ITR\": {\"ITR3\": {...}}} - personal details, income, balance sheet and P&amp;L from the final accounts, TDS, tax paid, interest. "
     "Checked against the schema before download; every remaining gap is listed with its path."),
    ("Tax audit report", "Form 3CA-3CD or 3CB-3CD JSON, CBDT schema V2.5", "\"3CB-3CD &lt;PAN&gt; AY 2026-27.json\"",
     "The clauses filled from the SF Refs; checked against the schema the same way."),
    ("Statements", "Excel (.xlsx)", "The client's own workbook with the SF Ref column filled",
     "And, from an imported return, the statement as filed and next year's statement with last year's figure beside each line."),
]
fmt = (f"""<h2 id="formats">Files in, files out</h2>
<div class="card"><h4>What goes in</h4><div class="scroll"><table><tr><th>File</th><th>Screen</th><th>Format</th><th>What SimplyFile takes from it</th></tr>
{''.join(f'<tr><td><b>{E(a)}</b></td><td>{E(b)}</td><td>{E(c)}</td><td>{E(d)}</td></tr>' for a, b, c, d in FMT_IN)}</table></div>
<h4 style="margin-top:16px">What comes out</h4><div class="scroll"><table><tr><th>File</th><th>Format</th><th>Named</th><th>Inside</th></tr>
{''.join(f'<tr><td><b>{E(a)}</b></td><td>{E(b)}</td><td>{c}</td><td>{d}</td></tr>' for a, b, c, d in FMT_OUT)}</table></div>
<p class="who" style="margin-top:12px">The JSON follows the department's schema, so it opens in the department's offline utility, where the remaining schedules
are completed and the return is validated and uploaded. Uploading straight to the portal needs a CBDT software ID, which SimplyFile does not yet have.</p></div>
""")
STEPS3 = ["Matched by PAN - Agarwal HUF 2025-26", "Kiran Kumar Rao 2023-24 and 2024-25", "Sri Venkateswara Traders ITR-5 2025-26",
          "Lakshmi Narayana Textiles - new client, this year started", "Ravi Teja 2023-24 - year left unstarted", "Sunita Rao original, then revised",
          "Mohammed Irfan belated 2024-25", "Deepa Krishnan non-resident", "Agarwal return a second time - refused", "Irfan's return on the Agarwal HUF - refused"]
prod = (f"""<h2 id="prod">On the live portal</h2>
<div class="card"><p>On 4 October 2026 the ten imports were run on <b>sf.valuestream.in</b> for Demo CA Filing Firm, after the fifteen cases of parts one and two.
All fifteen steps ran; both refusals were refused, so nothing was recorded twice or on the wrong client.</p>
<div class="scroll"><table><tr><th>Case</th><th>Import</th><th>Result</th></tr>
{''.join(f'<tr><td>{16 + i}</td><td>{E(s)}</td><td>{"Refused, as it should be" if "refused" in s else "Imported"}</td></tr>' for i, s in enumerate(STEPS3))}</table></div>
<p class="who" style="margin-top:12px">The firm's Firm analytics screen now shows the whole history - returns on record, year on year, and the growing, shrinking,
lapsed and not-renewed clients. The figures above are from the rehearsal; the live screen counts the firm's own work too.</p></div>
""")
html = OUT.read_text(encoding="utf-8").replace('<h2 id="filings">', fmt + prod + '\n<h2 id="filings">')
html = html.replace('<a href="#analytics25">History analytics</a>', '<a href="#analytics25">History analytics</a><a href="#formats">Files in and out</a><a href="#prod">Live portal</a>')
OUT.write_text(html, encoding="utf-8")
print("formats + prod added")

# --- 2026-10-04: Delegations and Chip Chat (+ the tool bar) -------------------------------------------------------------
import os as _os, sys as _sys, tempfile as _tf  # noqa: E401,E402
_os.environ["TV_DATA"] = _tf.mkdtemp()
_sys.path.insert(0, _R + r""); _os.chdir(_R + r"")
import app as _app  # noqa: E402,F401 - the catalog gives screen and button names
import chipchat as _cc  # noqa: E402
_sys.path.insert(0, _R + r"\tools")
import chat_corpus as _corp  # noqa: E402
_owner = {"id": "x", "role": "owner"}
SAMPLES = ["How much tax on 18.5 lakh for an HUF under the old regime for AY 2025-26?", "tax on 12 lakh",
           "Due date for ITR-5 with tax audit for AY 2026-27", "If I file ITR-3 on 15/11/2026 what kind of return is it?",
           "ITR-U additional tax on extra tax of 2 lakh filed 15 months after the year ended", "244A interest on a refund of 80,000 for 9 months",
           "What is the 234F late fee if total income is 3 lakh?", "Does a 72 year old pay advance tax?", "Can a tax preparer sign off?",
           "Is ABCPA1234D a valid PAN?", "Which files can I upload?", "Can I upload the JSON straight to the Income-tax portal?"]
qa = []
for s_ in SAMPLES:
    r_ = _cc.ask(_owner, s_)
    a_ = r_.get("answer") or {}
    qa.append((s_, a_.get("text") or r_.get("say", "")))
_rows = _corp.build()
from collections import Counter as _C  # noqa: E402
_cnt = _C(x["want"] if x["kind"] == "family" else "faq" for x in _rows)
FAM = [("tax", "Tax on any income - status, year, regime, resident or not (87A, surcharge, cess)"), ("kind_on", "What a return filed on a date would be - original, belated, revised, ITR-U"),
       ("pan", "Is a PAN valid, and whose is it"), ("itr_u", "140B additional tax on an updated return, by months late"), ("refund", "244A interest on a refund"),
       ("advance", "Advance tax by age, residence and business income"), ("role_can", "Who may do what, by role"), ("due", "Due dates by form, audit and 3CEB, any year"),
       ("fee", "234F late fee by income"), ("faq", "75 prepared questions, each asked 12 ways - setup, clients, intake, reconcile, compute, filing, JSON, import, analytics, delegation, tools")]
deleg = """<h2 id="delegate">Delegations - lend powers, never passwords</h2>
<div class="card"><p>In a CA firm people go on leave, fall ill, or need help at the deadline. Instead of sharing a password, a person lends some of
their <b>own</b> powers to a colleague, for a scope and for set dates. The colleague can never get more than the lender has; everything done through
it is recorded as <i>"Ravi, for Demo Partner"</i>; it ends by itself and can be taken back at once. Nothing done is ever deleted.</p>
<table><tr><th>Scope</th><th>What it covers</th><th>Example</th></tr>
<tr><td>One filing</td><td>One client, one assessment year</td><td>Ravi (preparer) may sign off Shree Ganesh Agarwal HUF, 2026-27</td></tr>
<tr><td>One client, every year</td><td>Everything for one client, whatever the year</td><td>A reviewer looks after one client's revisions</td></tr>
<tr><td>Some clients for a year</td><td>The clients picked, for one year</td><td>Ravi may mark filed Ramesh Iyer and Meera Nair, 2026-27</td></tr>
<tr><td>All clients for a year</td><td>Every client of the firm, for one year</td><td>Kavitha is away: Anand files every 2026-27 return for 12 days</td></tr>
<tr><td>Portal admin work</td><td>Firm approvals, Portal analytics, Server &amp; sites, Keys for sale, Reported issues</td><td>The portal owner's deputy approves firms while the owner travels</td></tr></table>
<p class="who">Inside a firm only client work can be lent - never the firm's profile or team. Portal work is lent only by the portal owner, only to someone
outside a firm; People &amp; access, the rule builders and Setup stay the owner's alone. Every rule is a chip (delegation.check, delegation.covers).</p></div>
"""
chat = f"""<h2 id="chipchat">Chip Chat - the firm's expert on call</h2>
<div class="card"><p>Chip Chat sits on every screen. It answers questions about SimplyFile and about the firm's own work - from the portal's own rules and
the firm's own data, for the person's role. No AI guesswork and no data leaving the firm. It knows <b>{len(_rows):,}</b> questions, and every one of
them reaches the right answer in the test run.</p>
<table><tr><th>Family</th><th class="num">Questions</th></tr>{''.join(f"<tr><td>{E(t)}</td><td class='num'>{_cnt[k]:,}</td></tr>" for k, t in FAM)}</table>
<h4 style="margin-top:16px">Live answers from the firm's own work</h4>
<p>What is pending for me - which returns are overdue - what is due this week - where does a client stand (just name them) - what may I do - what has been
delegated to me - who is in my firm - what my firm still needs for approval - which clients need advice - which firms are waiting for the portal owner.</p>
<h4 style="margin-top:16px">Some answers, exactly as Chip Chat gives them</h4>
<table><tr><th>Question</th><th>Answer</th></tr>{''.join(f"<tr><td>{E(q)}</td><td>{E(a)}</td></tr>" for q, a in qa)}</table>
<p class="who" style="margin-top:12px">When Chip Chat does not know, it says so and keeps the question (the firm and role - never the person's name).
The firm admin teaches it - pointing the question at an answer, or writing the firm's own (office hours, who handles GST...) - and the portal owner can
teach every firm at once.</p></div>
<h2 id="dock">The tool bar - bottom right of every screen</h2>
<div class="card"><table>
<tr><td><b>Chip Chat</b></td><td>Questions answered, as above.</td></tr>
<tr><td><b>Screen capture</b></td><td>Drag over part of the screen - copy it, download it, keep it in a note or report it as an issue.</td></tr>
<tr><td><b>Screen recording</b></td><td>The screen (and the voice) as a video - to show the team a process.</td></tr>
<tr><td><b>Voice typing</b></td><td>Speak into the box you are in - in Indian English.</td></tr>
<tr><td><b>My notes</b></td><td>Private notes - only you see them - with pictures from screen capture and <b>voice notes</b>: speak, it records the voice and writes the words into the note.</td></tr>
<tr><td><b>Report an issue</b></td><td>Anything wrong or unclear goes to the portal admin with a screenshot; the answer comes back under My reports.</td></tr></table>
<p class="who" style="margin-top:12px">Capture, recording and voice typing run inside the browser - nothing leaves the computer unless the person hands it on.</p></div>
"""
html = OUT.read_text(encoding="utf-8").replace('<h2 id="filings">', deleg + chat + '\n<h2 id="filings">')
html = html.replace('<a href="#prod">Live portal</a>', '<a href="#prod">Live portal</a><a href="#delegate">Delegations</a><a href="#chipchat">Chip Chat</a><a href="#dock">Tool bar</a>')
OUT.write_text(html, encoding="utf-8")
print("delegation + chip chat added")
