"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ThumbsDown,
  Wrench,
  ExternalLink,
} from "lucide-react";
import { FindingItem } from "@/lib/types";
import { api } from "@/lib/api";
import { formatISTWithTz } from "@/lib/dateUtils";
import { PdfViewerModal } from "./PdfViewerModal";

interface EvidenceDrawerProps {
  finding: FindingItem | null;
  onClose: () => void;
  onOpenFix: (finding: FindingItem) => void;
  onUpdated: () => void;
}

export function EvidenceDrawer({
  finding,
  onClose,
  onOpenFix,
  onUpdated,
}: EvidenceDrawerProps) {
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [feedbackError, setFeedbackError] = useState("");
  const [pdfPreview, setPdfPreview] = useState<{
    documentId: string | number | null | undefined;
    filename: string;
    page: number;
    evidence?: string;
  } | null>(null);

  const openOriginalPdf = async (
    docIdRaw: string | null | undefined,
    filename: string,
    page: number,
    snippet?: string | null
  ) => {
    let docId = docIdRaw;
    if (!docId && filename) {
      try {
        const docs = await api.listDocuments();
        const m = docs.find((d) => d.filename.toLowerCase() === filename.toLowerCase());
        if (m) docId = m.id;
      } catch {
        // handled cleanly by PdfViewerModal
      }
    }
    setPdfPreview({
      documentId: docId,
      filename: filename || "document.pdf",
      page: page || 1,
      evidence: snippet || undefined,
    });
  };

  const handleFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!finding) return;
    setSubmitting(true);
    setFeedbackError("");
    try {
      await api.reportWrong(
        finding.id,
        reason.trim() || "Flagged incorrectly or already resolved"
      );
      setFeedbackOpen(false);
      setReason("");
      onUpdated();
      onClose();
    } catch (err: unknown) {
      setFeedbackError(err instanceof Error ? err.message : "Could not submit feedback.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
    <AnimatePresence>
      {finding && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-[2px]"
          />

          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 260 }}
            className="relative z-10 w-full max-w-lg bg-white h-full overflow-y-auto border-l border-[#E8E8E8] shadow-2xl flex flex-col justify-between"
          >
            <div className="p-6 sm:p-8 space-y-6">
              {/* Header */}
              <div className="flex items-start justify-between gap-4 border-b border-[#E8E8E8] pb-5">
                <div>
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                        finding.severity === "High"
                          ? "bg-red-50 text-red-700 border border-red-200"
                          : finding.severity === "Medium"
                          ? "bg-amber-50 text-amber-700 border border-amber-200"
                          : "bg-neutral-100 text-[#111111] border border-[#E8E8E8]"
                      }`}
                    >
                      {finding.severity} Severity
                    </span>
                    <span className="rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-2.5 py-0.5 text-[11px] font-medium text-[#111111] tabular-nums">
                      {finding.confidence}% Confidence
                    </span>
                    {finding.is_demo && (
                      <span className="rounded-full border border-[#E8E8E8] bg-white px-2.5 py-0.5 text-[11px] text-[#777777]">
                        Demo Data
                      </span>
                    )}
                  </div>
                  <h2 className="text-xl font-semibold tracking-tight text-[#111111]">
                    {finding.title}
                  </h2>
                  {finding.created_at && (
                    <p className="mt-1 text-[11px] text-[#777777]">
                      Recorded: {formatISTWithTz(finding.created_at)}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg border border-[#E8E8E8] p-2 text-[#777777] hover:text-[#111111]"
                  aria-label="Close evidence drawer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              {/* Confirmed Fact vs Possible Finding Banner */}
              <div
                className={`rounded-2xl border p-4 flex items-start gap-3 ${
                  finding.evidence?.is_confirmed_fact
                    ? "border-[#111111]/20 bg-[#F7F7F7]"
                    : "border-amber-200 bg-amber-50/50"
                }`}
              >
                {finding.evidence?.is_confirmed_fact ? (
                  <CheckCircle2 className="h-4 w-4 text-[#111111] mt-0.5 shrink-0" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                )}
                <div>
                  <p className="text-xs font-semibold text-[#111111]">
                    {finding.evidence?.fact_label || "Needs Verification"}
                  </p>
                  <p className="mt-1 text-xs text-[#777777] leading-relaxed">
                    {finding.evidence?.why_flagged || "Review supporting source evidence."}
                  </p>
                </div>
              </div>

              {/* Primary Source Evidence */}
              <div className="space-y-2.5">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                  Primary Source Evidence
                </p>
                <div className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 space-y-2">
                  <div className="flex items-center justify-between text-xs gap-2">
                    <span className="inline-flex items-center gap-1.5 font-medium text-[#111111]">
                      <FileText className="h-3.5 w-3.5" />
                      {finding.evidence?.source_document || "Uploaded Document"}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-[#777777] tabular-nums">
                        Page {finding.evidence?.page_number ?? 1}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          openOriginalPdf(
                            finding.evidence?.source_document_id,
                            finding.evidence?.source_document || "document.pdf",
                            finding.evidence?.page_number ?? 1,
                            finding.evidence?.extracted_text
                          )
                        }
                        className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-2.5 py-0.5 text-[11px] font-medium text-[#111111] hover:border-[#090909]"
                      >
                        Open PDF
                        <ExternalLink className="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                  <pre className="whitespace-pre-wrap font-mono text-xs text-[#111111] bg-white border border-[#E8E8E8] rounded-xl p-3 leading-relaxed">
                    {finding.evidence?.extracted_text || "No extracted snippet available."}
                  </pre>
                </div>
              </div>

              {/* Cross-Document Matching Evidence */}
              {finding.evidence?.matching_document && (
                <div className="space-y-2.5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-[#777777]">
                    Cross-Checked Document
                  </p>
                  <div className="rounded-2xl border border-[#E8E8E8] bg-white p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs gap-2">
                      <span className="inline-flex items-center gap-1.5 font-medium text-[#111111]">
                        <FileText className="h-3.5 w-3.5" />
                        {finding.evidence.matching_document}
                      </span>
                      <div className="flex items-center gap-2">
                        {finding.evidence.matching_page && (
                          <span className="text-[#777777] tabular-nums">
                            Page {finding.evidence.matching_page}
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() =>
                            openOriginalPdf(
                              finding.evidence?.matching_document_id,
                              finding.evidence?.matching_document || "document.pdf",
                              finding.evidence?.matching_page ?? 1,
                              finding.evidence?.matching_text
                            )
                          }
                          className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-[#F7F7F7] px-2.5 py-0.5 text-[11px] font-medium text-[#111111] hover:border-[#090909]"
                        >
                          Open PDF
                          <ExternalLink className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                    <p className="text-xs text-[#777777] leading-relaxed">
                      {finding.evidence.matching_text}
                    </p>
                  </div>
                </div>
              )}

              {/* Resolution Evidence if resolved */}
              {finding.status === "Resolved" && finding.resolution_evidence && (
                <div className="rounded-2xl border border-green-200 bg-green-50 p-4">
                  <p className="text-xs font-semibold text-green-800">
                    Resolved with User Verification
                  </p>
                  <p className="mt-1 text-xs text-green-700">
                    {finding.resolution_evidence}
                  </p>
                  {finding.resolved_at && (
                    <p className="mt-1 text-[11px] text-green-700/80">
                      Completed: {formatISTWithTz(finding.resolved_at)}
                    </p>
                  )}
                </div>
              )}

              {/* "This is wrong" feedback */}
              {feedbackOpen && (
                <form
                  onSubmit={handleFeedback}
                  className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4 space-y-3"
                >
                  <label className="block text-xs font-medium text-[#111111]">
                    Why is this finding incorrect?
                  </label>
                  <textarea
                    rows={2}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="e.g., Nominee was added last month on an updated endorsement..."
                    className="w-full rounded-xl border border-[#E8E8E8] bg-white p-2.5 text-xs text-[#111111] focus:border-[#090909] focus:outline-none"
                  />
                  {feedbackError && (
                    <p className="text-xs text-red-600">{feedbackError}</p>
                  )}
                  <div className="flex items-center gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => setFeedbackOpen(false)}
                      className="rounded-lg px-3 py-1.5 text-xs text-[#777777] hover:text-[#111111]"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={submitting}
                      className="rounded-lg bg-[#090909] px-3.5 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                    >
                      {submitting ? "Submitting..." : "Dismiss Finding"}
                    </button>
                  </div>
                </form>
              )}
            </div>

            {/* Footer actions */}
            <div className="border-t border-[#E8E8E8] bg-[#F7F7F7] px-6 py-4 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => setFeedbackOpen((v) => !v)}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#E8E8E8] bg-white px-4 py-2 text-xs font-medium text-[#777777] hover:text-[#111111] transition-colors"
              >
                <ThumbsDown className="h-3.5 w-3.5" />
                This is wrong
              </button>

              {finding.status !== "Resolved" && (
                <button
                  type="button"
                  onClick={() => onOpenFix(finding)}
                  className="inline-flex items-center gap-2 rounded-full bg-[#090909] px-5 py-2.5 text-xs font-medium text-white hover:bg-neutral-800 transition-colors"
                >
                  <Wrench className="h-3.5 w-3.5" />
                  Open Fix Wizard
                </button>
              )}
            </div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>

    <PdfViewerModal
      open={Boolean(pdfPreview)}
      documentId={pdfPreview?.documentId}
      filename={pdfPreview?.filename || "document.pdf"}
      initialPage={pdfPreview?.page || 1}
      evidence={pdfPreview?.evidence}
      onClose={() => setPdfPreview(null)}
    />
    </>
  );
}
