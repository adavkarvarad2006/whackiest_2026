import { ChatConversation, ChatMessage, ChatResponse } from "./types";

const MOCK_HISTORY_KEY = "arthalens_mock_chat_history";

function readMockConversations(): ChatConversation[] {
  if (typeof window === "undefined") return [];
  const raw = localStorage.getItem(MOCK_HISTORY_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as ChatConversation[];
  } catch {
    return [];
  }
}

function writeMockConversations(conversations: ChatConversation[]): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(MOCK_HISTORY_KEY, JSON.stringify(conversations));
}

function buildMockAnswer(question: string): Omit<ChatResponse, "conversation_id"> {
  const q = question.toLowerCase();

  if (q.includes("nominee")) {
    return {
      answer:
        "Your uploaded insurance policy does not contain recorded nominee details, and your PPF/term records show one partial nominee entry that needs verification.",
      confidence: "NEEDS_REVIEW",
      sources: [
        { document: "insurance_policy.pdf", page: 2 },
        { document: "hdfc_bank_statement.pdf", page: 4 },
      ],
      is_mock: true,
    };
  }

  if (q.includes("leak") || q.includes("recurring") || q.includes("subscription")) {
    return {
      answer:
        "Two recurring debit mandates totaling ₹14,400/year were detected in your recent bank statements without matching active policy or investment receipts.",
      confidence: "HIGH",
      sources: [
        { document: "hdfc_bank_statement.pdf", page: 3 },
        { document: "ais_summary_fy25.pdf", page: 1 },
      ],
      is_mock: true,
    };
  }

  if (q.includes("tax") || q.includes("form 16") || q.includes("ais")) {
    return {
      answer:
        "Your Form 16 salary TDS matches your AIS summary, though interest income from one fixed deposit appears in AIS without a corresponding bank interest certificate.",
      confidence: "MEDIUM",
      sources: [
        { document: "form16_fy25.pdf", page: 1 },
        { document: "ais_summary_fy25.pdf", page: 2 },
      ],
      is_mock: true,
    };
  }

  return {
    answer:
      "Based on your currently indexed financial documents, your mapped assets, nominee coverage, and open findings are synchronized. Connect the live RAG backend (`POST /api/chat`) for real-time semantic retrieval across newly uploaded PDFs.",
    confidence: "NEEDS_REVIEW",
    sources: [{ document: "arthalens_portfolio_summary.pdf", page: 1 }],
    is_mock: true,
  };
}

export const mockChatService = {
  async sendMessage(question: string, conversationId: string): Promise<ChatResponse> {
    const reply = buildMockAnswer(question);
    const now = new Date().toISOString();

    const userMsg: ChatMessage = {
      id: `u_${Date.now()}`,
      role: "user",
      content: question,
      created_at: now,
    };

    const assistantMsg: ChatMessage = {
      id: `a_${Date.now() + 1}`,
      role: "assistant",
      content: reply.answer,
      confidence: reply.confidence,
      sources: reply.sources,
      created_at: now,
      is_mock: true,
    };

    const existing = readMockConversations();
    const idx = existing.findIndex((c) => c.conversation_id === conversationId);
    if (idx >= 0) {
      existing[idx] = {
        ...existing[idx],
        updated_at: now,
        messages: [...existing[idx].messages, userMsg, assistantMsg],
      };
    } else {
      existing.unshift({
        conversation_id: conversationId,
        title: question.slice(0, 48) + (question.length > 48 ? "…" : ""),
        updated_at: now,
        messages: [userMsg, assistantMsg],
      });
    }
    writeMockConversations(existing);

    return {
      ...reply,
      conversation_id: conversationId,
    };
  },

  async getHistory(conversationId?: string): Promise<ChatConversation[]> {
    const all = readMockConversations();
    if (conversationId) {
      return all.filter((c) => c.conversation_id === conversationId);
    }
    return all;
  },
};
