import {
  ActionAuditLogItem,
  AutomationTaskDetail,
  ChatConversation,
  ChatResponse,
  DashboardSummary,
  DocumentItem,
  DocumentType,
  FinancialReminderItem,
  FindingItem,
  NomineeAssetTile,
  User,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.VITE_API_URL ||
  "http://localhost:8000";
const TOKEN_KEY = "arthalens_token";
const USER_KEY = "arthalens_user";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function setAuthSession(token: string, user: User): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 35000);
  if (init.signal) {
    init.signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError" && !init.signal?.aborted) {
      throw new Error("Request timed out after 35s. Please try again.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      if (err?.detail) detail = err.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  async signup(name: string, email: string, password: string) {
    const data = await apiFetch<{ access_token: string; user: User }>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
    setAuthSession(data.access_token, data.user);
    return data;
  },

  async login(email: string, password: string) {
    const data = await apiFetch<{ access_token: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAuthSession(data.access_token, data.user);
    return data;
  },

  async demoLogin() {
    const data = await apiFetch<{ access_token: string; user: User }>("/api/auth/demo", {
      method: "POST",
    });
    setAuthSession(data.access_token, data.user);
    return data;
  },

  me() {
    return apiFetch<User>("/api/auth/me");
  },

  async updateProfile(name: string): Promise<User> {
    const updated = await apiFetch<User>("/api/auth/me", {
      method: "PATCH",
      body: JSON.stringify({ name }),
    });
    const token = getStoredToken();
    if (token) setAuthSession(token, updated);
    return updated;
  },

  getDashboard() {
    return apiFetch<DashboardSummary>("/api/dashboard");
  },

  listDocuments() {
    return apiFetch<DocumentItem[]>("/api/documents");
  },

  getDocument(docId: string) {
    return apiFetch<DocumentItem>(`/api/documents/${docId}`);
  },

  async fetchDocumentFile(docId: string | number): Promise<Blob> {
    const token = getStoredToken();
    const headers = new Headers();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    const res = await fetch(`${API_BASE}/api/documents/${docId}/file`, {
      method: "GET",
      headers,
    });
    if (!res.ok) {
      let detail = `Unable to load PDF (${res.status})`;
      try {
        const err = await res.json();
        if (err?.detail) detail = err.detail;
      } catch {
        // ignore non-json error
      }
      throw new Error(detail);
    }
    return res.blob();
  },

  uploadDocuments(files: File[], docTypeHint?: DocumentType) {
    const formData = new FormData();
    files.forEach((f) => formData.append("files", f));
    if (docTypeHint) {
      formData.append("doc_type_hint", docTypeHint);
    }
    return apiFetch<{
      uploaded: DocumentItem[];
      findings_generated: number;
      findings: FindingItem[];
    }>("/api/documents/upload", {
      method: "POST",
      body: formData,
    });
  },

  reprocessDocument(docId: string) {
    return apiFetch<DocumentItem>(`/api/documents/${docId}/reprocess`, {
      method: "POST",
    });
  },

  deleteDocument(docId: string) {
    return apiFetch<{ deleted: boolean; id: string }>(`/api/documents/${docId}`, {
      method: "DELETE",
    });
  },

  listFindings(params?: { status?: string; severity?: string }) {
    const sp = new URLSearchParams();
    if (params?.status) sp.set("status", params.status);
    if (params?.severity) sp.set("severity", params.severity);
    const qs = sp.toString();
    return apiFetch<FindingItem[]>(`/api/findings${qs ? `?${qs}` : ""}`);
  },

  reportWrong(findingId: string, reason: string) {
    return apiFetch<FindingItem>(`/api/findings/${findingId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
  },

  saveFixProgress(
    findingId: string,
    payload: { verification_evidence: string; completed_steps: string[]; nominee_name?: string }
  ) {
    return apiFetch<FindingItem>(`/api/findings/${findingId}/progress`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  completeFix(
    findingId: string,
    payload: { verification_evidence: string; completed_steps: string[]; nominee_name?: string }
  ) {
    return apiFetch<FindingItem>(`/api/findings/${findingId}/fix`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listAutomationTasks() {
    return apiFetch<{ tasks: AutomationTaskDetail[]; total: number }>("/api/automation/tasks");
  },

  listFinancialReminders() {
    return apiFetch<{ reminders: FinancialReminderItem[] }>("/api/automation/reminders");
  },

  getFindingAutomation(findingId: string) {
    return apiFetch<AutomationTaskDetail>(`/api/automation/findings/${findingId}`);
  },

  automateFinding(findingId: string, useGroq: boolean = true) {
    return apiFetch<AutomationTaskDetail>(`/api/automation/findings/${findingId}/automate`, {
      method: "POST",
      body: JSON.stringify({ use_groq: useGroq }),
    });
  },

  generateFindingRequest(findingId: string, useGroq: boolean = true) {
    return apiFetch<AutomationTaskDetail>(`/api/automation/findings/${findingId}/generate-request`, {
      method: "POST",
      body: JSON.stringify({ use_groq: useGroq }),
    });
  },

  approveFindingAction(
    findingId: string,
    payload: { approved: boolean; edited_draft_email?: string; notes?: string }
  ) {
    return apiFetch<AutomationTaskDetail>(`/api/automation/findings/${findingId}/approve`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async downloadAutomationForm(findingId: string): Promise<{ blob: Blob; filename: string }> {
    const token = getStoredToken();
    const headers = new Headers();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    const res = await fetch(`${API_BASE}/api/automation/findings/${findingId}/download-form`, {
      method: "GET",
      headers,
    });
    if (!res.ok) {
      throw new Error(`Could not download form (${res.status})`);
    }
    const disp = res.headers.get("Content-Disposition") || "";
    const match = disp.match(/filename="([^"]+)"/);
    return {
      blob: await res.blob(),
      filename: match ? match[1] : `ArthaLens_Form_${findingId}.pdf`,
    };
  },

  async uploadActionEvidence(
    findingId: string,
    params: {
      evidence_type?: string;
      confirmation_text?: string;
      nominee_name?: string;
      endorsement_reference?: string;
      confirmation_date?: string;
      file?: File | null;
    }
  ): Promise<AutomationTaskDetail> {
    const token = getStoredToken();
    const headers = new Headers();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    const formData = new FormData();
    formData.append("evidence_type", params.evidence_type || "Uploaded Endorsement");
    formData.append("confirmation_text", params.confirmation_text || "");
    if (params.nominee_name) formData.append("nominee_name", params.nominee_name);
    if (params.endorsement_reference) formData.append("endorsement_reference", params.endorsement_reference);
    if (params.confirmation_date) formData.append("confirmation_date", params.confirmation_date);
    if (params.file) formData.append("file", params.file);

    const res = await fetch(`${API_BASE}/api/automation/findings/${findingId}/evidence`, {
      method: "POST",
      headers,
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.detail || `Evidence upload failed (${res.status})`);
    }
    return data as AutomationTaskDetail;
  },

  verifyFindingCompletion(
    findingId: string,
    payload?: {
      confirmation_text?: string;
      nominee_name?: string;
      endorsement_reference?: string;
      confirmation_date?: string;
    }
  ) {
    return apiFetch<AutomationTaskDetail>(`/api/automation/findings/${findingId}/verify`, {
      method: "POST",
      body: JSON.stringify(payload || {}),
    });
  },

  getFindingAuditLogs(findingId: string) {
    return apiFetch<{ finding_id: string; logs: ActionAuditLogItem[] }>(
      `/api/automation/findings/${findingId}/audit-logs`
    );
  },

  async listAssets(): Promise<NomineeAssetTile[]> {
    try {
      return await apiFetch<NomineeAssetTile[]>("/api/assets");
    } catch {
      const dashboard = await apiFetch<DashboardSummary>("/api/dashboard");
      return dashboard.nominee_tiles;
    }
  },

  async getChatSuggestions(): Promise<string[]> {
    const data = await apiFetch<{ suggestions: string[] }>("/api/chat/suggestions");
    return Array.isArray(data.suggestions) ? data.suggestions : [];
  },

  sendChatMessage(question: string, conversationId: string): Promise<ChatResponse> {
    return apiFetch<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        question,
        message: question,
        conversation_id: conversationId,
      }),
    });
  },

  async streamChatMessage(
    question: string,
    conversationId: string,
    opts?: {
      signal?: AbortSignal;
      onToken?: (token: string, partialText: string) => void;
    }
  ): Promise<ChatResponse> {
    const token = getStoredToken();
    const headers = new Headers({ "Content-Type": "application/json" });
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    const timeoutCtrl = new AbortController();
    let timedOut = false;
    const timeoutId = setTimeout(() => {
      timedOut = true;
      timeoutCtrl.abort();
    }, 45000);
    if (opts?.signal) {
      if (opts.signal.aborted) {
        clearTimeout(timeoutId);
        timeoutCtrl.abort();
      } else {
        opts.signal.addEventListener("abort", () => timeoutCtrl.abort(), { once: true });
      }
    }

    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers,
        signal: timeoutCtrl.signal,
        body: JSON.stringify({
          question,
          message: question,
          conversation_id: conversationId,
        }),
      });
    } catch (err: unknown) {
      clearTimeout(timeoutId);
      if (timedOut) {
        throw new Error("Request timed out waiting for ArthaLens AI. Please retry.");
      }
      throw err;
    }

    if (!res.ok) {
      clearTimeout(timeoutId);
      let detail = `Request failed (${res.status})`;
      try {
        const err = await res.json();
        if (err?.detail) detail = err.detail;
      } catch {
        // ignore
      }
      throw new Error(detail);
    }

    if (!res.body) {
      clearTimeout(timeoutId);
      return api.sendChatMessage(question, conversationId);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let partial = "";
    let finalPayload: ChatResponse | null = null;

    const processFrame = (frame: string) => {
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;
        try {
          const evt = JSON.parse(raw) as {
            type: string;
            token?: string;
            payload?: ChatResponse;
          };
          if (evt.type === "token" && evt.token) {
            partial += evt.token;
            opts?.onToken?.(evt.token, partial);
          } else if (evt.type === "done" && evt.payload) {
            finalPayload = evt.payload;
          }
        } catch {
          // ignore malformed partial SSE chunk
        }
      }
    };

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          processFrame(frame);
        }
      }
      // Flush any final SSE event buffered before EOF without trailing double newline
      buffer += decoder.decode().replace(/\r\n/g, "\n");
      if (buffer.trim()) {
        processFrame(buffer);
      }
    } catch (err: unknown) {
      if (timedOut) {
        throw new Error("Response stream timed out. Please retry.");
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }

    const resolved = finalPayload as ChatResponse | null;
    if (!resolved || typeof resolved.answer !== "string" || !resolved.answer.trim()) {
      if (partial.trim()) {
        return {
          answer: partial.trim(),
          confidence: "NEEDS_REVIEW",
          sources: [],
          citations: [],
          conversation_id: conversationId,
        };
      }
      throw new Error("Empty or incomplete response received from server.");
    }
    return resolved;
  },

  getChatHistory(conversationId?: string): Promise<ChatConversation[]> {
    const query = conversationId
      ? `?conversation_id=${encodeURIComponent(conversationId)}`
      : "";
    return apiFetch<ChatConversation[]>(`/api/chat/history${query}`);
  },

  deleteConversation(conversationId: string) {
    return apiFetch<{ deleted: boolean; conversation_id: string }>(
      `/api/chat/history/${encodeURIComponent(conversationId)}`,
      { method: "DELETE" }
    );
  },

  clearChatHistory() {
    return apiFetch<{ cleared: boolean; deleted_count: number }>("/api/chat/history", {
      method: "DELETE",
    });
  },

  async exportChatHistory(params: {
    scope: "single" | "all";
    format: "pdf" | "txt" | "json";
    conversationId?: string;
    fallbackFilename: string;
  }): Promise<{ blob: Blob; filename: string }> {
    const token = getStoredToken();
    const headers = new Headers();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    const path =
      params.scope === "single" && params.conversationId
        ? `/api/chat/history/${encodeURIComponent(params.conversationId)}/export?format=${params.format}`
        : `/api/chat/history/export-all?format=${params.format}`;

    const res = await fetch(`${API_BASE}${path}`, { method: "GET", headers });
    if (!res.ok) {
      let detail = `Export failed (${res.status})`;
      try {
        const err = await res.json();
        if (err?.detail) detail = err.detail;
      } catch {
        // ignore
      }
      throw new Error(detail);
    }

    const headerName = res.headers.get("X-Export-Filename");
    const disp = res.headers.get("Content-Disposition") || "";
    const match = disp.match(/filename="([^"]+)"/);
    const filename = headerName || (match ? match[1] : params.fallbackFilename);
    const blob = await res.blob();
    return { blob, filename };
  },
};

export function formatINR(amount: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
}
