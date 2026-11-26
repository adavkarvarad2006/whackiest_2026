import {
  ChatConversation,
  ChatResponse,
  DashboardSummary,
  DocumentItem,
  DocumentType,
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

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

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
        conversation_id: conversationId,
      }),
    });
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
