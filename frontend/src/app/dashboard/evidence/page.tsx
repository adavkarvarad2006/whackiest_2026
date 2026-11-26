"use client";

import React, { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { api } from "@/lib/api";
import { FindingItem } from "@/lib/types";

export default function EvidencePage() {
  const [findings, setFindings] = useState<FindingItem[]>([]);

  useEffect(() => {
    api.listFindings().then(setFindings).catch(() => {});
  }, []);

  return (
    <DashboardShell
      title="Evidence"
      subtitle="Exact document citations, page numbers, and extracted text snippets"
      hasDemoData={findings.some((f) => f.is_demo)}
    >
      <div className="space-y-4">
        {findings.map((f) => (
          <div
            key={f.id}
            className="rounded-3xl border border-[#E8E8E8] bg-white p-6 space-y-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold text-[#111111]">{f.title}</h3>
              <span className="rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#111111]">
                {f.evidence.fact_label}
              </span>
            </div>

            <div className="flex items-center gap-2 text-xs text-[#777777]">
              <FileText className="h-3.5 w-3.5" />
              <span>{f.evidence.source_document}</span>
              <span>•</span>
              <span>Page {f.evidence.page_number}</span>
            </div>

            <pre className="whitespace-pre-wrap rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 font-mono text-xs text-[#111111]">
              {f.evidence.extracted_text}
            </pre>

            <p className="text-xs text-[#777777]">{f.evidence.why_flagged}</p>
          </div>
        ))}
      </div>
    </DashboardShell>
  );
}
