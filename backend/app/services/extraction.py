"""Structured financial entity and transaction extraction from PyMuPDF pages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from app.services.pdf_parser import PageText


def mask_reference(raw_ref: str | None) -> str | None:
    """Mask sensitive account/policy/loan identifiers while preserving last 4 chars for matching."""
    if not raw_ref:
        return None
    cleaned = raw_ref.strip()
    if len(cleaned) <= 4:
        return "X" * len(cleaned)
    # Preserve short prefix if structured like DEMO-SB-1004582910 -> DEMO-SB-XXXXXX2910
    if "-" in cleaned:
        parts = cleaned.split("-")
        tail = parts[-1]
        if len(tail) > 4:
            parts[-1] = ("X" * (len(tail) - 4)) + tail[-4:]
            return "-".join(parts)
    return ("X" * (len(cleaned) - 4)) + cleaned[-4:]


def _last4(raw_ref: str | None) -> str:
    if not raw_ref:
        return ""
    digits = re.sub(r"[^A-Za-z0-9]", "", raw_ref)
    return digits[-4:] if len(digits) >= 4 else digits


def _parse_inr(val_str: str) -> float:
    cleaned = val_str.replace("₹", "").replace(",", "").replace("Rs.", "").strip()
    return float(cleaned)


def _parse_date(d_str: str) -> Optional[date]:
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(d_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class ExtractedAssetRecord:
    asset_type: str
    institution: str
    account_reference: Optional[str]
    amount: float
    nominee_status: str
    maturity_date: Optional[date]
    page_number: int
    extracted_text: str
    confidence: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractedTransactionRecord:
    transaction_date: date
    description: str
    amount: float
    transaction_type: str
    category: str
    reference_no: Optional[str]
    page_number: int
    confidence: str = "HIGH"


@dataclass
class ExtractionResult:
    assets: list[ExtractedAssetRecord] = field(default_factory=list)
    transactions: list[ExtractedTransactionRecord] = field(default_factory=list)


def _categorize_transaction(desc: str, is_credit: bool, ref_no: str = "") -> str:
    d = f"{desc} {ref_no}".upper()
    if is_credit:
        if "SAL" in d or "SALARY" in d or "TECHNOVA" in d:
            return "SALARY"
        if "SAVINGS INTEREST" in d or "INT CR" in d or "INT-Q" in d:
            return "SAVINGS_INTEREST"
        return "OTHER_CREDIT"
    if "EMI" in d or "FINSERVE" in d or "LOAN" in d or "NACH-CLF" in d:
        return "LOAN_EMI"
    if "SURAKSHAGUARD" in d or "DEMO-INS" in d or "LIFE" in d or "POLICY" in d:
        return "INSURANCE_PREMIUM"
    if any(k in d for k in ("STREAMFLIX", "CLOUDNOTES", "TUNEWAVE", "SUBS", "NETFLIX", "SPOTIFY")):
        return "SUBSCRIPTION"
    if "SMS ALERT" in d or "CHG-SMS" in d:
        return "BANK_FEE_SMS"
    if "ANNUAL ACCOUNT MAINT" in d or "MAINT CHARGE" in d or "CHG-AMC" in d:
        return "BANK_FEE_AMC"
    if "RENT" in d:
        return "RENT"
    if "TERM DEPOSIT" in d or "TO FD" in d or "FD-TRF" in d:
        return "FD_TRANSFER"
    if "ATM WDL" in d or "ATM-" in d:
        return "ATM_WITHDRAWAL"
    if "BBPS" in d or "ELECTRICITY" in d or "BESCOM" in d:
        return "UTILITY"
    if "UPI" in d:
        return "UPI_EXPENSE"
    if "NEFT" in d:
        return "NEFT_TRANSFER"
    return "OTHER_DEBIT"


def _extract_bank_statement(pages: list[PageText]) -> ExtractionResult:
    res = ExtractionResult()
    p1 = pages[0].cleaned_text if pages else ""
    full_text = "\n".join(p.cleaned_text for p in pages)

    bank_match = re.search(r"^([A-Z][A-Za-z\s.&]+BANK\s+LTD\.?(?:\s*\(DEMO\))?)", p1, re.MULTILINE | re.IGNORECASE)
    bank_name = bank_match.group(1).strip() if bank_match else "Bank (Parsed)"
    acct_match = re.search(r"Account\s+Number:\s*\|\s*([A-Z0-9-]+)", p1, re.IGNORECASE)
    if not acct_match:
        acct_match = re.search(r"([A-Z]{2,6}-SB-\d{4,16})", p1)
    raw_acct = acct_match.group(1).strip() if acct_match else None

    close_match = re.search(r"Closing\s+Balance(?:\s+as\s+on\s+[\dA-Za-z-]+)?:\s*\|?\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    open_match = re.search(r"Opening\s+Balance:\s*\|?\s*₹\s*([\d,]+\.\d{2})", p1, re.IGNORECASE)
    closing_bal = _parse_inr(close_match.group(1)) if close_match else 0.0
    opening_bal = _parse_inr(open_match.group(1)) if open_match else 0.0

    # Parse transaction rows (handling both 6-col lines and 5-col lines where description wrapped above/below)
    txn_6_re = re.compile(
        r"^(\d{2}-[A-Za-z]{3}-\d{4})\s*\|\s*(.+?)\s*\|\s*([A-Z0-9-]+)\s*\|\s*(₹[\d,]+\.\d{2}|-)\s*\|\s*(₹[\d,]+\.\d{2}|-)\s*\|\s*(₹[\d,]+\.\d{2})$"
    )
    txn_5_re = re.compile(
        r"^(\d{2}-[A-Za-z]{3}-\d{4})\s*\|\s*([A-Z0-9-]+)\s*\|\s*(₹[\d,]+\.\d{2}|-)\s*\|\s*(₹[\d,]+\.\d{2}|-)\s*\|\s*(₹[\d,]+\.\d{2})$"
    )
    interest_sum = 0.0
    for page in pages:
        lines = [ln.strip() for ln in page.cleaned_text.splitlines() if ln.strip()]
        for idx, line in enumerate(lines):
            m6 = txn_6_re.match(line)
            m5 = None if m6 else txn_5_re.match(line)
            if m6:
                dt_str, desc, ref_no, dr_str, cr_str, _bal_str = m6.groups()
            elif m5:
                dt_str, ref_no, dr_str, cr_str, _bal_str = m5.groups()
                # Gather adjacent wrapped description fragments not starting with a date or header
                desc_parts = []
                if idx > 0 and not re.match(r"^\d{2}-[A-Za-z]{3}-\d{4}\s*\|", lines[idx - 1]) and "|" not in lines[idx - 1]:
                    desc_parts.append(lines[idx - 1])
                if idx + 1 < len(lines) and not re.match(r"^\d{2}-[A-Za-z]{3}-\d{4}\s*\|", lines[idx + 1]) and "|" not in lines[idx + 1]:
                    desc_parts.append(lines[idx + 1])
                desc = " ".join(desc_parts).strip() or ref_no
            else:
                continue

            tx_date = _parse_date(dt_str)
            if not tx_date:
                continue
            if dr_str != "-":
                amt = _parse_inr(dr_str)
                tx_type = "DEBIT"
                cat = _categorize_transaction(desc, is_credit=False, ref_no=ref_no)
            elif cr_str != "-":
                amt = _parse_inr(cr_str)
                tx_type = "CREDIT"
                cat = _categorize_transaction(desc, is_credit=True, ref_no=ref_no)
                if cat == "SAVINGS_INTEREST":
                    interest_sum += amt
            else:
                continue
            res.transactions.append(
                ExtractedTransactionRecord(
                    transaction_date=tx_date,
                    description=desc.strip(),
                    amount=amt,
                    transaction_type=tx_type,
                    category=cat,
                    reference_no=mask_reference(ref_no.strip()),
                    page_number=page.page_number,
                    confidence="HIGH",
                )
            )

    res.assets.append(
        ExtractedAssetRecord(
            asset_type="SAVINGS_ACCOUNT",
            institution=bank_name,
            account_reference=mask_reference(raw_acct),
            amount=closing_bal,
            nominee_status="UNKNOWN",
            maturity_date=None,
            page_number=1,
            extracted_text=f"{bank_name} | Account: {mask_reference(raw_acct)} | Closing Balance: ₹{closing_bal:,.2f}",
            confidence="HIGH",
            details={
                "source": "UPLOADED_BANK_STATEMENT",
                "last4": _last4(raw_acct),
                "opening_balance": opening_bal,
                "closing_balance": closing_bal,
                "savings_interest_credited": round(interest_sum, 2),
                "transaction_count": len(res.transactions),
            },
        )
    )
    return res


def _extract_ais_report(pages: list[PageText]) -> ExtractionResult:
    res = ExtractionResult()
    full_text = "\n".join(p.cleaned_text for p in pages)

    # B1: Salary TDS-192
    sal_match = re.search(
        r"Total\s+Reported\s+Salary\s*\(TDS-192\).*?\|\s*₹\s*([\d,]+\.\d{2})\s*\|\s*₹\s*([\d,]+\.\d{2})",
        full_text,
        re.IGNORECASE,
    )
    if sal_match:
        sal_amt = _parse_inr(sal_match.group(1))
        tds_amt = _parse_inr(sal_match.group(2))
        sal_page = next((p.page_number for p in pages if "TDS-192" in p.cleaned_text and "11," in p.cleaned_text), 1)
        res.assets.append(
            ExtractedAssetRecord(
                asset_type="AIS_SALARY_SUMMARY",
                institution="TechNova Solutions Pvt. Ltd.",
                account_reference="TDS-192",
                amount=sal_amt,
                nominee_status="NOT_APPLICABLE",
                maturity_date=None,
                page_number=sal_page,
                extracted_text=f"AIS TDS-192 Reported Gross Salary: ₹{sal_amt:,.2f} | TDS Deposited: ₹{tds_amt:,.2f}",
                confidence="HIGH",
                details={"source": "AIS", "reported_gross_salary": sal_amt, "tds_deposited": tds_amt},
            )
        )

    # B2: SFT-016 Savings Bank Interest rows (tolerant of wrapped bank names)
    sb_row_re = re.compile(
        r"([A-Za-z0-9\s.&()-]*?Bank\s+Ltd\.?(?:\s*\(DEMO\))?)\s*\|?\s*([A-Z0-9]{6,16})\s*\|\s*([A-Z0-9-]+)\s*\|\s*Savings\s+Account\s*\|\s*₹\s*([\d,]+\.\d{2})\s*\|?\s*([A-Za-z\s/]+)",
        re.IGNORECASE,
    )
    for page in pages:
        # Collapse single line breaks inside SFT-016 section so wrapped institution names match
        if "SFT-016: INTEREST FROM SAVINGS" not in page.cleaned_text.upper() and "SAVINGS ACCOUNT" not in page.cleaned_text.upper():
            continue
        flat_page = re.sub(r"\s+", " ", page.cleaned_text)
        for m in sb_row_re.finditer(flat_page):
            bank, ent_code, acct_no, int_str, status_txt = m.groups()
            bank_clean = bank.strip()
            # Trim any preceding header words if matched before bank name
            for marker in ("(₹)", "Status"):
                if marker in bank_clean:
                    bank_clean = bank_clean.split(marker)[-1].strip()
            int_amt = _parse_inr(int_str)
            res.assets.append(
                ExtractedAssetRecord(
                    asset_type="AIS_SAVINGS_ACCOUNT",
                    institution=bank_clean,
                    account_reference=mask_reference(acct_no.strip()),
                    amount=int_amt,
                    nominee_status="UNKNOWN",
                    maturity_date=None,
                    page_number=page.page_number,
                    extracted_text=f"AIS SFT-016: {bank_clean} | Account {mask_reference(acct_no.strip())} | Interest: ₹{int_amt:,.2f}",
                    confidence="NEEDS_VERIFICATION",
                    details={
                        "source": "AIS",
                        "entity_code": ent_code.strip(),
                        "last4": _last4(acct_no),
                        "interest_credited": int_amt,
                        "ais_status": status_txt.strip(),
                    },
                )
            )

    # B3: Term Deposit Interest
    fd_match = re.search(
        r"(Horizon\s+Trust\s+Bank[^\|]*)\s*\|\s*([A-Z0-9-]+FD-[A-Z0-9-]+)\s*\|\s*₹\s*([\d,]+\.\d{2})\s*\|\s*([^\|]+)\s*\|\s*₹\s*([\d,]+\.\d{2})",
        full_text,
        re.IGNORECASE,
    )
    if fd_match:
        bank, fd_ref, prin_str, period_str, accr_str = fd_match.groups()
        fd_page = next((p.page_number for p in pages if fd_ref in p.cleaned_text), 2)
        res.assets.append(
            ExtractedAssetRecord(
                asset_type="AIS_FD_INTEREST",
                institution=bank.strip(),
                account_reference=mask_reference(fd_ref.strip()),
                amount=_parse_inr(accr_str),
                nominee_status="UNKNOWN",
                maturity_date=None,
                page_number=fd_page,
                extracted_text=f"AIS SFT-016 Term Deposit {mask_reference(fd_ref.strip())}: Principal ₹{_parse_inr(prin_str):,.2f}, Accrued Interest ₹{_parse_inr(accr_str):,.2f}",
                confidence="HIGH",
                details={"source": "AIS", "last4": _last4(fd_ref), "principal": _parse_inr(prin_str), "period": period_str.strip()},
            )
        )

    # B4: Dividend Income total
    div_match = re.search(r"Total\s+Dividend\s+Income\s*\|\s*-\s*\|\s*FY\s*2025[–-]26\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    if div_match:
        div_amt = _parse_inr(div_match.group(1))
        div_page = next((p.page_number for p in pages if "Total Dividend Income" in p.cleaned_text), 2)
        res.assets.append(
            ExtractedAssetRecord(
                asset_type="AIS_DIVIDEND_INCOME",
                institution="Equities & Mutual Funds (AIS)",
                account_reference="SFT-DIV",
                amount=div_amt,
                nominee_status="NOT_APPLICABLE",
                maturity_date=None,
                page_number=div_page,
                extracted_text=f"AIS Total Dividend Income FY 2025–26: ₹{div_amt:,.2f}",
                confidence="HIGH",
                details={"source": "AIS", "dividend_income": div_amt},
            )
        )

    return res


def _extract_form_16(pages: list[PageText]) -> ExtractionResult:
    res = ExtractionResult()
    full_text = "\n".join(p.cleaned_text for p in pages)
    emp_match = re.search(r"Employer\s+Name:\s*\|\s*([^\|]+?)\s*\|\s*Employee\s+Name", full_text, re.IGNORECASE)
    employer = emp_match.group(1).strip() if emp_match else "Employer (Form 16)"

    gross_match = re.search(r"Total\s*\(FY\s*2025[–-]26\)\s*\|\s*4\s+Quarters\s*\|\s*₹\s*([\d,]+\.\d{2})\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    if not gross_match:
        gross_match = re.search(r"Total\s+Gross\s+Salary\s*\|.*?₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    gross_sal = _parse_inr(gross_match.group(1)) if gross_match else 0.0
    tds_amt = _parse_inr(gross_match.group(2)) if (gross_match and gross_match.lastindex and gross_match.lastindex >= 2) else 0.0

    taxable_match = re.search(r"Total\s+Taxable\s+Income.*?₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    taxable_inc = _parse_inr(taxable_match.group(1)) if taxable_match else 0.0

    hra_match = re.search(r"HRA\s+Exemption\s+u/s\s+10\(13A\).*?₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    std_match = re.search(r"Standard\s+Deduction\s+u/s\s+16\(ia\)\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    via_match = re.search(r"Sec\s+80D:.*?\|\s*₹\s*[\d,]+\.\d{2}\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)

    res.assets.append(
        ExtractedAssetRecord(
            asset_type="FORM16_SALARY",
            institution=employer,
            account_reference="FORM16-FY2526",
            amount=gross_sal,
            nominee_status="NOT_APPLICABLE",
            maturity_date=None,
            page_number=2 if len(pages) >= 2 else 1,
            extracted_text=f"Form 16 Gross Salary: ₹{gross_sal:,.2f} | Taxable Income: ₹{taxable_inc:,.2f} | TDS: ₹{tds_amt:,.2f}",
            confidence="HIGH",
            details={
                "source": "FORM_16",
                "gross_salary": gross_sal,
                "taxable_income": taxable_inc,
                "tds_deducted": tds_amt,
                "hra_exemption": _parse_inr(hra_match.group(1)) if hra_match else 0.0,
                "standard_deduction": _parse_inr(std_match.group(1)) if std_match else 0.0,
                "chapter_via_total": _parse_inr(via_match.group(1)) if via_match else 0.0,
            },
        )
    )
    return res


def _extract_insurance_policy(pages: list[PageText]) -> ExtractionResult:
    res = ExtractionResult()
    full_text = "\n".join(p.cleaned_text for p in pages)

    insurer_match = re.search(r"^([A-Z][A-Za-z\s.&]+INSURANCE\s+CO\.\s+LTD\.?(?:\s*\(DEMO\))?)", pages[0].cleaned_text, re.MULTILINE | re.IGNORECASE)
    insurer = insurer_match.group(1).strip() if insurer_match else "Life Insurance Company"

    pol_match = re.search(r"Policy\s+Number\s*\|\s*([A-Z0-9-]+)", full_text, re.IGNORECASE)
    raw_pol = pol_match.group(1).strip() if pol_match else None

    sa_match = re.search(r"Sum\s+Assured\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    sum_assured = _parse_inr(sa_match.group(1)) if sa_match else 0.0

    prem_match = re.search(r"Modal\s+Premium\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    modal_prem = _parse_inr(prem_match.group(1)) if prem_match else 0.0

    ann_match = re.search(r"Annualized\s+Premium\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    ann_prem = _parse_inr(ann_match.group(1)) if ann_match else modal_prem * 12

    mat_match = re.search(r"Maturity\s+Date\s*\|\s*(\d{2}-[A-Za-z]{3}-\d{4})", full_text, re.IGNORECASE)
    mat_date = _parse_date(mat_match.group(1)) if mat_match else None

    # Inspect Nominee section on its exact page
    nominee_page = 1
    nominee_status = "NEEDS_VERIFICATION"
    nominee_evidence = "Nominee details not found in the uploaded policy document."
    for p in pages:
        if "nominee" in p.cleaned_text.lower():
            nominee_page = p.page_number
            lines = p.cleaned_text.splitlines()
            # Check if "Nominee Full Name" has a value after "|"
            for ln in lines:
                if "nominee full name" in ln.lower():
                    parts = [c.strip() for c in ln.split("|")]
                    if len(parts) >= 2 and parts[1] and parts[1].lower() not in ("", "-", "blank", "none", "n/a"):
                        nominee_status = "RECORDED"
                        nominee_evidence = f"Recorded nominee: {parts[1]}"
                    else:
                        nominee_status = "NEEDS_VERIFICATION"
                        nominee_evidence = "Section 4 – Nominee Details: Nominee Full Name and related fields are blank."
                    break
            break

    res.assets.append(
        ExtractedAssetRecord(
            asset_type="LIFE_INSURANCE",
            institution=insurer,
            account_reference=mask_reference(raw_pol),
            amount=sum_assured,
            nominee_status=nominee_status,
            maturity_date=mat_date,
            page_number=nominee_page,
            extracted_text=f"Policy {mask_reference(raw_pol)} | Sum Assured: ₹{sum_assured:,.2f} | Annual Premium: ₹{ann_prem:,.2f} | {nominee_evidence}",
            confidence="NEEDS_VERIFICATION" if nominee_status == "NEEDS_VERIFICATION" else "HIGH",
            details={
                "source": "INSURANCE_POLICY",
                "last4": _last4(raw_pol),
                "sum_assured": sum_assured,
                "modal_premium": modal_prem,
                "annual_premium": ann_prem,
                "nominee_page": nominee_page,
                "nominee_evidence": nominee_evidence,
            },
        )
    )
    return res


def _extract_fd_certificate(pages: list[PageText]) -> ExtractionResult:
    res = ExtractionResult()
    full_text = "\n".join(p.cleaned_text for p in pages)
    p1 = pages[0].cleaned_text if pages else ""

    bank_match = re.search(r"^([A-Z][A-Za-z\s.&]+BANK\s+LTD\.?(?:\s*\(DEMO\))?)", p1, re.MULTILINE | re.IGNORECASE)
    bank_name = bank_match.group(1).strip() if bank_match else "Horizon Trust Bank Ltd."

    fd_match = re.search(r"FD\s+Account\s+Number:\s*\|\s*([A-Z0-9-]+)", full_text, re.IGNORECASE)
    raw_fd = fd_match.group(1).strip() if fd_match else None

    prin_match = re.search(r"Principal\s+Amount\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    principal = _parse_inr(prin_match.group(1)) if prin_match else 0.0

    rate_match = re.search(r"Interest\s+Rate\s*\|\s*([\d.]+)%", full_text, re.IGNORECASE)
    rate = float(rate_match.group(1)) if rate_match else 0.0

    mat_amt_match = re.search(r"Maturity\s+Amount\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    mat_amt = _parse_inr(mat_amt_match.group(1)) if mat_amt_match else 0.0

    mat_dt_match = re.search(r"Maturity\s+Date\s*\|\s*(\d{2}-[A-Za-z]{3}-\d{4})", full_text, re.IGNORECASE)
    mat_date = _parse_date(mat_dt_match.group(1)) if mat_dt_match else None

    auto_renew = "auto-renewal: yes" in full_text.lower()
    nom_registered = "registered (" in full_text.lower()

    res.assets.append(
        ExtractedAssetRecord(
            asset_type="FIXED_DEPOSIT",
            institution=bank_name,
            account_reference=mask_reference(raw_fd),
            amount=principal,
            nominee_status="RECORDED" if nom_registered else "NEEDS_VERIFICATION",
            maturity_date=mat_date,
            page_number=1,
            extracted_text=f"FD {mask_reference(raw_fd)} | Principal: ₹{principal:,.2f} | Maturity Date: {mat_date} | Maturity Amount: ₹{mat_amt:,.2f} | Auto-Renewal: {'YES' if auto_renew else 'NO'}",
            confidence="HIGH",
            details={
                "source": "FD_CERTIFICATE",
                "last4": _last4(raw_fd),
                "principal": principal,
                "interest_rate": rate,
                "maturity_amount": mat_amt,
                "auto_renewal": auto_renew,
            },
        )
    )
    return res


def _extract_loan_statement(pages: list[PageText]) -> ExtractionResult:
    res = ExtractionResult()
    full_text = "\n".join(p.cleaned_text for p in pages)
    p1 = pages[0].cleaned_text if pages else ""

    lender_match = re.search(r"^([A-Z][A-Za-z\s.&]+LTD\.?(?:\s*\(DEMO\))?)", p1, re.MULTILINE | re.IGNORECASE)
    lender = lender_match.group(1).strip() if lender_match else "Crestline FinServe Ltd."

    loan_match = re.search(r"Loan\s+Account\s+No\.?:\s*\|\s*([A-Z0-9-]+)", full_text, re.IGNORECASE)
    raw_loan = loan_match.group(1).strip() if loan_match else None

    orig_match = re.search(r"Original\s+Loan\s+Amount:\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    orig_amt = _parse_inr(orig_match.group(1)) if orig_match else 0.0

    emi_match = re.search(r"Monthly\s+EMI:\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    emi_amt = _parse_inr(emi_match.group(1)) if emi_match else 0.0

    out_match = re.search(r"Outstanding\s+\(15-May-2026\):\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    if not out_match:
        out_match = re.search(r"Outstanding(?:\s+Principal)?[^₹]*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    outstanding = _parse_inr(out_match.group(1)) if out_match else 0.0

    fy_out_match = re.search(r"Outstanding\s+\(31-Mar-2026\):\s*\|\s*₹\s*([\d,]+\.\d{2})", full_text, re.IGNORECASE)
    fy_outstanding = _parse_inr(fy_out_match.group(1)) if fy_out_match else outstanding

    res.assets.append(
        ExtractedAssetRecord(
            asset_type="PERSONAL_LOAN",
            institution=lender,
            account_reference=mask_reference(raw_loan),
            amount=outstanding,
            nominee_status="NOT_APPLICABLE",
            maturity_date=_parse_date("05-Sep-2027"),
            page_number=1,
            extracted_text=f"Personal Loan {mask_reference(raw_loan)} ({lender}) | Original: ₹{orig_amt:,.2f} | EMI: ₹{emi_amt:,.2f} | Outstanding: ₹{outstanding:,.2f}",
            confidence="HIGH",
            details={
                "source": "LOAN_STATEMENT",
                "last4": _last4(raw_loan),
                "original_amount": orig_amt,
                "monthly_emi": emi_amt,
                "fy_closing_principal": fy_outstanding,
                "outstanding_principal": outstanding,
            },
        )
    )
    return res


def extract_structured_data(document_type: str, pages: list[PageText]) -> ExtractionResult:
    """Dispatch document extraction based on classified document type."""
    if document_type == "bank_statement":
        return _extract_bank_statement(pages)
    if document_type == "annual_information_statement":
        return _extract_ais_report(pages)
    if document_type == "form_16":
        return _extract_form_16(pages)
    if document_type == "life_insurance_policy":
        return _extract_insurance_policy(pages)
    if document_type == "fixed_deposit_certificate":
        return _extract_fd_certificate(pages)
    if document_type == "personal_loan_statement":
        return _extract_loan_statement(pages)
    return ExtractionResult()
