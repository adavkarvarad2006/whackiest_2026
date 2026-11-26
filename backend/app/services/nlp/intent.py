"""Level 3 & Level 5 NLP: Semantic Intent Recognition, Financial Concept Mapping, and Pragmatic Reasoning."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.nlp.lexical import LexicalAnalysis
from app.services.nlp.syntactic import SyntacticAnalysis

INTENTS = [
    "BANK_ACCOUNT_QUERY",
    "INSURANCE_QUERY",
    "NOMINEE_QUERY",
    "TAX_QUERY",
    "SALARY_QUERY",
    "LOAN_QUERY",
    "EMI_QUERY",
    "FD_QUERY",
    "INVESTMENT_QUERY",
    "SUBSCRIPTION_QUERY",
    "EXPENSE_QUERY",
    "FINANCIAL_GAP_QUERY",
    "FINANCIAL_RISK_QUERY",
    "GENERAL_FINANCIAL_OVERVIEW",
    "DOCUMENT_QUERY",
    "UNKNOWN_INTENT",
]


@dataclass
class IntentResult:
    intent: str
    confidence: float
    secondary_intents: list[str]
    pragmatic_type: str | None  # e.g., HOLISTIC_HEALTH_CHECK, RISK_TRIAGE, EXPLANATION
    processing_route: str  # RAG | SQL | SQL+RAG | HYBRID


PRAGMATIC_HEALTH_PATTERNS = (
    "financially prepared",
    "everything okay",
    "everything ok",
    "worry about",
    "financial health",
    "blindspot",
    "biggest risk",
    "anything wrong",
    "financial overview",
    "summary of my finances",
    "kya sab theek",
    "koi tension",
    "financial condition",
)


def classify_intent(lexical: LexicalAnalysis, syntax: SyntacticAnalysis) -> IntentResult:
    norm = lexical.normalized_text
    lemmas = set(lexical.lemmas)

    # Level 5 Pragmatic checks first
    if any(p in norm for p in PRAGMATIC_HEALTH_PATTERNS):
        if "worry" in norm or "risk" in norm or "blindspot" in norm or "wrong" in norm:
            return IntentResult(
                intent="FINANCIAL_RISK_QUERY",
                confidence=0.92,
                secondary_intents=["FINANCIAL_GAP_QUERY", "GENERAL_FINANCIAL_OVERVIEW"],
                pragmatic_type="RISK_TRIAGE",
                processing_route="HYBRID",
            )
        return IntentResult(
            intent="GENERAL_FINANCIAL_OVERVIEW",
            confidence=0.92,
            secondary_intents=["FINANCIAL_GAP_QUERY", "FINANCIAL_RISK_QUERY"],
            pragmatic_type="HOLISTIC_HEALTH_CHECK",
            processing_route="HYBRID",
        )

    scores: dict[str, float] = {k: 0.0 for k in INTENTS}

    if "nominee" in lemmas or "beneficiary" in norm or syntax.relation == "missing_nominee":
        scores["NOMINEE_QUERY"] += 0.92
    if "insurance" in lemmas or "policy" in lemmas or "premium" in lemmas or "sum assured" in norm:
        scores["INSURANCE_QUERY"] += 0.80
    if "bank" in lemmas or "account" in lemmas or "ifsc" in norm or syntax.relation == "account_missing_from_statements":
        scores["BANK_ACCOUNT_QUERY"] += 0.85
    if "fixed deposit" in norm or "fd" in lexical.tokens or "maturity" in lemmas or "mature" in lemmas:
        scores["FD_QUERY"] += 0.88
    if "emi" in lemmas or "equated monthly instalment" in norm:
        scores["EMI_QUERY"] += 0.90
    if "loan" in lemmas or "outstanding" in lemmas or "principal" in lemmas or "lender" in lemmas:
        scores["LOAN_QUERY"] += 0.86
    if "salary" in lemmas or "payroll" in lemmas or "employer" in lemmas:
        scores["SALARY_QUERY"] += 0.86
    if "form16" in norm or "tds" in lemmas or "tax" in lemmas or "80c" in norm or "80d" in norm or "ais" in norm:
        scores["TAX_QUERY"] += 0.84
    if "subscription" in lemmas or "streamflix" in norm or "cloudnotes" in norm or "tunewave" in norm:
        scores["SUBSCRIPTION_QUERY"] += 0.90
    if "expense" in lemmas or "charge" in lemmas or "fee" in lemmas or "deduct" in lemmas or "spend" in lemmas or "rent" in lemmas:
        scores["EXPENSE_QUERY"] += 0.82
    if "mutual fund" in norm or "systematic investment" in norm or "sip" in lemmas or "dividend" in lemmas or "ppf" in norm or "epf" in norm or "investment" in lemmas:
        scores["INVESTMENT_QUERY"] += 0.86
    if "gap" in lemmas or "overlooked" in norm or "undiscovered" in norm or "forgotten" in lemmas or ("missing" in lemmas and "nominee" not in lemmas):
        scores["FINANCIAL_GAP_QUERY"] += 0.85
    if "risk" in lemmas or "discrepancy" in lemmas or "mismatch" in lemmas or "flag" in lemmas:
        scores["FINANCIAL_RISK_QUERY"] += 0.84
    if "document" in lemmas or "pdf" in lemmas or "uploaded" in lemmas or "which document" in norm:
        scores["DOCUMENT_QUERY"] += 0.72

    # Disambiguate priority when multiple signals fire cleanly
    if scores["NOMINEE_QUERY"] > 0 and scores["INSURANCE_QUERY"] > 0:
        scores["NOMINEE_QUERY"] += 0.15
    if syntax.is_comparison and ("ais" in norm or "form16" in norm or "salary" in lemmas):
        scores["SALARY_QUERY"] += 0.18
        scores["TAX_QUERY"] += 0.12
    if scores["SUBSCRIPTION_QUERY"] > 0 and scores["EXPENSE_QUERY"] > 0:
        scores["SUBSCRIPTION_QUERY"] += 0.10

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_intent, top_score = ranked[0]
    if top_score < 0.30:
        top_intent = "UNKNOWN_INTENT"
        top_score = 0.25

    secondary = [k for k, v in ranked[1:4] if v >= 0.55]

    # Route determination (Financial Reasoning Engine)
    if top_intent in ("SUBSCRIPTION_QUERY", "EXPENSE_QUERY") and syntax.question_type in ("WH_HOW_MUCH", "WH_HOW_MANY"):
        route = "SQL+RAG"
    elif top_intent in ("BANK_ACCOUNT_QUERY",) and syntax.question_type == "WH_HOW_MANY":
        route = "SQL"
    elif top_intent == "FD_QUERY" and syntax.question_type == "WH_WHEN":
        route = "SQL+RAG"
    elif top_intent in ("INSURANCE_QUERY",) and not syntax.has_negation and not syntax.is_superlative and not syntax.is_comparison:
        route = "RAG"
    elif top_intent == "UNKNOWN_INTENT":
        route = "RAG"
    else:
        route = "HYBRID"

    pragmatic = "EXPLANATION" if syntax.question_type == "WH_WHY" else None
    return IntentResult(
        intent=top_intent,
        confidence=round(min(0.98, top_score), 2),
        secondary_intents=secondary,
        pragmatic_type=pragmatic,
        processing_route=route,
    )
