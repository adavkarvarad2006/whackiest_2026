"""Named Entity Recognition (NER) for financial queries and PDF pages."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.extraction import mask_reference
from app.services.pdf_parser import PageText


@dataclass
class NerEntity:
    entity_type: str
    entity_value: str
    page_number: int
    supporting_text: str
    confidence: str = "HIGH"


ACCOUNT_RE = re.compile(r"\b([A-Z]{2,6}-SB-\d{4,16})\b")
FD_RE = re.compile(r"\b([A-Z]{2,6}-FD-\d{4,16})\b")
POLICY_RE = re.compile(r"\b([A-Z]{2,6}-LI-\d{4,16})\b")
LOAN_RE = re.compile(r"\b([A-Z]{2,6}-PL-\d{4,16})\b")
AMOUNT_RE = re.compile(r"(₹\s?[\d,]+(?:\.\d{1,2})?)")
DATE_RE = re.compile(r"\b(\d{2}-[A-Za-z]{3}-\d{4})\b")
RATE_RE = re.compile(r"\b(\d{1,2}\.\d{1,2}\s*%)\b")
BANK_RE = re.compile(r"\b([A-Z][A-Za-z\s&-]+Bank\s+Ltd\.?(?:\s*\(DEMO\))?)", re.IGNORECASE)
INSTITUTION_RE = re.compile(r"\b([A-Z][A-Za-z\s&-]+(?:Insurance\s+Co\.|FinServe|Solutions|Mutual\s+Fund)[^\n|]{0,25})", re.IGNORECASE)


def extract_entities_from_text(text: str, page_number: int = 1) -> list[NerEntity]:
    """Extract structured financial entities from text with masked account/policy refs."""
    entities: list[NerEntity] = []
    seen: set[tuple[str, str, int]] = set()

    def add(etype: str, val: str, snippet: str, conf: str = "HIGH"):
        val_c = re.sub(r"\s+", " ", val).strip()[:240]
        if not val_c:
            return
        key = (etype, val_c, page_number)
        if key in seen:
            return
        seen.add(key)
        entities.append(
            NerEntity(
                entity_type=etype,
                entity_value=val_c,
                page_number=page_number,
                supporting_text=snippet.strip()[:280],
                confidence=conf,
            )
        )

    for line in text.splitlines():
        ln = line.strip()
        if not ln:
            continue
        low = ln.lower()

        for m in ACCOUNT_RE.finditer(ln):
            add("ACCOUNT_REF", mask_reference(m.group(1)) or m.group(1), ln)
        for m in FD_RE.finditer(ln):
            add("FD_REF", mask_reference(m.group(1)) or m.group(1), ln)
        for m in POLICY_RE.finditer(ln):
            add("POLICY_NUMBER", mask_reference(m.group(1)) or m.group(1), ln)
        for m in LOAN_RE.finditer(ln):
            add("LOAN_REF", mask_reference(m.group(1)) or m.group(1), ln)
        for m in BANK_RE.finditer(ln):
            add("BANK_NAME", m.group(1), ln)
        for m in INSTITUTION_RE.finditer(ln):
            add("INSTITUTION", m.group(1), ln)
        for m in RATE_RE.finditer(ln):
            add("INTEREST_RATE", m.group(1), ln)

        for m in DATE_RE.finditer(ln):
            etype = "MATURITY_DATE" if "maturity" in low else "DATE"
            add(etype, m.group(1), ln)

        for m in AMOUNT_RE.finditer(ln):
            val = m.group(1)
            if "salary" in low:
                add("SALARY", val, ln)
            elif "emi" in low:
                add("EMI", val, ln)
            elif "premium" in low:
                add("PREMIUM", val, ln)
            elif "tds" in low or "tax" in low:
                add("TAX_AMOUNT", val, ln)
            else:
                add("CURRENCY_AMOUNT", val, ln)

        if "account holder:" in low or "policyholder" in low or "assessee name:" in low or "customer name:" in low or "borrower name:" in low:
            parts = [p.strip() for p in ln.split("|")]
            for i, p in enumerate(parts):
                if any(k in p.lower() for k in ("holder", "assessee", "customer name", "borrower")) and i + 1 < len(parts):
                    cand = parts[i + 1].strip()
                    if cand and len(cand) <= 60 and not cand.startswith("DEMO-"):
                        add("CUSTOMER_NAME", cand, ln)

    return entities[:60]


def extract_entities_from_pages(pages: list[PageText]) -> list[NerEntity]:
    all_ents: list[NerEntity] = []
    for p in pages:
        all_ents.extend(extract_entities_from_text(p.cleaned_text, page_number=p.page_number))
    return all_ents[:150]


def extract_entities_from_query(question: str) -> list[dict[str, str]]:
    """Lightweight NER over the user's question for query understanding & logging-safe context."""
    ents = extract_entities_from_text(question, page_number=0)
    return [{"type": e.entity_type, "value": e.entity_value} for e in ents]
