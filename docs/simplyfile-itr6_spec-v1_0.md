# ITR-6 - a company's return (AY 2026-27)

Built 2026-10-11. A domestic company (PAN 4th letter **C**) goes the firm road that ITR-3 / ITR-5 use - Clients & years,
Intake & map, Reconcile, Compute & close, Tax audit - with no second engine: `company.py` gathers the facts and asks the
chips `company.*`; `compute.compute()` takes the company's heads, total income and tax from it and keeps everything else
(TDS / challans from 26AS, 234A/B/C, the balance, sign-off, filing, revisions) as it is. The ITR-6 JSON is built by
`itr_json.py` from chip `itr.map` (504 ITR-6 rows) and `itr.books` (Schedule III layout) and checked against the CBDT
schema before download.

## What is supported

| Area | What the portal does | Chip |
|---|---|---|
| Client master | Status *Company (domestic)*, form ITR-6; CIN (MCA 21-character shape), date of incorporation, kind (private / public unlisted / listed / OPC), tax option (normal, 115BA, 115BAA, 115BAB) with the AY first opted and the Form 10-IB/IC/ID ack and date, manufacturing, MSME, Ind AS, nature-of-business code, directors (DIN, PAN, designation, father's name, address) and shareholders (%, shares, face value, issue price, allotment date) | `clients.settings`, `company.settings`, `company.problem` |
| Rate | Normal 25% when the turnover of PY 2023-24 is within 400 crore, else 30% (blank turnover -> 30% and a warning); 115BA 25%; 115BAA 22%; 115BAB 15% on the business, 22% on the rest | `company.rate` |
| Surcharge, cess | 7% above 1 crore, 12% above 10 crore with marginal relief; flat 10% under 115BAA / 115BAB; 4% cess; rounded to 10 | `company.tax` (`company.tax_s1`, `_s2`) |
| Special rates | STCG 111A 20%, LTCG 112A 12.5% above 1.25 lakh, LTCG 112 12.5% (Schedule SI) | `company.tax` |
| MAT | 15% of book profit (with its own surcharge, marginal relief and cess) when higher than the normal tax; none under 115BAA / 115BAB | `company.mat` |
| MAT credit | Excess of MAT over normal tax becomes a credit; brought-forward credit set off oldest first up to (normal - MAT), 15 AYs; none usable under 115BAA / 115BAB | `company.mat`, `company.loss_ok`, `company.setoff` |
| Depreciation | Per block from the fixed-asset schedule: WDV, additions 180 days or more / less (half rate), sales first out of the full-rate part, additional 20% on new P&M of a manufacturing company (half now, half carried), s.50 gain when a block is sold beyond its WDV | `company.dep_block` |
| Business income | The computation statement line by line: profit before tax, book depreciation added back, s.32 depreciation, CSR (Explanation 2 to s.37(1)), s.36 / 37 / 40 / 40A / 43B (incl. 43B(h) MSME) added back, other-head income taken out, 43B / 40(a) paid this year allowed | `company.settings` `bp_items` |
| Losses | CYLA: house-property loss up to 2 lakh, business loss against other heads; capital losses inside the head (s.74). BFLA: business loss b/f against business income only, within 8 AYs, return in time (s.80), s.79 51% test for a closely held company; unabsorbed depreciation without limit against any head. CFL / UD: what is carried | `company.setoff`, `company.loss_ok` |
| Deductions | 80M (dividends passed on a month before the due date - also under 115BAA); 80G (no-limit and 10%-qualifying-limit categories, the CSR Kosh proviso; none under 115BAA / 115BAB); VI-A never against special-rate gains | `company.d80m`, `company.d80g`, `company.rate` via |
| Due date | 31 October for every company (s.139(1) Expl. 2(a)), with or without a 44AB audit; 30 November with Form 3CEB; the AY 2026-27 CBDT extension of the audit date (Circular 07/2026 as recorded in `close.dates`) applies; the JSON's `ItrFilingDueDate` stays the Act's date; 234A from the due-date rule as for ITR-3 / 5 | `close.dates` `audit_forms` |
| Tax audit | Form **3CA**-3CD (accounts audited under the Companies Act), PartA status 5; the existing 3CD clause machinery | `tar.settings`, `tar.codes` |
| ITR-6 JSON | Part A-GEN 1 / 2 (CIN, kind, option and its form, turnover band, 44AB / 92E, key persons, holders of 10%+, nature of business, unlisted flag, MSME), Part A-BS / P&L / Trading / Manufacturing (Schedule III, from `ITR6 BS / PL <item>` rows), Schedule BP, DPM / DOA / DEP, OS, CG totals, CYLA, BFLA, CFL, UD, SH-1, MAT, MATC, SI, 80G (each donee from the party master), VI-A, TDS2, IT, Part B-TI / TTI (deemed income u/s 115JB, credit u/s 115JAA), bank (current / CC / OD accounts), verification by the managing director | `itr.map` ITR-6, `itr.books` form_items, `itr.codes` by_form ITR-6, `itr.settings` |

Screens: **Clients & years** shows a *Company (ITR-6)* box for status Company (`static/company.js`); **Compute & close**
shows a company section (rate and why, depreciation by block, losses set off and carried, 80M / 80G, MAT and credit, and
the year's facts to type: turnover of PY 2023-24, s.79, dividend paid and date, option exercised this year, audit report
date / ack, losses b/f by AY, MAT credit b/f by AY). The computation Excel carries depreciation by block and MAT.

## SF Refs for a company (Intake & map)

| Ref | Means |
|---|---|
| `ITR6 BP <item>` | a line of the computation statement: `profit`, `tax`, `book_dep`, `it_dep`, `csr`, `s36`, `s37`, `s40`, `s40a`, `s43b`, `other_add`, `dividend`, `os_income`, `cg_income`, `hp_income`, `exempt`, `s43b_paid`, `s40_paid`, `other_less` (no item: the label's words decide add or less) |
| `ITR6 DEP <block>` | a block of the fixed-asset schedule: `pm15`, `pm30`, `pm40`, `pm45`, `bldg5`, `bldg10`, `bldg40`, `furn10`, `intang25`, `ships20`; columns read by their titles (opening WDV, additions 180 days or more / less, sale, new P&M 180+ / under 180, additional depreciation b/f) |
| `ITR6 MAT <item>` | Form 29B book profit: `pat`, `add_tax`, `add_reserve`, `add_provision`, `add_dividend`, `add_exempt_exp`, `add_reval_dep`, `add_other`, `less_reserve`, `less_exempt`, `less_bf`, `less_other` (no MAT rows: the P&L profit before tax, flagged) |
| `ITR6 OS <item>` | `dividend`, `interest`, `deposit`, `refund`, `rent`, `other` |
| `ITR6 CG <item>` | `stcg_111a`, `stcg`, `ltcg_112a`, `ltcg_112` (a loss is a negative figure) |
| `ITR6 80G <category>` | `100`, `50`, `100q`, `50q`, `csr_kosh`; the row's words are the donee (PAN and address from the party master) |
| `ITR6 BS <item>`, `ITR6 PL <item>` | the Schedule III balance sheet and P&L items of chip `itr.books` form_items ITR-6 (same names as ITR-3 / ITR-5 plus share capital, securities premium, director loans, current maturities, CSR expenditure, the manufacturing account's raw material / WIP / wages) |

## Sources (official, downloaded 2026-10-11)

| What | URL | Kept at |
|---|---|---|
| ITR-6 JSON schema V1.0, AY 2026-27 (released 04-Aug-2026) | https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-08/ITR-6_2026_Main_V1.0.json | `Requirements/itr6/schema/` (download), copied to `schemas/itr/ITR-6_2026_Main_V1.0.json` |
| ITR-6 validation rules V1.0, AY 2026-27 | https://www.incometax.gov.in/iec/foportal/sites/default/files/2026-08/CBDT__e-Filing_ITR-6_Validation%20Rules_Version%201.0_AY%202026-27.pdf | `Requirements/itr6/validation/`, copied to `schemas/itr/` |
| Downloads page (listing; no ITR-6 schema change document is published) | https://www.incometax.gov.in/iec/foportal/downloads | - |
| Domestic company AY 2026-27 help page (rates, 115BAA / BAB, MAT, forms) | https://www.incometax.gov.in/iec/foportal/help/company/return-applicable | - |
| Memorandum to the Finance Bill 2026 (AY 2026-27 company rates unchanged: 25% within 400 crore of PY 2023-24, surcharge as AY 2025-26, 4% cess; MAT 14% / no new credit only from tax year 2026-27 under the 2025 Act) | https://www.indiabudget.gov.in/doc/memo.pdf | read only (scratch), not kept |

The offline utility (Windows / Mac zip) and the Excel utility were not downloaded (executables / macros). Every
downloaded file was read only as data (`python -I`, JSON / PDF text), nothing run. The validation rules' rate table
(page 63) restates the rates used.

## Files

`company.py` · `compute.py` (the company branch, MAT in the computation Excel) · `clients.py` (the company part) ·
`itr_json.py` (form_items books, dotted `each`, per-form bank codes, `co.*` facts) · `app.py` (`/api/clients/settings`
carries `company`) · `static/company.js`, hooks in `static/page-clients.js` and `static/page-compute.js` ·
chips `company.*` (settings, problem, rate, tax / tax_s1 / tax_s2, mat, dep_block, setoff, loss_ok, d80g, d80m) and the
changed `clients.settings`, `close.dates`, `intake.ref`, `intake.ref_part_ok`, `itr.settings`, `itr.codes`, `itr.books`,
`itr.map`, `tar.settings`, `tar.codes`, `ui.clients`, `ui.compute`, `rulebook.sections`, `guide.compute`, `chat.faq` -
all written by `tools/make_itr6_chips.py` (re-runnable; every case worked out and checked) · demo
`tools/showcase/company_demo.py` (two invented companies and their documents), `tools/showcase/pre_companies.py`
(the showcase seed) · test `tools/e2e_itr6.py` · tour `tours/sf-company.json` (video `tmp/tour_video/sf-company/`).

## The New filing wizard: what it needs to open the Company card

The wizard (`wizard.py`, chips `wizard.*`) already has a `company` who-card (`flow: firm`, `form: ITR-6`) that shows
*not yet*: chip `wizard.who_state` opens a card only when it is switched on **and** `clients.settings` knows its status.
The status now exists (`company`, PAN letter C, ITR-6), so the one switch left is:

1. chip `wizard.settings` -> `who[id=company]`: `"supported": true` and `"note": ""`;
2. `wizard.py` self-check: `assert _state(_row("company")) == "open"` (it asserts not_yet today);
3. chip `wizard.docs`: for `company` mark required the final accounts / books, the computation of income and the
   fixed-asset schedule (kind `books`), 26AS (and AIS); the GST certificate stays optional (its constitution
   *Private / Public Limited Company* is already in `wizard.constitution`);
4. the client the wizard makes from a company's documents is saved with an empty `company` part (kind private,
   option normal) - the CA completes CIN, option, directors and shareholders on Clients & years (`company.clean`
   accepts the empty part); after that the flow is the firm one (Intake & map -> Reconcile -> Compute & close);
5. Chip Chat: the wizard row saying a company is "not yet" (chip `chat.faq`) changes to point at New filing > A company.

## Not covered yet (honest list)

- Schedule CG's asset-wise rows (only the totals and Schedule SI), AL (assets and liabilities of an unlisted company),
  OI / QD (other information, quantitative details), GST, FA, TPSA, ICDS, ESR, 115TD, FD, IF, HP details - left to the
  department's utility, as ITR-5 leaves them; the JSON is valid without them, the utility asks for what applies.
- Form 29B (the MAT report) is not produced; Ind AS MAT transition adjustments are not worked out.
- s.79(1)(b) start-up relief and s.79(2) exceptions; 115BAA's adjustment of losses / unabsorbed depreciation attributable
  to additional depreciation (`AmtAdjOptTaxUs115BAA` is 0); 115BAB's split of non-manufacturing gains.
- Additional depreciation at 35% (backward areas), SLM for power units.
- 80G on CSR donations other than the Kosh / Ganga funds is left to the category the CA chooses.
- Foreign companies, companies claiming s.11 (ITR-7), IFSC units, presumptive 44AD for a company (not allowed anyway).
- Rates are verified for AY 2026-27 only; another AY uses them with a warning on the screen.
- The ITR-6 schema's `ReceiptNo` (original return's ack on a revision) is passed as typed - the same as ITR-3 / ITR-5.
