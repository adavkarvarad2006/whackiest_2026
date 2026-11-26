# ArthaLens RAG Evaluation Report

- **Dataset:** `DEMO_001` (28 test questions, 6 PDFs ingested)
- **Retrieval Precision@6:** `58.93%`
- **Retrieval Recall@6:** `92.74%`
- **Page Citation Accuracy:** `100.00%` (28/28)
- **SQL Analytics Accuracy:** `5/5` checks passed
- **Answer Correctness (Groq LLM):** `Pending GROQ_API_KEY`
- **Unsupported-Answer Rate:** `Pending GROQ_API_KEY`

## Parameterized SQL Accuracy Checks

- [PASS] Distinct Bank Accounts == 2
- [PASS] Annual Subscriptions == ₹16,164.00
- [PASS] AIS vs Form 16 Diff == ₹18,000.00
- [PASS] FD Days Remaining == 41
- [PASS] Loan EMI Matches == 12

## Per-Question Retrieval Metrics

| ID | Mode | Precision@6 | Recall@6 | Page Hit | LLM Status |
|---|---|---:|---:|---|---|
| Q001 | Hybrid | 0.67 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q002 | Hybrid | 0.67 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q003 | RAG | 1.00 | 0.50 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q004 | RAG | 0.50 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q005 | SQL | 0.83 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q006 | SQL | 0.50 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q007 | RAG | 0.33 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q008 | Hybrid | 0.67 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q009 | RAG | 0.33 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q010 | RAG | 0.50 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q011 | Hybrid | 1.00 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q012 | Hybrid | 1.00 | 0.80 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q013 | Hybrid | 0.67 | 0.67 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q014 | RAG | 1.00 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q015 | RAG | 1.00 | 0.50 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q016 | Hybrid | 0.50 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q017 | SQL | 0.33 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q018 | Hybrid | 0.50 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q019 | RAG | 0.33 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q020 | RAG | 0.67 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q021 | RAG | 0.33 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q022 | SQL | 0.50 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q023 | RAG | 0.33 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q024 | Hybrid | 0.83 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q025 | Hybrid | 0.50 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q026 | Hybrid | 0.33 | 0.50 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q027 | SQL | 0.33 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
| Q028 | RAG | 0.33 | 1.00 | Yes | SKIPPED (GROQ_API_KEY not set) |
