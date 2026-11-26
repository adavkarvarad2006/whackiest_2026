"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Maximize2,
  Minimize2,
  RotateCw,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { api } from "@/lib/api";
import {
  computeFitScale,
  computeHighlightRect,
  detectUpsideDownCorrection,
  FitMode,
  normalizeDegrees,
  TextItemLike,
} from "@/lib/pdfGeometry";

interface PdfViewerModalProps {
  open: boolean;
  documentId: string | number | null | undefined;
  filename: string;
  initialPage?: number;
  evidence?: string;
  onClose: () => void;
}

export function PdfViewerModal({
  open,
  documentId,
  filename,
  initialPage = 1,
  evidence,
  onClose,
}: PdfViewerModalProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const highlightRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);
  const autoCorrectionCacheRef = useRef<Map<number, number>>(new Map());
  const activeScaleRef = useRef<number>(1.0);

  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [zoom, setZoom] = useState(1.0);
  const [displayScale, setDisplayScale] = useState(1.0);
  const [fitMode, setFitMode] = useState<FitMode>("width");
  const [manualRotations, setManualRotations] = useState<Record<number, number>>({});
  const [effectiveRotation, setEffectiveRotation] = useState(0);
  const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Keyboard shortcuts: Escape to close, Left/Right arrows to change page
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") setCurrentPage((p) => Math.max(1, p - 1));
      if (e.key === "ArrowRight" && numPages > 0) setCurrentPage((p) => Math.min(numPages, p + 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose, numPages]);

  // Fetch authenticated PDF binary & initialize PDF.js
  useEffect(() => {
    if (!open) return;
    if (!documentId) {
      setPdfDoc(null);
      setPdfBlob(null);
      setError("Original document reference is unavailable for this citation.");
      return;
    }

    let cancelled = false;
    let loadedDoc: PDFDocumentProxy | null = null;
    let loadingTaskRef: { destroy: () => Promise<void> } | null = null;

    async function loadPdf() {
      setLoading(true);
      setError(null);
      setPdfDoc(null);
      setPdfBlob(null);
      setManualRotations({});
      setPageSize(null);
      autoCorrectionCacheRef.current.clear();

      try {
        const blob = await api.fetchDocumentFile(documentId!);
        if (cancelled) return;
        setPdfBlob(blob);

        const buffer = await blob.arrayBuffer();
        const pdfjsLib = await import("pdfjs-dist");
        pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

        const loadingTask = pdfjsLib.getDocument({ data: new Uint8Array(buffer) });
        loadingTaskRef = loadingTask;
        loadedDoc = await loadingTask.promise;
        if (cancelled) {
          await loadedDoc.cleanup();
          return;
        }

        setPdfDoc(loadedDoc);
        setNumPages(loadedDoc.numPages);
        const target = Math.max(1, Math.min(initialPage || 1, loadedDoc.numPages));
        setCurrentPage(target);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load original PDF document.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadPdf();
    return () => {
      cancelled = true;
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
        renderTaskRef.current = null;
      }
      if (loadedDoc) {
        loadedDoc.cleanup().catch(() => {});
      }
      if (loadingTaskRef) {
        loadingTaskRef.destroy().catch(() => {});
      }
    };
  }, [open, documentId, initialPage]);

  // Reset scroll position to top when changing pages
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
      containerRef.current.scrollLeft = 0;
    }
  }, [currentPage]);

  // Render active page to canvas with true rotation & scaling + aligned evidence highlights
  const renderPage = useCallback(async () => {
    if (!pdfDoc || !canvasRef.current || !containerRef.current) return;

    // Cancel any in-flight render before drawing to prevent pdfjs #canvasInUse errors
    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
      renderTaskRef.current = null;
    }

    const pdfjsLib = await import("pdfjs-dist");
    const page = await pdfDoc.getPage(currentPage);
    const nativeRotation = normalizeDegrees(page.rotate || 0);

    // Fetch text content once so we can both auto-detect upside-down pages and align highlights
    const textContent = await page.getTextContent();
    let autoCorrection = autoCorrectionCacheRef.current.get(currentPage);
    if (autoCorrection === undefined) {
      const nativeViewport = page.getViewport({ scale: 1.0, rotation: nativeRotation });
      autoCorrection = detectUpsideDownCorrection(
        textContent.items as Array<{ str?: string; transform?: number[] }>,
        nativeViewport.transform,
        pdfjsLib.Util.transform
      );
      autoCorrectionCacheRef.current.set(currentPage, autoCorrection);
    }

    const manualOffset = manualRotations[currentPage] ?? 0;
    const totalRotation = normalizeDegrees(nativeRotation + autoCorrection + manualOffset);
    setEffectiveRotation(totalRotation);

    const unscaled = page.getViewport({ scale: 1.0, rotation: totalRotation });
    const container = containerRef.current;
    const effectiveScale = computeFitScale({
      fitMode,
      manualZoom: zoom,
      unscaledWidth: unscaled.width,
      unscaledHeight: unscaled.height,
      containerWidth: container.clientWidth,
      containerHeight: container.clientHeight,
    });
    activeScaleRef.current = effectiveScale;
    setDisplayScale(effectiveScale);

    const dpr = typeof window !== "undefined" ? Math.min(window.devicePixelRatio || 1, 3) : 1;
    const viewport = page.getViewport({ scale: effectiveScale, rotation: totalRotation });
    const displayWidth = Math.floor(viewport.width);
    const displayHeight = Math.floor(viewport.height);
    setPageSize({ width: displayWidth, height: displayHeight });

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = Math.max(1, Math.floor(viewport.width * dpr));
    canvas.height = Math.max(1, Math.floor(viewport.height * dpr));
    canvas.style.width = `${displayWidth}px`;
    canvas.style.height = `${displayHeight}px`;

    // Start from clean identity matrix; pass DPR scale via PDF.js transform param cleanly
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const renderTransform = dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined;
    const task = page.render({
      canvasContext: ctx,
      canvas: null,
      viewport,
      transform: renderTransform,
    });
    renderTaskRef.current = task;

    try {
      await task.promise;
    } catch (err: unknown) {
      // Ignore expected cancellation when user rapidly zooms, rotates, resizes, or switches pages
      if (err && typeof err === "object" && "name" in err && err.name === "RenderingCancelledException") {
        return;
      }
      throw err;
    } finally {
      if (renderTaskRef.current === task) {
        renderTaskRef.current = null;
      }
    }

    // Render orientation-aware semi-transparent yellow highlights over matching text items
    const overlay = highlightRef.current;
    if (overlay) {
      overlay.innerHTML = "";
      overlay.style.width = `${displayWidth}px`;
      overlay.style.height = `${displayHeight}px`;

      if (evidence && currentPage === initialPage) {
        const keywords = Array.from(
          new Set(
            evidence
              .toLowerCase()
              .split(/[^a-z0-9₹.,/-]+/)
              .filter((w) => w.length >= 4 && !["page", "document", "this", "that", "with", "from"].includes(w))
          )
        ).slice(0, 8);

        if (keywords.length > 0) {
          for (const item of textContent.items) {
            if (!("str" in item) || !item.str.trim()) continue;
            const lower = item.str.toLowerCase();
            if (!keywords.some((kw) => lower.includes(kw))) continue;

            const rect = computeHighlightRect(
              item as TextItemLike,
              viewport.transform,
              effectiveScale,
              pdfjsLib.Util.transform
            );
            if (!rect) continue;

            const box = document.createElement("div");
            box.style.position = "absolute";
            box.style.left = `${rect.left}px`;
            box.style.top = `${rect.top}px`;
            box.style.width = `${rect.width}px`;
            box.style.height = `${rect.height}px`;
            box.style.background = "rgba(250, 204, 21, 0.38)";
            box.style.borderRadius = "3px";
            box.style.pointerEvents = "none";
            overlay.appendChild(box);
          }
        }
      }
    }
  }, [pdfDoc, currentPage, zoom, fitMode, manualRotations, evidence, initialPage]);

  useEffect(() => {
    renderPage().catch((err) => {
      if (err && typeof err === "object" && "name" in err && err.name === "RenderingCancelledException") {
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to render PDF page.");
    });
  }, [renderPage]);

  // Re-render cleanly when modal container resizes in fit-width or fit-page mode
  useEffect(() => {
    if (!open || fitMode === "custom" || !containerRef.current) return;
    let rafId = 0;
    const obs = new ResizeObserver(() => {
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        renderPage().catch(() => {});
      });
    });
    obs.observe(containerRef.current);
    return () => {
      cancelAnimationFrame(rafId);
      obs.disconnect();
    };
  }, [open, fitMode, renderPage]);

  const handleDownload = () => {
    if (!pdfBlob) return;
    const url = URL.createObjectURL(pdfBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "document.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-[2px] p-3 sm:p-6"
      onClick={onClose}
    >
      <div
        className="w-full max-w-5xl h-[90vh] rounded-3xl border border-[#E8E8E8] bg-white shadow-2xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E8E8E8] bg-white px-4 sm:px-6 py-3.5">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="h-8 w-8 rounded-xl bg-[#090909] text-white flex items-center justify-center shrink-0">
              <FileText className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[#111111] truncate">{filename}</p>
              <p className="text-[11px] text-[#777777]">
                Original PDF Viewer {numPages > 0 ? `• Page ${currentPage} of ${numPages}` : ""}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            {/* Page Navigation */}
            <button
              type="button"
              disabled={currentPage <= 1 || loading}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] p-2 text-[#111111] hover:border-[#090909] disabled:opacity-40"
              aria-label="Previous page"
              title="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-2 text-xs font-medium text-[#111111] tabular-nums">
              {numPages > 0 ? `${currentPage} / ${numPages}` : "—"}
            </span>
            <button
              type="button"
              disabled={currentPage >= numPages || loading}
              onClick={() => setCurrentPage((p) => Math.min(numPages, p + 1))}
              className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] p-2 text-[#111111] hover:border-[#090909] disabled:opacity-40"
              aria-label="Next page"
              title="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>

            <div className="mx-1 h-5 w-px bg-[#E8E8E8]" />

            {/* Zoom, Rotate & Fit Controls */}
            <button
              type="button"
              disabled={loading}
              onClick={() => {
                const next = Math.max(0.4, Number((activeScaleRef.current - 0.2).toFixed(2)));
                setFitMode("custom");
                setZoom(next);
              }}
              className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] p-2 text-[#111111] hover:border-[#090909] disabled:opacity-40"
              aria-label="Zoom out"
              title="Zoom out"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <span className="px-1.5 text-[11px] font-medium text-[#555555] tabular-nums">
              {Math.round(displayScale * 100)}%
            </span>
            <button
              type="button"
              disabled={loading}
              onClick={() => {
                const next = Math.min(3.0, Number((activeScaleRef.current + 0.2).toFixed(2)));
                setFitMode("custom");
                setZoom(next);
              }}
              className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] p-2 text-[#111111] hover:border-[#090909] disabled:opacity-40"
              aria-label="Zoom in"
              title="Zoom in"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => setFitMode("width")}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-xs font-medium transition-colors ${
                fitMode === "width"
                  ? "bg-[#090909] text-white border-[#090909]"
                  : "bg-[#F7F7F7] text-[#111111] border-[#E8E8E8] hover:border-[#090909]"
              }`}
              title="Fit to width"
            >
              <Maximize2 className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Fit Width</span>
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => setFitMode("page")}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-xs font-medium transition-colors ${
                fitMode === "page"
                  ? "bg-[#090909] text-white border-[#090909]"
                  : "bg-[#F7F7F7] text-[#111111] border-[#E8E8E8] hover:border-[#090909]"
              }`}
              title="Fit complete page"
            >
              <Minimize2 className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Fit Page</span>
            </button>
            <button
              type="button"
              disabled={loading || !pdfDoc}
              onClick={() =>
                setManualRotations((prev) => ({
                  ...prev,
                  [currentPage]: normalizeDegrees((prev[currentPage] ?? 0) + 90),
                }))
              }
              className="inline-flex items-center gap-1 rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] px-2.5 py-1.5 text-xs font-medium text-[#111111] hover:border-[#090909] disabled:opacity-40"
              aria-label="Rotate page 90 degrees"
              title={`Rotate 90° (current ${effectiveRotation}°)`}
            >
              <RotateCw className="h-3.5 w-3.5" />
              {effectiveRotation !== 0 && (
                <span className="text-[10px] tabular-nums">{effectiveRotation}°</span>
              )}
            </button>

            <div className="mx-1 h-5 w-px bg-[#E8E8E8]" />

            {/* Download & Close */}
            <button
              type="button"
              disabled={!pdfBlob}
              onClick={handleDownload}
              className="inline-flex items-center gap-1.5 rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] px-3 py-1.5 text-xs font-medium text-[#111111] hover:border-[#090909] disabled:opacity-40"
              title="Download PDF"
            >
              <Download className="h-3.5 w-3.5" />
              Download
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-[#E8E8E8] bg-[#F7F7F7] p-2 text-[#111111] hover:border-[#090909]"
              aria-label="Close PDF viewer"
              title="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Cited Evidence Context Strip */}
        {evidence && currentPage === initialPage && (
          <div className="border-b border-amber-200 bg-amber-50/70 px-5 py-2 text-xs text-amber-900">
            <span className="font-semibold">Cited Evidence (Page {initialPage}):</span> {evidence}
          </div>
        )}

        {/* Canvas Viewport */}
        <div
          ref={containerRef}
          className="flex-1 overflow-auto bg-[#F4F4F5] p-4 sm:p-6"
        >
          {loading && (
            <div className="mx-auto my-12 w-fit rounded-2xl border border-[#E8E8E8] bg-white px-6 py-4 text-sm text-[#555555]">
              Loading original PDF document...
            </div>
          )}

          {error && (
            <div className="mx-auto my-12 max-w-md rounded-2xl border border-red-200 bg-white p-6 text-center space-y-2">
              <AlertCircle className="h-6 w-6 text-red-600 mx-auto" />
              <p className="text-sm font-semibold text-[#111111]">Unable to open PDF</p>
              <p className="text-xs text-[#777777]">{error}</p>
            </div>
          )}

          {!loading && !error && pdfDoc && (
            <div
              className="relative mx-auto shadow-lg border border-[#E8E8E8] bg-white"
              style={
                pageSize
                  ? { width: `${pageSize.width}px`, height: `${pageSize.height}px` }
                  : undefined
              }
            >
              <canvas ref={canvasRef} className="block" />
              <div ref={highlightRef} className="absolute inset-0 pointer-events-none" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
