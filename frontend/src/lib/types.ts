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
  created_at?: string;
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

export interface FindingAutomationSummary {
  workflow_type: string;
  automation_level: AutomationLevel;
  task_status: AutomationTaskStatus;
  required_approval: boolean;
  approval_granted: boolean;
  institution_name?: string | null;
  account_or_policy_ref?: string | null;
  estimated_impact_inr?: number | null;
}

export type AutomationLevel =
  | "FULLY_AUTOMATABLE"
  | "AUTOMATABLE_WITH_USER_APPROVAL"
  | "GUIDED_EXTERNAL_ACTION"
  | "MANUAL_VERIFICATION_REQUIRED";

export type AutomationTaskStatus =
  | "Not Started"
  | "In Progress"
  | "Awaiting External Confirmation"
  | "Evidence Received"
  | "Verification Required"
  | "Completed"
  | "Failed";

export interface AutomationStep {
  id: string;
  label: string;
  execution_mode: "AUTO_INTERNAL" | "USER_APPROVAL" | "EXTERNAL_INSTITUTION" | "EVIDENCE_VERIFY";
  completed: boolean;
}

export interface ActionEvidenceItem {
  id: string;
  evidence_type: string;
  filename?: string | null;
  extracted_data: Record<string, unknown>;
  verification_status: "VERIFIED" | "FAILED" | "NEEDS_REVIEW";
  verification_explanation: string;
  uploaded_at: string;
}

export interface ActionAuditLogItem {
  id: string;
  action: string;
  actor: string;
  previous_status?: string | null;
  new_status?: string | null;
  details: string;
  created_at: string;
}

export interface FinancialReminderItem {
  id: string;
  finding_id?: string;
  task_id?: string;
  reminder_type: string;
  title: string;
  message: string;
  due_date?: string | null;
  days_remaining?: number | null;
  status: string;
  created_at?: string;
}

export interface AutomationTaskDetail {
  id: string;
  finding_id: string;
  workflow_type: string;
  automation_level: AutomationLevel;
  task_status: AutomationTaskStatus;
  required_approval: boolean;
  approval_granted: boolean;
  approved_at?: string | null;
  issue_summary: string;
  required_action: string;
  external_institution_required: boolean;
  institution_name?: string | null;
  account_or_policy_ref?: string | null;
  expected_evidence: string;
  estimated_impact_inr?: number | null;
  progress_pct: number;
  steps: AutomationStep[];
  draft_email?: string | null;
  ai_generated: boolean;
  last_verification_summary?: string | null;
  supports_form_download: boolean;
  extracted_entities: Record<string, unknown>;
  institution_directory: {
    official_name?: string;
    official_website?: string | null;
    support_email?: string | null;
    helpline?: string;
    form_name?: string;
    form_code?: string;
    update_steps?: string[];
    is_verified_directory?: boolean;
  };
  workflow_data: Record<string, unknown>;
  evidences: ActionEvidenceItem[];
  audit_logs: ActionAuditLogItem[];
  reminders: FinancialReminderItem[];
  created_at: string;
  updated_at: string;
}

export interface FindingItem {
  id: string;
  user_id: string;
  finding_type?: string;
  title: string;
  category: string;
  severity: Severity;
  confidence: number;
  status: FindingStatus;
  is_demo: boolean;
  impact_amount?: number | null;
  evidence: EvidenceDetail;
  recommended_steps: string[];
  completed_steps?: string[];
  draft_email?: string | null;
  feedback_wrong: boolean;
  feedback_note?: string | null;
  resolution_evidence?: string | null;
  resolved_at?: string | null;
  created_at?: string | null;
  automation?: FindingAutomationSummary | null;
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
  server_time_ist?: string;
}

export type ChatConfidence = "HIGH" | "MEDIUM" | "NEEDS_REVIEW" | "LOW" | string;

export interface ChatSource {
  document_id?: string | number | null;
  filename?: string;
  document: string;
  page_number?: number;
  page: number;
  evidence?: string;
  snippet?: string;
  relevance_score?: number | null;
}

export interface ChatRequest {
  question: string;
  conversation_id: string;
}

export interface ChatResponse {
  answer: string;
  intent?: string;
  language?: string;
  confidence: ChatConfidence;
  sources: ChatSource[];
  citations?: ChatSource[];
  needs_clarification?: boolean;
  clarification_options?: string[];
  followup_suggestions?: string[];
  conversation_id: string;
  retrieval_mode?: string;
  query_category?: string;
  timestamp?: string;
  is_mock?: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: string;
  language?: string;
  confidence?: ChatConfidence;
  sources?: ChatSource[];
  needs_clarification?: boolean;
  clarification_options?: string[];
  followup_suggestions?: string[];
  retrieval_mode?: string;
  query_category?: string;
  created_at: string;
  is_mock?: boolean;
}

export interface ChatConversation {
  conversation_id: string;
  title: string;
  created_at?: string;
  updated_at: string;
  messages: ChatMessage[];
}
