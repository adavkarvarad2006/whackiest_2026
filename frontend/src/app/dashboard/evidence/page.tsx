"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowUpRight, ExternalLink, FileText, RefreshCw, Search, Wrench } from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { EvidenceDrawer } from "@/components/EvidenceDrawer";
import { FixWizardModal } from "@/components/FixWizardModal";
import { PdfViewerModal } from "@/components/PdfViewerModal";
import { api } from "@/lib/api";
import { FindingItem } from "@/lib/types";

export default function EvidencePage() {
  const [findings, setFindings] = useState<FindingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [labelFilter, setLabelFilter] = useState<"ALL" | "Confirmed Fact" | "Needs Verification">("ALL");
  const [selectedFinding, setSelectedFinding] = useState<FindingItem | null>(null);
  const [fixFinding, setFixFinding] = useState<FindingItem | null>(null);
  const [pdfPreview, setPdfPreview] = useState<{
    documentId: string | number | null | undefined;
    filename: string;
    page: number;
    evidence?: string;
  } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await api.listFindings();
      setFindings(list);
    } catch {
      // keep existing state cleanly
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openOriginalPdf = async (f: FindingItem) => {
    const filename = f.evidence?.source_document || "Uploaded Document";
    const page = f.evidence?.page_number ?? 1;
    let docId: string | undefined = f.evidence?.source_document_id;
    if (!docId && filename) {
      try {
        const docs = await api.listDocuments();
        const match = docs.find((d) => d.filename.toLowerCase() === filename.toLowerCase());
        if (match) docId = match.id;
      } catch {
        // handled by modal
      }
    }
    setPdfPreview({
      documentId: docId,
      filename,
      page,
      evidence: f.evidence?.extracted_text,
    });
  };

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return findings.filter((f) => {
      const lbl = f.evidence?.fact_label || "Needs Verification";
      if (labelFilter !== "ALL" && lbl !== labelFilter) return false;
      if (q) {
        const hay = `${f.title} ${f.evidence?.source_document || ""} ${f.evidence?.extracted_text || ""} ${f.evidence?.why_flagged || ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [findings, labelFilter, searchQuery]);

  return (
    <DashboardShell
      title="Evidence"
      subtitle="Exact document citations, page numbers, and extracted text snippets"
      hasDemoData={findings.some((f) => f.is_demo)}
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {(["ALL", "Confirmed Fact", "Needs Verification"] as const).map((lbl) => (
              <button
                key={lbl}
                type="button"
                onClick={() => setLabelFilter(lbl)}
                className={`rounded-full px-3.5 py-1.5 text-xs font-medium border transition-colors ${
                  labelFilter === lbl
                    ? "bg-[#090909] text-white border-[#090909]"
                    : "bg-white text-[#777777] border-[#E8E8E8] hover:text-[#111111]"
                }`}
              >
                {lbl === "ALL" ? "All Evidence" : lbl}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-[#777777]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search snippets or PDFs..."
                className="w-48 sm:w-56 rounded-full border border-[#E8E8E8] bg-white pl-8 pr-3 py-1.5 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
              />
            </div>
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-3.5 py-1.5 text-xs font-medium text-[#111111] hover:border-[#090909]"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        </div>

        {filtered.length === 0 ? (
          <div className="rounded-3xl border border-[#E8E8E8] bg-white p-8 text-xs text-[#777777]">
            No evidence records match your filter.
          </div>
        ) : (
          filtered.map((f) => (
            <div
              key={f.id}
              className="rounded-3xl border border-[#E8E8E8] bg-white p-6 space-y-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-[#111111]">{f.title}</h3>
                <span className="rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#111111]">
                  {f.evidence?.fact_label || "Needs Verification"}
                </span>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-xs text-[#777777]">
                  <FileText className="h-3.5 w-3.5" />
                  <span>{f.evidence?.source_document || "Uploaded Document"}</span>
                  <span>•</span>
                  <span>Page {f.evidence?.page_number ?? 1}</span>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => openOriginalPdf(f)}
                    className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-3 py-1 text-[11px] font-medium text-[#111111] hover:border-[#090909]"
                  >
                    Open PDF (p.{f.evidence?.page_number ?? 1})
                    <ExternalLink className="h-3 w-3" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedFinding(f)}
                    className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1 text-[11px] font-medium text-[#111111] hover:border-[#090909]"
                  >
                    Inspect
                    <ArrowUpRight className="h-3 w-3" />
                  </button>
                  {f.status !== "Resolved" && f.status !== "Dismissed" && (
                    <button
                      type="button"
                      onClick={() => setFixFinding(f)}
                      className="inline-flex items-center gap-1 rounded-full bg-[#090909] px-3 py-1 text-[11px] font-medium text-white hover:bg-neutral-800"
                    >
                      <Wrench className="h-3 w-3" />
                      Fix
                    </button>
                  )}
                </div>
              </div>

              <pre className="whitespace-pre-wrap rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 font-mono text-xs text-[#111111]">
                {f.evidence?.extracted_text || "No extracted snippet available."}
              </pre>

              <p className="text-xs text-[#777777]">{f.evidence?.why_flagged || ""}</p>
            </div>
          ))
        )}
      </div>

      <EvidenceDrawer
        finding={selectedFinding}
        onClose={() => setSelectedFinding(null)}
        onOpenFix={(item) => {
          setSelectedFinding(null);
          setFixFinding(item);
        }}
        onUpdated={load}
      />

      <FixWizardModal
        finding={fixFinding}
        onClose={() => setFixFinding(null)}
        onCompleted={load}
      />

      <PdfViewerModal
        open={Boolean(pdfPreview)}
        documentId={pdfPreview?.documentId}
        filename={pdfPreview?.filename || "document.pdf"}
        initialPage={pdfPreview?.page || 1}
        evidence={pdfPreview?.evidence}
        onClose={() => setPdfPreview(null)}
      />
    </DashboardShell>
  );
}
