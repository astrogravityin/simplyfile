"""The demo self-filer's documents for My return (2026-10-06): a pre-filled JSON, a Form 16 (Parts A and B, as TRACES and an
employer lay them out), an AIS (PDF, locked the department's way: pan + DDMMYYYY) and a 26AS text export - all invented and
obviously fake (Demo Software, PAN ZZDPK0042Q, phone 90000 00042, @demo.example). Run from the repo root:

    python tools/showcase/make_myreturn_demo.py      ->  tools/tour_video/showcase/self/ (gitignored)
"""
import io
import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path("tools/tour_video/showcase/self")
OUT.mkdir(parents=True, exist_ok=True)
PAN, DOB, NAME = "ZZDPK0042Q", "1988-04-15", ("Anil", "Kumar", "Demo")
TAN, EMP = "HYDD00042E", "DEMO SOFTWARE PRIVATE LIMITED"
BANK_TAN = "HYDD00077B"

prefill = {
    "personalInfo": {"assesseeName": {"firstName": NAME[0], "middleName": NAME[1], "surNameOrOrgName": NAME[2]}, "pan": PAN, "dob": DOB,
                     "address": {"residenceNo": "Flat 42, Demo Residency", "roadOrStreet": "Demo Road", "localityOrArea": "Madhapur",
                                 "cityOrTownOrDistrict": "Hyderabad", "stateCode": "36", "countryCode": "91", "pinCode": 500081,
                                 "countryCodeMobile": 91, "mobileNo": 9000000042, "emailAddress": "anil.demo@demo.example"},
                     "filingStatus": {"residentialStatus": "RES"}},
    "form24q": {"salaries": {"salary": [{"nameOfEmployer": EMP, "natOfEmployment": "OTH", "tanOfEmployer": TAN,
                                         "salarys": {"grossSalary": 1440000, "salary": 1440000, "valueOfPerquisites": 0, "profitsinLieuOfSalary": 0}}]},
                "incomeDeductions": {"salary": 1440000, "perquisitesValue": 0, "profitsInSalary": 0, "deductionUs16Ia": 75000, "professionalTaxUs16Iii": 2400},
                "allwncExemptUs10DtlsType": [{"salNatureDesc": "10(13A)", "salOthAmount": 120000}]},
    "form26as": {"tdsOnSalaries": {"tdsOnSalary": [{"employerOrDeductorOrCollectDetl": {"tan": TAN, "employerOrDeductorOrCollecterName": EMP},
                                                    "incChrgSal": 1440000, "totalTDSSal": 132000}]},
                 "tdsOnOthThanSals": {"tdSonOthThanSal": [{"employerOrDeductorOrCollectDetl": {"tan": BANK_TAN, "employerOrDeductorOrCollecterName": "DEMO BANK LIMITED"},
                                                           "amtForTaxDeduct": 62000, "totTDSOnAmtPaid": 6200, "claimOutOfTotTDSOnAmtPaid": 6200, "tdsSection": "194A"}]},
                 "taxPayments": {"taxPayment": []}},
    "insights": {"intrstFrmSavingBank": 18400, "intrstFrmTermDeposit": 62000},
    "bankAccountDtls": [{"addtnlBankDetails": [{"ifsccode": "DEMO0000042", "bankName": "DEMO BANK LIMITED", "bankAccountNo": "004200420042", "useForRefund": True}]}],
}
(OUT / "01 Pre-filled JSON - ZZDPK0042Q - AY 2026-27.json").write_text(json.dumps(prefill, indent=1), encoding="utf-8")


def pdf(lines: list[str], password: str = "") -> bytes:
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    if password:
        from reportlab.lib import pdfencrypt
        c = canvas.Canvas(b, pagesize=A4, encrypt=pdfencrypt.StandardEncryption(password, canPrint=1))
    y = 800
    for ln in lines:
        if ln == "<page>":
            c.showPage(); y = 800; continue
        c.setFont("Helvetica-Bold" if ln.isupper() else "Helvetica", 8.5)
        c.drawString(36, y, ln)
        y -= 13
        if y < 50:
            c.showPage(); y = 800
    c.save()
    return b.getvalue()


f16 = [
    "FORM NO. 16 [See rule 31(1)(a)]", "PART A",
    "Certificate under section 203 of the Income-tax Act, 1961 for tax deducted at source on salary paid to an employee under section 192",
    "Certificate No. DEMO042 Last updated on 10-Jun-2026",
    "Name and address of the Employer/Specified Bank", f"{EMP}, Demo Tech Park, Hyderabad 500081",
    "Name and address of the Employee/ Specified senior citizen", "ANIL KUMAR DEMO, Flat 42, Demo Residency, Hyderabad",
    "PAN of the Deductor TAN of the Deductor PAN of the Employee/ specified senior citizen",
    f"AAACD0042C {TAN} {PAN}",
    "Assessment Year 2026-27 Period with the Employer From 01-Apr-2025 To 31-Mar-2026",
    "Summary of amount paid/credited and tax deducted at source thereon in respect of the employee",
    "Quarter(s) Receipt Numbers Amount paid/ credited Amount of tax deducted (Rs.) Amount of tax deposited/ remitted (Rs.)",
    "Q1 DEMOQ1 3,60,000.00 33,000.00 33,000.00", "Q2 DEMOQ2 3,60,000.00 33,000.00 33,000.00",
    "Q3 DEMOQ3 3,60,000.00 33,000.00 33,000.00", "Q4 DEMOQ4 3,60,000.00 33,000.00 33,000.00",
    "Total (Rs.) 14,40,000.00 1,32,000.00 1,32,000.00",
    "<page>",
    "PART B (Annexure-I)", "Details of Salary Paid and any other income and tax deducted",
    "A Whether opting out of taxation u/s 115BAC(1A)? No",
    "1. Gross Salary",
    "(a) Salary as per provisions contained in section 17(1) 14,40,000.00",
    "(b) Value of perquisites under section 17(2) (as per Form No. 12BA, wherever applicable) 0.00",
    "(c) Profits in lieu of salary under section 17(3) (as per Form No. 12BA, wherever applicable) 0.00",
    "(d) Total 14,40,000.00",
    "2. Less: Allowances to the extent exempt under section 10",
    "(a) Travel concession or assistance under section 10(5) 0.00",
    "(e) House rent allowance under section 10(13A) 0.00",
    "(h) Total amount of exemption claimed under section 10 0.00",
    "3. Total amount of salary received from current employer 14,40,000.00",
    "4. Less: Deductions under section 16",
    "(a) Standard deduction under section 16(ia) 75,000.00",
    "(c) Tax on employment under section 16(iii) 0.00",
    "6. Income chargeable under the head \"Salaries\" 13,65,000.00",
    "10. Deductions under Chapter VI-A Gross Amount Deductible Amount",
    "(a) Deduction in respect of life insurance premia, contributions to provident fund etc. under section 80C 1,72,800.00 1,50,000.00",
    "(e) Deductions in respect of amount paid/deposited to notified pension scheme under section 80CCD (1B) 50,000.00 50,000.00",
    "(f) Deduction in respect of contribution by Employer to pension scheme under section 80CCD (2) 72,000.00 72,000.00",
    "(g) Deduction in respect of health insurance premia under section 80D 31,200.00 25,000.00",
    "12. Total taxable income 12,93,000.00", "13. Tax on total income 1,26,950.00",
    "17. Tax payable 1,32,028.00", "19. Net tax payable 1,32,000.00",
]
(OUT / "02 Form 16 - Demo Software - AY 2026-27.pdf").write_bytes(pdf(f16))

ais = [
    "ANNUAL INFORMATION STATEMENT (AIS)", f"PAN {PAN} Name ANIL KUMAR DEMO Financial Year 2025-26 Assessment Year 2026-27",
    "PART B1 - INFORMATION RELATING TO TAX DEDUCTED OR COLLECTED AT SOURCE",
    "SR. NO. INFORMATION CODE INFORMATION DESCRIPTION INFORMATION SOURCE COUNT AMOUNT",
    f"1 TDS-192 Salary received {EMP} ({TAN}) 4 14,40,000",
    f"2 TDS-194A Interest other than Interest on securities DEMO BANK LIMITED ({BANK_TAN}) 1 62,000",
    "PART B2 - INFORMATION RELATING TO SPECIFIED FINANCIAL TRANSACTION (SFT)",
    "SR. NO. INFORMATION CODE INFORMATION DESCRIPTION INFORMATION SOURCE COUNT AMOUNT",
    "1 SFT-016(SB) Interest income Savings bank DEMO BANK LIMITED 1 18,400",
    "2 SFT-016(TD) Interest income Time deposit DEMO BANK LIMITED 2 62,000",
    "3 SFT-015 Dividend income DEMO INDUSTRIES LIMITED 1 9,500",
]
(OUT / "03 AIS - ZZDPK0042Q - FY 2025-26.pdf").write_bytes(pdf(ais, PAN.lower() + "15041988"))

s26 = "\n".join([
    "^Annual Tax Statement^",
    f"^Permanent Account Number (PAN)^{PAN}^Current Status of PAN^Active^Financial Year^2025-26^Assessment Year^2026-27^",
    "^Name of Assessee^ANIL KUMAR DEMO^",
    "^PART-I - Details of Tax Deducted at Source^",
    "^Sr. No.^Name of Deductor^TAN of Deductor^^^^^Total Amount Paid / Credited(Rs.)^Total Tax Deducted #(Rs.)^Total TDS Deposited(Rs.)",
    f"^1^{EMP}^{TAN}^^^^^1440000.00^132000.00^132000.00",
    "^^Sr. No.^Section^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited(Rs.)^Tax Deducted ##(Rs.)^TDS Deposited(Rs.)",
    "^^1^192^31-Mar-2026^F^15-May-2026^-^1440000.00^132000.00^132000.00",
    f"^2^DEMO BANK LIMITED^{BANK_TAN}^^^^^62000.00^6200.00^6200.00",
    "^^Sr. No.^Section^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited(Rs.)^Tax Deducted ##(Rs.)^TDS Deposited(Rs.)",
    "^^1^194A^31-Mar-2026^F^15-May-2026^-^62000.00^6200.00^6200.00",
])
(OUT / "04 26AS - ZZDPK0042Q - AY 2026-27.txt").write_text(s26, encoding="utf-8")


# --- 2026-10-07, showcase parts 9-11: a CAMS capital-gains CSV and a bank statement for the same person (self-more/); the employer's Form 16
# downloaded again (the "already here - replace it?" question); an HUF and a consultant who start from their pre-filled JSON --------
def csv(rows: list[list[str]]) -> bytes:
    return ("\n".join(",".join(f'"{c}"' for c in r) for r in rows) + "\n").encode()


MORE = OUT.parent / "self-more"         # kept out of self/: tools/e2e_myreturn.py reads every file in self/
MORE.mkdir(exist_ok=True)
(MORE / "05 CAMS capital gains - ZZDPK0042Q - FY 2025-26.csv").write_bytes(csv([
    ["Consolidated Capital Gains Statement - Demo Registrar - FY 2025-26 - ANIL KUMAR DEMO - ZZDPK0042Q"], [],
    ["Scheme Name", "ISIN", "Category", "Units", "Purchase Date", "Purchase Value", "NAV as on 31/01/2018", "Redemption Date", "Redemption Amount", "STT"],
    ["Demo Bluechip Fund - Growth", "INF000Z01011", "Equity", "800", "15/06/2017", "80,000.00", "150.00", "10/09/2025", "2,40,000.00", "2"],
    ["Demo Flexicap Fund - Growth", "INF000Z01029", "Equity", "400", "12/03/2020", "40,000.00", "", "10/09/2025", "1,10,000.00", "1"],
    ["Demo Midcap Fund - Growth", "INF000Z01037", "Equity", "200", "10/01/2025", "40,000.00", "", "10/08/2025", "52,000.00", "1"],
    ["Demo Gilt Fund - Growth", "INF000Z01052", "Debt", "100", "10/01/2021", "2,00,000.00", "", "01/12/2025", "2,40,000.00", "0"],
    ["Grand Total", "", "", "", "", "3,60,000.00", "", "", "6,42,000.00", ""]]))
BANK = [["Date", "Narration", "Chq/Ref No", "Withdrawal Amt", "Deposit Amt", "Closing Balance"],
        ["01/04/2025", "OPENING BALANCE", "", "", "", "2,10,000.00"],
        ["30/04/2025", "NEFT CR-DEMO SOFTWARE PVT LTD-SALARY APR", "S1", "", "1,10,000.00", "3,20,000.00"],
        ["05/05/2025", "UPI-DEMO GROCER", "U1", "4,200.00", "", "3,15,800.00"],
        ["30/06/2025", "INT.PD:0000000000:01-04-2025 TO 30-06-2025", "", "", "4,600.00", "3,20,400.00"],
        ["10/09/2025", "NEFT CR-DEMO REGISTRAR-REDEMPTION", "R1", "", "3,50,000.00", "6,70,400.00"],
        ["30/09/2025", "INT.PD:0000000000:01-07-2025 TO 30-09-2025", "", "", "4,600.00", "6,75,000.00"],
        ["15/12/2025", "TRF TO SELF A/C DEMO FD", "", "3,00,000.00", "", "3,75,000.00"],
        ["31/12/2025", "INT.PD:0000000000:01-10-2025 TO 31-12-2025", "", "", "4,600.00", "3,79,600.00"],
        ["31/03/2026", "INT.PD:0000000000:01-01-2026 TO 31-03-2026", "", "", "4,600.00", "3,84,200.00"]]
(MORE / "06 Bank statement - Demo Bank - FY 2025-26.csv").write_bytes(csv(BANK))

AGAIN = OUT.parent / "self-again"       # 26AS downloaded again later in the year (one per return: the "already here" question)
AGAIN.mkdir(exist_ok=True)
for old in AGAIN.iterdir():
    old.unlink()
(AGAIN / "26AS - ZZDPK0042Q - AY 2026-27 - downloaded again.txt").write_text(s26, encoding="utf-8")


def prefill_of(first: str, last: str, pan: str, dob: str, n: int, sal: list, oth: list, interest: dict) -> dict:
    return {"personalInfo": {"assesseeName": {"firstName": first, "surNameOrOrgName": last}, "pan": pan, "dob": dob,
                             "address": {"residenceNo": f"Flat {n}, Demo Residency", "roadOrStreet": "Demo Road", "localityOrArea": "Madhapur",
                                         "cityOrTownOrDistrict": "Hyderabad", "stateCode": "36", "countryCode": "91", "pinCode": 500081,
                                         "countryCodeMobile": 91, "mobileNo": 9000000000 + n, "emailAddress": f"demo{n}@demo.example"},
                             "filingStatus": {"residentialStatus": "RES"}},
            "form26as": {"tdsOnSalaries": {"tdsOnSalary": sal}, "tdsOnOthThanSals": {"tdSonOthThanSal": [
                {"employerOrDeductorOrCollectDetl": {"tan": t, "employerOrDeductorOrCollecterName": nm}, "amtForTaxDeduct": a, "totTDSOnAmtPaid": x,
                 "claimOutOfTotTDSOnAmtPaid": x, "tdsSection": s} for t, nm, a, x, s in oth]}, "taxPayments": {"taxPayment": []}},
            "insights": interest,
            "bankAccountDtls": [{"addtnlBankDetails": [{"ifsccode": f"DEMO00000{n}", "bankName": "DEMO BANK LIMITED", "bankAccountNo": f"00{n}00{n}00{n}", "useForRefund": True}]}]}


HUF = OUT.parent / "huf"                # a family HUF: deposits in the HUF's name; the Karta signs
HUF.mkdir(exist_ok=True)
(HUF / "Pre-filled JSON - ZZDHF0045L - AY 2026-27.json").write_text(json.dumps(prefill_of(
    "", "DEMO FAMILY HUF", "ZZDHF0045L", "1990-04-01", 45, [], [(BANK_TAN, "DEMO BANK LIMITED", 840000, 84000, "194A")],
    {"intrstFrmSavingBank": 21000, "intrstFrmTermDeposit": 840000}), indent=1), encoding="utf-8")

KAV = OUT.parent / "kavya"              # a consultant with no Form 16: fees from clients, TDS under 194J, her bank statement
KAV.mkdir(exist_ok=True)
(KAV / "Pre-filled JSON - ZZDPC0044K - AY 2026-27.json").write_text(json.dumps(prefill_of(
    "KAVYA", "DEMO CONSULTANT", "ZZDPC0044K", "1985-05-05", 44, [],
    [("HYDD00091C", "DEMO CLIENT ONE PRIVATE LIMITED", 900000, 90000, "194J"), ("HYDD00092D", "DEMO CLIENT TWO LLP", 600000, 60000, "194J")],
    {"intrstFrmSavingBank": 9200}), indent=1), encoding="utf-8")
(KAV / "Bank statement - Demo Bank - Kavya - FY 2025-26.csv").write_bytes(csv([
    ["Date", "Narration", "Chq/Ref No", "Withdrawal Amt", "Deposit Amt", "Closing Balance"],
    ["01/04/2025", "NEFT CR-DEMO CLIENT ONE PVT LTD-INV 101", "N1", "", "4,05,000.00", "4,05,000.00"],
    ["15/04/2025", "UPI-DEMO GROCER", "U1", "3,000.00", "", "4,02,000.00"],
    ["30/06/2025", "INT.PD:0000000000:01-04-2025 TO 30-06-2025", "", "", "2,300.00", "4,04,300.00"],
    ["05/07/2025", "BY CASH DEPOSIT CDM", "", "", "60,000.00", "4,64,300.00"],
    ["12/08/2025", "IMPS-DEMO CLIENT TWO LLP-FEES", "I2", "", "5,40,000.00", "10,04,300.00"],
    ["20/11/2025", "NEFT CR-DEMO CLIENT ONE PVT LTD-INV 117", "N2", "", "4,05,000.00", "14,09,300.00"],
    ["10/01/2026", "NEFT CR-DEMO CLIENT THREE-WORKSHOP", "N3", "", "2,40,000.00", "16,49,300.00"],
    ["31/03/2026", "INT.PD:0000000000:01-01-2026 TO 31-03-2026", "", "", "2,300.00", "16,51,600.00"]]))

# --- 2026-10-08, wave 4 in the films (parts 9-11) - kept out of self/ (tools/e2e_myreturn.py reads every file there) ----------------
# a second employer (weekend teaching, another TAN: the two-employer check), the AIS and 26AS with that employer too - and the 26AS's
# Part IV (Part A2) with the plot buyer's 194IA TDS; the CAMS statement as a PDF; last year's filed ITR-3 (its losses); a revised
# Form 16 from Demo Software (same TAN: replace or keep both); a GSTR-3B summary for Kavya's GSTIN. All made up.
TAN2, EMP2 = "HYDD00043F", "DEMO TRAINING ACADEMY LLP"
f16b = [
    "FORM NO. 16 [See rule 31(1)(a)]", "PART A",
    "Certificate under section 203 of the Income-tax Act, 1961 for tax deducted at source on salary paid to an employee under section 192",
    "Certificate No. DEMO043 Last updated on 12-Jun-2026",
    "Name and address of the Employer/Specified Bank", f"{EMP2}, Demo Learning Centre, Hyderabad 500032",
    "Name and address of the Employee/ Specified senior citizen", "ANIL KUMAR DEMO, Flat 42, Demo Residency, Hyderabad",
    "PAN of the Deductor TAN of the Deductor PAN of the Employee/ specified senior citizen",
    f"AAACD0043D {TAN2} {PAN}",
    "Assessment Year 2026-27 Period with the Employer From 01-Apr-2025 To 31-Mar-2026",
    "Quarter(s) Receipt Numbers Amount paid/ credited Amount of tax deducted (Rs.) Amount of tax deposited/ remitted (Rs.)",
    "Q1 DEMOQ5 60,000.00 1,500.00 1,500.00", "Q2 DEMOQ6 60,000.00 1,500.00 1,500.00",
    "Q3 DEMOQ7 60,000.00 1,500.00 1,500.00", "Q4 DEMOQ8 60,000.00 1,500.00 1,500.00",
    "Total (Rs.) 2,40,000.00 6,000.00 6,000.00",
    "<page>",
    "PART B (Annexure-I)", "Details of Salary Paid and any other income and tax deducted",
    "A Whether opting out of taxation u/s 115BAC(1A)? No",
    "1. Gross Salary",
    "(a) Salary as per provisions contained in section 17(1) 2,40,000.00",
    "(d) Total 2,40,000.00",
    "4. Less: Deductions under section 16",
    "(a) Standard deduction under section 16(ia) 75,000.00",
    "6. Income chargeable under the head \"Salaries\" 1,65,000.00",
    "12. Total taxable income 1,65,000.00", "19. Net tax payable 6,000.00",
]
(MORE / "02 Form 16 - Demo Training Academy - AY 2026-27.pdf").write_bytes(pdf(f16b))
ais2 = ais[:5] + [f"2 TDS-192 Salary received {EMP2} ({TAN2}) 4 2,40,000"] + [ais[5].replace("2 TDS-194A", "3 TDS-194A")] + ais[6:]
(MORE / "03 AIS - ZZDPK0042Q - FY 2025-26.pdf").write_bytes(pdf(ais2, PAN.lower() + "15041988"))
BUYER = ("DEMO BUYER", "ZZDPB0050B")      # the plot's buyer (tools/showcase/pre10.py types the same PAN on the plot's row)
s26b = s26.split("\n") + [
    f"^3^{EMP2}^{TAN2}^^^^^240000.00^6000.00^6000.00",
    "^^Sr. No.^Section^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited(Rs.)^Tax Deducted ##(Rs.)^TDS Deposited(Rs.)",
    "^^1^192^31-Mar-2026^F^15-May-2026^-^240000.00^6000.00^6000.00",
    "^PART-IV - Details of Tax Deducted at Source u/s 194IA/ 194IB/ 194M/ 194S (For Seller/Landlord of Property/Contractors or Professionals/Seller of Virtual Digital Asset)^",
    "^Sr. No.^Acknowledgement Number^Name of Deductor^PAN of Deductor^Transaction Date^Total Transaction Amount (Rs.)^Total TDS Deposited (Rs.)^Total Amount Deposited other than TDS (Rs.)",
    f"^1^DEMOACK42^{BUYER[0]}^{BUYER[1]}^10-Nov-2025^4800000.00^48000.00^0.00",
    "^^Sr. No.^TDS Certificate Number^Section^Date of Deposit^Status of Booking*^Date of Booking^Demand Payment^TDS Deposited (Rs.)^Total Amount Deposited other than TDS (Rs.)",
    "^^1^-^194IA^05-Dec-2025^F^10-Dec-2025^0.00^48000.00^0.00",
    "^PART-V - Details of Transactions under Proviso to section 194B^"]
(MORE / "04 26AS - ZZDPK0042Q - AY 2026-27.txt").write_text("\n".join(s26b), encoding="utf-8")
cas = ["CAMS - Consolidated Account Statement", "Capital Gain / Loss Statement for the period 01-Apr-2025 to 31-Mar-2026",
       "Investor ANIL KUMAR DEMO PAN ZZDPK0042Q - Demo Registrar - all made up",
       "Demo Bluechip Equity Fund - Growth ISIN: INF000Z01011 Folio 4201",
       "Redemption 10-Sep-2025 800.000 2,40,000.00 15-Jun-2017 80,000.00 1,20,000.00",
       "Demo Flexicap Equity Fund - Growth ISIN: INF000Z01029 Folio 4202",
       "Redemption 10-Sep-2025 400.000 1,10,000.00 12-Mar-2020 40,000.00",
       "Demo Midcap Equity Fund - Growth ISIN: INF000Z01037 Folio 4203",
       "Redemption 10-Aug-2025 200.000 52,000.00 10-Jan-2025 40,000.00",
       "Demo Gilt Fund - Growth ISIN: INF000Z01052 Folio 4204",
       "Redemption 01-Dec-2025 100.000 2,40,000.00 10-Jan-2021 2,00,000.00"]
(MORE / "05 CAMS capital gains - ZZDPK0042Q - FY 2025-26.pdf").write_bytes(pdf(cas))
itr3_prev = {"ITR": {"ITR3": {"Form_ITR3": {"FormName": "ITR-3", "AssessmentYear": "2025"},
                              "PartA_GEN1": {"PersonalInfo": {"PAN": PAN, "AssesseeName": {"FirstName": NAME[0], "MiddleName": NAME[1], "SurNameOrOrgName": NAME[2]},
                                                              "DOB": DOB}},
                              "Verification": {"Date": "2025-07-28"},
                              "ScheduleCFL": {"LossCFCurrentAssmntYear2025": {"CarryFwdLossDetail": {"DateOfFiling": "2024-07-25", "TotalSTCGPTILossCF": 20000}},
                                              "CurrentAYloss": {"LossSummaryDetail": {"TotalLTCGPTILossCF": 15000}}}}}}
(MORE / "07 ITR-3 AY 2025-26 filed - ZZDPK0042Q.json").write_text(json.dumps(itr3_prev, indent=1), encoding="utf-8")
(AGAIN / "Form 16 - Demo Software - AY 2026-27 - revised.pdf").write_bytes(pdf(
    [x.replace("Last updated on 10-Jun-2026", "Last updated on 20-Jun-2026 (revised)") for x in f16]))
(KAV / "GSTR-3B summary - ZZDPC0044K - FY 2025-26.csv").write_text("\n".join(
    ["GSTIN,Tax Period,Total Taxable value,Zero rated supplies,Nil rated and exempted supplies,Non-GST supplies"]
    + [f"36ZZDPC0044K1Z5,{m} 2025,{v},0,0,0" for m, v in (("April", 405000), ("July", 60000), ("August", 540000), ("November", 405000))]
    + ["36ZZDPC0044K1Z5,January 2026,240000,0,0,0"]) + "\n", encoding="utf-8")
for d in (OUT, MORE, AGAIN, HUF, KAV):
    print("wrote", d.name + ":", ", ".join(sorted(p.name for p in d.iterdir())))


# --- 2026-10-11, New filing (the wizard): people who start from their documents, nobody added first --------------------------
# wizard-sal/ : Ravi Demo Salaried (ZZDPR0047N, born 11-02-1986) - two employers, funds sold (the AIS shows it), a plot sold (26AS
#               Part IV 194IA). His Form 16 names his PAN, not his name: the wizard's popup asks the name and date of birth, and
#               the AIS (locked with PAN + date of birth) opens once the date is given. Upload order: tools/e2e_wizard.py.
# wizard-huf/ : Demo Verma HUF (ZZDHW0046M) - deposits and a fund sale; 26AS names the HUF, the popup asks for the Karta.
# wizard-misc/: a file the readers do not know (it must say "Not recognised").
def f16_for(emp, tan, dpan, pan, name, gross, tds, q):
    each = gross / 4
    head = ["FORM NO. 16 [See rule 31(1)(a)]", "PART A",
            "Certificate under section 203 of the Income-tax Act, 1961 for tax deducted at source on salary paid to an employee under section 192",
            f"Certificate No. DEMO{q} Last updated on 10-Jun-2026",
            "Name and address of the Employer/Specified Bank", f"{emp}, Demo Business Park, Hyderabad 500081",
            "Name and address of the Employee/ Specified senior citizen", f"{name}, Flat 47, Demo Enclave, Hyderabad",
            "PAN of the Deductor TAN of the Deductor PAN of the Employee/ specified senior citizen", f"{dpan} {tan} {pan}",
            "Assessment Year 2026-27 Period with the Employer From 01-Apr-2025 To 31-Mar-2026",
            "Quarter(s) Receipt Numbers Amount paid/ credited Amount of tax deducted (Rs.) Amount of tax deposited/ remitted (Rs.)"]
    quarters = [f"Q{n} DEMO{q}{n} {each:,.2f} {tds / 4:,.2f} {tds / 4:,.2f}" for n in range(1, 5)]
    tail = [f"Total (Rs.) {gross:,.2f} {tds:,.2f} {tds:,.2f}", "<page>",
            "PART B (Annexure-I)", "Details of Salary Paid and any other income and tax deducted",
            "A Whether opting out of taxation u/s 115BAC(1A)? No", "1. Gross Salary",
            f"(a) Salary as per provisions contained in section 17(1) {gross:,.2f}", f"(d) Total {gross:,.2f}",
            "4. Less: Deductions under section 16", "(a) Standard deduction under section 16(ia) 75,000.00",
            f"6. Income chargeable under the head 'Salaries' {gross - 75000:,.2f}", f"19. Net tax payable {tds:,.2f}"]
    return head + quarters + tail


def s26_for(pan, name, deductors, part4=None):
    """A TRACES text export: Part I per deductor (name, TAN, section, amount, TDS), and Part IV's 194IA buyer when given."""
    out = ["^Annual Tax Statement^", f"^Permanent Account Number (PAN)^{pan}^Current Status of PAN^Active^Financial Year^2025-26^Assessment Year^2026-27^",
           f"^Name of Assessee^{name}^", "^PART-I - Details of Tax Deducted at Source^",
           "^Sr. No.^Name of Deductor^TAN of Deductor^^^^^Total Amount Paid / Credited(Rs.)^Total Tax Deducted #(Rs.)^Total TDS Deposited(Rs.)"]
    for n, (who, tan, sec, amt, tds) in enumerate(deductors, 1):
        out += [f"^{n}^{who}^{tan}^^^^^{amt:.2f}^{tds:.2f}^{tds:.2f}",
                "^^Sr. No.^Section^Transaction Date^Status of Booking*^Date of Booking^Remarks**^Amount Paid / Credited(Rs.)^Tax Deducted ##(Rs.)^TDS Deposited(Rs.)",
                f"^^1^{sec}^31-Mar-2026^F^15-May-2026^-^{amt:.2f}^{tds:.2f}^{tds:.2f}"]
    if part4:
        buyer, bpan, amt, tds = part4
        out += ["^PART-IV - Details of Tax Deducted at Source u/s 194IA/ 194IB/ 194M/ 194S (For Seller/Landlord of Property/Contractors or Professionals/Seller of Virtual Digital Asset)^",
                "^Sr. No.^Acknowledgement Number^Name of Deductor^PAN of Deductor^Transaction Date^Total Transaction Amount (Rs.)^Total TDS Deposited (Rs.)^Total Amount Deposited other than TDS (Rs.)",
                f"^1^DEMOACK47^{buyer}^{bpan}^14-Dec-2025^{amt:.2f}^{tds:.2f}^0.00",
                "^^Sr. No.^TDS Certificate Number^Section^Date of Deposit^Status of Booking*^Date of Booking^Demand Payment^TDS Deposited (Rs.)^Total Amount Deposited other than TDS (Rs.)",
                f"^^1^-^194IA^05-Jan-2026^F^10-Jan-2026^0.00^{tds:.2f}^0.00",
                "^PART-V - Details of Transactions under Proviso to section 194B^"]
    return "\n".join(out)


SAL = OUT.parent / "wizard-sal"
SAL.mkdir(exist_ok=True)
RPAN, RNAME = "ZZDPR0047N", "RAVI DEMO SALARIED"            # born 11-02-1986 - the AIS opens with zzdpr0047n11021986
T1, E1, T2, E2 = "HYDD00047G", "DEMO ANALYTICS PRIVATE LIMITED", "HYDD00048H", "DEMO CLOUD SERVICES LLP"
(SAL / "1 Form 16 - Demo Analytics - AY 2026-27.pdf").write_bytes(pdf(f16_for(E1, T1, "AAACD0047C", RPAN, RNAME, 1260000, 98000, "471")))
(SAL / "2 AIS - ZZDPR0047N - FY 2025-26.pdf").write_bytes(pdf([
    "ANNUAL INFORMATION STATEMENT (AIS)", f"PAN {RPAN} Name {RNAME} Financial Year 2025-26 Assessment Year 2026-27",
    "PART B1 - INFORMATION RELATING TO TAX DEDUCTED OR COLLECTED AT SOURCE",
    "SR. NO. INFORMATION CODE INFORMATION DESCRIPTION INFORMATION SOURCE COUNT AMOUNT",
    f"1 TDS-192 Salary received {E1} ({T1}) 4 12,60,000", f"2 TDS-192 Salary received {E2} ({T2}) 2 3,00,000",
    f"3 TDS-194A Interest other than Interest on securities DEMO BANK LIMITED ({BANK_TAN}) 1 41,000",
    "PART B2 - INFORMATION RELATING TO SPECIFIED FINANCIAL TRANSACTION (SFT)",
    "SR. NO. INFORMATION CODE INFORMATION DESCRIPTION INFORMATION SOURCE COUNT AMOUNT",
    "1 SFT-016(SB) Interest income Savings bank DEMO BANK LIMITED 1 12,300",
    "2 SFT-016(TD) Interest income Time deposit DEMO BANK LIMITED 1 41,000",
    "3 SFT-018 Sale of units of mutual fund DEMO REGISTRAR 3 4,02,000"], RPAN.lower() + "11021986"))
(SAL / "3 26AS - ZZDPR0047N - AY 2026-27.txt").write_text(s26_for(RPAN, RNAME, [
    (E1, T1, "192", 1260000, 98000), (E2, T2, "192", 300000, 9000), ("DEMO BANK LIMITED", BANK_TAN, "194A", 41000, 4100)],
    ("DEMO PLOT BUYER", "ZZDPB0051C", 6200000, 62000)), encoding="utf-8")
(SAL / "4 Form 16 - Demo Cloud Services - AY 2026-27.pdf").write_bytes(pdf(f16_for(E2, T2, "AAACD0048D", RPAN, RNAME, 300000, 9000, "481")))
(SAL / "5 CAMS capital gains - ZZDPR0047N - FY 2025-26.pdf").write_bytes(pdf([
    "CAMS - Consolidated Account Statement", "Capital Gain / Loss Statement for the period 01-Apr-2025 to 31-Mar-2026",
    f"Investor {RNAME} PAN {RPAN} - Demo Registrar - all made up",
    "Demo Bluechip Equity Fund - Growth ISIN: INF000Z01011 Folio 4701",
    "Redemption 12-Sep-2025 900.000 2,52,000.00 15-Jun-2019 1,35,000.00",
    "Demo Short Duration Debt Fund - Growth ISIN: INF000Z01060 Folio 4702",
    "Redemption 03-Feb-2026 500.000 1,50,000.00 10-May-2023 1,30,000.00"]))

WH = OUT.parent / "wizard-huf"
WH.mkdir(exist_ok=True)
HPAN, HNAME = "ZZDHW0046M", "DEMO VERMA HUF"
(WH / "1 26AS - ZZDHW0046M - AY 2026-27.txt").write_text(s26_for(HPAN, HNAME, [("DEMO BANK LIMITED", BANK_TAN, "194A", 520000, 52000)]), encoding="utf-8")
(WH / "2 AIS - ZZDHW0046M - FY 2025-26.csv").write_bytes(csv([
    ["Annual Information Statement (AIS) - Demo - all made up"], [f"PAN {HPAN} Name {HNAME} Financial Year 2025-26 Assessment Year 2026-27"],
    ["SR. NO.", "INFORMATION CODE", "INFORMATION DESCRIPTION", "INFORMATION SOURCE", "COUNT", "AMOUNT"],
    ["1", "SFT-016(TD)", "Interest income Time deposit", "DEMO BANK LIMITED", "2", "5,20,000"],
    ["2", "SFT-016(SB)", "Interest income Savings bank", "DEMO BANK LIMITED", "1", "14,000"],
    ["3", "SFT-015", "Dividend income", "DEMO INDUSTRIES LIMITED", "1", "22,000"],
    ["4", "SFT-018", "Sale of units of mutual fund", "DEMO REGISTRAR", "1", "3,20,000"]]))
(WH / "3 CAMS capital gains - ZZDHW0046M - FY 2025-26.pdf").write_bytes(pdf([
    "CAMS - Consolidated Account Statement", "Capital Gain / Loss Statement for the period 01-Apr-2025 to 31-Mar-2026",
    f"Investor {HNAME} PAN {HPAN} - Demo Registrar - all made up",
    "Demo Bluechip Equity Fund - Growth ISIN: INF000Z01011 Folio 4601",
    "Redemption 20-Oct-2025 1000.000 3,20,000.00 15-Jan-2021 2,10,000.00"]))
MISC = OUT.parent / "wizard-misc"
MISC.mkdir(exist_ok=True)
(MISC / "Family trip notes.txt").write_text("Packing list for the demo family trip: tickets, snacks, umbrella. Nothing about tax here.\n", encoding="utf-8")
for d in (SAL, WH, MISC):
    print("wrote", d.name + ":", ", ".join(sorted(p.name for p in d.iterdir())))


# --- 2026-10-11 later, New filing's worked examples (chip wizard.cases): one folder per path, every name and number made up -------
# (ZZ... PANs, Demo ... names, @demo.example). The firm cases clone the showcase firm's books / ITR-5 layout with the name and PAN
# swapped; Lakshmi Narayana Textiles is the demo register's own (made-up) firm. tools/showcase/pre_cases.py plays each through the
# wizard for the demo seed; tools/make_case_tours.py makes each one's film script.
import zipfile  # noqa: E402

from openpyxl import load_workbook  # noqa: E402

SHOW = OUT.parent


def fresh(name):
    d = SHOW / name
    d.mkdir(exist_ok=True)
    for old in d.iterdir():
        old.unlink()
    return d


def ais_csv(pan, name, fy, ay, rows):
    return csv([["Annual Information Statement (AIS) - Demo - all made up"], [f"PAN {pan} Name {name} Financial Year {fy} Assessment Year {ay}"],
                ["SR. NO.", "INFORMATION CODE", "INFORMATION DESCRIPTION", "INFORMATION SOURCE", "COUNT", "AMOUNT"]]
               + [[str(i), c, d, s, "1", a] for i, (c, d, s, a) in enumerate(rows, 1)])


def salary_row(tan, emp, gross, tds):
    return {"employerOrDeductorOrCollectDetl": {"tan": tan, "employerOrDeductorOrCollecterName": emp}, "incChrgSal": gross, "totalTDSSal": tds}


def bank_csv(rows):
    return csv([["Date", "Narration", "Chq/Ref No", "Withdrawal Amt", "Deposit Amt", "Closing Balance"]] + rows)


# 1 salaried, one employer - ITR-1 (the pre-filled JSON names her: nothing asked)
d = fresh("case-salaried")
P1, N1, T_R, E_R = "ZZDPS0052D", "PRIYA DEMO SALARIED", "HYDD00052J", "DEMO RETAIL PRIVATE LIMITED"
(d / "1 Pre-filled JSON - ZZDPS0052D - AY 2026-27.json").write_text(json.dumps(prefill_of(
    "PRIYA", "DEMO SALARIED", P1, "1992-03-12", 52, [salary_row(T_R, E_R, 960000, 41000)], [(BANK_TAN, "DEMO BANK LIMITED", 30000, 3000, "194A")],
    {"intrstFrmSavingBank": 6200, "intrstFrmTermDeposit": 30000}), indent=1), encoding="utf-8")
(d / "2 Form 16 - Demo Retail - AY 2026-27.pdf").write_bytes(pdf(f16_for(E_R, T_R, "AAACD0052E", P1, N1, 960000, 41000, "521")))
(d / "3 26AS - ZZDPS0052D - AY 2026-27.txt").write_text(s26_for(P1, N1, [(E_R, T_R, "192", 960000, 41000), ("DEMO BANK LIMITED", BANK_TAN, "194A", 30000, 3000)]), encoding="utf-8")

# 2 two employers - the 26AS shows both TANs, the second Form 16 is asked for
d = fresh("case-two-jobs")
P2, N2 = "ZZDPT0053E", "ARUN DEMO TWOJOBS"
TA, EA, TB, EB = "HYDD00053K", "DEMO FOODS PRIVATE LIMITED", "HYDD00054L", "DEMO LOGISTICS LLP"
(d / "1 26AS - ZZDPT0053E - AY 2026-27.txt").write_text(s26_for(P2, N2, [(EA, TA, "192", 540000, 18000), (EB, TB, "192", 420000, 12000)]), encoding="utf-8")
(d / "2 Form 16 - Demo Foods - AY 2026-27.pdf").write_bytes(pdf(f16_for(EA, TA, "AAACD0053F", P2, N2, 540000, 18000, "531")))
(d / "3 Form 16 - Demo Logistics - AY 2026-27.pdf").write_bytes(pdf(f16_for(EB, TB, "AAACD0054G", P2, N2, 420000, 12000, "541")))

# 4 a pensioner with deposit interest (born 1956: senior limits, 80TTB)
d = fresh("case-pensioner")
P4, N4, TP = "ZZDPP0054F", "SAVITRI DEMO PENSIONER", "HYDD00055M"
(d / "1 Form 16 - Demo Bank pension - AY 2026-27.pdf").write_bytes(pdf(f16_for("DEMO BANK LIMITED - PENSION DISBURSING BRANCH", TP, "AAACD0055H", P4, N4, 480000, 8000, "551")))
(d / "2 26AS - ZZDPP0054F - AY 2026-27.txt").write_text(s26_for(P4, N4, [("DEMO BANK LIMITED - PENSION DISBURSING BRANCH", TP, "192", 480000, 8000),
                                                                      ("DEMO BANK LIMITED", BANK_TAN, "194A", 210000, 0)]), encoding="utf-8")
(d / "3 AIS - ZZDPP0054F - FY 2025-26.csv").write_bytes(ais_csv(P4, N4, "2025-26", "2026-27", [
    ("SFT-016(TD)", "Interest income Time deposit", "DEMO BANK LIMITED", "2,10,000"), ("SFT-016(SB)", "Interest income Savings bank", "DEMO BANK LIMITED", "18,500")]))

# 5 a consultant on 44ADA - fees with 194J, no Form 16
d = fresh("case-consultant")
P5 = "ZZDPN0055G"
(d / "1 Pre-filled JSON - ZZDPN0055G - AY 2026-27.json").write_text(json.dumps(prefill_of(
    "NEHA", "DEMO CONSULTANT", P5, "1989-11-02", 55, [],
    [("HYDD00093E", "DEMO CLIENT THREE PRIVATE LIMITED", 1200000, 120000, "194J"), ("HYDD00094F", "DEMO CLIENT FOUR LLP", 450000, 45000, "194J")],
    {"intrstFrmSavingBank": 7400}), indent=1), encoding="utf-8")
(d / "2 Bank statement - Demo Bank - Neha - FY 2025-26.csv").write_bytes(bank_csv([
    ["01/04/2025", "OPENING BALANCE", "", "", "", "1,20,000.00"], ["20/05/2025", "NEFT CR-DEMO CLIENT THREE PVT LTD-INV 7", "N1", "", "5,40,000.00", "6,60,000.00"],
    ["30/06/2025", "INT.PD:0000000000:01-04-2025 TO 30-06-2025", "", "", "1,850.00", "6,61,850.00"], ["14/09/2025", "IMPS-DEMO CLIENT FOUR LLP-FEES", "I1", "", "4,05,000.00", "10,66,850.00"],
    ["12/12/2025", "NEFT CR-DEMO CLIENT THREE PVT LTD-INV 9", "N2", "", "5,40,000.00", "16,06,850.00"], ["31/03/2026", "INT.PD:0000000000:01-01-2026 TO 31-03-2026", "", "", "1,850.00", "16,08,700.00"]]))

# 6 a small trader on 44AD with GST - a shop, receipts mostly by UPI
d = fresh("case-trader")
P6 = "ZZDPK0056H"
(d / "1 Pre-filled JSON - ZZDPK0056H - AY 2026-27.json").write_text(json.dumps(prefill_of(
    "RAMU", "DEMO KIRANA", P6, "1979-06-30", 56, [], [(BANK_TAN, "DEMO BANK LIMITED", 22000, 2200, "194A")], {"intrstFrmSavingBank": 5100, "intrstFrmTermDeposit": 22000}),
    indent=1), encoding="utf-8")
(d / "2 GSTR-3B summary - ZZDPK0056H - FY 2025-26.csv").write_text("\n".join(
    ["GSTIN,Tax Period,Total Taxable value,Zero rated supplies,Nil rated and exempted supplies,Non-GST supplies"]
    + [f"36ZZDPK0056H1Z8,{m},{v},0,0,0" for m, v in (("April 2025", 1450000), ("July 2025", 1380000), ("October 2025", 1620000),
                                                      ("January 2026", 1550000))]) + "\n", encoding="utf-8")
(d / "3 Bank statement - Demo Bank - Ramu - FY 2025-26.csv").write_bytes(bank_csv([
    ["01/04/2025", "OPENING BALANCE", "", "", "", "85,000.00"], ["30/04/2025", "UPI SETTLEMENT-DEMO KIRANA-APR", "U1", "", "3,90,000.00", "4,75,000.00"],
    ["05/05/2025", "NEFT DR-DEMO WHOLESALE SUPPLIERS", "N1", "3,40,000.00", "", "1,35,000.00"], ["31/07/2025", "UPI SETTLEMENT-DEMO KIRANA-JUL", "U2", "", "4,10,000.00", "5,45,000.00"],
    ["15/10/2025", "BY CASH DEPOSIT CDM", "", "", "75,000.00", "6,20,000.00"], ["31/01/2026", "UPI SETTLEMENT-DEMO KIRANA-JAN", "U3", "", "4,60,000.00", "10,80,000.00"]]))

# 12 a non-resident: NRO interest and rent from a flat let out
d = fresh("case-nri")
P12, N12 = "ZZDPA0060M", "KIRAN DEMO ABROAD"
(d / "1 26AS - ZZDPA0060M - AY 2026-27.txt").write_text(s26_for(P12, N12, [("DEMO BANK LIMITED", BANK_TAN, "195", 160000, 50000),
                                                                         ("DEMO TENANT PRIVATE LIMITED", "HYDD00060P", "194I", 360000, 36000)]), encoding="utf-8")
(d / "2 AIS - ZZDPA0060M - FY 2025-26.csv").write_bytes(ais_csv(P12, N12, "2025-26", "2026-27", [
    ("SFT-016(TD)", "Interest income Time deposit (NRO)", "DEMO BANK LIMITED", "1,60,000"), ("TDS-194I", "Rent on land or building", "DEMO TENANT PRIVATE LIMITED", "3,60,000")]))

# 13 an updated return for AY 2025-26 - the return filed, and the AIS with the deposit interest left out
d = fresh("case-itru")
P13 = "ZZDPU0061N"
itr1 = {"ITR": {"ITR1": {"CreationInfo": {"SWVersionNo": "1.0", "SWCreatedBy": "SW00000000", "JSONCreatedBy": "SW00000000", "JSONCreationDate": "2025-07-20"},
                         "Form_ITR1": {"FormName": "ITR-1", "Description": "Demo - made up", "AssessmentYear": "2025", "SchemaVer": "Ver1.0", "FormVer": "Ver1.0"},
                         "PersonalInfo": {"AssesseeName": {"FirstName": "MEENA", "SurNameOrOrgName": "DEMO UPDATED"}, "PAN": P13, "DOB": "1987-01-25",
                                          "Address": {"ResidenceNo": "Flat 61, Demo Residency", "CityOrTownOrDistrict": "Hyderabad", "StateCode": "36", "PinCode": 500081,
                                                      "EmailAddress": "demo61@demo.example", "MobileNo": 9000000061}},
                         "ITR1_IncomeDeductions": {"GrossSalary": 840000, "TotalIncome": 765000},
                         "ITR1_TaxComputation": {"NetTaxLiability": 18400}, "Refund": {"RefundDue": 0}, "Verification": {"Date": "2025-07-20"}}}}
(d / "1 ITR-1 AY 2025-26 filed - ZZDPU0061N.json").write_text(json.dumps(itr1, indent=1), encoding="utf-8")
(d / "2 AIS - ZZDPU0061N - FY 2024-25.csv").write_bytes(ais_csv(P13, "MEENA DEMO UPDATED", "2024-25", "2025-26", [
    ("TDS-192", "Salary received DEMO INSURANCE BROKERS PRIVATE LIMITED (HYDD00061Q)", "DEMO INSURANCE BROKERS PRIVATE LIMITED", "8,40,000"),
    ("SFT-016(TD)", "Interest income Time deposit", "DEMO BANK LIMITED", "96,000")]))


# --- the businesses ------------------------------------------------------------------------------------------------------------
SRC = SHOW / "c3"
BOOKS_SRC = SRC / "Sri Venkateswara Traders - Trading, P&L and Balance Sheet AY 2026-27.xlsx"
STMT_SRC = SRC / "Sri Venkateswara Traders - IT Stmt, Dep, Loans, 40A(2)(b) AY 2026-27.xlsx"
LLP_SRC = SHOW / "c12" / "Greenfield Agritech LLP - Income statement AY 2026-27.xlsx"


def cloned(src, out, swaps):
    """A copy of a showcase workbook with every text cell's names swapped."""
    wb = load_workbook(src)
    for ws in wb.worksheets:
        for r in ws.iter_rows():
            for c in r:
                if isinstance(c.value, str):
                    v = c.value
                    for a, b in swaps:
                        v = v.replace(a, b)
                    c.value = v
    wb.save(out)


def gst_cert(gstin, name, constitution, address):
    return pdf(["GOVERNMENT OF INDIA", "FORM GST REG-06", "[See Rule 10(1)]", "Registration Certificate",
                f"Registration Number : {gstin}", f"1. Legal Name : {name}", f"2. Trade Name, if any : {name}",
                f"3. Constitution of Business : {constitution}", f"4. Address of Principal Place of Business : {address}",
                "5. Date of Liability : 01/07/2017", "6. Period of Validity From 01/07/2017 To Not Applicable", "7. Type of Registration : Regular",
                "Demo certificate - made up, not issued by any authority"])


def deed(title, opening, people, closing):
    return pdf([title] + opening + [f"{who} {i}: {n}, PAN {p}, profit share {s}%" for i, (who, n, p, s) in enumerate(people, 1)] + closing
               + ["Demo document - every name and number made up"])


def gst_zip(gstin, turnover):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for mm, yy in [(m, 2025) for m in range(4, 13)] + [(m, 2026) for m in range(1, 4)]:
            tx = round(turnover / 12, 2)
            z.writestr(f"GSTR3B_{gstin}_{mm:02d}{yy}.json", json.dumps({"gstin": gstin, "ret_period": f"{mm:02d}{yy}", "sup_details": {
                "osup_det": {"txval": tx, "iamt": 0, "camt": round(tx * 0.09, 2), "samt": round(tx * 0.09, 2), "csamt": 0},
                "osup_zero": {"txval": 0, "iamt": 0, "csamt": 0}, "osup_nil_exmp": {"txval": 0}, "osup_nongst": {"txval": 0}}}))
    return b.getvalue()


# 8 a trading firm with GST and a tax audit - Demo Balaji Traders (the showcase firm's books, its name and PAN swapped)
d = fresh("case-firm-trading")
FP, FN, FG = "ZZDFB0057J", "DEMO BALAJI TRADERS", "36ZZDFB0057J1Z3"
SW = [("SRI VENKATESWARA TRADERS", FN), ("Sri Venkateswara Traders", "Demo Balaji Traders"), ("AAFFS4721M", FP)]
(d / "1 GST certificate - Demo Balaji Traders.pdf").write_bytes(gst_cert(FG, FN, "Partnership", "Shop 57, Demo Market, Hyderabad, Telangana 500001"))
(d / "2 Partnership deed - Demo Balaji Traders.pdf").write_bytes(deed("DEED OF PARTNERSHIP", [
    "This deed of partnership is made on 1 April 2019 at Hyderabad between the partners below,",
    f"carrying on business under the name and style of M/s {FN} (the firm).", f"PAN of the firm {FP}"],
    [("Partner", "Balaji Demo Rao", "ZZDPR0071A", 40), ("Partner", "Lakshmi Demo Rao", "ZZDPR0072B", 35), ("Partner", "Venkat Demo Rao", "ZZDPR0073C", 25)],
    ["Remuneration to working partners: as allowed by section 40(b)(v) of the Income-tax Act, 1961.", "Interest on capital: 12% a year (section 40(b)(iv))."]))
(d / "3 26AS - ZZDFB0057J - AY 2026-27.txt").write_text(s26_for(FP, FN, [("DEMO BANK LIMITED", BANK_TAN, "194A", 120000, 12000),
                                                                       ("DEMO CONSTRUCTIONS PRIVATE LIMITED", "HYDD00057R", "194C", 3000000, 60000)]), encoding="utf-8")
cloned(BOOKS_SRC, d / "4 Demo Balaji Traders - Trading, P&L and Balance Sheet AY 2026-27.xlsx", SW)
cloned(STMT_SRC, d / "5 Demo Balaji Traders - IT Stmt, Dep, Loans AY 2026-27.xlsx", SW)
(d / "6 GSTR-3B - 36ZZDFB0057J1Z3 - FY 2025-26.zip").write_bytes(gst_zip(FG, 31000000))
prev5 = (SHOW / "d" / "04 ITR-5 AY 2025-26 - Sri Venkateswara Traders - AAFFS4721M.json").read_text(encoding="utf-8")
for a, b in SW:
    prev5 = prev5.replace(a, b)
(d / "7 ITR-5 AY 2025-26 - Demo Balaji Traders - ZZDFB0057J.json").write_text(prev5, encoding="utf-8")

# 9 a manufacturing firm with stock and depreciation - Lakshmi Narayana Textiles, already in the demo register (AY 2026-27 waits)
d = fresh("case-firm-mfg")
MP, MN, MG = "AAGFL5512K", "LAKSHMI NARAYANA TEXTILES", "36AAGFL5512K1Z2"
SWM = [("SRI VENKATESWARA TRADERS", MN), ("Sri Venkateswara Traders", "Lakshmi Narayana Textiles"), ("AAFFS4721M", MP),
       ("TRADING AND PROFIT AND LOSS ACCOUNT", "MANUFACTURING, TRADING AND PROFIT AND LOSS ACCOUNT")]
(d / "1 GST certificate - Lakshmi Narayana Textiles.pdf").write_bytes(gst_cert(MG, MN, "Partnership", "Plot 12, Demo Industrial Estate, Sircilla, Telangana 505301"))
(d / "2 Partnership deed - Lakshmi Narayana Textiles.pdf").write_bytes(deed("DEED OF PARTNERSHIP", [
    "This deed of partnership is made on 1 April 2015 at Sircilla between the partners below,",
    f"carrying on the manufacture of cloth under the name M/s {MN} (the firm).", f"PAN of the firm {MP}"],
    [("Partner", "Narayana Demo Murthy", "ZZDPM0081D", 60), ("Partner", "Lakshmi Demo Murthy", "ZZDPM0082E", 40)],
    ["Remuneration to working partners: as allowed by section 40(b)(v).", "Interest on capital: 12% a year."]))
(d / "3 26AS - AAGFL5512K - AY 2026-27.txt").write_text(s26_for(MP, MN, [("DEMO BANK LIMITED", BANK_TAN, "194A", 85000, 8500),
                                                                       ("DEMO GARMENTS PRIVATE LIMITED", "HYDD00081S", "194Q", 18500000, 18500)]), encoding="utf-8")
mfg = d / "4 Lakshmi Narayana Textiles - Manufacturing, P&L and Balance Sheet AY 2026-27.xlsx"
cloned(BOOKS_SRC, mfg, SWM)
wb = load_workbook(mfg)
ws = wb.create_sheet("Stock")
for r in [["Statement of closing stock as on 31.03.2026 (Form 3CD clause 14, s.145A)"], [], ["Item", "Quantity", "Valuation", "Amount (Rs)"],
          ["Raw material - cotton yarn (kg)", 12500, "Cost", 3125000], ["Work in progress - grey cloth (m)", 8000, "Cost", 960000],
          ["Finished goods - dyed cloth (m)", 21000, "Lower of cost and market", 4410000], ["Total", "", "", 8495000]]:
    ws.append(r)
ws = wb.create_sheet("Depreciation")
for r in [["Statement regarding depreciation as per Income-tax Rules (Form 3CD clause 18)"], [], ["Sl", "Block of assets", "WDV 01.04.2025", "Additions", "Depreciation"],
          [1, "Plant & Machinery - looms (15%)", 6400000, 1200000, 1050000], [2, "Factory building (10%)", 2800000, 0, 280000], [3, "Vehicles (15%)", 900000, 0, 135000]]:
    ws.append(r)
wb.save(mfg)
(d / "5 GSTR-3B - 36AAGFL5512K1Z2 - FY 2025-26.zip").write_bytes(gst_zip(MG, 46000000))

# 10 an LLP in services - Demo Pixel Works LLP
d = fresh("case-llp")
LP, LN, LG = "ZZDFP0058K", "DEMO PIXEL WORKS LLP", "36ZZDFP0058K1Z6"
(d / "1 GST certificate - Demo Pixel Works LLP.pdf").write_bytes(gst_cert(LG, LN, "Limited Liability Partnership", "Unit 58, Demo Tech Park, Hyderabad, Telangana 500081"))
(d / "2 LLP agreement - Demo Pixel Works LLP.pdf").write_bytes(deed("LIMITED LIABILITY PARTNERSHIP AGREEMENT", [
    "This agreement is made on 5 June 2021 between the designated partners below.", f"LLP name: {LN}, PAN of the LLP {LP}",
    "Business: software and design services."],
    [("Partner", "Sana Demo Pixel", "ZZDPS0091F", 50), ("Partner", "Rohan Demo Pixel", "ZZDPR0092G", 50)],
    ["Both partners are designated partners under section 7 of the LLP Act, 2008.", "Remuneration as allowed by section 40(b)."]))
(d / "3 26AS - ZZDFP0058K - AY 2026-27.txt").write_text(s26_for(LP, LN, [("DEMO BANKING SOFTWARE PRIVATE LIMITED", "HYDD00058T", "194J", 4200000, 420000),
                                                                       ("DEMO RETAIL CHAIN LIMITED", "HYDD00059U", "194J", 1800000, 180000)]), encoding="utf-8")
cloned(LLP_SRC, d / "4 Demo Pixel Works LLP - Income statement AY 2026-27.xlsx", [("GREENFIELD AGRITECH LLP", LN), ("Greenfield Agritech LLP", "Demo Pixel Works LLP"), ("AAKFG3307Q", LP)])

# 11 an AOP - Demo Residents Welfare Association (its PAN's 4th letter A), no GST
d = fresh("case-aop")
AP, AN = "ZZDAR0059L", "DEMO RESIDENTS WELFARE ASSOCIATION"
(d / "1 Agreement of association - Demo Residents Welfare Association.pdf").write_bytes(deed("AGREEMENT OF ASSOCIATION", [
    "The residents of Demo Enclave, Hyderabad, have associated themselves to run the common areas.",
    f"The association known as {AN}, PAN {AP}"],
    [("Member", "Prakash Demo Resident", "ZZDPP0101H", 34), ("Member", "Farida Demo Resident", "ZZDPF0102J", 33), ("Member", "George Demo Resident", "ZZDPG0103K", 33)],
    ["Members' shares are equal and known (section 167B)."]))
(d / "2 26AS - ZZDAR0059L - AY 2026-27.txt").write_text(s26_for(AP, AN, [("DEMO BANK LIMITED", BANK_TAN, "194A", 240000, 24000)]), encoding="utf-8")
cloned(LLP_SRC, d / "3 Demo Residents Welfare Association - Income statement AY 2026-27.xlsx",
       [("GREENFIELD AGRITECH LLP", AN), ("Greenfield Agritech LLP", "Demo Residents Welfare Association"), ("AAKFG3307Q", AP)])
for name in ("case-salaried", "case-two-jobs", "case-pensioner", "case-consultant", "case-trader", "case-nri", "case-itru",
             "case-firm-trading", "case-firm-mfg", "case-llp", "case-aop"):
    print("wrote", name + ":", ", ".join(sorted(p.name for p in (SHOW / name).iterdir())))


# the documents each person's case needs besides (AIS, 26AS) - so Review opens past Gather
(SHOW / "case-salaried" / "4 AIS - ZZDPS0052D - FY 2025-26.csv").write_bytes(ais_csv(P1, N1, "2025-26", "2026-27", [
    ("TDS-192", f"Salary received {E_R} ({T_R})", E_R, "9,60,000"), ("SFT-016(TD)", "Interest income Time deposit", "DEMO BANK LIMITED", "30,000"),
    ("SFT-016(SB)", "Interest income Savings bank", "DEMO BANK LIMITED", "6,200")]))
(SHOW / "case-two-jobs" / "4 AIS - ZZDPT0053E - FY 2025-26.csv").write_bytes(ais_csv(P2, N2, "2025-26", "2026-27", [
    ("TDS-192", f"Salary received {EA} ({TA})", EA, "5,40,000"), ("TDS-192", f"Salary received {EB} ({TB})", EB, "4,20,000")]))
(SHOW / "case-consultant" / "3 26AS - ZZDPN0055G - AY 2026-27.txt").write_text(s26_for(P5, "NEHA DEMO CONSULTANT", [
    ("DEMO CLIENT THREE PRIVATE LIMITED", "HYDD00093E", "194J", 1200000, 120000), ("DEMO CLIENT FOUR LLP", "HYDD00094F", "194J", 450000, 45000)]), encoding="utf-8")
(SHOW / "case-consultant" / "4 AIS - ZZDPN0055G - FY 2025-26.csv").write_bytes(ais_csv(P5, "NEHA DEMO CONSULTANT", "2025-26", "2026-27", [
    ("TDS-194J", "Fees for professional services", "DEMO CLIENT THREE PRIVATE LIMITED", "12,00,000"), ("TDS-194J", "Fees for professional services", "DEMO CLIENT FOUR LLP", "4,50,000"),
    ("SFT-016(SB)", "Interest income Savings bank", "DEMO BANK LIMITED", "7,400")]))
(SHOW / "case-trader" / "4 26AS - ZZDPK0056H - AY 2026-27.txt").write_text(s26_for(P6, "RAMU DEMO KIRANA", [
    ("DEMO BANK LIMITED", BANK_TAN, "194A", 22000, 2200)]), encoding="utf-8")
(SHOW / "case-trader" / "5 AIS - ZZDPK0056H - FY 2025-26.csv").write_bytes(ais_csv(P6, "RAMU DEMO KIRANA", "2025-26", "2026-27", [
    ("SFT-016(TD)", "Interest income Time deposit", "DEMO BANK LIMITED", "22,000"), ("GST-TURNOVER", "Turnover as per GSTR-3B", "GSTN", "60,00,000")]))
(SHOW / "case-itru" / "3 26AS - ZZDPU0061N - AY 2025-26.txt").write_text(s26_for(P13, "MEENA DEMO UPDATED", [
    ("DEMO INSURANCE BROKERS PRIVATE LIMITED", "HYDD00061Q", "192", 840000, 21000), ("DEMO BANK LIMITED", BANK_TAN, "194A", 96000, 9600)])
    .replace("Financial Year^2025-26^Assessment Year^2026-27", "Financial Year^2024-25^Assessment Year^2025-26").replace("-2026^", "-2025^"), encoding="utf-8")
f16u = [x.replace("Assessment Year 2026-27", "Assessment Year 2025-26").replace("01-Apr-2025 To 31-Mar-2026", "01-Apr-2024 To 31-Mar-2025")
        .replace("10-Jun-2026", "10-Jun-2025") for x in f16_for("DEMO INSURANCE BROKERS PRIVATE LIMITED", "HYDD00061Q", "AAACD0061R", P13, "MEENA DEMO UPDATED", 840000, 21000, "611")]
(SHOW / "case-itru" / "4 Form 16 - Demo Insurance Brokers - AY 2025-26.pdf").write_bytes(pdf(f16u))
print("wrote the cases' AIS / 26AS")


# --- 2026-10-11 night, the companies (ITR-6) as worked examples: the two demo companies of tools/showcase/company_demo.py, their
# own documents (the same bytes - in the demo seed the wizard finds them "already there"), and a certificate of incorporation (CIN,
# date, directors) - plus Zenith's GST certificate - so the wizard can make the company from its papers. All made up.
import sys as _sys  # noqa: E402
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import company_demo  # noqa: E402

for key, folder in (("zenith", "case-company-trading"), ("kaveri", "case-company-mfg")):
    d = fresh(folder)
    x = company_demo.COMPANIES[key]
    c, co = x["client"], x["client"]["company"]
    short = c["name"].replace(" Private Limited", "")
    (d / f"00 Certificate of incorporation - {short}.pdf").write_bytes(pdf([
        "GOVERNMENT OF INDIA", "MINISTRY OF CORPORATE AFFAIRS", "Registrar of Companies, Hyderabad", "CERTIFICATE OF INCORPORATION",
        "[Pursuant to sub-section (2) of section 7 and sub-section (1) of section 8 of the Companies Act, 2013]",
        f"I hereby certify that {c['name'].upper()} is incorporated on this day under the Companies Act, 2013 and that the company is limited by shares.",
        f"The Corporate Identity Number (CIN) of the company is {co['cin']}", f"Date of incorporation: {co['incorporated']}",
        f"PAN of the company {c['pan']}"]
        + [f"Director {i}: {p['name']}, DIN {p['din']}, PAN {p['pan']}" for i, p in enumerate(co["directors"], 1)]
        + ["Demo certificate - made up, not issued by any authority"]))
    if key == "zenith":
        (d / f"00 GST certificate - {short}.pdf").write_bytes(gst_cert(c["gst"], c["name"].upper(), "Private Limited Company", c["address"]))
    for name, data in company_demo.documents(key):      # the very names pre_companies.py uploads: in the demo seed they are "already there"
        (d / name).write_bytes(data)
    print("wrote", folder + ":", ", ".join(sorted(p.name for p in d.iterdir())))
