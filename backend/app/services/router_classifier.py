"""Hybrid RAG + SQL query intent router (parameterized SQL only)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services import sql_analytics


def classify_and_gather_sql_context(db: Session, user_id: int, question: str) -> tuple[str, dict[str, Any]]:
    """
    Classify the question into RAG, SQL, or HYBRID and invoke only
    predefined, parameterized SQL analytics functions relevant to the query.
    """
    q = question.lower()
    sql_data: dict[str, Any] = {}

    is_count_or_calc = any(
        k in q
        for k in (
            "how many",
            "how much",
            "calculate",
            "total",
            "annual",
            "monthly",
            "spend",
            "spending",
            "cost",
            "count",
            "sum",
            "balance",
            "outstanding",
        )
    )
    is_comparison_or_flag = any(
        k in q
        for k in (
            "compare",
            "discrepancy",
            "difference",
            "mismatch",
            "flag",
            "blindspot",
            "verification",
            "missing",
            "undiscovered",
            "overlooked",
            "reconcile",
            "match",
            "ais",
            "form 16",
            "why",
            "all financial assets",
            "findings",
        )
    )

    if any(k in q for k in ("bank account", "accounts", "ais", "overlooked", "undiscovered", "discovered")):
        sql_data["bank_accounts"] = sql_analytics.sql_bank_accounts_summary(db, user_id)

    if any(k in q for k in ("subscription", "recurring", "charge", "fee", "maintenance", "sms", "expense", "spend")):
        sql_data["subscriptions_and_recurring"] = sql_analytics.sql_subscription_and_recurring_expenses(db, user_id)

    if any(k in q for k in ("fd", "fixed deposit", "mature", "maturity", "deposit")):
        sql_data["fixed_deposits"] = sql_analytics.sql_upcoming_fd_maturities(db, user_id)

    if any(k in q for k in ("salary", "form 16", "form16", "ais", "income", "tds", "discrepancy", "compare")):
        sql_data["ais_vs_form16"] = sql_analytics.sql_ais_vs_form16_comparison(db, user_id)

    if any(k in q for k in ("loan", "emi", "outstanding", "principal", "repay")):
        sql_data["loan_reconciliation"] = sql_analytics.sql_loan_and_emi_reconciliation(db, user_id)

    if any(k in q for k in ("nominee", "flag", "blindspot", "finding", "verification", "attention", "red", "amber", "asset", "summary", "overview")):
        sql_data["assets_and_findings"] = sql_analytics.sql_all_assets_and_findings(db, user_id)

    if not sql_data and is_count_or_calc:
        sql_data["assets_and_findings"] = sql_analytics.sql_all_assets_and_findings(db, user_id)

    if sql_data and is_comparison_or_flag:
        mode = "HYBRID"
    elif sql_data and is_count_or_calc:
        mode = "SQL+RAG"
    elif sql_data:
        mode = "HYBRID"
    else:
        mode = "RAG"

    return mode, sql_data
