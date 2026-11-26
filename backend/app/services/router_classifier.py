"""Hybrid RAG + SQL Financial Reasoning Router (parameterized SQL only)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services import sql_analytics
from app.services.nlp.intent import IntentResult
from app.services.nlp.syntactic import SyntacticAnalysis


def gather_sql_context_for_intent(
    db: Session,
    user_id: int,
    intent_res: IntentResult,
    syntax: SyntacticAnalysis,
    resolved_query: str,
) -> tuple[str, dict[str, Any]]:
    """Route NLP intent + syntactic profile to predefined, parameterized SQL analytics."""
    sql_data: dict[str, Any] = {}
    intents = {intent_res.intent, *intent_res.secondary_intents}
    q = resolved_query.lower()

    if "GENERAL_FINANCIAL_OVERVIEW" in intents or intent_res.pragmatic_type in ("HOLISTIC_HEALTH_CHECK", "RISK_TRIAGE"):
        sql_data["holistic_financial_health"] = sql_analytics.sql_holistic_financial_health(db, user_id)

    if "BANK_ACCOUNT_QUERY" in intents or "FINANCIAL_GAP_QUERY" in intents or "ais" in q:
        sql_data["bank_accounts"] = sql_analytics.sql_bank_accounts_summary(db, user_id)

    if "SUBSCRIPTION_QUERY" in intents or "EXPENSE_QUERY" in intents:
        sql_data["subscriptions_and_recurring"] = sql_analytics.sql_subscription_and_recurring_expenses(db, user_id)

    if "FD_QUERY" in intents:
        sql_data["fixed_deposits"] = sql_analytics.sql_upcoming_fd_maturities(db, user_id)

    if "SALARY_QUERY" in intents or "TAX_QUERY" in intents:
        sql_data["ais_vs_form16"] = sql_analytics.sql_ais_vs_form16_comparison(db, user_id)

    if "LOAN_QUERY" in intents or "EMI_QUERY" in intents:
        sql_data["loan_reconciliation"] = sql_analytics.sql_loan_and_emi_reconciliation(db, user_id)

    if (
        "NOMINEE_QUERY" in intents
        or "INSURANCE_QUERY" in intents
        or "FINANCIAL_RISK_QUERY" in intents
        or "FINANCIAL_GAP_QUERY" in intents
        or "INVESTMENT_QUERY" in intents
    ):
        sql_data["assets_and_findings"] = sql_analytics.sql_all_assets_and_findings(db, user_id)

    route = intent_res.processing_route
    if sql_data and route == "RAG" and (syntax.is_comparison or syntax.has_negation or syntax.is_superlative):
        route = "HYBRID"
    return route, sql_data


def classify_and_gather_sql_context(db: Session, user_id: int, question: str) -> tuple[str, dict[str, Any]]:
    """Backward-compatible wrapper using lexical + syntactic + intent analysis."""
    from app.services.nlp.intent import classify_intent
    from app.services.nlp.lexical import analyze_lexical
    from app.services.nlp.syntactic import analyze_syntax

    lex = analyze_lexical(question)
    syn = analyze_syntax(lex)
    intent_res = classify_intent(lex, syn)
    return gather_sql_context_for_intent(db, user_id, intent_res, syn, lex.normalized_text)
