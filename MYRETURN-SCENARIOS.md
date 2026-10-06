# My return - individual income-tax scenarios (AY 2026-27)

What an individual's return can hold, where each figure comes from, and what SimplyFile's My return does with it.
Written 2026-10-06 from the department's AY 2026-27 forms and the Finance Act 2026. Status: **done** / **part** / **todo**.

## The documents - who gives them and where to get them

| Document | Issued by | Where to get it | What it gives the return |
|---|---|---|---|
| Form 16 (Part A + B) | Employer (TRACES) | Employer's HR / payroll, by 15 June | Salary, exemptions, standard deduction, 80C...80CCD(2) declared, TDS on salary |
| Form 16A | Bank / payer (TRACES) | The bank or client that deducted | TDS on interest, fees, rent (also in 26AS) |
| Form 26AS (Annual Tax Statement) | Income Tax Department (TRACES) | incometax.gov.in > e-File > Income Tax Returns > View Form 26AS > TRACES | Every TDS / TCS credited to your PAN, refunds; tax payments up to FY 2022-23 |
| AIS (Annual Information Statement) | Income Tax Department | incometax.gov.in > Services > AIS (PDF or JSON; PDF password = PAN in small letters + date of birth DDMMYYYY) | Salary, interest, dividends, sale of shares / funds / property, rent, business receipts, GST turnover, **tax payments (advance, self-assessment) from FY 2023-24** |
| TIS (Taxpayer Information Summary) | Income Tax Department | Same page as the AIS | The AIS totalled per category (the figures the department will use) |
| Pre-filled JSON | Income Tax Department | incometax.gov.in > e-File > Income Tax Returns > Download Pre-Filled Data | Who you are, banks, salary per employer, TDS, taxes paid, interest |
| Last year's / filed return (JSON) | You (from the e-filing portal) | incometax.gov.in > e-File > Income Tax Returns > View Filed Returns > Download JSON | Your date of birth, the regime used, losses carried forward, what was filed |
| Bank statement | Your bank | Net banking > Statements (PDF / Excel) | Receipts of a profession or business with no TDS, interest not in the AIS |
| GST returns (GSTR-1 / 3B, annual) | GST portal | gst.gov.in > Returns > View filed returns | Turnover of a GST-registered business (must agree with the receipts shown) |
| Capital gains statement | Broker / CAMS / KFintech | Broker back office (Tax P&L), CAMS / KFintech consolidated statement | Each sale: date, sale value, cost, grandfathered value (112A), STT |
| Home loan interest certificate | Lender | Lender's portal | Interest (24(b)) and principal (80C) |
| Rent receipts / agreement | Landlord | - | HRA claim (old regime) |
| Investment proofs | LIC, PPF, ELSS, NPS, insurer | Each provider | 80C, 80CCD(1B), 80D, 80E, 80G |
| Advance / self-assessment tax challans (280) | Bank / e-Pay Tax | incometax.gov.in > e-File > e-Pay Tax > Payment history | Tax you paid yourself (also in the AIS Part B3) |

## Which form

| Form | Who | Status |
|---|---|---|
| ITR-1 Sahaj | Resident, income up to 50 lakh: salary / pension, up to **two** houses, other sources, 112A gains up to 1.25 lakh, farm income up to 5,000 | **done** |
| ITR-2 | Individuals / HUF without business: capital gains, more houses, foreign assets or income, director, unlisted shares, not resident, losses | **done** (part: see capital gains, foreign) |
| ITR-4 Sugam | Resident, income up to 50 lakh, **presumptive** business / profession (44AD, 44ADA, 44AE), 112A up to 1.25 lakh | **done 2026-10-06** (44AD, 44ADA, checked against the department's V1.1 schema; 44AE todo) |
| ITR-3 | Business / profession with books, or presumptive with anything ITR-4 does not allow | **part** (the CA side builds it from books; My return chooses it and says so) |

Due dates (section 139(1) as amended by the Finance Act 2026): ITR-1 / ITR-2 31 July 2026; ITR-3 / ITR-4 without audit **31 August 2026**;
audit 31 October - **extended to 21 November 2026 by CBDT Circular 07/2026** (audit report 30 September -> 21 October); belated 31 December 2026; revised free to 31 December 2026, then with the s.234I fee to **31 March 2027**.

## Scenarios

### Salary and pension
- One employer, Form 16 - **done** (TRACES Form 16 read in layout, 80CCD(2) to its own row, TDS checked against 26AS)
- Two or more employers in the year (two Form 16s; double standard deduction is a common mistake) - **done** (one standard deduction)
- Exempt allowances: HRA (old regime, metro / non-metro), LTA, gratuity, leave encashment - **done** (from Form 16; HRA worked out from rent)
- Professional tax, standard deduction (75,000 new / 50,000 old) - **done**
- Family pension (1/3 or 15,000 / 25,000) - **done**
- Arrears and relief under section 89 (Form 10E) - **todo**
- Salary from abroad / foreign employer - **todo** (ITR-2)

### House property
- Self-occupied (interest up to 2 lakh, old regime) - **done**
- Let out (rent, municipal tax, 30%, interest) and the loss set off against salary up to 2 lakh (CYLA) - **done**
- Co-owned (share percent) - **part** (100% assumed)
- Pre-construction interest (1/5 for 5 years), 80EE / 80EEA - **todo**

### Other sources
- Savings interest (80TTA 10,000 / 80TTB 50,000 for seniors) - **done**
- FD / RD interest (AIS SFT-016, 26AS 194A) - **done**
- Dividends (every SFT-015 row) - **done**
- Interest on income-tax refund - **done**
- Gifts, lottery / online games (30%, 115BB / 115BBJ), crypto (30%, 115BBH) - **todo**

### Capital gains
- Listed shares / equity funds 112A (12.5%, 1.25 lakh exempt) and 111A (20%) totals - **done** (totals typed or from AIS)
- Per-scrip lines in Schedule 112A (ISIN, grandfathering on 31-01-2018) - **todo**
- Debt funds (slab rate), property sale (12.5% without indexation, or 20% with indexation for land / building bought before 23-07-2024), 54 / 54EC / 54F reinvestment - **todo**
- Losses carried forward (Schedule CFL, 8 years) - **todo**

### Business and profession (presumptive)
- Professional / consultant / freelancer under **44ADA**: 50% of receipts (or more, if declared), receipts up to 50 lakh, or 75 lakh when cash is 5% or less - **done 2026-10-06**
- Contractor / trader under **44AD**: 6% of digital receipts, 8% of cash, turnover up to 2 crore (3 crore when cash is 5% or less) - **done 2026-10-06**
- Receipts seen by the department: AIS / 26AS 194J, 194C, 194H, 194O - **done 2026-10-06** (shown beside the receipts typed, a gap is a check)
- GSTIN and GST turnover (must agree with the receipts) - **done 2026-10-06** (typed on Check, into Schedule BP; reading GSTR-3B / the AIS GST line is todo)
- Bank statement as the receipts' source (no TDS) - **done 2026-10-06** (PDF, Excel .xlsx / .xls, CSV; separate Debit / Credit columns or one Amount with Dr / Cr; each credit sorted - receipts, cash, interest, tax refund, salary, reversal, own transfer - and "Use these receipts" fills the business card; a scanned PDF is not read)
- Advance tax: for 44AD / 44ADA one instalment by 15 March is enough (234C) - **done 2026-10-06**
- 44AE (goods carriages) - **todo**
- Books of account, audit (44AB) - not in My return; the CA side (Intake, Reconcile, Compute, Tax audit)

### Deductions (Chapter VI-A)
- 80C, 80CCC, 80CCD(1), 80CCD(1B), 80CCD(2), 80D (self, parents, senior), 80E, 80G, 80TTA / 80TTB, 80U - **done**
- 80DD, 80DDB, 80EE / 80EEA, 80EEB, 80GG (rent without HRA), 80GGC - **done 2026-10-06** (old regime; with Schedules 80DD, 80EE, 80EEA, 80EEB, 80GGC; an HUF gets 80DD, 80DDB, 80GGC)

### Taxes paid, interest, fees
- TDS from 26AS / AIS / Form 16, TCS - **done** (TCS part)
- Advance and self-assessment tax: AIS Part B3 (only the return's own year) - **done 2026-10-06**; typed on Check - **done**
- 234A / 234B / 234C (amounts rounded down to 100), 234F late fee - **done**
- 234I fee on a revised return after 31 December - **done 2026-10-06** (revise free to 31 Dec, then to 31 Mar with the fee; CA side records it on the filing)

### The return itself
- Regime: new (default) or old; the old only when filed by the due date (115BAC(6)); for business income the old regime needs Form 10-IEA by the due date - **done** (Form 10-IEA reminder shown; its date and acknowledgement in ITR-4 todo)
- 87A rebate (new: income up to 12 lakh, rebate up to 60,000, marginal relief) - **done**
- Original, belated (139(4)), revised (139(5)), updated (139(8A), ITR-U) - **part** (original / belated / revised dates; ITR-U todo)
- Already filed: compare every figure with the filed JSON - **done**
- Residential status, NRI, RNOR, DTAA relief, foreign assets (Schedule FA) - **todo**
- Clubbing (spouse / minor child income) - **todo**
- Agricultural income above 5,000 (partial integration) - **todo**
