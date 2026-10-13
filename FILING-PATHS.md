# Filing paths - every way into a return, its worked example and its film

2026-10-11. **New filing** (`#/wizard`, `wizard.py` + `wizard_firm.py`, `static/page-wizard.js`) is the first thing a firm sees: the
who-cards sit on the Clients & years hero and on the New filing start screen. Every word, card, document list, rule and route is a
chip (`wizard.*`, `ui.wizard`, `guide.wizard`); `tools/make_wizard_chips.py` writes them with their test cases.

## Who, and where the return is made

| Card | Status (PAN 4th letter) | Form | Flow |
|---|---|---|---|
| Myself (self-filer's desk) | individual (P) | ITR-1 / 2 / 3 / 4 | My return |
| An individual - salaried, pensioner, investor, professional, business owner | individual (P) | ITR-1 / 2 / 3 / 4 | My return |
| A family HUF | huf (H) | ITR-2 / 3 / 4 | My return |
| A partnership firm | firm (F) | ITR-5 (+ 3CD) | firm flow: Intake & map -> Reconcile -> Tax audit -> Compute & close |
| An LLP | llp (F) | ITR-5 (+ 3CD) | firm flow |
| An AOP or BOI | aop (A) / boi (B) - the PAN decides | ITR-5 | firm flow |
| A company | company (C) | ITR-6 (+ 3CD) | firm flow - the certificate of incorporation makes the client (CIN, date, directors); the popup takes the tax option (normal / 115BA / 115BAA / 115BAB) and manufacturing; company.py computes (MAT, 115BAA ...) |
| A trust | - | ITR-7 | **not yet** - one switch: `wizard.settings` who[trust].supported (opens once clients.settings has a trust status) |

A not-yet card says so in one line (`ui.wizard` ny_trust) and offers an individual's return instead or Clients & years - never a
dead end. The company card was switched on the same night, once ITR-6 was built (`company.py`, docs/ITR6.md): its documents are the
certificate of incorporation (`coi`, read by `wizard.entity_sniff`), the final accounts, computation of income and fixed-asset
schedule (kind books), 26AS / AIS and the GST certificate.

**What kind of work** (`wizard.scenarios` group work; shown for a business, and for a person or an HUF once "A business or
profession" is picked - `wizard.work_open`): trading, manufacturing, services, a profession, farming, registered for GST,
small turnover on the presumptive basis (44AD / 44ADA - not for an LLP or an AOP), full books (44AA), tax audit (44AB, Form 3CD),
partners' salary and interest (40(b) - firm or LLP only), stock and inventory, depreciation. Presumptive and books rule each other
out; a tax audit brings the books. A person's kind of work becomes My return's business kind (`wizard.biz_kind`).

**A business's documents** are identified by `wizard_firm.read` (chip `wizard.entity_sniff`): the GST certificate (REG-06 - GSTIN,
legal name, constitution -> status by `wizard.constitution`), the partnership deed / LLP agreement / agreement of association (the
partners' names, PANs and shares - shown in the popup to confirm), the books in Excel; GSTR-3B / GSTR-1 JSON (or their zip) by the
tax audit's reader, last year's ITR-5 JSON by the old-returns reader, 26AS / AIS / bank by My return's. Where each goes: chip
`wizard.route` (books and bank -> Intake & map, 26AS / AIS / TIS -> Reconcile, GST returns -> Tax audit, certificate and deed ->
the client). The client is made with its status, GSTIN and partners, and its year set (ITR-5, audit, 44AD). Review opens the
next firm screen (`wizard.firm_next`).

## The worked examples (chip `wizard.cases`)

Each is in the demo seed (`tools/showcase/pre_cases.py`, run by `record_all.sh` after `pre_companies.py` - so the two company
cases find the complete demo companies and their documents "already there"): played through the wizard and left at Review, so
after the nightly reset (21:30 UTC) every one waits under *Carry on where you left off*. Documents: `tools/showcase/make_myreturn_demo.py`
-> `tools/tour_video/showcase/<folder>/` (made up: ZZ... PANs, Demo ... names, @demo.example). Film script: `tours/<film>.json`
(`tools/make_case_tours.py`), recorded by `tools/showcase/record_cases.sh` into `tmp/tour_video/<film>/`, published small by
`tools/showcase/case_films.py` into `static/showcase/<film>.mp4` (New filing's *Watch how*, the landing page's Watch group
"Every filing, step by step").

| # | Case | Who | Form | Documents | Opens | Film |
|---|---|---|---|---|---|---|
| 1 | Salaried, one employer | individual | ITR-1 | pre-filled JSON, Form 16, 26AS, AIS (`case-salaried`) | My return | `sf-case-salaried` |
| 2 | Two employers | individual | ITR-1 | 26AS, Form 16 x2, AIS - the second Form 16 is asked for (`case-two-jobs`) | My return | `sf-case-two-jobs` |
| 3 | Salary + funds sold + a plot sold | individual | ITR-2 | Form 16 x2, locked AIS, 26AS (194IA), CAMS (`wizard-sal`) | My return (Review) | `sf-case-salary-cg-property` |
| 4 | Pensioner with interest | individual | ITR-1 | bank pension Form 16, 26AS, AIS (`case-pensioner`) | My return | `sf-case-pensioner` |
| 5 | Consultant on 44ADA | individual | ITR-4 | pre-filled JSON (194J), bank statement, 26AS, AIS (`case-consultant`) | My return | `sf-case-consultant` |
| 6 | Small trader on 44AD with GST | individual | ITR-4 | pre-filled JSON, GSTR-3B summary, bank, 26AS, AIS (`case-trader`) | My return | `sf-case-trader` |
| 7 | HUF with a house and capital gains | huf | ITR-2 | 26AS, AIS, CAMS - the Karta asked (`wizard-huf`) | My return | `sf-case-huf` |
| 8 | Trading firm with GST and a tax audit | firm | ITR-5 + 3CD | GST certificate, deed, 26AS, books x2, GSTR-3B zip, last ITR-5 (`case-firm-trading`) | Tax audit | `sf-case-firm-trading` |
| 9 | Manufacturing firm, stock and depreciation | firm (Lakshmi Narayana Textiles, already a client) | ITR-5 + 3CD | GST certificate, deed, 26AS, manufacturing books, GSTR-3B zip (`case-firm-mfg`) | Tax audit | `sf-case-firm-mfg` |
| 10 | LLP in services | llp | ITR-5 | GST certificate (LLP), LLP agreement, 26AS (194J), income statement (`case-llp`) | Compute & close | `sf-case-llp-services` |
| 11 | AOP | aop | ITR-5 | agreement of association, 26AS, income statement (`case-aop`) | Compute & close | `sf-case-aop` |
| 14 | Trading company on 115BAA | company (Zenith Demo Traders Pvt Ltd) | ITR-6 + 3CD | certificate of incorporation, GST certificate, final accounts, computation, asset schedule, 26AS (`case-company-trading`) | Tax audit | `sf-case-company-trading` |
| 15 | Manufacturing company with MAT | company (Kaveri Demo Fabricators Pvt Ltd) | ITR-6 + 3CD | certificate of incorporation, final accounts, computation (29B rows), asset schedule, 26AS (`case-company-mfg`) | Tax audit | `sf-case-company-mfg` |
| 12 | Non-resident | individual | ITR-2 | 26AS (195, 194I), AIS - residence asked (`case-nri`) | My return | `sf-case-nri` |
| 13 | Updated return (ITR-U), AY 2025-26 | individual | ITR-1 | the return filed (JSON), AIS, 26AS of that year (`case-itru`) | My return | `sf-case-updated-return` |
| 16 | Small business - only a bank statement (gym trainer) | individual | ITR-4 | one bank statement, read row by row (`case-bank-only`) | My return, Classify step | `sf-case-bank-only` |

The screen's own walk: `tours/sf-wizard.json` (= chip guide.wizard, held together by selfcheck).

## Small business - only a bank statement (2026-10-13)

A gym trainer, tutor or shop-keeper with no books and no Form 16. In New filing pick **An individual**, then **Small business - only a
bank statement** (`wizard.scenarios` bankonly; implies business, services, presumptive; rules out books and a tax audit). The bank
statement is the one document (`wizard.docs`: AIS and 26AS become optional through `wizard.doc_need` except_for).

1. **Read** - `myreturn_read.bank_pdf_serial` (chip `bank.statement`): serial number + date rows, wrapped narration, repeated page
   heads / footers; each entry's direction from the running balance; the holder, account, IFSC (bank) and address from the header.
   **Reconciled**: opening + credits - debits = closing and no entry missing - otherwise said in plain words and the statement is
   not used (`bank.check` bank_recon, red).
2. **Classify** - `bankclass.py` (chip `bank.classify`): counterparty of each narration, own name compared loosely with the holder's,
   lender and merchant words, a credit followed by an equal debit within 2 days (pass-through). Classes the person taps: Customer
   receipts / Cash takings / Own money / Loan / Not income (money out: Personal / Business cost / Own money / Loan repayment).
   Only customer receipts are digital turnover; interest goes to Other sources; "Not sure" is left out until decided (amber check).
3. **Tax** - the existing machinery: 44AD 6% of digital / 8% of cash (`myreturn.business`), ITR-4 eligibility, 44AB(e), both regimes,
   234F / 234A / 234B / 234C for a belated return (`close.dates`: 31 August for business returns from AY 2026-27). **s.234F only where filing
   was compulsory** (chip `myreturn.must_file`: income over the basic exemption, or a 7th-proviso condition of s.139(1) - Rs 1 crore in
   current accounts, Rs 50 lakh in savings (read from the statement), foreign travel over Rs 2 lakh, electricity over Rs 1 lakh, TDS/TCS
   Rs 25,000 (50,000 senior), turnover over Rs 60 lakh / receipts over Rs 10 lakh; the person confirms the three the statement cannot show). Otherwise the
   screen says filing is not compulsory but recommended, and a belated return is still allowed (s.139(4)).
4. **GST** - `bank.gst_gap`: services Rs 20 lakh (Rs 10 lakh Manipur, Mizoram, Nagaland, Tripura), goods Rs 40 lakh (Rs 20 lakh); a
   warning on the Classify step, never a registration.
5. **JSON** - ITR-4 (`schemas/itr/ITR-4_2026_Main_V1.1.json`), checked before download; the steps of uploading it on the income-tax
   portal are chip `bank.upload`.
Asked in the popup only when the statement did not give them: PAN, date of birth, mobile, e-mail, father's name (address from the
statement). Tests: `tools/e2e_bankonly.py`. Documents: `tools/showcase/make_bankonly_demo.py` (a made-up Kotak-style statement).
The recorder's privacy mask (a real statement on a recording): `TOUR_MASK=1`, chip `tour.mask`, `TOUR_MASK_WORDS=<json list>`.

## Tests

`tools/e2e_wizard.py` - HUF, salaried + capital gains, Not recognised, the tenant wall, carry on / discard; a trust refused as not
yet; a company from its certificate of incorporation (CIN, directors, option 115BAA, ITR-6, books into Intake & map); a trading firm with GST + audit end to end (certificate -> client, deed -> partners popup, each document into
its screen, Review -> Tax audit, Remove takes a book out of Intake & map); a manufacturing firm found by its certificate; an LLP
certificate on a firm card asked about and switched; an AOP from its agreement and 26AS.
