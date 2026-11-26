# ArthaLens Large-Scale Synthetic Financial Dataset (50 Customers / 500 PDFs)

> **Disclaimer:** Every customer profile, PAN/TAN/Aadhaar, bank account, policy, loan, mutual fund folio, and transaction in `arthalens_dataset/` is **100% synthetic** and generated solely for RAG evaluation.

## Dataset Distribution (500 PDFs)

| Document Type | Quantity |
|---|---:|
| Bank Statements (`bank_statement_01.pdf`, `bank_statement_02.pdf`) | 100 |
| AIS Reports (`ais_report.pdf`) | 50 |
| Form 16 (`form16.pdf`) | 50 |
| Insurance Policies (`insurance_policy_01.pdf`, `insurance_policy_02.pdf`) | 75 |
| Fixed Deposit Certificates (`fd_certificate.pdf`) | 50 |
| Personal Loan Statements (`loan_statement.pdf`) | 50 |
| Mutual Fund Statements (`mutual_fund_statement.pdf`) | 50 |
| Credit Card Statements (`credit_card_statement.pdf`) | 25 |
| PPF / EPF Statements (`ppf_epf_statement.pdf`) | 25 |
| Tax Supporting Documents (`tax_supporting_doc.pdf`) | 25 |
| **Total** | **500** |

## Connected Profile Mix (50 Customers: `CUST001`–`CUST050`)

- **10 Clean Profiles** (`CUST002`–`CUST011`): Fully consistent across documents.
- **15 Single-Issue Profiles** (`CUST012`–`CUST026`): One isolated Gap, Leak, or Risk blindspot.
- **15 Multi-Issue Profiles** (`CUST001`, `CUST027`–`CUST040`): Multiple interconnected Gaps, Leaks, Risks, and Investment scenarios.
- **5 Conflicting-Info Profiles** (`CUST041`–`CUST045`): AIS vs Form 16 variance, EMI mismatch, outdated/conflicting nominee, duplicate insurance cover.
- **5 Incomplete-Doc Profiles** (`CUST046`–`CUST050`): Missing tax proofs, dormant account, forgotten/matured FD, missing nominee.

## Ingestion & Evaluation

1. Ingest all 500 PDFs into PostgreSQL + pgvector (or SQLite fallback):
   ```bash
   python arthalens_dataset/ingestion/ingest_all.py --database-url "$DATABASE_URL"
   ```
2. Evaluate across all 350 test questions in `metadata/chatbot_test_questions.json`:
   ```bash
   python arthalens_dataset/evaluation/evaluate_rag.py --database-url "$DATABASE_URL"
   ```
   Results are written to `arthalens_dataset/evaluation/evaluation_report.json`.
