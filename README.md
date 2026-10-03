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
| Filing | **Clients & years** · **Intake & map** · **Reconcile** |
| Document | User manuals · How to Use links · Guide Me Builder · Tour Video |
| Portal | Projects & portal · Account & key |
| Account | Buy a key |
| Admin | Keys for sale · People & access · Portal activity · Visitors · Storage · Reported issues · Memory watch · How to Use pages |
| Build | Ops & chips · Rules |

## The Filing screens

- **Clients & years** (`clients.py`): each assessee once — name, PAN, status, address, contacts, GSTIN, banks,
  partners — carried into every assessment year with its form (ITR-3 / ITR-5), 3CD audit flag and stage.
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
| `store.py` `wallet.py` `providers.py` `keyshare.py` `keysales.py` `narrator.py` `media.py` | accounts' AI keys, money, buying and selling key credit |
| `projects.py` `scan.py` `source.py` `manuals.py` `guideme.py` `tourvideo.py` | Projects & portal, How to Use, manuals, Guide Me, Tour Video |
| `core/` | the framework |
| `chips/` `rules/` | every decision |
| `static/` | the screens |
| `tours/` `tools/tour_video/` | narrated tour scripts and their recorder |
| `Requirements/` `SimplyFile-Workflow.html` | the client's material — kept here, never committed |

Deploying: `DEPLOY.md`.
