"""Level 3 & Level 5 NLP: Semantic Intent Recognition, Three-Tier Query Classification, and Pragmatic Reasoning."""

from __future__ import annotations

import re
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
    "CREDIT_SCORE_QUERY",
    "GENERAL_CONCEPT_QUERY",
    "UNKNOWN_INTENT",
]

QUERY_CATEGORIES = (
    "GENERAL_KNOWLEDGE",
    "PERSONAL_FINANCIAL_DATA",
    "HYBRID_QUERY",
)

_PERSONAL_POSSESSIVE_RE = re.compile(
    r"\b(my|mine|i've|our|mera|mere|meri|humara|hamara|do i have|have i|am i|what do i|"
    r"how many .{0,30} do i|happens to me)\b",
    re.IGNORECASE,
)

_PERSONAL_WORKSPACE_RE = re.compile(
    r"\b(uploaded|workspace|form\s*16|form16|ais|pdf|pdfs|bank statement|statement|"
    r"horizon|metrocivic|saffron|deccan|surakshaguard|bharatlife|kavach|"
    r"streamflix|cloudnotes|tunewave|demo-|transactions?|closing balance|"
    r"deducted every month|monthly deductions?|paisa kat|paise kat)\b",
    re.IGNORECASE,
)

_GENERAL_CONCEPT_RE = re.compile(
    r"\b(what is|what are|explain|define|meaning|advantages?|disadvantages?|benefits?|"
    r"drawbacks?|pros and cons|types of|difference between|how does .{1,40} work|"
    r"how do .{1,40} work|with an example|example of|formula|compound interest|"
    r"inflation|credit score|recurring deposit|tax[- ]?saving)\b",
    re.IGNORECASE,
)

_HYBRID_EVALUATIVE_RE = re.compile(
    r"\b(good|bad|high|low|too much|too high|enough|sufficient|adequate|"
    r"diversified|diversification|balanced|allocation|optimal|competitive|"
    r"worth it|prepared|worry about|healthy|improve|optimize|better|"
    r"suitable|right for me|whether my)\b",
    re.IGNORECASE,
)

_GENERAL_VS_RE = re.compile(
    r"\b(fd|fixed deposit|rd|recurring deposit|sip|mutual fund|ppf|elss|nps|term|health insurance)\s+"
    r"(?:vs|versus|and|or)\s+"
    r"(fd|fixed deposit|rd|recurring deposit|sip|mutual fund|ppf|elss|nps|lump\s*sum|whole life|life insurance)\b",
    re.IGNORECASE,
)


@dataclass
class IntentResult:
    intent: str
    confidence: float
    secondary_intents: list[str]
    pragmatic_type: str | None  # e.g., HOLISTIC_HEALTH_CHECK, RISK_TRIAGE, EXPLANATION
    processing_route: str  # GENERAL_LLM | RAG | SQL | SQL+RAG | HYBRID | HYBRID_REASONING
    query_category: str = "PERSONAL_FINANCIAL_DATA"  # GENERAL_KNOWLEDGE | PERSONAL_FINANCIAL_DATA | HYBRID_QUERY
    routing_reason: str = ""


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


def detect_personal_markers(orig_text: str, norm_text: str) -> bool:
    """Detect whether the user explicitly references personal financial records or workspace data."""
    combined = f"{orig_text.lower()} {norm_text.lower()}"
    if _PERSONAL_POSSESSIVE_RE.search(combined):
        return True
    if _PERSONAL_WORKSPACE_RE.search(combined):
        # Guard against generic concept phrasing like "How does a bank statement work?"
        if re.search(r"\b(what is|meaning|how does .{1,35} work)\b", combined) and not re.search(r"\b(my|mera|meri|mere|uploaded|ais|form16|form 16)\b", combined):
            return False
        return True
    return False


def classify_query_category(
    lexical: LexicalAnalysis,
    syntax: SyntacticAnalysis,
    intent: str,
    pragmatic_type: str | None = None,
    prior_category: str | None = None,
) -> tuple[str, str]:
    """
    Classify user query into one of three categories:
    - GENERAL_KNOWLEDGE: Financial literacy / definitions / comparisons / concepts via Groq directly
    - PERSONAL_FINANCIAL_DATA: User-specific financial records via RAG + SQL
    - HYBRID_QUERY: Evaluative / advisory / benchmark questions combining personal data + general finance reasoning
    """
    orig = lexical.original_text.lower().strip()
    norm = lexical.normalized_text.lower().strip()
    combined = f"{orig} {norm}"

    has_personal = detect_personal_markers(orig, norm)
    has_general_concept = bool(_GENERAL_CONCEPT_RE.search(combined) or _GENERAL_VS_RE.search(combined))
    has_evaluative = bool(_HYBRID_EVALUATIVE_RE.search(combined))

    # Evaluative personal questions & holistic portfolio checks -> HYBRID_QUERY
    if pragmatic_type in ("HOLISTIC_HEALTH_CHECK", "RISK_TRIAGE") or intent == "GENERAL_FINANCIAL_OVERVIEW":
        return "HYBRID_QUERY", "Holistic or risk evaluation combining personal records with financial principles."

    if has_personal and has_evaluative:
        return "HYBRID_QUERY", "Personal financial query with evaluative/benchmark reasoning."

    # Audit/workspace-specific intents even without 'my' (e.g., "Which policies don't have nominees?")
    if intent in ("NOMINEE_QUERY", "FINANCIAL_GAP_QUERY", "FINANCIAL_RISK_QUERY", "SUBSCRIPTION_QUERY", "DOCUMENT_QUERY"):
        if has_evaluative:
            return "HYBRID_QUERY", f"Evaluative workspace audit ({intent})."
        return "PERSONAL_FINANCIAL_DATA", f"Workspace-specific audit intent ({intent})."

    if has_personal:
        return "PERSONAL_FINANCIAL_DATA", f"Explicit personal/workspace markers detected for {intent}."

    # Missing-item negation queries on bank/insurance/FD/loan (e.g., "policies where nominee details unavailable")
    if syntax.has_negation and intent in ("BANK_ACCOUNT_QUERY", "INSURANCE_QUERY", "FD_QUERY", "LOAN_QUERY"):
        return "PERSONAL_FINANCIAL_DATA", f"Workspace negation/gap check for {intent}."

    # General financial knowledge queries (e.g. "What is an FD?", "FD kya hota hai?", "Explain SIP with an example.")
    if has_general_concept or intent in ("CREDIT_SCORE_QUERY", "GENERAL_CONCEPT_QUERY"):
        return "GENERAL_KNOWLEDGE", f"General financial concept/educational query ({intent})."

    # Multi-turn short/anaphoric follow-ups inherit prior thread category if no explicit personal marker overrides it
    if prior_category == "GENERAL_KNOWLEDGE":
        return "GENERAL_KNOWLEDGE", "Follow-up continuing general financial knowledge conversation."
    if prior_category == "HYBRID_QUERY":
        return "HYBRID_QUERY", "Follow-up continuing hybrid reasoning conversation."
    if prior_category == "PERSONAL_FINANCIAL_DATA":
        return "PERSONAL_FINANCIAL_DATA", "Follow-up continuing personal financial record query."

    # Default when no personal/workspace signals exist -> GENERAL_KNOWLEDGE
    if intent in ("FD_QUERY", "INVESTMENT_QUERY", "INSURANCE_QUERY", "TAX_QUERY", "LOAN_QUERY", "EMI_QUERY", "EXPENSE_QUERY", "SALARY_QUERY", "BANK_ACCOUNT_QUERY", "UNKNOWN_INTENT"):
        return "GENERAL_KNOWLEDGE", f"No personal markers present; routing general query ({intent}) to Groq LLM."

    return "PERSONAL_FINANCIAL_DATA", f"Default personal route ({intent})."


def classify_intent(
    lexical: LexicalAnalysis,
    syntax: SyntacticAnalysis,
    prior_category: str | None = None,
) -> IntentResult:
    norm = lexical.normalized_text
    lemmas = set(lexical.lemmas)

    # Level 5 Pragmatic checks first
    if any(p in norm for p in PRAGMATIC_HEALTH_PATTERNS):
        if "worry" in norm or "risk" in norm or "blindspot" in norm or "wrong" in norm:
            cat, reason = classify_query_category(lexical, syntax, "FINANCIAL_RISK_QUERY", "RISK_TRIAGE", prior_category)
            return IntentResult(
                intent="FINANCIAL_RISK_QUERY",
                confidence=0.92,
                secondary_intents=["FINANCIAL_GAP_QUERY", "GENERAL_FINANCIAL_OVERVIEW"],
                pragmatic_type="RISK_TRIAGE",
                processing_route="HYBRID_REASONING" if cat == "HYBRID_QUERY" else "HYBRID",
                query_category=cat,
                routing_reason=reason,
            )
        cat, reason = classify_query_category(lexical, syntax, "GENERAL_FINANCIAL_OVERVIEW", "HOLISTIC_HEALTH_CHECK", prior_category)
        return IntentResult(
            intent="GENERAL_FINANCIAL_OVERVIEW",
            confidence=0.92,
            secondary_intents=["FINANCIAL_GAP_QUERY", "FINANCIAL_RISK_QUERY"],
            pragmatic_type="HOLISTIC_HEALTH_CHECK",
            processing_route="HYBRID_REASONING" if cat == "HYBRID_QUERY" else "HYBRID",
            query_category=cat,
            routing_reason=reason,
        )

    scores: dict[str, float] = {k: 0.0 for k in INTENTS}

    if "nominee" in lemmas or "beneficiary" in norm or syntax.relation == "missing_nominee":
        scores["NOMINEE_QUERY"] += 0.92
    if "insurance" in lemmas or "policy" in lemmas or "premium" in lemmas or "sum assured" in norm:
        scores["INSURANCE_QUERY"] += 0.80
    if "bank" in lemmas or "account" in lemmas or "ifsc" in norm or syntax.relation == "account_missing_from_statements":
        scores["BANK_ACCOUNT_QUERY"] += 0.85
    if "fixed deposit" in norm or "recurring deposit" in norm or "fd" in lexical.tokens or "rd" in lexical.tokens or "maturity" in lemmas or "mature" in lemmas:
        scores["FD_QUERY"] += 0.88
    if "emi" in lemmas or "equated monthly instalment" in norm:
        scores["EMI_QUERY"] += 0.90
    if "loan" in lemmas or "outstanding" in lemmas or "principal" in lemmas or "lender" in lemmas:
        scores["LOAN_QUERY"] += 0.86
    if "salary" in lemmas or "payroll" in lemmas or "employer" in lemmas:
        scores["SALARY_QUERY"] += 0.86
    if "form16" in norm or "tds" in lemmas or "tax" in lemmas or "80c" in norm or "80d" in norm or "ais" in norm or "elss" in norm:
        scores["TAX_QUERY"] += 0.84
    if "subscription" in lemmas or "streamflix" in norm or "cloudnotes" in norm or "tunewave" in norm:
        scores["SUBSCRIPTION_QUERY"] += 0.90
    if "expense" in lemmas or "charge" in lemmas or "fee" in lemmas or "deduct" in lemmas or "spend" in lemmas or "rent" in lemmas:
        scores["EXPENSE_QUERY"] += 0.82
    if "mutual fund" in norm or "systematic investment" in norm or "sip" in lemmas or "dividend" in lemmas or "ppf" in norm or "epf" in norm or "investment" in lemmas or "portfolio" in lemmas or "diversified" in norm or "allocation" in lemmas:
        scores["INVESTMENT_QUERY"] += 0.86
    if "credit score" in norm or "cibil" in norm:
        scores["CREDIT_SCORE_QUERY"] += 0.90
    if "compound interest" in norm or "compounding" in norm or "inflation" in lemmas:
        scores["GENERAL_CONCEPT_QUERY"] += 0.88
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
    pragmatic = "EXPLANATION" if syntax.question_type == "WH_WHY" else None
    query_category, routing_reason = classify_query_category(
        lexical=lexical,
        syntax=syntax,
        intent=top_intent,
        pragmatic_type=pragmatic,
        prior_category=prior_category,
    )

    # Route determination (Three-tier + Financial Reasoning Engine)
    if query_category == "GENERAL_KNOWLEDGE":
        route = "GENERAL_LLM"
    elif query_category == "HYBRID_QUERY":
        route = "HYBRID_REASONING"
    elif top_intent in ("SUBSCRIPTION_QUERY", "EXPENSE_QUERY") and syntax.question_type in ("WH_HOW_MUCH", "WH_HOW_MANY"):
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

    return IntentResult(
        intent=top_intent,
        confidence=round(min(0.98, top_score), 2),
        secondary_intents=secondary,
        pragmatic_type=pragmatic,
        processing_route=route,
        query_category=query_category,
        routing_reason=routing_reason,
    )
