# ArthaLens Synthetic Financial Document Dataset (`DEMO_001`)

> **Disclaimer:** All documents, customer identities, PAN/TAN/Aadhaar identifiers, bank accounts, policy numbers, loan accounts, and transactions in this dataset are **100% synthetic DEMO DATA** created solely for software testing and RAG/LLM evaluation. They are not valid for financial, tax, or legal use.

## Dataset Overview

- **Fictional Customer:** Ananya Sharma (Age 28, Software Engineer, TechNova Solutions Pvt. Ltd., Bengaluru, Karnataka)
- **Synthetic PAN:** `DEMOP0001A (DEMO)`
- **Financial Year / Assessment Year:** `FY 2025–26` / `AY 2026–27`
- **Dataset Reference Date:** `15-May-2026`

## Folder Structure

```text
ArthaLens_Demo_Dataset/
├── Documents/
│   ├── Bank_Statement.pdf        (4 pages, 119 transactions, Apr 2025 – Mar 2026)
│   ├── AIS_Report.pdf            (2 pages, FY 2025–26 Annual Information Statement)
│   ├── Form_16.pdf               (2 pages, FY 2025–26 Part A & Part B)
│   ├── Insurance_Policy.pdf      (2 pages, Term Life Policy DEMO-LI-8841209)
│   ├── FD_Certificate.pdf        (2 pages, Fixed Deposit DEMO-FD-902184)
│   └── Loan_Statement.pdf        (2 pages, Personal Loan DEMO-PL-5509123)
├── Metadata/
│   ├── ground_truth.json         (Expected findings, page refs, extracted text, Q&A)
│   ├── extracted_entities.json   (Structured entity inventory with page citations)
│   └── chatbot_test_questions.json (28 RAG/SQL/Hybrid evaluation questions)
└── README.md
```

## Interconnected Test Scenarios

| Finding ID | Scenario | Source Documents | Expected Status | Summary |
|---|---|---|---|---|
| `F001` | Undiscovered Bank Account | `AIS_Report.pdf` (p.2), `Bank_Statement.pdf` (p.1) | `AMBER` | MetroCivic Co-op Bank (`DEMO-SB-77319044`, ₹4,850.00 interest) appears in AIS only; needs ownership/status verification. |
| `F002` | Missing Nominee | `Insurance_Policy.pdf` (p.2) | `RED` | Section 4 (Nominee Details) of Policy `DEMO-LI-8841209` is blank. |
| `F003` | Salary Discrepancy | `AIS_Report.pdf` (p.1), `Form_16.pdf` (pp.1–2) | `AMBER` | AIS reports ₹11,60,400.00 gross salary vs Form 16 ₹11,42,400.00 (₹18,000.00 variance; TDS matches at ₹62,400.00). |
| `F004` | Recurring Subscriptions & Fees | `Bank_Statement.pdf` (pp.1–4) | `INFO` | 3 monthly subscriptions (`₹1,347.00/mo` = `₹16,164.00/yr`), monthly SMS fee (`₹15.00/mo`), and annual AMC (`₹590.00`). |
| `F005` | Upcoming FD Maturity | `FD_Certificate.pdf` (p.1), `Bank_Statement.pdf` (p.2) | `AMBER` | FD `DEMO-FD-902184` (`₹2,50,000.00` → `₹2,68,492.00`) matures on `25-Jun-2026` (41 days from `15-May-2026`) with auto-renewal disabled. |
| `F006` | Loan EMI Verification | `Bank_Statement.pdf` (pp.1–3), `Loan_Statement.pdf` (pp.1–2) | `GREEN` | All 12 FY 2025–26 NACH debits of `₹14,689.84` match Personal Loan `DEMO-PL-5509123` (`₹2,17,987.90` outstanding as of `15-May-2026`). |

## Internal Mathematical Consistency

- **Payroll → Bank → Form 16:** Monthly gross `₹95,200.00` − EPF `₹5,400.00` − PT `₹200.00` − TDS `₹5,200.00` = `₹84,400.00` net salary credited monthly (`₹10,12,800.00/yr`).
- **HRA Rent → Form 16:** `12 × ₹19,500.00 = ₹2,34,000.00` rent paid in bank statement matches declared rent in Form 16 (`₹2,34,000 − 10% of Basic ₹54,000 = ₹1,80,000` HRA exemption).
- **Insurance → Bank → Form 16:** `12 × ₹2,200.00 = ₹26,400.00` NACH debits match Insurance Policy premium history and Form 16 Sec 80C component.
- **Savings Interest → Bank → AIS:** 4 quarterly interest credits (`₹1,620 + ₹1,780 + ₹1,840 + ₹1,960 = ₹7,200.00`) match AIS Horizon Trust Bank entry exactly.
- **FD Principal → Bank → AIS:** `₹2,50,000.00` transfer on `25-Jun-2025` in Bank Statement funds `DEMO-FD-902184` (`7.20% p.a.` quarterly compounding → `₹2,68,492.00` on `25-Jun-2026`; `₹14,057.00` accrued in FY 2025–26 reported in AIS).
