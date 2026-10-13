# SimplyFile — sf.valuestream.in

Tax filing for a CA office: client master → client statements with an **SF Ref** column → reconcile with 26AS /
AIS / TIS → (next) tax computation and the Form 3CD / ITR-3 / ITR-5 utilities.

Self-contained: this folder is the whole portal. It is built on the same framework as sm.valuestream.in (`core/`:
sign-in, people & access, activity, visitors, storage, memory watch, How to Use, chips & rules), copied in, not linked.
Nothing here reads from or writes to any other project.

## Run it

```bat
start.cmd
```

(`./start.sh` on macOS / Linux.) First run makes `.venv` and installs `requirements.txt`. Opens on
http://localhost:8830; data goes to `data\` (never committed). The first account made becomes the owner.

Check everything, no paid call: `python selfcheck.py`.

## Menus

| Group | Screens |
|---|---|
| Filing | **New filing** · **Clients & years** · **My return** · **Intake & map** · **Reconcile** |
| Document | User manuals · How to Use links · Guide Me Builder · Tour Video |
| Portal | Projects & portal · Account & key |
| Account | Buy a key |
| Admin | Keys for sale · People & access · Portal activity · Visitors · Storage · Reported issues · Memory watch · How to Use pages |
| Build | Ops & chips · Rules |

## The Filing screens

- **My firm - the first screen** (`page-firm.js`, `firms.py`, 2026-10-12): a newcomer with no firm sees only a warm heading and two large cards - "I'm filing my own return (or my family HUF's)" and "I run a CA practice and file for clients" - each with an illustration, one line, small "you'll need" tags and one button; the Start here card waits until a firm exists (chip `start.settings` needs_firm), and the long Keep-these-ready checklist lives inside the chosen kind's own draft. An individual gives four details (name, PAN, mobile, email; kind `self` in `firm.settings`), presses Open my account and lands on New filing at once (`after_approved_route`). A wrong pick is not a trap: *Not what you meant? Choose again* (confirm) discards a draft with nothing uploaded and nobody else in it (`POST /api/firm/discard`). Words are `ui.firm` (kind words are keys suffixed with the kind id, e.g. `pick_self`, `f_name_self`); the cards' art is `page.firm` kind_art. Test: `tools/e2e_demo.py` step 1b.
- **New filing** (`wizard.py`, `static/page-wizard.js`, 2026-10-11): the guided way in - say who the return is for and what applies (plain-word cards, the section small), see the documents it needs and where to get each, drop them in. Each file is identified by My return's own readers (type, PAN, name, AY, TAN); the client is made from the PAN and name found (or found by PAN), a popup asks only what is missing or does not agree, and the documents' hints ask for more (fund sales -> CAMS, 194IA -> the property sale, a second TAN -> that Form 16). Then My return opens at the right step. Progress is kept on the server (carry on later). Chips `wizard.*`, `myreturn.sniff`, words `ui.wizard`; test `tools/e2e_wizard.py`; tour `tours/sf-wizard.json`. Later the same day it covers every return: a person, an HUF, a partnership firm, an LLP, an AOP / BOI, a company (the firm flow - the GST certificate makes the client, the deed's partners in the popup, each document into Intake & map / Reconcile / Tax audit), with "What kind of work?" for a business; a company (ITR-6, its certificate of incorporation makes the client) - and a trust shows as not yet (one chip switch). Every path, its worked example (demo seed `tools/showcase/pre_cases.py`) and its film (`tours/sf-case-*.json`): **[FILING-PATHS.md](FILING-PATHS.md)**.
- **Small business - only a bank statement** (`bankclass.py`, `static/myreturn-bank.js`, chips `bank.*`, 2026-10-13): no books, no Form 16 - the statement alone. It is read row by row and reconciled (opening + credits - debits = closing), each credit and debit is grouped by who it is with and pre-classified (customer receipts, own money, loan, refund, interest, cash), the person taps what only they can tell, and the turnover, the 6% / 8% presumptive profit (s.44AD), the GST registration limit, the late fee and the ITR-4 JSON follow. Worked example `sf-case-bank-only`; FILING-PATHS.md; `tools/e2e_bankonly.py`.
- **Tour recorder privacy mask** (`tools/tour_video/make_tour.py`, chip `tour.mask`): `TOUR_MASK=1` (or a tour's `"mask": true`) blurs PANs, Aadhaar, account numbers, phones, e-mails, UPI ids, addresses and the names in `TOUR_MASK_WORDS` before every frame, and a value left readable fails the recording.
- **Clients & years** (`clients.py`): each assessee once — name, PAN, status, address, contacts, GSTIN, banks,
  partners — carried into every assessment year with its form (ITR-3 / ITR-5 / ITR-6), 3CD audit flag and stage.
- **A company's return - ITR-6** (`company.py`, `static/company.js`, 2026-10-11): status *Company* (PAN letter C) with its
  CIN, option (normal / 115BA / 115BAA / 115BAB), directors and shareholders; the same Intake & map (refs `ITR6 BP / DEP /
  MAT / OS / CG / 80G / BS / PL`), Reconcile and Compute & close, where a company section works out depreciation by block,
  losses set off and carried (s.72, s.79, unabsorbed depreciation), 80M / 80G, MAT u/s 115JB and its credit, and the
  ITR-6 JSON checked against the CBDT schema; audit report 3CA-3CD; due 31 October. Chips `company.*`
  (`tools/make_itr6_chips.py`); test `tools/e2e_itr6.py`; demo `tools/showcase/pre_companies.py`; tour `tours/sf-company.json`.
  Everything, the sources and what is left: **[docs/ITR6.md](docs/ITR6.md)**.
- **Intake & map** (`intake.py`): the client's Excel (.xls / .xlsx / .csv, Tally exports included) per year. Every
  row with a figure gets an **SF Ref** — `3CD 31(a) #2`, `ITR3 HP`, several joined with `;` — from a person, from the
  file's own SF Ref column, or from a suggestion a person accepts. Download the workbook back with the column filled.
- **Reconcile** (`recon.py`): 26AS (TRACES text export) and AIS / TIS (CSV / Excel) against the books — TDS per
  deductor, income per head, tax-paid challans. Red findings must be fixed or explained before a year moves to Review.

## Chips and ops

Every threshold, pattern, rule table, decision and word is a chip in `chips/` (the framework's own in `core/chips/`),
built from the framework's ops and proved by its own test cases — edit in **Build → Ops & chips**, no code change.
SimplyFile's decisions: `clients.problem`, `clients.shape_ok`, `intake.ref_part_ok`, `intake.suggest`,
`intake.row_state`, `recon.agrees`, `recon.verdict`, `recon.groups`, `recon.same_party`, `recon.blocks`.
Python only reads files and asks the chips.

## Email (SMTP) — once here, once on the server

Owner → **Projects & portal → Portal & sign-up**: set the portal address, then **Email (SMTP)**:

| | Gmail | Hostinger mailbox |
|---|---|---|
| SMTP server | `smtp.gmail.com` | `smtp.hostinger.com` |
| Port · Security | `587` · `starttls` | `465` · `ssl` |
| Username / Send from | your full Gmail address | the full mailbox address |
| Password | a 16-character App Password (Google → Security → 2-Step Verification → App passwords) | the mailbox password |
| Sender name | `SimplyFile` | `SimplyFile` |

Press **Send a test email**, then pick **Who may sign up** (`closed` or `domain` for an office). The password stays in
that site's `data/` folder, never in git.

## Folder

| | |
|---|---|
| `app.py` | the routes |
| `clients.py` `intake.py` `recon.py` | the Filing screens |
| `compute.py` `company.py` `itr_json.py` | the computation (a company's in `company.py`), the ITR / 3CD JSON |
| `store.py` `wallet.py` `providers.py` `keyshare.py` `keysales.py` `narrator.py` `media.py` | accounts' AI keys, money, buying and selling key credit |
| `projects.py` `scan.py` `source.py` `manuals.py` `guideme.py` `tourvideo.py` | Projects & portal, How to Use, manuals, Guide Me, Tour Video |
| `core/` | the framework |
| `chips/` `rules/` | every decision |
| `static/` | the screens |
| `tours/` `tools/tour_video/` | narrated tour scripts and their recorder |
| `Requirements/` `SimplyFile-Workflow.html` | the client's material — kept here, never committed |

Deploying: `DEPLOY.md`.
