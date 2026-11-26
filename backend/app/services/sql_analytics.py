"""Predefined, parameterized SQL analytics functions for exact numerical calculations."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document, FinancialAsset, Finding, Transaction
from app.services.intelligence import get_reference_date
from app.timezone_utils import IST_TIMEZONE, format_ist_display, get_ist_now


def sql_bank_accounts_summary(db: Session, user_id: int) -> dict[str, Any]:
    """Count and list verified and AIS-discovered bank accounts strictly for user_id."""
    rows = db.execute(
        select(FinancialAsset, Document.filename)
        .join(Document, Document.id == FinancialAsset.source_document_id)
        .where(
            FinancialAsset.user_id == user_id,
            FinancialAsset.asset_type.in_(["SAVINGS_ACCOUNT", "AIS_SAVINGS_ACCOUNT"]),
        )
    ).all()

    accounts = []
    seen_last4: set[str] = set()
    for asset, fname in rows:
        last4 = (asset.details or {}).get("last4", "")
        key = last4 or f"{asset.institution}_{asset.account_reference}"
        accounts.append({
            "asset_type": asset.asset_type,
            "institution": asset.institution,
            "account_reference": asset.account_reference,
            "amount_inr": float(asset.amount),
            "last4": last4,
            "source_document": fname,
            "page": asset.page_number,
            "confidence": asset.confidence,
        })
        seen_last4.add(key)

    return {
        "distinct_bank_accounts_count": len(seen_last4),
        "accounts": accounts,
    }


def sql_subscription_and_recurring_expenses(db: Session, user_id: int) -> dict[str, Any]:
    """Calculate exact monthly and annualized subscription and recurring expenses via SQL."""
    rows = db.execute(
        select(
            Transaction.category,
            Transaction.description,
            func.count(Transaction.id).label("tx_count"),
            func.sum(Transaction.amount).label("total_amount"),
            func.avg(Transaction.amount).label("avg_amount"),
            Document.filename,
        )
        .join(Document, Document.id == Transaction.document_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == "DEBIT",
            Transaction.category.in_(
                ["SUBSCRIPTION", "BANK_FEE_SMS", "BANK_FEE_AMC", "LOAN_EMI", "INSURANCE_PREMIUM", "RENT"]
            ),
        )
        .group_by(Transaction.category, Transaction.description, Document.filename)
    ).all()

    subscriptions = []
    bank_fees = []
    other_recurring = []

    for cat, desc, cnt, total, avg, fname in rows:
        item = {
            "category": cat,
            "description": desc,
            "occurrences": int(cnt),
            "per_occurrence_inr": round(float(avg), 2),
            "annual_total_inr": round(float(total), 2),
            "source_document": fname,
        }
        if cat == "SUBSCRIPTION":
            subscriptions.append(item)
        elif cat in ("BANK_FEE_SMS", "BANK_FEE_AMC"):
            bank_fees.append(item)
        else:
            other_recurring.append(item)

    sub_annual = round(sum(s["annual_total_inr"] for s in subscriptions), 2)
    sub_monthly = round(
        sum(s["per_occurrence_inr"] for s in subscriptions if s["occurrences"] >= 6), 2
    )
    return {
        "subscription_count": len(subscriptions),
        "monthly_subscriptions_inr": sub_monthly,
        "annual_subscriptions_inr": sub_annual,
        "subscriptions": subscriptions,
        "bank_fees_annual_inr": round(sum(f["annual_total_inr"] for f in bank_fees), 2),
        "bank_fees": bank_fees,
        "other_recurring_debits": other_recurring,
    }


def sql_upcoming_fd_maturities(db: Session, user_id: int, window_days: int = 60) -> dict[str, Any]:
    """Identify Fixed Deposits maturing within `window_days` of reference date."""
    ref_date = get_reference_date()
    rows = db.execute(
        select(FinancialAsset, Document.filename)
        .join(Document, Document.id == FinancialAsset.source_document_id)
        .where(
            FinancialAsset.user_id == user_id,
            FinancialAsset.asset_type == "FIXED_DEPOSIT",
        )
    ).all()

    fds = []
    for asset, fname in rows:
        days_left = (asset.maturity_date - ref_date).days if asset.maturity_date else None
        fds.append({
            "institution": asset.institution,
            "account_reference": asset.account_reference,
            "principal_inr": float(asset.amount),
            "maturity_date": asset.maturity_date.isoformat() if asset.maturity_date else None,
            "days_remaining_from_reference": days_left,
            "within_window": days_left is not None and 0 <= days_left <= window_days,
            "maturity_amount_inr": (asset.details or {}).get("maturity_amount"),
            "auto_renewal": (asset.details or {}).get("auto_renewal"),
            "source_document": fname,
            "page": asset.page_number,
        })
    return {"reference_date": ref_date.isoformat(), "fixed_deposits": fds}


def sql_ais_vs_form16_comparison(db: Session, user_id: int) -> dict[str, Any]:
    """Compare AIS TDS-192 salary and Form 16 gross salary & TDS."""
    rows = db.execute(
        select(FinancialAsset, Document.filename)
        .join(Document, Document.id == FinancialAsset.source_document_id)
        .where(
            FinancialAsset.user_id == user_id,
            FinancialAsset.asset_type.in_(["AIS_SALARY_SUMMARY", "FORM16_SALARY"]),
        )
    ).all()

    ais_data = None
    form16_data = None
    for asset, fname in rows:
        payload = {
            "gross_salary_inr": float(asset.amount),
            "details": asset.details,
            "source_document": fname,
            "page": asset.page_number,
        }
        if asset.asset_type == "AIS_SALARY_SUMMARY":
            ais_data = payload
        else:
            form16_data = payload

    diff = None
    if ais_data and form16_data:
        diff = round(ais_data["gross_salary_inr"] - form16_data["gross_salary_inr"], 2)

    return {
        "ais_salary": ais_data,
        "form16_salary": form16_data,
        "gross_salary_difference_inr": diff,
    }


def sql_loan_and_emi_reconciliation(db: Session, user_id: int) -> dict[str, Any]:
    """Fetch personal loan outstanding balance and match against bank EMI debits."""
    loans = db.execute(
        select(FinancialAsset, Document.filename)
        .join(Document, Document.id == FinancialAsset.source_document_id)
        .where(
            FinancialAsset.user_id == user_id,
            FinancialAsset.asset_type == "PERSONAL_LOAN",
        )
    ).all()

    emi_stats = db.execute(
        select(
            func.count(Transaction.id),
            func.sum(Transaction.amount),
            func.avg(Transaction.amount),
        ).where(
            Transaction.user_id == user_id,
            Transaction.category == "LOAN_EMI",
        )
    ).one()

    return {
        "loans": [
            {
                "institution": a.institution,
                "account_reference": a.account_reference,
                "outstanding_principal_inr": float(a.amount),
                "details": a.details,
                "source_document": fname,
                "page": a.page_number,
            }
            for a, fname in loans
        ],
        "bank_statement_emi_debits_count": int(emi_stats[0] or 0),
        "bank_statement_emi_total_inr": round(float(emi_stats[1] or 0.0), 2),
        "bank_statement_emi_avg_inr": round(float(emi_stats[2] or 0.0), 2),
    }


def sql_all_assets_and_findings(db: Session, user_id: int) -> dict[str, Any]:
    """Return full structured snapshot of all assets and findings for user_id."""
    assets = db.execute(
        select(FinancialAsset, Document.filename)
        .join(Document, Document.id == FinancialAsset.source_document_id)
        .where(FinancialAsset.user_id == user_id)
    ).all()
    findings = db.scalars(
        select(Finding).where(Finding.user_id == user_id)
    ).all()

    return {
        "assets": [
            {
                "asset_type": a.asset_type,
                "institution": a.institution,
                "account_reference": a.account_reference,
                "amount_inr": float(a.amount),
                "nominee_status": a.nominee_status,
                "maturity_date": a.maturity_date.isoformat() if a.maturity_date else None,
                "source_document": fname,
                "page": a.page_number,
                "confidence": a.confidence,
            }
            for a, fname in assets
        ],
        "findings": [
            {
                "finding_type": f.finding_type,
                "title": f.title,
                "severity": f.severity,
                "confidence": f.confidence,
                "description": f.description,
                "evidence": f.evidence,
            }
            for f in findings
        ],
    }


def sql_holistic_financial_health(db: Session, user_id: int) -> dict[str, Any]:
    """Parameterized overview across assets, liabilities, insurance, recurring leaks, and open findings."""
    snapshot = sql_all_assets_and_findings(db, user_id)
    subs = sql_subscription_and_recurring_expenses(db, user_id)
    loans = sql_loan_and_emi_reconciliation(db, user_id)
    fds = sql_upcoming_fd_maturities(db, user_id)

    assets = snapshot["assets"]
    savings_total = sum(a["amount_inr"] for a in assets if a["asset_type"] == "SAVINGS_ACCOUNT")
    fd_total = sum(a["amount_inr"] for a in assets if a["asset_type"] == "FIXED_DEPOSIT")
    insurance_cover = sum(a["amount_inr"] for a in assets if a["asset_type"] == "LIFE_INSURANCE")
    loan_outstanding = sum(a["amount_inr"] for a in assets if a["asset_type"] == "PERSONAL_LOAN")

    open_findings = snapshot["findings"]
    return {
        "savings_balance_inr": round(savings_total, 2),
        "fixed_deposits_principal_inr": round(fd_total, 2),
        "life_insurance_cover_inr": round(insurance_cover, 2),
        "loan_outstanding_inr": round(loan_outstanding, 2),
        "annual_subscriptions_inr": subs["annual_subscriptions_inr"],
        "bank_fees_annual_inr": subs["bank_fees_annual_inr"],
        "upcoming_fd_maturities": fds["fixed_deposits"],
        "loan_emi_summary": loans,
        "findings_by_severity": {
            "RED": [f for f in open_findings if f["severity"] == "RED"],
            "AMBER": [f for f in open_findings if f["severity"] == "AMBER"],
            "INFO": [f for f in open_findings if f["severity"] == "INFO"],
            "GREEN": [f for f in open_findings if f["severity"] == "GREEN"],
        },
        "total_assets_count": len(assets),
    }


def sql_transactions_in_window(
    db: Session,
    user_id: int,
    start_date_str: str,
    end_date_str: str,
    label: str,
) -> dict[str, Any]:
    """Query exact financial transactions falling within an Asia/Kolkata (IST) calendar window."""
    start_d = date.fromisoformat(start_date_str)
    end_d = date.fromisoformat(end_date_str)
    rows = db.execute(
        select(Transaction, Document.filename)
        .join(Document, Document.id == Transaction.document_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= start_d,
            Transaction.transaction_date <= end_d,
        )
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
    ).all()

    items = [
        {
            "date": tx.transaction_date.isoformat(),
            "description": tx.description,
            "amount_inr": round(float(tx.amount), 2),
            "transaction_type": tx.transaction_type,
            "category": tx.category,
            "source_document": fname,
            "page": tx.page_number,
        }
        for tx, fname in rows
    ]
    total_debits = round(sum(i["amount_inr"] for i in items if i["transaction_type"] == "DEBIT"), 2)
    total_credits = round(sum(i["amount_inr"] for i in items if i["transaction_type"] == "CREDIT"), 2)
    return {
        "expression": label,
        "timezone": IST_TIMEZONE,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "transaction_count": len(items),
        "total_debits_inr": total_debits,
        "total_credits_inr": total_credits,
        "transactions": items[:25],
    }


def get_ist_runtime_context() -> dict[str, str]:
    now_ist = get_ist_now()
    return {
        "timezone": "Asia/Kolkata (IST, UTC+05:30)",
        "current_date_ist": now_ist.date().isoformat(),
        "current_datetime_ist": format_ist_display(now_ist, long_month=True),
        "current_iso_ist": now_ist.isoformat(),
    }
