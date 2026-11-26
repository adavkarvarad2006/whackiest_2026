# ArthaLens Frontend

Evidence-backed personal financial intelligence dashboard built with Next.js, React, TypeScript, and Tailwind CSS.

## Technology Stack

- **Framework:** Next.js 16.4.6 (App Router, Turbopack)
- **UI Library:** React 19.3.0
- **Language:** TypeScript 5
- **Styling:** Tailwind CSS 4.3.3
- **Charts & Icons:** Recharts 3.11.1, Lucide React 1.81.0

## Features Included

- **Landing Page** (`/`) with editorial sections and responsive navigation
- **Authentication** (`/login`, `/signup`, and demo login)
- **User Dashboard** (`/dashboard`) with KPIs, Financial Overview trend chart, Nominee Coverage Map, and recent findings
- **Document Upload & Management** (`/dashboard/documents`)
- **Financial Map** (`/dashboard/financial-map`)
- **Nominee Coverage** (`/dashboard/nominees`)
- **Findings & Fix Wizard** (`/dashboard/findings`)
- **Evidence Citations** (`/dashboard/evidence`)
- **Action Checklist** (`/dashboard/actions`)
- **Ask ArthaLens AI Chatbot** (`/dashboard/chat`) with chat history, suggested questions, source document citations, and confidence indicators

## Local Setup & Commands

1. **Install dependencies:**

```bash
cd frontend
npm install
```

2. **Configure environment variables:**

Copy `.env.example` to `.env.local` (never commit `.env*` files):

```bash
cp .env.example .env.local
```

Supported variables:
- `VITE_API_URL=http://localhost:8000`
- `NEXT_PUBLIC_API_URL=http://localhost:8000`

If neither is set, the API client defaults to `http://localhost:8000`.

3. **Run the development server:**

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

4. **Run the production build:**

```bash
npm run build
npm run start
```

## Backend API Requirements & Endpoints

The frontend communicates with the backend via the centralized service layer in `src/lib/api.ts`:

| Feature | Method | Endpoint |
| --- | --- | --- |
| Signup / Login / Demo | `POST` | `/api/auth/signup`, `/api/auth/login`, `/api/auth/demo` |
| Current User | `GET` | `/api/auth/me` |
| Dashboard Summary | `GET` | `/api/dashboard` |
| Document Upload | `POST` | `/api/documents/upload` |
| Document Listing | `GET` | `/api/documents` |
| Document Details | `GET` | `/api/documents/{id}` |
| Document Delete | `DELETE` | `/api/documents/{id}` |
| Financial Assets | `GET` | `/api/assets` |
| Findings List | `GET` | `/api/findings` |
| Finding Feedback / Fix | `POST` | `/api/findings/{id}/feedback`, `/api/findings/{id}/fix` |
| AI Chat Query | `POST` | `/api/chat` |
| AI Chat History | `GET` | `/api/chat/history` |

### Chatbot API Contract (`POST /api/chat`)

Request:
```json
{
  "question": "Do I have any missing nominees?",
  "conversation_id": "uuid"
}
```

Response:
```json
{
  "answer": "Your uploaded insurance policy does not contain recorded nominee details.",
  "confidence": "NEEDS_REVIEW",
  "sources": [
    {
      "document": "insurance_policy.pdf",
      "page": 2
    }
  ],
  "conversation_id": "uuid"
}
```

> **Development Fallback:** If `/api/chat` or `/api/chat/history` is not yet available on the backend, `src/lib/mockChatService.ts` provides a clearly separated development fallback so the UI remains testable without hardcoding mock answers into components.
