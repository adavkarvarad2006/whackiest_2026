"""Query expansion, ambiguity detection, and context-aware follow-up suggestions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FinancialAsset
from app.services.nlp.discourse import DiscourseState
from app.services.nlp.intent import IntentResult
from app.services.nlp.lexical import LexicalAnalysis
from app.services.nlp.syntactic import SyntacticAnalysis


def expand_queries(
    original_question: str,
    lexical: LexicalAnalysis,
    discourse: DiscourseState,
    intent_res: IntentResult,
) -> list[str]:
    """Generate 3-5 focused semantic search queries for hybrid vector + keyword retrieval."""
    queries: list[str] = [discourse.resolved_query]
    if lexical.normalized_text and lexical.normalized_text not in queries:
        queries.append(lexical.normalized_text)
    if original_question.strip() not in queries:
        queries.append(original_question.strip())

    intent = intent_res.intent
    if intent in ("BANK_ACCOUNT_QUERY", "FINANCIAL_GAP_QUERY"):
        queries.extend([
            "undisclosed bank accounts appearing in AIS SFT-016",
            "savings bank accounts missing from uploaded bank statements",
        ])
    elif intent == "NOMINEE_QUERY":
        queries.extend([
            "section 4 nominee details life insurance policy schedule",
            "nominee full name relationship recorded value",
        ])
    elif intent in ("SUBSCRIPTION_QUERY", "EXPENSE_QUERY"):
        queries.extend([
            "recurring monthly subscription streamflix cloudnotes tunewave",
            "bank maintenance fee sms alert service charge",
        ])
    elif intent in ("SALARY_QUERY", "TAX_QUERY"):
        queries.extend([
            "AIS TDS-192 reported gross salary vs Form 16 Part B",
            "Chapter VI-A deductions standard deduction taxable income",
        ])
    elif intent == "FD_QUERY":
        queries.append("fixed deposit principal amount interest rate maturity date auto-renewal")
    elif intent in ("LOAN_QUERY", "EMI_QUERY"):
        queries.append("personal loan monthly EMI outstanding principal repayment schedule")
    elif intent == "INVESTMENT_QUERY":
        queries.append("mutual fund SIP portfolio dividend income PPF EPF")
    elif intent in ("GENERAL_FINANCIAL_OVERVIEW", "FINANCIAL_RISK_QUERY"):
        queries.extend([
            "nominee details fixed deposit maturity loan outstanding savings balance",
            "AIS salary discrepancy recurring subscriptions",
        ])

    # Deduplicate preserving order
    deduped: list[str] = []
    for q in queries:
        qn = q.strip()
        if qn and qn not in deduped:
            deduped.append(qn)
    return deduped[:5]


def detect_ambiguity(
    db: Session,
    user_id: int,
    question: str,
    lexical: LexicalAnalysis,
    syntax: SyntacticAnalysis,
    intent_res: IntentResult,
    discourse: DiscourseState,
) -> tuple[bool, str, list[str]]:
    """
    Detect singular ambiguous queries (e.g., "When does my policy expire?") when the user
    owns >= 2 distinct assets in that category and didn't specify or compare them.
    """
    low = question.lower()
    # Never trigger ambiguity on plural/aggregate/comparison/count/missing-check queries
    if (
        syntax.is_comparison
        or syntax.is_superlative
        or syntax.has_negation
        or syntax.question_type in ("WH_HOW_MANY", "WH_HOW_MUCH", "WH_WHICH", "WH_WHY")
        or discourse.coreference_applied
    ):
        return False, "", []

    # Check if user explicitly named an institution or reference token
    has_specific_ref = any(
        k in low for k in ("horizon", "metrocivic", "saffron", "deccan", "surakshaguard", "bharatlife", "kavach", "demo-", "primary", "secondary", "salary account")
    )
    if has_specific_ref:
        return False, "", []

    def _dedup_assets(rows: list[FinancialAsset], default_label: str) -> list[str]:
        seen_refs: dict[str, str] = {}
        # Prefer primary asset_type rows over AIS_* rows so names are cleaner
        ordered = sorted(rows, key=lambda r: (1 if (r.asset_type or "").startswith("AIS_") else 0, r.id))
        for r in ordered:
            ref = (r.account_reference or "").strip().upper()
            inst = (r.institution or "").lstrip(")-: ").strip()
            key = ref or inst.upper()
            if not key or key in seen_refs:
                continue
            label = f"{inst} ({r.account_reference or default_label})" if inst else (r.account_reference or default_label)
            seen_refs[key] = label
        return list(seen_refs.values())

    # Singular insurance policy ambiguity
    if intent_res.intent == "INSURANCE_QUERY" and any(p in low for p in ("my policy", "the policy", "this policy", "policy expire", "policy mature")):
        policies = list(
            db.scalars(
                select(FinancialAsset).where(
                    FinancialAsset.user_id == user_id,
                    FinancialAsset.asset_type == "LIFE_INSURANCE",
                )
            )
        )
        opts = _dedup_assets(policies, "Policy")
        if len(opts) >= 2:
            msg = (
                f"You have {len(opts)} insurance policies on record: "
                + "; ".join(opts)
                + ". Which policy would you like me to check?"
            )
            return True, msg, [f"Check {o}" for o in opts]

    # Singular bank account ambiguity
    if intent_res.intent == "BANK_ACCOUNT_QUERY" and any(p in low for p in ("my bank account", "my account balance", "the bank account")):
        accts = list(
            db.scalars(
                select(FinancialAsset).where(
                    FinancialAsset.user_id == user_id,
                    FinancialAsset.asset_type.in_(["SAVINGS_ACCOUNT", "AIS_SAVINGS_ACCOUNT"]),
                )
            )
        )
        opts = _dedup_assets(accts, "Account")
        if len(opts) >= 2:
            msg = (
                f"You have {len(opts)} bank accounts identified: "
                + "; ".join(opts)
                + ". Which account are you asking about?"
            )
            return True, msg, [f"Show details for {o}" for o in opts]

    return False, "", []


def build_followup_suggestions(intent_res: IntentResult, language: str) -> list[str]:
    """Provide context-aware follow-up suggestions in the user's language and query tier."""
    if intent_res.query_category == "GENERAL_KNOWLEDGE":
        if language == "Hinglish":
            general_hi = {
                "FD_QUERY": ["Iske fayde aur nuksan kya hain?", "Mera FD kab mature hoga?"],
                "INVESTMENT_QUERY": ["Iske advantages kya hain?", "Mera investment portfolio diversified hai kya?"],
                "INSURANCE_QUERY": ["Term insurance aur health insurance mein kya fark hai?", "Meri insurance policy explain karo."],
                "CREDIT_SCORE_QUERY": ["Credit score kaise improve karein?", "Kya mera loan interest rate high hai?"],
            }
            return general_hi.get(intent_res.intent, ["Iska ek simple example do.", "Mere financial documents check karo."])
        general_en = {
            "FD_QUERY": ["What are its benefits?", "What about my FD?"],
            "INVESTMENT_QUERY": ["What are its advantages and risks?", "Is my investment portfolio diversified?"],
            "INSURANCE_QUERY": ["What is the difference between term and health insurance?", "Explain my insurance policy."],
            "CREDIT_SCORE_QUERY": ["How can someone improve a credit score?", "Is my loan interest rate high?"],
        }
        return general_en.get(intent_res.intent, ["Can you give a practical example?", "What about my financial records?"])

    if language == "Hinglish":
        mapping = {
            "FD_QUERY": ["Iska principal aur interest kitna hai?", "Kya mera FD interest rate accha hai?"],
            "NOMINEE_QUERY": ["Kaunsi document page par nominee blank hai?", "Meri FD mein nominee hai kya?"],
            "BANK_ACCOUNT_QUERY": ["AIS mein kaunsa bank account extra dikh raha hai?", "Har mahine kitne bank charges lag rahe hain?"],
            "SALARY_QUERY": ["AIS aur Form 16 mein kitna difference hai?", "Mera taxable income kitna hai?"],
            "LOAN_QUERY": ["Mera monthly EMI bank statement se match hota hai?", "Kya mera loan interest rate high hai?"],
        }
        return mapping.get(intent_res.intent, ["Mere finances mein koi risk ya gap hai kya?", "Mera FD kab mature hoga?"])

    mapping_en = {
        "FD_QUERY": ["What is its principal amount?", "Is my FD interest rate good?"],
        "NOMINEE_QUERY": ["Which document supports this finding?", "Do my fixed deposits have nominees registered?"],
        "BANK_ACCOUNT_QUERY": ["Is any account appearing in AIS missing from my bank statement?", "What is my closing balance?"],
        "SALARY_QUERY": ["Is there any discrepancy between AIS and Form 16?", "What deductions did I claim u/s 80C?"],
        "SUBSCRIPTION_QUERY": ["What are all my recurring monthly expenses?", "Are there any bank maintenance fees?"],
        "LOAN_QUERY": ["Does my bank statement match my loan EMI?", "Explain whether my loan interest rate is high."],
        "INVESTMENT_QUERY": ["Is my investment portfolio diversified?", "How does compounding help long-term investments?"],
    }
    return mapping_en.get(
        intent_res.intent,
        ["Anything I should worry about in my finances?", "Is my investment portfolio diversified?"],
    )
