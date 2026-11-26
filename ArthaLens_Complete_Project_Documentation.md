# ArthaLens — AI-Powered Financial Document Intelligence Platform

> **"Other apps track what you tell them. ArthaLens finds what you forgot."**

**Document Type:** Complete Business, Product & Technical Architecture Documentation  
**Platform Version:** 1.0 (Production Prototype — FastAPI + Next.js 16 + PostgreSQL/pgvector + Groq LLM)  
**Timezone Standard:** Indian Standard Time (IST / Asia/Kolkata, UTC+05:30)

---

## Table of Contents

1. Cover Page
2. Executive Summary
3. Problem Statement
4. Proposed Solution
5. Novelty and Innovation
6. Target Users and User Personas
7. Core Features
8. Technology Stack – Detailed Explanation
9. How the AI and RAG Pipeline Works
10. Hybrid AI Chatbot Architecture
11. System Architecture
12. Security and Privacy
13. Real-World Use Cases
14. Advantages and Impact
15. Limitations
16. Future Scope
17. Conclusion
18. Glossary

---

## 2. Executive Summary

**ArthaLens** is an AI-powered financial document intelligence platform built to turn scattered household financial PDFs into a unified, searchable, audit-ready financial map. Instead of asking individuals to manually log daily expenses into spreadsheets or budgeting forms, ArthaLens ingests the documents people already receive — Bank Statements, Annual Information Statements (AIS), Form 16 tax certificates, Life Insurance Policy schedules, Fixed Deposit (FD) certificates, and Personal Loan statements — extracts verifiable facts with exact page references, and proactively surfaces what is missing, maturing, leaking, or inconsistent.

Modern households generate dozens of financial documents across banks, insurers, employers, and tax portals every year. Critical details such as an unrecorded policy nominee, an upcoming FD maturity window without auto-renewal, recurring OTT/SaaS charges, or a salary mismatch between AIS and Form 16 frequently remain hidden across separate PDFs until an emergency or tax deadline occurs. Traditional trackers focus mainly on manual entry or category budgets; ArthaLens focuses on **cross-document blind-spot discovery**.

ArthaLens combines **PyMuPDF** document parsing, **LangChain** chunking, **Sentence Transformers** (`all-MiniLM-L6-v2`) semantic vector indexing in **PostgreSQL + pgvector**, parameterized **SQL analytics**, a **5-level English/Hinglish NLP pipeline**, **Groq LLM inference** (`qwen/qwen3.8-27b`), a **Three-Tier Hybrid Chatbot** (answering general financial literacy questions cleanly even with zero documents uploaded alongside evidence-backed personal and hybrid queries), and an **AI-Powered Guided Fix Wizard** with strict human-in-the-loop safety and evidence verification.

---

## 3. Problem Statement

Individuals and families rarely lose financial clarity due to lack of effort; they lose it because critical facts live in disconnected PDFs across emails, portals, and drawers:

- **Fragmented Multi-Document Storage:** Banking records, tax filings (AIS / Form 16), term deposits, insurance schedules, and loan statements sit in separate portals with incompatible layouts.
- **Forgotten Bank Accounts & Indirect Assets:** Savings accounts reported in tax AIS (`SFT-016`) or dividend-paying investments may not have current bank statements saved locally, risking dormancy or overlooked funds.
- **Unverified or Missing Nominee Information:** Policy schedules frequently leave nomination sections blank or unclear, creating severe claim delays for dependents during emergencies.
- **Overlooked FD Maturity Dates:** Term deposits approaching maturity without auto-renewal instructions risk sitting idle at lower savings rates or missing timely reinvestment opportunities.
- **Unnoticed Subscriptions & Maintenance Charges:** Small recurring monthly debits (`₹199–₹999`), silent plan price hikes, SMS charges, and annual account maintenance fees accumulate quietly over 12 months.
- **Cross-Document Financial Inconsistencies:** Comparing gross salary in an employer's Form 16 against tax portal AIS (`TDS-192`), or matching loan NACH auto-debits against a lender's repayment schedule, is tedious and error-prone manually.

**Why Conventional Financial Apps Fall Short:**  
Many conventional personal finance apps rely primarily on manual transaction logging, single-account categorization, or budget alerts. Without cross-document PDF understanding, citation traceability, or automated gap detection across tax, insurance, banking, and deposit records, they track what a user actively enters rather than uncovering hidden blind spots inside existing documents.

---

## 4. Proposed Solution

ArthaLens converts passive financial PDFs into structured intelligence and verifiable action workflows through nine integrated stages:

1. **Document Upload:** Users upload digital PDFs (Bank Statements, AIS, Form 16, Insurance Policies, FD Certificates, Loan Statements) individually or in batches through an authenticated Next.js interface.
2. **Structured Text & Entity Extraction:** PyMuPDF extracts horizontal text row-by-row while ignoring diagonal watermarks and preserving tables, page numbers, masked account/policy IDs, assets, and transactions.
3. **Meaningful Page Chunking:** LangChain `RecursiveCharacterTextSplitter` splits extracted pages into overlapping semantic chunks (`900` tokens, `125`-token overlap) tagged with exact filename, document type, and page metadata.
4. **Vector Embedding Generation:** Sentence Transformers (`all-MiniLM-L6-v2`) converts each chunk into a 384-dimensional L2-normalized vector (mean-pooling sliding windows so long chunks never truncate tail rows).
5. **Dual Hybrid Indexing (Vector + Relational SQL):** Chunks and embeddings are stored in PostgreSQL `pgvector` (with HNSW cosine + GIN full-text indexes), while structured balances, maturity dates, nominees, and transactions populate relational SQL tables.
6. **Hybrid Retrieval & Cross-Document Analytics:** Cross-document rules detect gaps (`GAP_MISSING_NOMINEE`, `GAP_UNDISCOVERED_ACCOUNT`, `GAP_MISSING_LOAN_STATEMENT`), leaks (`LEAK_RECURRING_SUBSCRIPTIONS`, `LEAK_BANK_CHARGES`), and risks (`RISK_SALARY_DISCREPANCY`, `RISK_UPCOMING_FD_MATURITY`).
7. **Three-Tier Intelligent Query Routing:** Ask ArthaLens classifies queries into **General Knowledge**, **Personal Financial Data**, or **Hybrid Query**, answering financial literacy questions directly via Groq even with zero uploads while isolating personal queries to the user's RAG + SQL context.
8. **Evidence-Backed Citations & Safe Rendering:** Assistant answers include verified document/page citation chips that open the original PDF directly on the cited page, rendered cleanly via XSS-safe Markdown (`react-markdown` + `remark-gfm`).
9. **Guided Action Automation & Proof Verification:** The Fix Wizard prepares forms, institution request drafts, FD reminders, and cancellation guides, requiring explicit user approval and uploaded confirmation evidence before marking sensitive actions `Completed`.

---

## 5. Novelty and Innovation

ArthaLens innovates by shifting personal finance software from **expense bookkeeping** to **cross-document blind-spot intelligence and verified resolution**:

- **Cross-Document Financial Intelligence:** Automatically reconciles multiple document classes (e.g., AIS vs Bank Statement, AIS vs Form 16, Loan Schedule vs Bank Statement NACH debits) to uncover gaps single documents cannot reveal.
- **Blind-Spot First Design:** Surfaces high-impact risks (missing nominee verification, overlooked accounts, missing loan schedules, approaching FD maturity) rather than only monthly pie charts.
- **Nominee Coverage & Verification Map:** Aggregates every asset and policy into a color-coded `GREEN` (`RECORDED`) / `AMBER` / `RED` (`NEEDS_VERIFICATION`) family-readiness map without claiming a nominee is missing merely due to document omission.
- **Leak & Price-Jump Detection:** Groups recurring subscription merchants and bank fees, calculates annual leakage in ₹, and flags price increases over statement cycles.
- **Evidence-Backed AI with Original PDF Grounding:** Every personal claim cites exact document names and page numbers, clicking straight into a custom-oriented PDF viewer (`0°/90°/180°/270°` support, fit-to-container scaling, evidence highlighting).
- **Hybrid Three-Tier Chatbot (English & Hinglish):** Seamlessly switches between zero-doc financial education (`"FD kya hota hai?"`), private document RAG (`"When will my FD mature?"`), and combined benchmark reasoning (`"Is my FD interest rate good?"`).
- **AI Fix Wizard with Fail-Closed Evidence Verification:** Automates internal prep (prefilled Section 39 nomination PDFs, enquiry drafts, maturity countdown reminders) while strictly blocking unauthorized auto-submission and verifying uploaded endorsement PDFs before resolution.

| Traditional Financial Apps | ArthaLens Platform |
| --- | --- |
| Tracks manually entered data or single feeds | Extracts structured intelligence from uploaded financial PDFs |
| Focuses mainly on expense budgeting | Prioritizes blind-spot, nominee-gap, and risk identification |
| Views each statement or account in isolation | Performs cross-document reconciliation (AIS, Form 16, Bank, Loan) |
| Static summary charts with limited traceability | Evidence-backed findings linked directly to source PDF pages |
| Manual keyword search or rigid FAQ menus | 5-level NLP + Hybrid RAG & General-Knowledge AI assistant (English/Hinglish) |

**Implemented vs Planned Innovation Scope:** Cross-document reconciliation, Nominee Coverage Map, 5-level NLP, Hybrid Chatbot, Evidence-verified Fix Wizard, and PDF/TXT/JSON chat exports are **implemented in the current codebase**. Multi-member consented family handover vaults and Account Aggregator live API sync are **planned future enhancements**.

---

## 6. Target Users and User Personas

- **Individual Savers:** Struggle to keep track of FD certificates, savings accounts, and recurring app fees. ArthaLens organizes uploaded PDFs into a clear asset summary and answers financial literacy questions (`"What is compound interest?"`) before any upload. *Practical Use Case:* A first-time earner explores SIP/FD concepts, uploads two bank/FD PDFs, and spots ₹6,000/year in unused subscriptions.
- **Working Professionals:** Manage salary Form 16, AIS tax statements, multiple savings accounts, personal loans, and insurance policies. ArthaLens cross-checks AIS vs Form 16, reconciles EMIs, and surfaces overlooked accounts. *Practical Use Case:* Prior to ITR filing, a software engineer uncovers an ₹18,000 AIS vs Form 16 variance and a secondary bank account in AIS.
- **Families & Dependents:** Need clarity on insurance nominees and where core assets are held so family members can navigate records during emergencies. ArthaLens provides the Nominee Coverage Map and prefilled Section 39 nomination request packets. *Practical Use Case:* A household reviews policy coverage, downloads prefilled nomination forms, and tracks insurer endorsement receipts. *(Note: Multi-user shared family login is planned; single-account organization and exportable reports are implemented today.)*
- **Senior Citizens & Caregivers:** Benefit from plain-language English/Hinglish explanations, FD maturity reminders, and simplified tracking of bank maintenance/SMS fee debits across PDFs without complex spreadsheets. *Practical Use Case:* Checking `"Mera FD kab mature hoga?"` to see exact maturity date, principal, and renewal comparisons.
- **Small Business Owners / Freelancers:** Often juggle overlapping business/personal bank charges, recurring software subscriptions (`CloudNotes Pro`, etc.), and loan EMI debits across PDF statements. *Practical Use Case:* Detecting recurring SaaS charges and missing loan amortization statements to prepare CA tax briefs. *(Note: Multi-GST/ERP invoicing is outside current scope; document intelligence supports core banking, tax, and loan PDFs.)*

---

## 7. Core Features (Implemented Inventory)

1. **Smart Financial Document Upload:** Validates `.pdf` extension, non-empty payload, `20 MB` max size, `%PDF-` signature, and SHA-256 deduplication; supports single & multi-file upload and auto-classifies 6 financial PDF classes.
2. **PDF Text & Structured Data Extraction:** PyMuPDF visual-row reconstruction removes diagonal watermarks, preserves financial table columns with ` | ` separators, extracts masked IDs (`DEMO-SB-XXXXXX2910`), assets, NER entities, and categorized transactions.
3. **AI-Powered Financial Chatbot (`Ask ArthaLens`):** Built on a 5-level NLP pipeline (lexical Hinglish/typo normalization, syntactic negation/IST temporal windows, semantic intent classification, multi-turn discourse coreference, pragmatic reasoning) paired with SSE token streaming, `"ArthaLens is thinking..."` state, request timeouts, retry recovery, and XSS-safe Markdown rendering.
4. **Hybrid General-Knowledge & RAG Question Answering:** Routes `GENERAL_KNOWLEDGE` directly to Groq without RAG (zero document requirement, zero fabricated citations), `PERSONAL_FINANCIAL_DATA` through user-isolated pgvector + SQL, and `HYBRID_QUERY` through separated *Your Financial Data* and *General Financial Explanation* reasoning.
5. **Financial Blind-Spot Detection:** Flags missing nominee verification, AIS-reported overlooked bank accounts, term deposits without certificates, dividend-implied holdings, missing loan statements, salary discrepancies, recurring subscriptions, and upcoming FD maturities.
6. **Nominee Coverage Map:** Dedicated visual dashboard (`/dashboard/nominees`) scoring nominee readiness (`GREEN` / `AMBER` / `RED`) across savings, FDs, and policies with direct Fix Wizard launch.
7. **Recurring Expense & Subscription Detection:** Groups `SUBSCRIPTION`, `BANK_FEE_SMS`, and `BANK_FEE_AMC` debits, annualizes expenditure, flags price jumps, and provides merchant cancellation guidance.
8. **Cross-Document Financial Analysis:** Compares AIS `SFT-016` vs uploaded bank statements, AIS `TDS-192` vs Form 16 Part B, and Loan Statement EMIs vs Bank Statement NACH debits.
9. **Evidence-Backed Findings & Original PDF Viewer:** Every finding and chat citation displays source document name, page number, and snippet; clicking opens `PdfViewerModal` (`pdfjs-dist`) respecting page rotation metadata (`0°/90°/180°/270°`), responsive container fit, zoom/page controls, and evidence highlight overlays.
10. **Chat History & Multi-Format Export:** Persists threads in SQLite/PostgreSQL with IST (`+05:30`) timestamps, history search, thread deletion/clear, and single/bulk exports in **PDF** (ReportLab), **TXT**, and **JSON**.
11. **Automation Dashboard & Financial Report/Form Generation (`/dashboard/actions` & Fix Wizard):** Classifies findings into 4 automation tiers, schedules FD maturity countdown reminders, generates prefilled downloadable PDF servicing/Section 39 nomination packets, drafts editable enquiry emails, enforces user approval before external submission, and verifies uploaded confirmation PDFs cleanly.
12. **Security Guardrails & Immutable Audit Trail (`ActionAuditLog`):** Enforces JWT user isolation (`401`/`404`), blocks prohibited autonomous actions (`AUTO_SUBMIT_FORM`, `PORTAL_LOGIN_WITH_CREDENTIALS`, `MODIFY_BANK_NOMINEE`, `EXECUTE_TRANSACTION`, `AUTO_CANCEL_POLICY`) with `HTTP 403`, and logs every status change in IST.

---

## 8. Technology Stack – Detailed Explanation

### Verified Implemented Technologies
- **Frontend:**
  - **Next.js 16.4.6 (App Router + Turbopack) & React 19.3.0:** Powers all `/dashboard/*`, `/login`, and `/signup` routes using React Server/Client components. *(Note: ArthaLens uses Next.js App Router rather than React Router.)*
  - **TypeScript 5 & Tailwind CSS 4.3:** Enforces end-to-end API type safety (`frontend/src/lib/types.ts`) and ArthaLens's crisp monochrome UI aesthetic (`#090909` / `#F7F7F7` / `#E8E8E8`).
  - **Native Fetch API Client (`frontend/src/lib/api.ts`):** Handles authenticated JSON requests, SSE chat streaming (`AbortController` timeouts + EOF frame flush), multipart uploads, and blob exports. *(Note: Native Fetch API is used instead of Axios.)*
  - **`pdfjs-dist`, `lucide-react`, `recharts`, `framer-motion`, `react-markdown`, `remark-gfm`, `rehype-highlight`:** Client-side oriented PDF canvas rendering, icons, financial trend charts, micro-animations, and XSS-safe Markdown code/table formatting.
- **Backend:**
  - **Python 3.12, FastAPI (>=0.115), Uvicorn, Pydantic v2:** High-performance async REST & SSE API layer with strict request/response schema validation and IST (`ZoneInfo("Asia/Kolkata")`) serialization.
- **AI, NLP & RAG:**
  - **Groq OpenAI-Compatible API (`https://api.groq.com/openai/v1`, `qwen/qwen3.8-27b`) via async `httpx`:** Provides low-latency structured JSON reasoning with retries (`429`/`5xx`), `413` context compaction, and secret redaction.
  - **Sentence Transformers (`all-MiniLM-L6-v2`, 384-dim) & `tiktoken`:** Generates L2-normalized dense embeddings with sliding-window mean pooling for semantic retrieval.
  - **LangChain Text Splitters (`RecursiveCharacterTextSplitter`):** Preserves table row integrity while chunking extracted text cleanly.
  - **Custom 5-Level FinTech NLP Engine (`backend/app/services/nlp/`):** Tokenization, Hinglish normalization, syntactic negation & IST relative date windows, semantic intent + 3-tier routing, discourse coreference, NER, and pragmatic health evaluation.
- **Document Processing & PDF Generation:**
  - **PyMuPDF (`fitz` >=1.24) & ReportLab (>=4.2):** Extracts table-aligned PDF text/metadata cleanly and builds downloadable Section 39 prefilled packets, chat PDF exports, and technical documentation.
- **Database & Security:**
  - **PostgreSQL 16 + `pgvector` (HNSW cosine + GIN `tsvector` indexes) via SQLAlchemy 2.0 & `psycopg`:** Stores vector chunks (`Vector(384)`), JSONB evidence, UUID conversations, relational assets/transactions, and automation audit logs, with a dialect-safe SQLite development fallback (`arthalens_local.db`).
  - **`python-jose` (HS256 JWT) & `passlib[bcrypt]`:** Stateless Bearer authentication and salted password hashing.

### Planned / Deployment Architecture Note
- **Implemented:** `docker-compose.yml` defining `pgvector/pgvector:pg16` PostgreSQL container (`arthalens-postgres`) and backend container orchestration.
- **Planned:** Cloud production hosting manifests for Render (FastAPI + managed PostgreSQL/pgvector) and Vercel (Next.js frontend), plus Two-Factor Authentication (2FA) and production TLS/encryption-at-rest configuration.

---

## 9. How the AI and RAG Pipeline Works

ArthaLens implements a deterministic, user-isolated **9-step RAG + Hybrid SQL pipeline**:

1. **Document Ingestion:** PDF signature verification (`%PDF-`), SHA-256 deduplication, and disk persistence under `storage/uploads/{user_id}/`.
2. **Page-Preserving Extraction:** PyMuPDF extracts clean lines while recording exact 1-indexed `page_number`.
3. **Token-Aware Chunking:** LangChain `RecursiveCharacterTextSplitter` (`cl100k_base`, `chunk_size=900`, `chunk_overlap=125`) emits `[Document: <file> | Type: <type> | Page: <n>]` contextualized chunks.
4. **Embedding Generation:** `all-MiniLM-L6-v2` encodes chunks into 384-dim normalized vectors (`_embed_single_long_text` splits >180-word chunks into overlapping windows and mean-pools).
5. **Dual Vector + Metadata Storage:** Persisted in `document_chunks` filtered strictly by `user_id` and `document_id`.
6. **NLP Query Processing:** 5-level NLP normalizes Hinglish/abbreviations/typos, resolves pronouns across history, and selects expanded search queries.
7. **Hybrid Vector + Keyword Retrieval:** On PostgreSQL, `pgvector` cosine similarity `(1 - (embedding <=> q_vec))` + `0.20 * ts_rank_cd(to_tsvector(...))` ranks top-K (`top_k=6`, `threshold=0.22`) chunks strictly for `WHERE dc.user_id = :user_id`.
8. **Grounded Prompt Construction & Groq Inference:** Retrieved evidence chunks + verified parameterized SQL context + IST timestamps are sent to Groq (`temperature=0.1` for personal facts).
9. **Citation Validation:** `_merge_sources` verifies every cited filename and page number against the user's real database documents before returning `ChatResponse` and persisting `chat_messages`.

**RAG vs Traditional LLM vs Hybrid AI (and Why RAG ≠ Retraining):**  
- **Does RAG train the LLM on private PDFs?** **No.** Uploaded documents are never used to fine-tune or update Groq model weights. Instead, documents remain encrypted/isolated inside the user's database and are retrieved strictly at query time as temporary read-only context. Deleting a document deletes its chunks immediately.
- **Traditional LLM:** Relies solely on pre-trained parametric weights; cannot know personal FD maturity dates and risks hallucination if asked private questions.
- **Pure RAG:** Strictly grounded in retrieved snippets; refuses answers when no matching uploaded documents exist.
- **ArthaLens Hybrid AI:** Combines Groq's financial concept fluency for general questions, strict RAG + SQL for personal facts, and separated dual-section reasoning when evaluating personal records against general benchmarks.

**500-PDF Quantitative Benchmark (`arthalens_dataset/evaluation/evaluation_report.json`):**  
- Documents processed: `500` (`1,348` chunks) | Questions tested: `350` (`300` answerable, `25` unanswerable, `25` cross-customer isolation)  
- Answer correctness: **100%** (`350/350`) | Recall@6: **97.33%** | Citation accuracy: **100%** | Customer isolation pass rate: **100%** | Unsupported answer rate: **0.0%**.

---

## 10. Hybrid AI Chatbot Architecture

Every user message passes through `classify_query_category` in `backend/app/services/nlp/intent.py`:

- **Tier A — `GENERAL_KNOWLEDGE` (`route = GENERAL_LLM`):** Conceptual/educational questions without personal possessives (`"What is an FD?"`, `"FD kya hota hai?"`, `"Difference between FD and RD?"`, `"What is compound interest?"`, `"Explain SIP with an example."`). Skips vector search cleanly, works with **0 uploaded documents**, formats clear explanations with illustrative examples & pros/cons, and enforces `citations = []`.
- **Tier B — `PERSONAL_FINANCIAL_DATA` (`route = RAG | SQL | SQL+RAG | HYBRID`):** Queries containing personal markers (`my`, `mera`, `do I have`, masked IDs, workspace gap audits such as `"When will my FD mature?"`, `"How many FDs do I have?"`, `"What about my FD?"`). Executes user-isolated RAG + SQL analytics and returns `UNAVAILABLE` if documents are absent.
- **Tier C — `HYBRID_QUERY` (`route = HYBRID_REASONING`):** Evaluative or portfolio-adequacy questions combining personal records with general benchmarks (`"Is my FD interest rate good?"`, `"Is my investment portfolio diversified?"`, `"Am I financially prepared?"`). Structures output explicitly into **Your Financial Data** and **General Financial Explanation**.

**Conversational Context & Hinglish Support:**  
- Lexical stage detects Hinglish markers (`mera`, `kya`, `kab`, `kaise`, `kitna`, `hota`) and replies in matching English or Hinglish.
- Discourse stage checks the previous assistant turn's `retrieval_mode`: follow-ups like `"What are its benefits?"` after `"What is an FD?"` preserve `GENERAL_KNOWLEDGE` while resolving `"its" -> "fixed deposit"`, whereas `"What about my FD?"` detects `"my"` and dynamically pivots to `PERSONAL_FINANCIAL_DATA` RAG + SQL retrieval.

---

## 11. System Architecture

*(Vector diagram rendered directly in the compiled PDF)*:  
User → Next.js 16 Frontend (`DashboardShell`, `PdfViewerModal`, `FixWizardModal`, `AskArthaLensPage` with `AssistantMarkdown`) → FastAPI REST & SSE API (`auth`, `documents`, `intelligence`, `automation`, `chat`) → HS256 JWT Authentication & `user_id` Authorization → Document Ingestion (`PyMuPDF` + `LangChain` chunker + `NER` / `extraction`) → `SentenceTransformer` (`all-MiniLM-L6-v2`) → PostgreSQL + `pgvector` Database + Disk PDF Storage → 5-Level NLP Router (`RAG` + Parameterized SQL) → Groq LLM (`qwen/qwen3.8-27b`) → Citation & Guardrail Validation → Dashboard / Chat / Verified Automation Actions.

---

## 12. Security and Privacy

| Security Control | Status | Implementation Detail in ArthaLens |
| --- | --- | --- |
| Authentication | **Implemented** | Stateless HS256 JWT Bearer tokens (`create_access_token`, configurable expiry) |
| Password Hashing | **Implemented** | Salted Bcrypt via `passlib[bcrypt]` (`hash_password`, `verify_password`) |
| Authorization & Tenant Isolation | **Implemented** | Every DB query (`documents`, `document_chunks`, `financial_assets`, `findings`, `chat_messages`, `automation_tasks`) filters by `current_user.id`; unauthorized cross-user access returns `404` |
| Secure PDF Access | **Implemented** | Owner-verified `HTTP 206` Byte-Range PDF streaming (`GET /api/documents/{id}/file`) with `%PDF-` signature validation and filename sanitization |
| Sensitive Identifier Masking | **Implemented** | `mask_reference()` masks account/policy/loan identifiers cleanly (preserving only final 4 characters, e.g., `DEMO-SB-XXXXXX2910`) |
| Secret & Credential Hygiene | **Implemented** | `.env` excluded via `.gitignore`; startup validates `GROQ_API_KEY`; `_SECRET_REDACT_RE` scrubs `gsk_*` from error logs/responses; no banking passwords stored or accepted |
| Financial Safety & Audit Trail | **Implemented** | `FORBIDDEN_AUTONOMOUS_ACTIONS` blocks auto-submit, portal login, auto-cancel, transactions, and unverified completion (`HTTP 403`) with immutable `ActionAuditLog` timestamps in IST |
| Two-Factor Authentication (2FA) | **Planned** | TOTP / SMS OTP verification prior to sensitive exports or action approvals |
| Production HTTPS / Encryption at Rest | **Planned** | Reverse-proxy TLS termination (HTTPS), cloud KMS key rotation, and encrypted PostgreSQL/object-storage volumes for production hosting |

---

## 13. Real-World Use Cases (Illustrative Scenarios)

1. **Working Professional Discovers an Overlooked Bank Account:** *Rohan* uploads his bank statement and Tax AIS PDF. Cross-document reconciliation finds `AIS_SAVINGS_ACCOUNT` (`MetroCivic Bank`, ₹7,200 interest) missing from uploaded statements, generates a bank status enquiry email, and tracks statement upload to resolution.
2. **Family Organizes Insurance & Completes Nominee Endorsement Verification:** *Ananya* notices a `RED` Policy Nominee alert on a ₹1 Cr policy. The Fix Wizard extracts insurer/policy info, streams a prefilled Section 39 PDF, records draft approval (`Awaiting External Confirmation`), rejects an unrelated test endorsement (`Failed`), and resolves only after extracting confirmed nominee + endorsement ref `SR-NOM-88421` from her uploaded confirmation PDF.
3. **User Audits Recurring Subscriptions & Price Jumps:** Bank statement transaction clustering reveals ₹16,934/year in recurring OTT, cloud note, and maintenance/SMS fees (`StreamFlix`, `CloudNotes Pro`, `TuneWave`), highlighting monthly price increases and surfacing direct official cancellation instructions.
4. **User Acts Early on Approaching FD Maturity:** Extracted certificate shows a ₹2,50,000 Fixed Deposit maturing soon with `Auto-Renewal: NOT opted`. ArthaLens schedules an automated `FD_MATURITY` countdown reminder, generates a 3-option renewal comparison, and prepares a rate enquiry draft for the bank.
5. **Cross-Document Tax Reconciliation Before ITR Filing:** Comparing AIS (`₹11,60,400`) vs Form 16 (`₹11,42,400`) flags an `₹18,000` gross salary discrepancy (even though TDS matches), drafts an employer payroll query, and generates structured questions for Rohan's Chartered Accountant.
6. **New User Learns FD Concepts Before Uploading Any PDFs:** *Meera* logs in with 0 documents and asks `"FD kya hota hai?"` → `"What are its benefits?"` → `"What about my FD?"`. ArthaLens answers the first two using Groq's financial literacy mode with zero fake citations, then cleanly switches to `PERSONAL_FINANCIAL_DATA` guidance on turn 3.

---

## 14. Advantages and Impact

- **Saves Manual Effort:** Replaces hours of cross-checking multi-page PDFs with instant entity maps and cited queries.
- **Surfaces Hidden Blind Spots:** Elevates silent risks (unconfirmed nominees, forgotten accounts, missing loan schedules) to top priority.
- **Searchable Financial Vault:** Converts static financial PDFs into natural-language English and Hinglish search with page-level jump links.
- **Democratizes Financial Literacy:** Bridges conceptual understanding (`What is SIP / compound interest?`) with personal evidence cleanly.
- **Verified Resolution Discipline:** Prevents premature closure of critical compliance tasks until real institutional proof is uploaded and verified.

---

## 15. Limitations

- **Scanned Image-Only PDFs:** Purely image-based scanned documents without an embedded text layer require future OCR integration; current extraction relies on PyMuPDF text spans.
- **Source Document Completeness:** Findings reflect only uploaded files; unlisted policies, offline cash assets, or un-uploaded broker statements cannot be inferred automatically.
- **Regex/Template Sensitivity:** Highly non-standard third-party bank layouts may yield partial entity extraction requiring manual review (`NEEDS_REVIEW`).
- **Time-Sensitive Rates & Tax Rules:** General financial answers explain concepts rather than live RBI repo rates, current bank FD card rates, or yearly tax slab amendments.
- **Free-Tier LLM Rate Ceilings & Security Maintenance:** External LLM APIs (e.g., Groq free-tier TPM quotas) require request throttling/retry handling, and ongoing security hardening (HTTPS, 2FA, encryption-at-rest) is critical before multi-tenant public rollout.

---

## 16. Future Scope (Planned Enhancements)

- **OCR Pipeline (`Future`):** Tesseract / multimodal Vision OCR for photographed receipts and scanned legacy passbooks.
- **Automated Background Reminders (`Future`):** Email/push digests before FD maturity, insurance premium grace dates, and ITR deadlines (building upon persisted `FinancialReminder` records).
- **Voice-Enabled Multilingual Assistant (`Future`):** Speech-to-text / text-to-speech in regional Indian languages alongside Hinglish.
- **Expanded Financial Formats & Consent Integrations (`Future`):** CSV/Excel ledgers, CAMS/KFintech CAS investment imports, and regulated **Account Aggregator (AA)** consented feeds.
- **Family Handover Mode with 2FA (`Future`):** Encrypted emergency-access nominee vault protected by TOTP Two-Factor Authentication and role-based read consent.

---

## 17. Conclusion

**ArthaLens** reimagines personal finance tools around a simple insight: people rarely need yet another manual expense spreadsheet — they need clarity across the financial PDFs they already possess. By uniting deterministic PyMuPDF extraction, `pgvector` hybrid retrieval, 5-level bilingual NLP, three-tier Groq reasoning, verifiable page citations, and an evidence-gated AI Fix Wizard, ArthaLens delivers measurable clarity for individuals, professionals, and households alike.

> **"Other apps track what you tell them. ArthaLens finds what you forgot."**

---

## 18. Glossary

- **LLM (Large Language Model):** An AI model trained on broad language patterns (accessed here via Groq's API) capable of reasoning, summarizing, and generating structured explanations.
- **RAG (Retrieval-Augmented Generation):** An architecture that retrieves relevant excerpts from user-owned documents at query time and feeds them to an LLM to ground answers in verifiable facts without retraining the model.
- **NLP (Natural Language Processing):** Algorithms that parse grammar, typos, abbreviations, languages (English/Hinglish), intent, and conversational context from human text.
- **Embeddings:** Compact numerical vectors (384 numbers in `all-MiniLM-L6-v2`) representing the semantic meaning of text so related concepts can be matched mathematically.
- **Vector Database:** A specialized index (`pgvector` inside PostgreSQL) enabling fast similarity search across high-dimensional embeddings alongside SQL filters.
- **API (Application Programming Interface):** Structured endpoints allowing the Next.js frontend and FastAPI backend to exchange authenticated data reliably.
- **FastAPI:** A modern, async Python web framework with automatic schema validation via Pydantic used to build ArthaLens's backend.
- **Groq:** An ultra-low-latency AI inference platform providing OpenAI-compatible Chat Completions endpoints for `qwen/qwen3.8-27b`.
- **Semantic Search:** Searching by conceptual meaning rather than exact keyword matching alone (e.g., matching `"when does my term deposit end"` to FD maturity pages).
- **Authentication:** Verifying who a user is (e.g., via email/password login and signed JWT access tokens).
- **Authorization:** Enforcing what an authenticated user is permitted to access or execute (strict `user_id` row ownership and action safety boundaries).
- **Audit Trail:** A chronological, tamper-evident log (`ActionAuditLog`) recording system and user actions, approvals, blocks, and status changes in IST.
- **Two-Factor Authentication (2FA):** An additional verification factor (e.g., authenticator TOTP code) beyond password login; planned as a security enhancement for ArthaLens.
