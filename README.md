# whackiest_2026

# ArthaLens – AI-Powered Personal Financial Intelligence Platform

> **Other apps track what you tell them. ArthaLens finds what you forgot.**

ArthaLens is an AI-powered financial intelligence platform that helps individuals discover potentially overlooked financial assets, identify nominee gaps, detect hidden financial leaks, and understand financial risks through intelligent analysis of uploaded financial documents.

Instead of manually checking multiple financial statements and policies, ArthaLens brings relevant information together into one unified **Money Map**.

---

## Problem Statement

People often manage their finances across multiple banks, insurance providers, investments and financial documents. Important information can get scattered or overlooked.

This can lead to:
- Forgotten or undiscovered financial assets.
- Missing or unverified nominee details.
- Hidden recurring charges and financial leaks.
- Conflicting information across financial documents.
- Difficulty organizing financial information for family members.

## Our Solution

ArthaLens uses AI and document intelligence to transform scattered financial documents into actionable financial insights.

### Key Features

- **Smart Document Extraction:** Extracts financial information from uploaded PDFs and scanned documents using AI and OCR.
- **Unified Money Map:** Organizes discovered financial assets in one place.
- **Nominee Coverage Map:** Displays nominee status using Green (confirmed), Amber (unverified) and Red (missing or conflicting evidence).
- **Cross-Document Intelligence:** Connects and compares information across multiple financial documents.
- **Financial Gap Detection:** Identifies potentially forgotten assets, missing information and financial risks.
- **Leak Detection:** Highlights recurring charges and potential unnecessary expenses.
- **Evidence-Based Insights:** Links findings to supporting document information.
- **AI Financial Assistant:** Answers questions using information retrieved from uploaded documents.

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI |
| Database | Supabase PostgreSQL |
| Vector Database | pgvector |
| AI / LLM | OpenAI API or Gemini API |
| Document Processing | PyMuPDF |
| OCR | PaddleOCR |
| RAG | LangChain / LlamaIndex |
| Authentication | Supabase Auth |
| File Storage | Supabase Storage |

## How It Works

1. **Upload:** Users upload financial documents such as bank statements, AIS and insurance policies.
2. **Extract:** PDF processing and OCR extract relevant information.
3. **Understand:** AI identifies financial entities and structures the extracted information.
4. **Connect:** Cross-document intelligence links related financial records.
5. **Verify:** Rule-based validation checks extracted information and identifies gaps or conflicts.
6. **Visualize:** The Money Map and Nominee Coverage Map present the results.
7. **Act:** Users receive evidence-backed findings and suggested next steps.

## RAG-Based AI Architecture

ArthaLens uses Retrieval-Augmented Generation (RAG) to answer questions based on uploaded financial documents.

- Extract text and divide it into smaller chunks.
- Generate vector embeddings for each chunk.
- Store embeddings using PostgreSQL with pgvector.
- Retrieve relevant information through semantic search.
- Generate context-aware answers using an LLM.

This helps keep AI responses grounded in the user's available document evidence.

## Novelty & Innovation

- Combines AI, OCR, RAG and rule-based verification.
- Discovers potentially overlooked financial information rather than only tracking manually entered assets.
- Connects information across multiple financial documents.
- Provides evidence-backed and explainable insights.
- Combines financial discovery, nominee verification and risk detection in one platform.

## Project Structure

```text
ArthaLens/
│
├── frontend/
│   ├── src/
│   ├── components/
│   └── pages/
│
├── backend/
│   ├── main.py
│   ├── routes/
│   ├── services/
│   ├── ai/
│   └── database/
│
├── document_processing/
│   ├── pdf_extractor.py
│   └── ocr_processor.py
│
├── rag/
│   ├── embeddings.py
│   ├── vector_search.py
│   └── retrieval.py
│
├── requirements.txt
└── README.md
```

*The structure is a suggested organization for the project.*

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js and npm
- Supabase account
- AI API key

### 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd ArthaLens
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
```

Activate the environment:

```bash
# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the backend:

```bash
uvicorn main:app --reload
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 4. Environment Variables

Create a `.env` file and configure the required credentials:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
OPENAI_API_KEY=your_openai_api_key
```

Never commit API keys or secret credentials to GitHub.

## Impact

ArthaLens aims to:
- Help individuals identify potentially overlooked financial assets.
- Improve awareness of nominee coverage.
- Highlight financial leaks and inconsistencies.
- Simplify financial organization for families.
- Make financial information easier to understand and act upon.

## Future Scope

- Multilingual financial assistance.
- Family Financial Handover Pack.
- More investment, loan and tax document support.
- Annual financial health reports.
- Integrations with consent-based financial data sources, subject to applicable requirements.

## Privacy & Security

Financial documents contain sensitive personal information. ArthaLens is designed with privacy and security as key priorities.

- Secure document storage.
- Access controls and authentication.
- Encryption and personal information masking.
- Evidence-based AI responses.
- User control over uploaded documents and data.

## Disclaimer

ArthaLens provides informational insights based on uploaded documents. It does not provide legal, tax or financial advice, independently verify information with financial institutions, or guarantee the completeness or accuracy of extracted information. Users should verify important findings with the relevant institution.

## Team

**Project:** ArthaLens  
**Event:** wHACKiest 2026  
**Category:** FinTech / AI

---

**ArthaLens – Because financial security starts with knowing what you might have overlooked.**
