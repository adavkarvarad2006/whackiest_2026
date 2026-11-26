export type DocumentType =
  | "Bank Statement"
  | "AIS (IT)"
  | "Form 16"
  | "Insurance Policy"
  | "Loan Statement"
  | "Fixed Deposit"
  | "Investment Statement";

export type Severity = "High" | "Medium" | "Low";
export type NomineeStatus = "GREEN" | "AMBER" | "RED";
export type FindingStatus = "Open" | "In Review" | "Resolved" | "Dismissed";

export interface User {
  id: string;
  name: string;
  email: string;
  is_demo: boolean;
}

export interface ExtractedEntity {
  label: string;
  value: string;
  confidence: number;
  page: number;
}

export interface DocumentItem {
  id: string;
  user_id: string;
  filename: string;
  doc_type: DocumentType;
  uploaded_at: string;
  size_bytes: number;
  page_count: number;
  status: "Processed" | "Processing" | "Error";
  pipeline_stage: "Upload" | "Extract" | "Classify" | "Reconcile" | "Generate Findings";
  is_demo: boolean;
  summary: string;
  extracted_entities: ExtractedEntity[];
  pages: { page: number; text: string }[];
}

export interface EvidenceDetail {
  source_document: string;
  source_document_id: string;
  page_number: number;
  extracted_text: string;
  matching_document?: string | null;
  matching_document_id?: string | null;
  matching_page?: number | null;
  matching_text?: string | null;
  why_flagged: string;
  is_confirmed_fact: boolean;
  fact_label: string;
}

export interface FindingItem {
  id: string;
  user_id: string;
  title: string;
  category: string;
  severity: Severity;
  confidence: number;
  status: FindingStatus;
  is_demo: boolean;
  impact_amount?: number | null;
  evidence: EvidenceDetail;
  recommended_steps: string[];
  draft_email?: string | null;
  feedback_wrong: boolean;
  feedback_note?: string | null;
  resolution_evidence?: string | null;
  resolved_at?: string | null;
}

export interface NomineeAssetTile {
  id: string;
  asset_name: string;
  category: string;
  institution: string;
  value: number;
  status: NomineeStatus;
  nominee_name?: string | null;
  source_document: string;
  note: string;
  is_demo: boolean;
}

export interface FinancialTrendPoint {
  month: string;
  income: number;
  expenses: number;
  investments: number;
  net_flow: number;
}

export interface DashboardSummary {
  total_assets_mapped: number;
  potential_blindspots: number;
  potential_annual_leaks: number;
  arthalens_score: number;
  monthly_financial_flow: number;
  nominee_coverage_pct: number;
  nominee_counts: { GREEN: number; AMBER: number; RED: number };
  trends: FinancialTrendPoint[];
  nominee_tiles: NomineeAssetTile[];
  recent_findings: FindingItem[];
  has_demo_data: boolean;
}

export type ChatConfidence = "HIGH" | "MEDIUM" | "NEEDS_REVIEW" | "LOW" | string;

export interface ChatSource {
  document: string;
  page: number;
  snippet?: string;
}

export interface ChatRequest {
  question: string;
  conversation_id: string;
}

export interface ChatResponse {
  answer: string;
  confidence: ChatConfidence;
  sources: ChatSource[];
  conversation_id: string;
  is_mock?: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  confidence?: ChatConfidence;
  sources?: ChatSource[];
  created_at: string;
  is_mock?: boolean;
}

export interface ChatConversation {
  conversation_id: string;
  title: string;
  updated_at: string;
  messages: ChatMessage[];
}
