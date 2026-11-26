"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  FileText,
  History,
  MessageSquare,
  Plus,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { api } from "@/lib/api";
import { ChatConfidence, ChatConversation, ChatMessage } from "@/lib/types";

const SUGGESTED_QUESTIONS = [
  "Do I have any missing nominees?",
  "What recurring leaks were detected in my statements?",
  "Does my Form 16 match my AIS tax summary?",
  "Which financial documents need immediate review?",
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
      className: "bg-emerald-50 text-emerald-700 border-emerald-200",
      Icon: ShieldCheck,
    };
  }
  if (normalized === "NEEDS_REVIEW" || normalized === "MEDIUM") {
    return {
      label: normalized.replace("_", " "),
      className: "bg-amber-50 text-amber-700 border-amber-200",
      Icon: ShieldAlert,
    };
  }
  return {
    label: normalized || "INFO",
    className: "bg-neutral-100 text-[#111111] border-[#E8E8E8]",
    Icon: ShieldAlert,
  };
}

export default function AskArthaLensPage() {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const loadHistory = useCallback(async () => {
    try {
      const history = await api.getChatHistory();
      setConversations(history);
    } catch {
      // Ignore history load errors
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    setActiveId(createConversationId());
    loadHistory();
  }, [loadHistory]);

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
    setSending(true);

    try {
      const res = await api.sendChatMessage(question, conversationId);
      const assistantMsg: ChatMessage = {
        id: `local_a_${Date.now()}`,
        role: "assistant",
        content: res.answer,
        confidence: res.confidence,
        sources: res.sources,
        created_at: new Date().toISOString(),
        is_mock: res.is_mock,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      await loadHistory();
    } finally {
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
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#777777]">
              <History className="h-3.5 w-3.5" />
              Chat History
            </div>
            <button
              type="button"
              onClick={startNewChat}
              className="inline-flex items-center gap-1 rounded-full bg-[#090909] px-3 py-1.5 text-[11px] font-medium text-white hover:bg-[#222222] transition-colors"
            >
              <Plus className="h-3 w-3" />
              New Chat
            </button>
          </div>

          {loadingHistory ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-12 rounded-2xl bg-[#F7F7F7] animate-pulse" />
              ))}
            </div>
          ) : conversations.length === 0 ? (
            <p className="text-xs text-[#777777] py-4">
              No previous conversations yet. Ask a question to start.
            </p>
          ) : (
            <div className="space-y-1.5 max-h-80 overflow-y-auto pr-1">
              {conversations.map((conv) => {
                const isActive = conv.conversation_id === activeId;
                return (
                  <button
                    key={conv.conversation_id}
                    type="button"
                    onClick={() => selectConversation(conv)}
                    className={`w-full text-left rounded-2xl px-3.5 py-2.5 transition-colors border ${
                      isActive
                        ? "bg-[#090909] text-white border-[#090909]"
                        : "bg-[#F7F7F7] text-[#111111] border-transparent hover:border-[#E8E8E8]"
                    }`}
                  >
                    <p className="text-xs font-medium truncate">{conv.title}</p>
                    <p
                      className={`mt-0.5 text-[10px] ${
                        isActive ? "text-white/60" : "text-[#777777]"
                      }`}
                    >
                      {conv.messages.length} messages
                    </p>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Main Chat Area */}
        <div className="lg:col-span-8 xl:col-span-9 rounded-3xl border border-[#E8E8E8] bg-white flex flex-col min-h-[600px] max-h-[75vh]">
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
                  {SUGGESTED_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => handleSend(q)}
                      className="text-left rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] px-4 py-3 text-xs font-medium text-[#111111] hover:border-[#090909] hover:bg-white transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => {
                const isUser = msg.role === "user";
                const badge = !isUser ? confidenceBadge(msg.confidence) : null;
                const BadgeIcon = badge?.Icon;

                return (
                  <div
                    key={msg.id}
                    className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-2xl rounded-3xl px-5 py-4 text-sm leading-relaxed ${
                        isUser
                          ? "bg-[#090909] text-white"
                          : "bg-[#F7F7F7] text-[#111111] border border-[#E8E8E8]"
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>

                      {!isUser && (
                        <div className="mt-3.5 pt-3 border-t border-[#E8E8E8] flex flex-wrap items-center gap-2">
                          {badge && BadgeIcon && (
                            <span
                              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${badge.className}`}
                            >
                              <BadgeIcon className="h-3 w-3" />
                              {badge.label}
                            </span>
                          )}

                          {msg.sources?.map((src, idx) => (
                            <span
                              key={`${src.document}-${src.page}-${idx}`}
                              className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-2.5 py-0.5 text-[11px] text-[#555555]"
                            >
                              <FileText className="h-3 w-3 text-[#111111]" />
                              {src.document} • p.{src.page}
                            </span>
                          ))}

                          {msg.is_mock && (
                            <span className="rounded-full border border-[#E8E8E8] bg-white px-2 py-0.5 text-[10px] text-[#777777]">
                              Dev Preview
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}

            {sending && (
              <div className="flex justify-start">
                <div className="rounded-3xl border border-[#E8E8E8] bg-[#F7F7F7] px-5 py-3.5 text-xs text-[#777777] flex items-center gap-2">
                  <MessageSquare className="h-3.5 w-3.5 animate-pulse" />
                  Searching financial documents...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input Bar */}
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
              placeholder="Ask about missing nominees, leaks, tax mismatches, or policies..."
              className="flex-1 rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] px-4 py-3 text-sm text-[#111111] placeholder:text-[#888888] focus:border-[#090909] focus:bg-white focus:outline-none"
            />
            <button
              type="submit"
              disabled={!input.trim() || sending}
              className="inline-flex items-center gap-2 rounded-2xl bg-[#090909] px-5 py-3 text-sm font-medium text-white hover:bg-[#222222] disabled:opacity-40 transition-colors"
            >
              <Send className="h-4 w-4" />
              <span className="hidden sm:inline">Ask</span>
            </button>
          </form>
        </div>
      </div>
    </DashboardShell>
  );
}
