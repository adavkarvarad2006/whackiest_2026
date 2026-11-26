"""Level 1 NLP: Language detection (English / Hinglish), tokenization, lemmatization, spell correction, and financial normalization."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

HINGLISH_MARKERS = {
    "mera", "mere", "meri", "kaun", "kaunsi", "kaunse", "kya", "hai", "hain", "nahi",
    "nhi", "kab", "kitna", "kitne", "kitni", "har", "mahine", "mahina", "mein", "me",
    "aur", "koi", "batao", "bataye", "dikhao", "paisa", "paise", "kat", "raha", "rahi",
    "hoga", "hogi", "kahan", "kyun", "kyu", "uska", "uski", "iska", "iski", "wala",
    "wali", "liye", "saal", "baki", "bacha", "lag", "gaya", "huye", "kare", "karna",
    "chahiye", "theek", "sahi", "galat", "zyada", "kam", "sabhi", "saare",
}

ABBREVIATIONS = {
    "fd": "fixed deposit",
    "fds": "fixed deposit",
    "emi": "equated monthly instalment loan payment",
    "emis": "equated monthly instalment loan payment",
    "mf": "mutual fund",
    "mfs": "mutual fund",
    "sip": "systematic investment plan mutual fund",
    "sips": "systematic investment plan mutual fund",
    "ais": "annual information statement",
    "tds": "tax deducted at source",
    "amc": "annual account maintenance charge bank fee",
    "ppf": "public provident fund",
    "epf": "employees provident fund",
    "cc": "credit card",
    "it": "income tax",
    "itr": "income tax return",
    "sa": "sum assured",
    "sb": "savings bank account",
    "hra": "house rent allowance",
}

SYNONYM_PHRASES = [
    (r"\b(bank charges|bank fees|account maintenance fees|maintenance charge|sms charges)\b", "bank fee maintenance charge"),
    (r"\b(nominee missing|without nominee|no nominee|nominee unavailable|nominee details unavailable|nominee not found)\b", "nominee missing unavailable"),
    (r"\b(forgotten accounts?|undiscovered accounts?|overlooked accounts?|unlisted accounts?|hidden accounts?)\b", "undiscovered overlooked bank account missing from statement"),
    (r"\b(deducted every month|recurring deductions?|auto[- ]?debit|monthly cuts?|unnecessary charges?)\b", "recurring monthly subscription payment bank charge"),
    (r"\b(happens to me|after my death|who gets my insurance|beneficiary)\b", "nominee life insurance beneficiary"),
    (r"\b(expire|expires|expiring|due for maturity|maturing)\b", "mature maturity expire"),
    # Hinglish -> English semantic normalization
    (r"\b(kab mature hoga|kab mature hogi|maturity kab)\b", "when does fixed deposit mature"),
    (r"\b(kitna outstanding|kitna loan baki|kitna bacha)\b", "how much loan outstanding principal balance"),
    (r"\b(har mahine|prati maah)\b", "every month monthly"),
    (r"\b(paisa kat raha|paise kat rahe|paisa kahan ja raha)\b", "money deducted recurring expense subscription charge"),
    (r"\b(nahi hai|nahi hain|nhi hai|missing hai|missing hain|nahi diya)\b", "missing not available"),
    (r"\b(kaunse|kaunsi|kaun sa|kaun si)\b", "which"),
    (r"\b(kitna|kitne|kitni)\b", "how much"),
    (r"\b(aur)\b", "and"),
    (r"\b(mein|me)\b", "in"),
    (r"\b(koi mismatch|koi farq|koi difference|mismatch hai kya)\b", "discrepancy mismatch difference"),
    (r"\b(batao|dikhao|samjhao)\b", "show explain"),
]

IRREGULAR_LEMMAS = {
    "policies": "policy",
    "accounts": "account",
    "deposits": "deposit",
    "statements": "statement",
    "charges": "charge",
    "charged": "charge",
    "deductions": "deduct",
    "deducted": "deduct",
    "deducting": "deduct",
    "subscriptions": "subscription",
    "payments": "payment",
    "paying": "pay",
    "paid": "pay",
    "maturing": "mature",
    "matures": "mature",
    "matured": "mature",
    "expiring": "expire",
    "expires": "expire",
    "expired": "expire",
    "discrepancies": "discrepancy",
    "mismatches": "mismatch",
    "differences": "difference",
    "findings": "finding",
    "nominees": "nominee",
    "loans": "loan",
    "emis": "emi",
    "investments": "investment",
    "expenses": "expense",
    "liabilities": "liability",
    "assets": "asset",
    "taxes": "tax",
    "salaries": "salary",
    "incomes": "income",
    "premiums": "premium",
}

FINANCIAL_VOCAB = sorted(
    set(IRREGULAR_LEMMAS.values())
    | {
        "nominee", "insurance", "policy", "statement", "maturity", "mature", "salary",
        "subscription", "discrepancy", "mismatch", "outstanding", "principal", "interest",
        "deposit", "account", "savings", "maintenance", "recurring", "dividend", "balance",
        "premium", "deduction", "exemption", "taxable", "prepared", "summary", "overview",
        "blindspot", "verification", "credit", "mutual", "provident", "forgotten", "dormant",
    }
)


@dataclass
class LexicalAnalysis:
    original_text: str
    language: str  # "English" or "Hinglish"
    normalized_text: str
    tokens: list[str]
    lemmas: list[str]
    expanded_abbreviations: list[str]
    spell_corrections: dict[str, str]


def detect_language(text: str) -> str:
    tokens = set(re.findall(r"[a-zA-Z]+", text.lower()))
    hits = tokens & HINGLISH_MARKERS
    # Hinglish if >= 2 markers or strong single Hindi interrogative/auxiliary marker
    if len(hits) >= 2 or bool(hits & {"mera", "mere", "meri", "kaunse", "kaunsi", "kitna", "kitne", "nahi", "hoga", "hain", "kya"}):
        return "Hinglish"
    return "English"


def _lemmatize_token(tok: str) -> str:
    if tok in IRREGULAR_LEMMAS:
        return IRREGULAR_LEMMAS[tok]
    if len(tok) > 5 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 5 and tok.endswith("ing"):
        return tok[:-3]
    if len(tok) > 4 and tok.endswith("ed"):
        return tok[:-2]
    if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def analyze_lexical(text: str) -> LexicalAnalysis:
    language = detect_language(text)
    cleaned = text.strip().lower()
    # Expand common contractions
    cleaned = re.sub(r"\bdon't\b", "do not", cleaned)
    cleaned = re.sub(r"\bdoesn't\b", "does not", cleaned)
    cleaned = re.sub(r"\bisn't\b", "is not", cleaned)
    cleaned = re.sub(r"\baren't\b", "are not", cleaned)
    cleaned = re.sub(r"\bhaven't\b", "have not", cleaned)
    cleaned = re.sub(r"\bhasn't\b", "has not", cleaned)
    cleaned = re.sub(r"\bwhat's\b", "what is", cleaned)
    cleaned = re.sub(r"\bform\s*16\b", "form16", cleaned)

    for pattern, repl in SYNONYM_PHRASES:
        cleaned = re.sub(pattern, repl, cleaned)

    raw_tokens = re.findall(r"[a-z0-9₹.,/-]+", cleaned)
    spell_corrections: dict[str, str] = {}
    expanded_abbrevs: list[str] = []
    norm_tokens: list[str] = []
    lemmas: list[str] = []

    for tok in raw_tokens:
        alpha = re.sub(r"[^a-z]", "", tok)
        if alpha in ABBREVIATIONS:
            exp = ABBREVIATIONS[alpha]
            expanded_abbrevs.append(f"{alpha.upper()} -> {exp}")
            norm_tokens.append(exp)
            lemmas.extend(exp.split())
            continue

        # Tolerant spelling correction only for purely alphabetic domain typos >= 5 chars
        if alpha == tok and len(tok) >= 5 and tok not in FINANCIAL_VOCAB and tok not in HINGLISH_MARKERS and tok not in IRREGULAR_LEMMAS:
            matches = difflib.get_close_matches(tok, FINANCIAL_VOCAB, n=1, cutoff=0.84)
            if matches:
                corrected = matches[0]
                spell_corrections[tok] = corrected
                tok = corrected

        norm_tokens.append(tok)
        lemmas.append(_lemmatize_token(tok))

    normalized_text = re.sub(r"\s+", " ", " ".join(norm_tokens)).strip()
    return LexicalAnalysis(
        original_text=text,
        language=language,
        normalized_text=normalized_text,
        tokens=raw_tokens,
        lemmas=lemmas,
        expanded_abbreviations=expanded_abbrevs,
        spell_corrections=spell_corrections,
    )
