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
print("wrote", ", ".join(sorted(p.name for p in OUT.iterdir())))
