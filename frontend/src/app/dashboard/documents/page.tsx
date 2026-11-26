"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  UploadCloud,
  FileText,
  Trash2,
  CheckCircle2,
  ChevronRight,
  Download,
  ExternalLink,
  RefreshCw,
  Search,
} from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { PdfViewerModal } from "@/components/PdfViewerModal";
import { api } from "@/lib/api";
import { DocumentItem, DocumentType } from "@/lib/types";

const PIPELINE_STAGES = [
  "Upload",
  "Extract",
  "Classify",
  "Reconcile",
  "Generate Findings",
];

const DOC_TYPES: DocumentType[] = [
  "Bank Statement",
  "AIS (IT)",
  "Form 16",
  "Insurance Policy",
  "Loan Statement",
  "Fixed Deposit",
  "Investment Statement",
];

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [docTypeHint, setDocTypeHint] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [sortBy, setSortBy] = useState<"newest" | "oldest" | "name">("newest");
  const [uploading, setUploading] = useState(false);
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteDoc, setConfirmDeleteDoc] = useState<DocumentItem | null>(null);
  const [pdfPreviewDoc, setPdfPreviewDoc] = useState<DocumentItem | null>(null);
  const [activeStage, setActiveStage] = useState<number>(-1);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const loadDocs = useCallback(async () => {
    try {
      const list = await api.listDocuments();
      setDocs(list);
      setSelectedDoc((prev) => {
        if (!prev) return list[0] ?? null;
        return list.find((d) => d.id === prev.id) ?? list[0] ?? null;
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    }
  }, []);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  const filteredDocs = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const list = docs.filter((d) => {
      if (typeFilter !== "ALL" && d.doc_type !== typeFilter) return false;
      if (q) {
        const hay = `${d.filename} ${d.doc_type} ${d.summary}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    return [...list].sort((a, b) => {
      if (sortBy === "name") return a.filename.localeCompare(b.filename);
      const da = new Date(a.uploaded_at || 0).getTime();
      const db = new Date(b.uploaded_at || 0).getTime();
      return sortBy === "oldest" ? da - db : db - da;
    });
  }, [docs, searchQuery, typeFilter, sortBy]);

  const handleFiles = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    setError("");
    setStatusMessage("");
    setUploading(true);
    setActiveStage(0);
    setUploadProgress(20);

    try {
      const stageTimer = setInterval(() => {
        setActiveStage((prev) => (prev < 3 ? prev + 1 : prev));
        setUploadProgress((prev) => (prev < 85 ? prev + 18 : prev));
      }, 300);

      const res = await api.uploadDocuments(
        files,
        docTypeHint ? (docTypeHint as DocumentType) : undefined
      );

      clearInterval(stageTimer);
      setActiveStage(4);
      setUploadProgress(100);
      setStatusMessage(
        `Processed ${res.uploaded.length} PDF(s) and generated ${res.findings_generated} new finding(s).`
      );
      await loadDocs();
      if (res.uploaded[0]) {
        setSelectedDoc(res.uploaded[0]);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setActiveStage(-1);
      setUploadProgress(0);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!confirmDeleteDoc) return;
    const id = confirmDeleteDoc.id;
    setDeletingId(id);
    setError("");
    setStatusMessage("");
    try {
      await api.deleteDocument(id);
      setStatusMessage(`Deleted "${confirmDeleteDoc.filename}" and recomputed findings.`);
      setConfirmDeleteDoc(null);
      if (selectedDoc?.id === id) setSelectedDoc(null);
      await loadDocs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  };

  const handleDownloadPdf = async (doc: DocumentItem) => {
    setError("");
    try {
      const blob = await api.fetchDocumentFile(doc.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = doc.filename || "document.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to download PDF");
    }
  };

  const handleReprocess = async (doc: DocumentItem) => {
    setReprocessingId(doc.id);
    setError("");
    setStatusMessage("");
    try {
      await api.reprocessDocument(doc.id);
      setStatusMessage(`Reprocessed "${doc.filename}" and updated entities.`);
      await loadDocs();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reprocess failed");
    } finally {
      setReprocessingId(null);
    }
  };

  return (
    <DashboardShell
      title="Documents"
      subtitle="Upload PDFs for text extraction, classification, and cross-document reconciliation"
      hasDemoData={docs.some((d) => d.is_demo)}
    >
      <div className="space-y-6">
        {/* Processing Pipeline */}
        <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#777777] mb-4">
            Document Processing Pipeline
          </p>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            {PIPELINE_STAGES.map((stage, idx) => {
              const isDone = activeStage >= idx;
              return (
                <React.Fragment key={stage}>
                  <div
                    className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-medium border transition-colors ${
                      isDone
                        ? "bg-[#090909] text-white border-[#090909]"
                        : "bg-[#F7F7F7] text-[#777777] border-[#E8E8E8]"
                    }`}
                  >
                    {isDone && <CheckCircle2 className="h-3.5 w-3.5" />}
                    {stage}
                  </div>
                  {idx < PIPELINE_STAGES.length - 1 && (
                    <ChevronRight className="h-4 w-4 text-[#CCCCCC]" />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Upload Zone */}
        <div className="rounded-3xl border border-[#E8E8E8] bg-white p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
            <div>
              <h2 className="text-base font-semibold text-[#111111]">
                Upload Financial PDFs
              </h2>
              <p className="text-xs text-[#777777]">
                Supports Bank Statements, AIS, Form 16, Insurance Policies, Loans, FDs &amp; Investments.
              </p>
            </div>
            <select
              value={docTypeHint}
              onChange={(e) => setDocTypeHint(e.target.value)}
              className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] px-3.5 py-2 text-xs font-medium text-[#111111] focus:border-[#090909] focus:outline-none"
            >
              <option value="">Auto-classify document type</option>
              {DOC_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragActive(false);
              handleFiles(e.dataTransfer.files);
            }}
            onClick={() => inputRef.current?.click()}
            className={`cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
              dragActive
                ? "border-[#090909] bg-[#F7F7F7]"
                : "border-[#E8E8E8] bg-[#F7F7F7]/50 hover:border-[#111111]/40"
            }`}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,application/pdf"
              multiple
              onChange={(e) => handleFiles(e.target.files)}
              className="hidden"
            />
            <UploadCloud className="mx-auto h-8 w-8 text-[#111111]" />
            <p className="mt-3 text-sm font-medium text-[#111111]">
              Drag and drop PDF files here, or click to browse
            </p>
            <p className="mt-1 text-xs text-[#777777]">
              Multiple PDF upload supported • Real PyMuPDF text &amp; entity extraction
            </p>

            {uploading && (
              <div className="mx-auto mt-5 max-w-xs">
                <div className="h-1.5 w-full rounded-full bg-[#E8E8E8] overflow-hidden">
                  <div
                    className="h-full bg-[#090909] transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="mt-1.5 text-[11px] text-[#777777]">
                  Processing... {uploadProgress}%
                </p>
              </div>
            )}
          </div>

          {statusMessage && (
            <div className="mt-4 rounded-xl border border-green-200 bg-green-50 px-4 py-2.5 text-xs text-green-800">
              {statusMessage}
            </div>
          )}
          {error && (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-700">
              {error}
            </div>
          )}
        </div>

        {/* Document List & Preview */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 rounded-3xl border border-[#E8E8E8] bg-white p-5 space-y-3">
            <div className="px-1 pb-3 border-b border-[#E8E8E8] space-y-2.5">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-[#111111]">
                  Uploaded Documents ({filteredDocs.length}/{docs.length})
                </h3>
                <button
                  type="button"
                  onClick={loadDocs}
                  className="inline-flex items-center gap-1 text-[11px] text-[#777777] hover:text-[#111111]"
                >
                  <RefreshCw className="h-3 w-3" />
                  Refresh
                </button>
              </div>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-[#777777]" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search filename or type..."
                  className="w-full rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] pl-8 pr-3 py-1.5 text-xs text-[#111111] focus:border-[#090909] focus:bg-white focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  aria-label="Filter by document type"
                  className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] px-2.5 py-1.5 text-[11px] text-[#111111] focus:border-[#090909] focus:outline-none"
                >
                  <option value="ALL">All Types</option>
                  {DOC_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as "newest" | "oldest" | "name")}
                  aria-label="Sort documents"
                  className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] px-2.5 py-1.5 text-[11px] text-[#111111] focus:border-[#090909] focus:outline-none"
                >
                  <option value="newest">Newest First</option>
                  <option value="oldest">Oldest First</option>
                  <option value="name">Name (A-Z)</option>
                </select>
              </div>
            </div>
            {filteredDocs.length === 0 ? (
              <p className="py-6 text-center text-xs text-[#777777]">
                No documents match your search or filter.
              </p>
            ) : filteredDocs.map((doc) => {
              const active = selectedDoc?.id === doc.id;
              return (
                <div
                  key={doc.id}
                  onClick={() => setSelectedDoc(doc)}
                  className={`cursor-pointer rounded-2xl border p-4 transition-colors flex items-start justify-between gap-3 ${
                    active
                      ? "border-[#090909] bg-[#F7F7F7]"
                      : "border-[#E8E8E8] bg-white hover:bg-[#F7F7F7]/60"
                  }`}
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#090909] text-white">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-[#111111] truncate">
                        {doc.filename}
                      </p>
                      <p className="mt-0.5 text-[11px] text-[#777777]">
                        {doc.doc_type} • {doc.page_count} pg • {doc.status}
                        {doc.is_demo ? " • Demo" : ""}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setConfirmDeleteDoc(doc);
                    }}
                    className="rounded-lg p-1.5 text-[#777777] hover:text-red-600"
                    aria-label={`Delete ${doc.filename}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })}
          </div>

          {/* Document Preview & Extracted Entities */}
          <div className="lg:col-span-7 rounded-3xl border border-[#E8E8E8] bg-white p-6">
            {selectedDoc ? (
              <div className="space-y-6">
                <div className="border-b border-[#E8E8E8] pb-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-[#090909] px-3 py-1 text-[11px] font-medium text-white">
                        {selectedDoc.doc_type}
                      </span>
                      <span
                        className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${
                          selectedDoc.status === "Processed"
                            ? "border-green-200 bg-green-50 text-green-700"
                            : selectedDoc.status === "Error"
                            ? "border-red-200 bg-red-50 text-red-700"
                            : "border-amber-200 bg-amber-50 text-amber-700"
                        }`}
                      >
                        {selectedDoc.status}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => setPdfPreviewDoc(selectedDoc)}
                        className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-3 py-1.5 text-[11px] font-medium text-[#111111] hover:border-[#090909]"
                      >
                        <ExternalLink className="h-3 w-3" />
                        Open Original PDF
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDownloadPdf(selectedDoc)}
                        className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-3 py-1.5 text-[11px] font-medium text-[#111111] hover:border-[#090909]"
                      >
                        <Download className="h-3 w-3" />
                        Download
                      </button>
                      <button
                        type="button"
                        disabled={reprocessingId === selectedDoc.id}
                        onClick={() => handleReprocess(selectedDoc)}
                        className="inline-flex items-center gap-1 rounded-full border border-[#E8E8E8] bg-white px-3 py-1.5 text-[11px] font-medium text-[#111111] hover:border-[#090909] disabled:opacity-50"
                      >
                        <RefreshCw
                          className={`h-3 w-3 ${reprocessingId === selectedDoc.id ? "animate-spin" : ""}`}
                        />
                        {reprocessingId === selectedDoc.id ? "Reprocessing..." : "Reprocess"}
                      </button>
                    </div>
                  </div>
                  <h3 className="mt-3 text-lg font-semibold text-[#111111]">
                    {selectedDoc.filename}
                  </h3>
                  <p className="mt-1 text-xs text-[#777777]">
                    {selectedDoc.summary}
                  </p>
                </div>

                {/* Extracted Entities */}
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-[#777777] mb-3">
                    Extracted Entities
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {selectedDoc.extracted_entities.map((ent, idx) => (
                      <div
                        key={`${ent.label}-${idx}`}
                        className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-2 text-xs"
                      >
                        <span className="text-[#777777]">{ent.label}: </span>
                        <span className="font-semibold text-[#111111]">
                          {ent.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Page Text Preview */}
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-[#777777] mb-3">
                    Extracted Text Preview
                  </p>
                  <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                    {selectedDoc.pages.map((p) => (
                      <div
                        key={p.page}
                        className="rounded-2xl border border-[#E8E8E8] bg-[#F7F7F7] p-4"
                      >
                        <p className="text-[11px] font-semibold text-[#777777] mb-2">
                          Page {p.page}
                        </p>
                        <pre className="whitespace-pre-wrap font-mono text-xs text-[#111111] leading-relaxed">
                          {p.text || "(No selectable text found on this page)"}
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-[#777777]">
                Select a document to inspect extracted entities and page text.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {confirmDeleteDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-3xl border border-[#E8E8E8] bg-white p-6 shadow-2xl space-y-4">
            <h3 className="text-base font-semibold text-[#111111]">
              Delete Document?
            </h3>
            <p className="text-xs text-[#777777] leading-relaxed">
              This will permanently remove <strong className="text-[#111111]">{confirmDeleteDoc.filename}</strong>, its indexed text chunks, and recompute your cross-document findings.
            </p>
            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteDoc(null)}
                className="rounded-full border border-[#E8E8E8] px-4 py-2 text-xs font-medium text-[#777777] hover:text-[#111111]"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deletingId === confirmDeleteDoc.id}
                onClick={handleDeleteConfirm}
                className="rounded-full bg-red-600 px-5 py-2 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deletingId === confirmDeleteDoc.id ? "Deleting..." : "Delete Document"}
              </button>
            </div>
          </div>
        </div>
      )}

      <PdfViewerModal
        open={Boolean(pdfPreviewDoc)}
        documentId={pdfPreviewDoc?.id}
        filename={pdfPreviewDoc?.filename || "document.pdf"}
        initialPage={1}
        onClose={() => setPdfPreviewDoc(null)}
      />
    </DashboardShell>
  );
}
