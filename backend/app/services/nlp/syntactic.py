"""Level 2 NLP: Syntactic structure, negation, comparisons, temporal expressions, and entity relations."""

from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.services.nlp.lexical import LexicalAnalysis
from app.timezone_utils import get_ist_today


@dataclass
class SyntacticAnalysis:
    question_type: str
    has_negation: bool
    is_comparison: bool
    is_superlative: bool
    temporal_expressions: list[str]
    subject: str | None
    verb: str | None
    obj: str | None
    relation: str | None
    temporal_windows: list[dict[str, str]] = field(default_factory=list)


NEGATION_WORDS = {"not", "no", "never", "without", "missing", "absent", "unavailable", "blank", "lack", "lacking", "nahi", "nhi"}
COMPARISON_WORDS = {"compare", "comparison", "mismatch", "discrepancy", "difference", "differ", "vs", "versus", "between", "match", "reconcile", "more", "less"}
SUPERLATIVE_WORDS = {"highest", "lowest", "largest", "biggest", "smallest", "most", "least", "maximum", "minimum", "top"}

TEMPORAL_PATTERNS = [
    r"\btoday\b",
    r"\byesterday\b",
    r"\bthis week\b",
    r"\blast week\b",
    r"\bthis month\b",
    r"\blast month\b",
    r"\baaj\b",
    r"\bkal\b",
    r"\bis hafte\b",
    r"\bpichhle hafte\b",
    r"\bis mahine\b",
    r"\bevery month\b",
    r"\bmonthly\b",
    r"\bannually\b",
    r"\byearly\b",
    r"\bupcoming\b",
    r"\bnext \d+ days?\b",
    r"\bfy\s*20\d{2}[–-]?\d{2}\b",
    r"\bwhen\b",
    r"\bdue date\b",
    r"\bmaturity date\b",
]


def resolve_relative_temporal_windows(norm_text: str, today_ist: date | None = None) -> list[dict[str, str]]:
    """Resolve relative date phrases ('today', 'yesterday', 'this month', 'last week') strictly in Asia/Kolkata."""
    ref = today_ist or get_ist_today()
    low = norm_text.lower()
    windows: list[dict[str, str]] = []

    if re.search(r"\b(today|aaj)\b", low):
        windows.append({"expression": "today", "start_date": ref.isoformat(), "end_date": ref.isoformat(), "timezone": "Asia/Kolkata"})
    if re.search(r"\b(yesterday|kal)\b", low):
        y = ref - timedelta(days=1)
        windows.append({"expression": "yesterday", "start_date": y.isoformat(), "end_date": y.isoformat(), "timezone": "Asia/Kolkata"})
    if re.search(r"\b(this week|is hafte)\b", low):
        start = ref - timedelta(days=ref.weekday())
        windows.append({"expression": "this_week", "start_date": start.isoformat(), "end_date": ref.isoformat(), "timezone": "Asia/Kolkata"})
    if re.search(r"\b(last week|pichhle hafte)\b", low):
        this_mon = ref - timedelta(days=ref.weekday())
        last_mon = this_mon - timedelta(days=7)
        last_sun = this_mon - timedelta(days=1)
        windows.append({"expression": "last_week", "start_date": last_mon.isoformat(), "end_date": last_sun.isoformat(), "timezone": "Asia/Kolkata"})
    if re.search(r"\b(this month|is mahine)\b", low):
        start = ref.replace(day=1)
        windows.append({"expression": "this_month", "start_date": start.isoformat(), "end_date": ref.isoformat(), "timezone": "Asia/Kolkata"})
    if re.search(r"\b(last month|pichhle mahine)\b", low):
        first_this = ref.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        windows.append({"expression": "last_month", "start_date": first_prev.isoformat(), "end_date": last_prev.isoformat(), "timezone": "Asia/Kolkata"})

    return windows


def _detect_question_type(norm_text: str, orig_text: str) -> str:
    low = orig_text.lower().strip()
    n = norm_text.lower()
    if "how many" in n:
        return "WH_HOW_MANY"
    if "how much" in n:
        return "WH_HOW_MUCH"
    if re.search(r"\b(when|kab)\b", low) or "when" in n:
        return "WH_WHEN"
    if re.search(r"\b(which|kaunsi|kaunse)\b", low):
        return "WH_WHICH"
    if re.search(r"\b(who|kis|kisko)\b", low):
        return "WH_WHO"
    if re.search(r"\b(why|kyun|kyu)\b", low):
        return "WH_WHY"
    if re.search(r"\b(where|kahan)\b", low):
        return "WH_WHERE"
    if re.match(r"^(is|are|do|does|did|can|am|will|have|has|kya)\b", low):
        return "YN_QUESTION"
    if re.match(r"^(show|list|explain|summarize|tell|give|find|calculate|compare)\b", low):
        return "IMPERATIVE"
    return "WH_WHAT"


def analyze_syntax(lexical: LexicalAnalysis) -> SyntacticAnalysis:
    norm = lexical.normalized_text
    lemmas = set(lexical.lemmas)
    tokens = set(re.findall(r"[a-z0-9]+", norm))

    q_type = _detect_question_type(norm, lexical.original_text)
    has_negation = bool((lemmas | tokens) & NEGATION_WORDS)
    is_comparison = bool((lemmas | tokens) & COMPARISON_WORDS)
    is_superlative = bool((lemmas | tokens) & SUPERLATIVE_WORDS)

    temporal_hits = []
    for pat in TEMPORAL_PATTERNS:
        for m in re.finditer(pat, norm):
            temporal_hits.append(m.group(0))
    temporal_windows = resolve_relative_temporal_windows(norm)

    # Identify core financial subject / object / grammatical relation
    subject = None
    obj = None
    verb = None
    relation = None

    if "policy" in lemmas or "insurance" in lemmas:
        subject = "insurance_policy"
    elif "account" in lemmas or "bank" in lemmas:
        subject = "bank_account"
    elif "fixed deposit" in norm or "fd" in lexical.tokens:
        subject = "fixed_deposit"
    elif "loan" in lemmas or "emi" in lemmas:
        subject = "personal_loan"
    elif "salary" in lemmas or "form16" in norm or "ais" in norm:
        subject = "salary_tax"
    elif "subscription" in lemmas or "charge" in lemmas or "expense" in lemmas:
        subject = "recurring_expense"

    if "nominee" in lemmas or "beneficiary" in lemmas:
        obj = "nominee"
        verb = "lack" if has_negation else "has"
        relation = "missing_nominee" if has_negation else "nominee_check"
    elif subject == "bank_account" and has_negation:
        obj = "uploaded_statement"
        verb = "missing_from"
        relation = "account_missing_from_statements"
    elif is_comparison and subject == "salary_tax":
        obj = "ais_vs_form16"
        verb = "compare"
        relation = "salary_reconciliation"
    elif "mature" in lemmas or "expire" in lemmas:
        obj = "maturity_date"
        verb = "mature"
        relation = "maturity_timeline"
    elif "deduct" in lemmas or "charge" in lemmas or "pay" in lemmas:
        obj = "amount"
        verb = "deduct"
        relation = "cash_outflow"

    return SyntacticAnalysis(
        question_type=q_type,
        has_negation=has_negation,
        is_comparison=is_comparison,
        is_superlative=is_superlative,
        temporal_expressions=temporal_hits,
        subject=subject,
        verb=verb,
        obj=obj,
        relation=relation,
        temporal_windows=temporal_windows,
    )
