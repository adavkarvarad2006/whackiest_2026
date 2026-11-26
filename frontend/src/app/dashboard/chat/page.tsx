"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronDown,
  Copy,
  Download,
  FileText,
  History,
  Loader2,
  MessageSquare,
  Plus,
  RotateCcw,
  Search,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
} from "lucide-react";
import { AssistantMarkdown } from "@/components/AssistantMarkdown";
import { DashboardShell } from "@/components/DashboardShell";
import { PdfViewerModal } from "@/components/PdfViewerModal";
import { api } from "@/lib/api";
import { formatISTWithTz } from "@/lib/dateUtils";
import { ChatConfidence, ChatConversation, ChatMessage, ChatSource } from "@/lib/types";

const DEFAULT_SUGGESTED_QUESTIONS = [
  "What is an FD?",
  "Difference between FD and RD?",
  "Is my FD interest rate good?",
  "Which policies don't have nominees?",
];

function createConversationId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `conv-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function confidenceBadge(confidence?: ChatConfidence) {
  const normalized = (confidence || "").toUpperCase();
  if (normalized === "HIGH" || normalized === "VERIFIED") {
    return {
      label: normalized,
      className:
        "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800",
      Icon: ShieldCheck,
    };
  }
  if (normalized === "NEEDS_REVIEW" || normalized === "MEDIUM") {
    return {
      label: normalized.replace("_", " "),
      className:
        "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800",
      Icon: ShieldAlert,
    };
  }
  return {
    label: normalized || "INFO",
    className:
      "bg-white text-[#374151] border-[#E5E5E5] dark:bg-[#2A2A2A] dark:text-[#F5F5F5] dark:border-[#404040]",
    Icon: ShieldAlert,
  };
}

export default function AskArthaLensPage() {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>(DEFAULT_SUGGESTED_QUESTIONS);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string>("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [historySearch, setHistorySearch] = useState("");
  const [chatError, setChatError] = useState("");
  const [confirmDeleteConv, setConfirmDeleteConv] = useState<ChatConversation | null>(null);
  const [confirmClearAll, setConfirmClearAll] = useState(false);
  const [clearingAll, setClearingAll] = useState(false);
  const [deletingConv, setDeletingConv] = useState(false);
  const [activePdf, setActivePdf] = useState<{
    documentId: string | number | null | undefined;
    filename: string;
    page: number;
    evidence?: string;
  } | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportNotice, setExportNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const exportMenuRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!exportOpen) return;
    const onOutsideClick = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setExportOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExportOpen(false);
    };
    document.addEventListener("mousedown", onOutsideClick);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onOutsideClick);
      window.removeEventListener("keydown", onKey);
    };
  }, [exportOpen]);

  const handleExport = async (scope: "single" | "all", format: "pdf" | "txt" | "json") => {
    if (exporting) return;
    setExportOpen(false);
    setExportNotice(null);
    setExporting(true);

    const activeConv = conversations.find((c) => c.conversation_id === activeId);
    const titlePart = (activeConv?.title || "Conversation").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_|_$/g, "").slice(0, 40) || "Conversation";
    const fallbackFilename =
      scope === "single"
        ? `ArthaLens_Chat_${titlePart}.${format}`
        : format === "txt"
        ? "ArthaLens_Chat_History.txt"
        : `ArthaLens_All_Conversations.${format}`;

    try {
      const { blob, filename } = await api.exportChatHistory({
        scope,
        format,
        conversationId: scope === "single" ? activeId : undefined,
        fallbackFilename,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setExportNotice({ type: "success", text: `Exported ${filename}` });
    } catch (err: unknown) {
      setExportNotice({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to export chat history.",
      });
    } finally {
      setExporting(false);
    }
  };

  const openCitationPdf = async (src: ChatSource) => {
    const filename = src.filename || src.document;
    const page = src.page_number ?? src.page ?? 1;
    const evidence = src.evidence || src.snippet;
    let docId = src.document_id;

    // Fallback lookup by filename from user's uploaded documents if older history lacks document_id
    if (!docId && filename) {
      try {
        const docs = await api.listDocuments();
        const match = docs.find((d) => d.filename.toLowerCase() === filename.toLowerCase());
        if (match) docId = match.id;
      } catch {
        // Handled cleanly inside PdfViewerModal if unavailable
      }
    }

    setActivePdf({
      documentId: docId,
      filename,
      page,
      evidence,
    });
  };

  const loadHistory = useCallback(async () => {
    try {
      const history = await api.getChatHistory();
      setConversations(history);
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : "Unable to load chat history.");
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    setActiveId(createConversationId());
    loadHistory();
    api
      .getChatSuggestions()
      .then((list) => {
        if (list.length > 0) setSuggestedQuestions(list);
      })
      .catch(() => {
        // fallback cleanly to DEFAULT_SUGGESTED_QUESTIONS
      });
  }, [loadHistory]);

  const filteredConversations = useMemo(() => {
    const q = historySearch.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) => {
      if (c.title.toLowerCase().includes(q)) return true;
      return c.messages.some((m) => m.content.toLowerCase().includes(q));
    });
  }, [conversations, historySearch]);

  const handleDeleteConversation = async () => {
    if (!confirmDeleteConv || deletingConv) return;
    setDeletingConv(true);
    setChatError("");
    try {
      await api.deleteConversation(confirmDeleteConv.conversation_id);
      if (activeId === confirmDeleteConv.conversation_id) {
        setActiveId(createConversationId());
        setMessages([]);
      }
      setConfirmDeleteConv(null);
      await loadHistory();
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : "Failed to delete conversation.");
    } finally {
      setDeletingConv(false);
    }
  };

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const startNewChat = () => {
    setActiveId(createConversationId());
    setMessages([]);
    setInput("");
  };

  const selectConversation = (conv: ChatConversation) => {
    setActiveId(conv.conversation_id);
    setMessages(conv.messages);
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  };

  const handleClearAllHistory = async () => {
    if (clearingAll) return;
    setClearingAll(true);
    setChatError("");
    try {
      await api.clearChatHistory();
      setConversations([]);
      setMessages([]);
      setActiveId(createConversationId());
      setConfirmClearAll(false);
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : "Failed to clear chat history.");
    } finally {
      setClearingAll(false);
    }
  };

  const handleCopyResponse = (msgId: string, content: string) => {
    if (!content) return;
    navigator.clipboard.writeText(content);
    setCopiedMsgId(msgId);
    setTimeout(() => setCopiedMsgId((curr) => (curr === msgId ? null : curr)), 2000);
  };

  const handleSend = async (questionText?: string) => {
    const question = (questionText ?? input).trim();
    if (!question || sending) return;

    const conversationId = activeId || createConversationId();
    if (!activeId) setActiveId(conversationId);

    const userMsg: ChatMessage = {
      id: `local_u_${Date.now()}`,
      role: "user",
      content: question,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!questionText) setInput("");
    setLastQuestion(question);
    setChatError("");
    setStreamingText("");
    setSending(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const res = await api.streamChatMessage(question, conversationId, {
        signal: controller.signal,
        onToken: (_tok, partial) => setStreamingText(partial),
      });
      const resolvedSources = res.citations && res.citations.length > 0 ? res.citations : res.sources;
      const assistantMsg: ChatMessage = {
        id: `local_a_${Date.now()}`,
        role: "assistant",
        content: res.answer,
        intent: res.intent,
        language: res.language,
        confidence: res.confidence,
        sources: resolvedSources,
        needs_clarification: res.needs_clarification,
        clarification_options: res.clarification_options,
        followup_suggestions: res.followup_suggestions,
        retrieval_mode: res.retrieval_mode,
        query_category: res.query_category,
        created_at: res.timestamp || new Date().toISOString(),
        is_mock: res.is_mock,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      await loadHistory();
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setChatError("Generation stopped by user.");
      } else {
        setChatError(
          err instanceof Error
            ? err.message
            : "Unable to get a response from Ask ArthaLens right now."
        );
      }
    } finally {
      abortControllerRef.current = null;
      setStreamingText("");
      setSending(false);
    }
  };

  return (
    <DashboardShell
      title="Ask ArthaLens"
      subtitle="Evidence-grounded AI Q&A across your financial documents with citations"
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Chat History Sidebar */}
        <div className="lg:col-span-4 xl:col-span-3 rounded-3xl border border-[#E8E8E8] bg-white p-5 flex flex-col gap-4 h-fit lg:sticky lg:top-24">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#777777]">
              <History className="h-3.5 w-3.5" />
              Chat History
            </div>
            <div className="flex items-center gap-1.5">
              {conversations.length > 0 && (
                <button
                  type="button"
                  onClick={() => setConfirmClearAll(true)}
                  className="rounded-full border border-[#E8E8E8] bg-white px-2.5 py-1.5 text-[11px] font-medium text-[#777777] hover:border-red-300 hover:text-red-600 transition-colors"
                  title="Clear all chat history"
                >
                  Clear
                </button>
              )}
              <button
                type="button"
                onClick={startNewChat}
                className="inline-flex items-center gap-1 rounded-full bg-[#090909] px-3 py-1.5 text-[11px] font-medium text-white hover:bg-[#222222] transition-colors"
              >
                <Plus className="h-3 w-3" />
                New Chat
              </button>
            </div>
          </div>

          {conversations.length > 0 && (
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-[#777777]" />
              <input
                type="text"
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                placeholder="Search history..."
                className="w-full rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] pl-8 pr-3 py-1.5 text-xs text-[#111111] focus:border-[#090909] focus:bg-white focus:outline-none"
              />
            </div>
          )}

          {loadingHistory ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 rounded-2xl bg-[#F7F7F7] animate-pulse" />
              ))}
            </div>
          ) : filteredConversations.length === 0 ? (
            <p className="text-xs text-[#777777] py-4">
              {conversations.length === 0
                ? "No previous conversations yet. Ask a question to start."
                : "No conversations match your search."}
            </p>
          ) : (
            <div className="space-y-1.5 max-h-80 overflow-y-auto pr-1">
              {filteredConversations.map((conv) => {
                const isActive = conv.conversation_id === activeId;
                return (
                  <div
                    key={conv.conversation_id}
                    className={`group flex items-center justify-between gap-1.5 rounded-2xl px-3.5 py-2.5 transition-colors border ${
                      isActive
                        ? "bg-[#090909] text-white border-[#090909]"
                        : "bg-[#F7F7F7] text-[#111111] border-transparent hover:border-[#E8E8E8]"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => selectConversation(conv)}
                      className="flex-1 min-w-0 text-left"
                    >
                      <p className="text-xs font-medium truncate">{conv.title}</p>
                      <p
                        className={`mt-0.5 text-[10px] ${
                          isActive ? "text-white/60" : "text-[#777777]"
                        }`}
                      >
                        {conv.messages.length} msgs • {formatISTWithTz(conv.updated_at)}
                      </p>
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDeleteConv(conv)}
                      aria-label={`Delete ${conv.title}`}
                      className={`rounded-lg p-1 transition-colors shrink-0 ${
                        isActive
                          ? "text-white/60 hover:text-white"
                          : "text-[#888888] hover:text-red-600"
                      }`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Main Chat Area */}
        <div className="lg:col-span-8 xl:col-span-9 rounded-3xl border border-[#E8E8E8] bg-white flex flex-col min-h-[600px] max-h-[75vh]">
          {/* Active Conversation Header & Export Controls */}
          <div className="border-b border-[#E8E8E8] px-5 sm:px-7 py-3.5 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-[#111111] truncate">
                {conversations.find((c) => c.conversation_id === activeId)?.title || "New Conversation"}
              </p>
              <p className="text-[11px] text-[#777777]">
                {messages.length > 0
                  ? `${messages.length} message(s) • Updated ${formatISTWithTz(
                      conversations.find((c) => c.conversation_id === activeId)?.updated_at ||
                        messages[messages.length - 1]?.created_at
                    )}`
                  : "Select a thread or ask a question (IST)"}
              </p>
            </div>

            <div className="relative flex items-center gap-2" ref={exportMenuRef}>
              {exportNotice && (
                <span
                  className={`hidden sm:inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] ${
                    exportNotice.type === "success"
                      ? "border-[#E8E8E8] bg-[#F7F7F7] text-[#111111]"
                      : "border-red-200 bg-red-50 text-red-700"
                  }`}
                >
                  {exportNotice.type === "success" && <CheckCircle2 className="h-3 w-3 text-[#111111]" />}
                  {exportNotice.text}
                </span>
              )}

              <button
                type="button"
                disabled={exporting}
                onClick={() => setExportOpen((o) => !o)}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-white px-3.5 py-1.5 text-xs font-medium text-[#111111] hover:border-[#090909] disabled:opacity-50 transition-colors"
              >
                {exporting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
                <span>{exporting ? "Exporting..." : "Export"}</span>
                <ChevronDown className="h-3 w-3 text-[#777777]" />
              </button>

              {exportOpen && (
                <div className="absolute right-0 top-10 z-30 w-60 rounded-2xl border border-[#E8E8E8] bg-white p-2 shadow-xl">
                  <div className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#777777]">
                    Current Conversation
                  </div>
                  {(["pdf", "txt", "json"] as const).map((fmt) => {
                    const hasSavedCurrent = conversations.some((c) => c.conversation_id === activeId);
                    return (
                      <button
                        key={`single-${fmt}`}
                        type="button"
                        disabled={!hasSavedCurrent}
                        onClick={() => handleExport("single", fmt)}
                        className="w-full text-left rounded-xl px-3 py-2 text-xs text-[#111111] hover:bg-[#F7F7F7] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                      >
                        Export as {fmt.toUpperCase()}
                      </button>
                    );
                  })}

                  <div className="my-1.5 h-px bg-[#E8E8E8]" />

                  <div className="px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#777777]">
                    Export All Conversations
                  </div>
                  {(["pdf", "txt", "json"] as const).map((fmt) => (
                    <button
                      key={`all-${fmt}`}
                      type="button"
                      disabled={conversations.length === 0}
                      onClick={() => handleExport("all", fmt)}
                      className="w-full text-left rounded-xl px-3 py-2 text-xs text-[#111111] hover:bg-[#F7F7F7] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      Export All as {fmt.toUpperCase()}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-5 sm:p-7 space-y-5">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center py-10 max-w-xl mx-auto">
                <div className="h-12 w-12 rounded-2xl bg-[#090909] text-white flex items-center justify-center mb-4">
                  <Sparkles className="h-5 w-5" />
                </div>
                <h2 className="text-lg font-semibold text-[#111111]">
                  Ask anything about your financial records
                </h2>
                <p className="mt-1.5 text-xs text-[#777777]">
                  Every answer includes confidence indicators and source document page citations.
                </p>

                <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full">
                  {suggestedQuestions.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => handleSend(q)}
                      className="text-left rounded-2xl border border-[#E5E5E5] bg-[#F7F7F7] px-4 py-3 text-xs font-medium text-[#171717] hover:border-[#090909] hover:bg-white dark:border-[#333333] dark:bg-[#1F1F1F] dark:text-[#F5F5F5] dark:hover:bg-[#2A2A2A] transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, msgIdx) => {
                const isUser = msg.role === "user";
                const badge = !isUser ? confidenceBadge(msg.confidence) : null;
                const BadgeIcon = badge?.Icon;
                const prevUserQuestion =
                  !isUser
                    ? [...messages.slice(0, msgIdx)].reverse().find((m) => m.role === "user")?.content
                    : undefined;

                return (
                  <div
                    key={msg.id}
                    className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-2xl rounded-3xl px-5 py-4 text-sm leading-relaxed ${
                        isUser
                          ? "bg-[#090909] text-white"
                          : "bg-[#F7F7F7] text-[#171717] border border-[#E5E5E5] dark:bg-[#1F1F1F] dark:text-[#F5F5F5] dark:border-[#333333]"
                      }`}
                    >
                      {isUser ? (
                        <p className="whitespace-pre-wrap text-white">{msg.content}</p>
                      ) : (
                        <AssistantMarkdown content={msg.content} />
                      )}
                      <p
                        className={`mt-1.5 text-[10px] ${
                          isUser ? "text-white/60 text-right" : "text-[#666666] dark:text-[#A3A3A3]"
                        }`}
                      >
                        {formatISTWithTz(msg.created_at)}
                      </p>

                      {!isUser && (
                        <div className="mt-3.5 pt-3 border-t border-[#E5E5E5] dark:border-[#333333] flex flex-wrap items-center gap-2">
                          {badge && BadgeIcon && (
                            <span
                              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${badge.className}`}
                            >
                              <BadgeIcon className="h-3 w-3" />
                              {badge.label}
                            </span>
                          )}

                          {msg.sources?.map((src, idx) => {
                            const docLabel = src.filename || src.document;
                            const pageLabel = src.page_number ?? src.page ?? 1;
                            return (
                              <button
                                key={`${docLabel}-${pageLabel}-${idx}`}
                                type="button"
                                onClick={() => openCitationPdf(src)}
                                title={`Open ${docLabel} at Page ${pageLabel}`}
                                className="inline-flex items-center gap-1 rounded-full border border-[#E5E5E5] bg-white px-2.5 py-0.5 text-[11px] font-medium text-[#374151] hover:border-[#090909] hover:text-[#111111] dark:border-[#404040] dark:bg-[#2A2A2A] dark:text-[#F5F5F5] dark:hover:border-white transition-colors cursor-pointer"
                              >
                                <FileText className="h-3 w-3 text-[#374151] dark:text-[#A3A3A3]" />
                                {docLabel} · Page {pageLabel}
                              </button>
                            );
                          })}

                          {msg.retrieval_mode === "GENERAL_LLM" && (
                            <span className="rounded-full border border-[#E5E5E5] bg-white px-2 py-0.5 text-[10px] font-medium text-[#666666] dark:border-[#404040] dark:bg-[#2A2A2A] dark:text-[#A3A3A3]">
                              General Knowledge
                            </span>
                          )}

                          {msg.retrieval_mode === "HYBRID_REASONING" && (
                            <span className="rounded-full border border-[#E5E5E5] bg-white px-2 py-0.5 text-[10px] font-medium text-[#666666] dark:border-[#404040] dark:bg-[#2A2A2A] dark:text-[#A3A3A3]">
                              Hybrid Analysis
                            </span>
                          )}

                          {msg.language && (
                            <span className="rounded-full border border-[#E5E5E5] bg-white px-2 py-0.5 text-[10px] text-[#666666] dark:border-[#404040] dark:bg-[#2A2A2A] dark:text-[#A3A3A3]">
                              {msg.language}
                            </span>
                          )}

                          {msg.intent && msg.intent !== "UNKNOWN_INTENT" && (
                            <span className="rounded-full border border-[#E5E5E5] bg-white px-2 py-0.5 text-[10px] text-[#666666] dark:border-[#404040] dark:bg-[#2A2A2A] dark:text-[#A3A3A3]">
                              {msg.intent.replace(/_/g, " ")}
                            </span>
                          )}

                          {msg.is_mock && (
                            <span className="rounded-full border border-[#E5E5E5] bg-white px-2 py-0.5 text-[10px] text-[#666666] dark:border-[#404040] dark:bg-[#2A2A2A] dark:text-[#A3A3A3]">
                              Dev Preview
                            </span>
                          )}

                          <div className="ml-auto flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => handleCopyResponse(msg.id, msg.content)}
                              className="inline-flex items-center gap-1 rounded-full border border-[#E5E5E5] bg-white px-2.5 py-0.5 text-[10px] font-medium text-[#374151] hover:border-[#090909] hover:text-[#111111] dark:border-[#404040] dark:bg-[#2A2A2A] dark:text-[#F5F5F5] dark:hover:border-white"
                              title="Copy response"
                            >
                              {copiedMsgId === msg.id ? <Check className="h-2.5 w-2.5" /> : <Copy className="h-2.5 w-2.5" />}
                              {copiedMsgId === msg.id ? "Copied" : "Copy"}
                            </button>
                            {prevUserQuestion && !sending && (
                              <button
                                type="button"
                                onClick={() => handleSend(prevUserQuestion)}
                                className="inline-flex items-center gap-1 rounded-full border border-[#E5E5E5] bg-white px-2.5 py-0.5 text-[10px] font-medium text-[#374151] hover:border-[#090909] hover:text-[#111111] dark:border-[#404040] dark:bg-[#2A2A2A] dark:text-[#F5F5F5] dark:hover:border-white"
                                title="Retry response"
                              >
                                <RotateCcw className="h-2.5 w-2.5" />
                                Retry
                              </button>
                            )}
                          </div>
                        </div>
                      )}

                      {!isUser && msg.needs_clarification && (msg.clarification_options?.length ?? 0) > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {msg.clarification_options?.map((opt) => (
                            <button
                              key={opt}
                              type="button"
                              onClick={() => handleSend(opt)}
                              className="rounded-full border border-[#090909] bg-white px-3 py-1 text-[11px] font-medium text-[#111111] hover:bg-[#090909] hover:text-white dark:border-[#E5E5E5] dark:bg-[#2A2A2A] dark:text-[#F5F5F5] transition-colors"
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      )}

                      {!isUser && !msg.needs_clarification && (msg.followup_suggestions?.length ?? 0) > 0 && (
                        <div className="mt-2.5 flex flex-wrap gap-1.5">
                          {msg.followup_suggestions?.map((fq) => (
                            <button
                              key={fq}
                              type="button"
                              onClick={() => handleSend(fq)}
                              className="rounded-full border border-[#E5E5E5] bg-white px-2.5 py-1 text-[11px] text-[#374151] hover:border-[#090909] hover:text-[#111111] dark:border-[#404040] dark:bg-[#2A2A2A] dark:text-[#F5F5F5] dark:hover:border-white transition-colors"
                            >
                              {fq}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}

            {sending && (
              <div className="flex justify-start">
                <div className="max-w-2xl rounded-3xl border border-[#E5E5E5] bg-[#F7F7F7] px-5 py-3.5 text-sm text-[#171717] dark:border-[#333333] dark:bg-[#1F1F1F] dark:text-[#F5F5F5] space-y-2">
                  {streamingText ? (
                    <AssistantMarkdown content={streamingText} />
                  ) : null}
                  <div className="text-xs text-[#666666] dark:text-[#A3A3A3] flex items-center gap-2">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-[#111111] dark:text-[#F5F5F5]" />
                    <span>{streamingText ? "Streaming grounded answer..." : "ArthaLens is thinking..."}</span>
                  </div>
                </div>
              </div>
            )}
            {!sending &&
              messages.length > 0 &&
              messages[messages.length - 1]?.role === "user" &&
              !chatError && (
                <div className="flex justify-start">
                  <div className="max-w-2xl rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-xs text-amber-900 flex items-center justify-between gap-3">
                    <span>No assistant response was saved for this turn.</span>
                    <button
                      type="button"
                      onClick={() => handleSend(messages[messages.length - 1].content)}
                      className="inline-flex items-center gap-1 rounded-full bg-[#090909] px-3 py-1 text-[11px] font-medium text-white hover:bg-neutral-800 shrink-0"
                    >
                      <RotateCcw className="h-3 w-3" />
                      Retry
                    </button>
                  </div>
                </div>
              )}
            <div ref={bottomRef} />
          </div>

          {/* Input Bar */}
          {chatError && (
            <div className="mx-5 mt-3 flex items-center justify-between gap-2 rounded-xl border border-red-200 bg-red-50 px-3.5 py-2 text-xs text-red-700">
              <span className="inline-flex items-center gap-1.5">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                {chatError}
              </span>
              <div className="flex items-center gap-3 shrink-0">
                {lastQuestion && !sending && (
                  <button
                    type="button"
                    onClick={() => handleSend(lastQuestion)}
                    className="inline-flex items-center gap-1 text-[11px] font-semibold underline"
                  >
                    <RotateCcw className="h-3 w-3" />
                    Retry
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setChatError("")}
                  className="text-[11px] font-medium underline"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="border-t border-[#E8E8E8] p-4 sm:p-5 flex items-center gap-3"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask in English or Hinglish (e.g., Mera FD kab mature hoga?)..."
              className="flex-1 rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] px-4 py-3 text-sm text-[#111111] placeholder:text-[#888888] focus:border-[#090909] focus:bg-white focus:outline-none"
            />
            {sending ? (
              <button
                type="button"
                onClick={handleStopGeneration}
                className="inline-flex items-center gap-2 rounded-2xl border border-[#090909] bg-white px-5 py-3 text-sm font-medium text-[#111111] hover:bg-[#F7F7F7] transition-colors"
                title="Stop generation"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
                <span className="hidden sm:inline">Stop</span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="inline-flex items-center gap-2 rounded-2xl bg-[#090909] px-5 py-3 text-sm font-medium text-white hover:bg-[#222222] disabled:opacity-40 transition-colors"
              >
                <Send className="h-4 w-4" />
                <span className="hidden sm:inline">Ask</span>
              </button>
            )}
          </form>
        </div>
      </div>

      <PdfViewerModal
        open={Boolean(activePdf)}
        documentId={activePdf?.documentId}
        filename={activePdf?.filename || "document.pdf"}
        initialPage={activePdf?.page || 1}
        evidence={activePdf?.evidence}
        onClose={() => setActivePdf(null)}
      />

      {confirmDeleteConv && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-3xl border border-[#E8E8E8] bg-white p-6 shadow-2xl space-y-4">
            <h3 className="text-base font-semibold text-[#111111]">
              Delete Conversation?
            </h3>
            <p className="text-xs text-[#777777] leading-relaxed">
              This will permanently remove <strong className="text-[#111111]">{confirmDeleteConv.title}</strong> and its persisted messages.
            </p>
            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteConv(null)}
                className="rounded-full border border-[#E8E8E8] px-4 py-2 text-xs font-medium text-[#777777] hover:text-[#111111]"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deletingConv}
                onClick={handleDeleteConversation}
                className="rounded-full bg-red-600 px-5 py-2 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deletingConv ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmClearAll && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-3xl border border-[#E8E8E8] bg-white p-6 shadow-2xl space-y-4">
            <h3 className="text-base font-semibold text-[#111111]">
              Clear All Chat History?
            </h3>
            <p className="text-xs text-[#777777] leading-relaxed">
              This will permanently delete all {conversations.length} saved conversation(s) for your account.
            </p>
            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setConfirmClearAll(false)}
                className="rounded-full border border-[#E8E8E8] px-4 py-2 text-xs font-medium text-[#777777] hover:text-[#111111]"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={clearingAll}
                onClick={handleClearAllHistory}
                className="rounded-full bg-red-600 px-5 py-2 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {clearingAll ? "Clearing..." : "Clear History"}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardShell>
  );
}
