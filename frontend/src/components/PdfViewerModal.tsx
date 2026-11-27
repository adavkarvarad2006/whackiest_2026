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
import type { PDFDocumentProxy, RenderTask, TextLayer } from "pdfjs-dist";
import { api } from "@/lib/api";
import { formatISTWithTz } from "@/lib/dateUtils";
import {
  buildEvidenceHighlightRects,
  computeFitScale,
  detectUpsideDownCorrection,
  FitMode,
  normalizeDegrees,
  TextItemLike,
} from "@/lib/pdfGeometry";
import {
  computeSafeDpr,
  destroyPdfSession,
  formatPdfErrorMessage,
  hasValidPdfSignature,
  initializeIsolatedPdfWorker,
  isAbortOrCancellationError,
  PDF_CMAP_URL,
  PDF_ICC_URL,
  PDF_STANDARD_FONT_URL,
  PDF_WASM_URL,
  pdfDiagError,
  pdfDiagLog,
  PdfSessionHandle,
} from "@/lib/pdfViewerEngine";

interface PdfViewerModalProps {
  open: boolean;
  documentId: string | number | null | undefined;
  filename: string;
  initialPage?: number;
  evidence?: string;
  uploadedAt?: string;
  onClose: () => void;
}

export function PdfViewerModal({
  open,
  documentId,
  filename,
  initialPage = 1,
  evidence,
  uploadedAt,
  onClose,
}: PdfViewerModalProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const textLayerDivRef = useRef<HTMLDivElement | null>(null);
  const highlightRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Strict single-flight guards preventing concurrent draws or post-destroy proxy access
  const sessionSeqRef = useRef<number>(0);
  const renderSeqRef = useRef<number>(0);
  const activeSessionRef = useRef<PdfSessionHandle | null>(null);
  const activeDocRef = useRef<PDFDocumentProxy | null>(null);
  const destroyedDocsRef = useRef<WeakSet<PDFDocumentProxy>>(new WeakSet());
  const renderTaskRef = useRef<RenderTask | null>(null);
  const textLayerTaskRef = useRef<TextLayer | null>(null);
  const autoCorrectionCacheRef = useRef<Map<number, number>>(new Map());
  const activeScaleRef = useRef<number>(1.0);
  const initialPageRef = useRef<number>(initialPage);

  useEffect(() => {
    initialPageRef.current = initialPage;
  }, [initialPage]);

  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(initialPage || 1);
  const [zoom, setZoom] = useState(1.0);
  const [displayScale, setDisplayScale] = useState(1.0);
  const [fitMode, setFitMode] = useState<FitMode>("width");
  const [manualRotations, setManualRotations] = useState<Record<number, number>>({});
  const [effectiveRotation, setEffectiveRotation] = useState(0);
  const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null);
  const [containerSize, setContainerSize] = useState<{ width: number; height: number }>({
    width: 0,
    height: 0,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emptyPageNotice, setEmptyPageNotice] = useState(false);

  const isDocUsable = useCallback((doc: PDFDocumentProxy | null): doc is PDFDocumentProxy => {
    if (!doc) return false;
    if (activeDocRef.current !== doc) return false;
    if (destroyedDocsRef.current.has(doc)) return false;
    if (doc.loadingTask?.destroyed) return false;
    return true;
  }, []);

  const clearStageDom = useCallback(() => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
      canvas.width = 1;
      canvas.height = 1;
    }
    if (textLayerDivRef.current) {
      textLayerDivRef.current.innerHTML = "";
    }
    if (highlightRef.current) {
      highlightRef.current.innerHTML = "";
    }
  }, []);

  const cancelActiveRender = useCallback(async () => {
    const prevTextLayer = textLayerTaskRef.current;
    textLayerTaskRef.current = null;
    if (prevTextLayer) {
      try {
        prevTextLayer.cancel();
      } catch {
        // ignore
      }
    }
    const prevRender = renderTaskRef.current;
    renderTaskRef.current = null;
    if (prevRender) {
      try {
        prevRender.cancel();
      } catch {
        // ignore
      }
      try {
        await prevRender.promise;
      } catch {
        // Expected RenderingCancelledException
      }
    }
  }, []);

  // Keyboard shortcuts: Escape to close, Left/Right arrows to navigate pages
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

  // Observe container viewport size with >= 8px threshold to avoid scrollbar oscillation loops
  useEffect(() => {
    if (!open || !containerRef.current) return;
    const el = containerRef.current;
    const updateSize = () => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (w <= 0 || h <= 0) return;
      setContainerSize((prev) =>
        Math.abs(prev.width - w) >= 8 || Math.abs(prev.height - h) >= 8
          ? { width: w, height: h }
          : prev
      );
    };
    updateSize();
    const obs = new ResizeObserver(() => updateSize());
    obs.observe(el);
    return () => obs.disconnect();
  }, [open, loading]);

  // Sync page number when jumping citations inside an already-open document
  useEffect(() => {
    if (!open || numPages <= 0) return;
    let cancelled = false;
    const target = Math.max(1, Math.min(initialPage || 1, numPages));
    Promise.resolve().then(() => {
      if (!cancelled) {
        setCurrentPage((prev) => (prev === target ? prev : target));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [open, initialPage, numPages]);

  // Fetch authenticated original PDF binary & load PDF.js document with isolated worker
  useEffect(() => {
    const sessionId = ++sessionSeqRef.current;
    renderSeqRef.current += 1;
    const destroyedDocs = destroyedDocsRef.current;

    // Immediately invalidate any previous document reference BEFORE async cleanup finishes
    const priorDoc = activeDocRef.current;
    activeDocRef.current = null;
    if (priorDoc) {
      destroyedDocs.add(priorDoc);
    }
    const priorSession = activeSessionRef.current;
    activeSessionRef.current = null;

    if (!open) {
      Promise.resolve().then(async () => {
        await cancelActiveRender();
        await destroyPdfSession(priorSession);
        clearStageDom();
        setPdfDoc(null);
        setPdfBlob(null);
        setNumPages(0);
        setPageSize(null);
        setManualRotations({});
        setError(null);
        setEmptyPageNotice(false);
        setLoading(false);
      });
      return;
    }

    const fetchAbort = new AbortController();
    let localCancelled = false;
    let localSession: Partial<PdfSessionHandle> | null = null;

    const isStale = () => localCancelled || sessionId !== sessionSeqRef.current;

    if (!documentId) {
      Promise.resolve().then(async () => {
        await cancelActiveRender();
        await destroyPdfSession(priorSession);
        if (isStale()) return;
        clearStageDom();
        setPdfDoc(null);
        setPdfBlob(null);
        setNumPages(0);
        setPageSize(null);
        setLoading(false);
        setError("Original document reference is unavailable for this citation.");
      });
      return () => {
        localCancelled = true;
      };
    }

    async function loadPdf() {
      setLoading(true);
      setError(null);
      setEmptyPageNotice(false);
      setPdfDoc(null);
      setPdfBlob(null);
      setNumPages(0);
      setZoom(1.0);
      setFitMode("width");
      setManualRotations({});
      setEffectiveRotation(0);
      setPageSize(null);
      autoCorrectionCacheRef.current.clear();

      // Wait for prior render & prior document session to finish tearing down cleanly
      await cancelActiveRender();
      await destroyPdfSession(priorSession);
      clearStageDom();
      if (isStale()) return;

      try {
        pdfDiagLog("Starting document load", { sessionId, documentId, filename });
        const { blob, status, contentType, contentLength, url } =
          await api.fetchDocumentFileWithMeta(documentId!, { signal: fetchAbort.signal });
        if (isStale()) return;

        const buffer = await blob.arrayBuffer();
        if (isStale()) return;

        const bytes = new Uint8Array(buffer);
        if (!hasValidPdfSignature(bytes)) {
          throw new Error(
            "Invalid PDF binary payload: missing %PDF- header signature."
          );
        }

        pdfDiagLog("Validated PDF payload", {
          sessionId,
          documentId,
          url,
          status,
          contentType,
          contentLength,
          actualBytes: bytes.byteLength,
        });

        setPdfBlob(blob);

        const pdfjsLib = await import("pdfjs-dist");
        if (isStale()) return;

        const worker = await initializeIsolatedPdfWorker(pdfjsLib, sessionId, isStale);
        localSession = { sessionId, worker };
        if (isStale()) {
          await destroyPdfSession(localSession);
          return;
        }

        pdfDiagLog("Creating PDF.js loading task", { sessionId, documentId });
        const loadingTask = pdfjsLib.getDocument({
          data: bytes,
          worker,
          standardFontDataUrl: PDF_STANDARD_FONT_URL,
          cMapUrl: PDF_CMAP_URL,
          cMapPacked: true,
          iccUrl: PDF_ICC_URL,
          wasmUrl: PDF_WASM_URL,
          useWorkerFetch: true,
        });

        localSession = { sessionId, worker, loadingTask };
        activeSessionRef.current = { sessionId, worker, loadingTask, doc: null };

        const loadedDoc = await loadingTask.promise;
        if (isStale()) {
          destroyedDocsRef.current.add(loadedDoc);
          await destroyPdfSession(localSession);
          return;
        }

        activeSessionRef.current = { sessionId, worker, loadingTask, doc: loadedDoc };
        activeDocRef.current = loadedDoc;

        pdfDiagLog("PDF document loaded", {
          sessionId,
          documentId,
          numPages: loadedDoc.numPages,
        });

        const targetPage = Math.max(1, Math.min(initialPageRef.current || 1, loadedDoc.numPages));
        setCurrentPage(targetPage);
        setNumPages(loadedDoc.numPages);
        setPdfDoc(loadedDoc);
      } catch (err: unknown) {
        if (isStale() || isAbortOrCancellationError(err)) {
          pdfDiagLog("Aborted or superseded PDF load ignored", { sessionId, documentId });
          await destroyPdfSession(localSession);
          return;
        }
        pdfDiagError("PDF load failed", err, { sessionId, documentId, filename });
        await destroyPdfSession(localSession);
        setPdfDoc(null);
        setPdfBlob(null);
        setNumPages(0);
        setError(formatPdfErrorMessage(err));
      } finally {
        if (!isStale()) {
          setLoading(false);
        }
      }
    }

    loadPdf();

    return () => {
      localCancelled = true;
      sessionSeqRef.current += 1;
      renderSeqRef.current += 1;
      fetchAbort.abort();

      if (activeDocRef.current) {
        destroyedDocs.add(activeDocRef.current);
        activeDocRef.current = null;
      }
      const sessionToDestroy = activeSessionRef.current || localSession;
      activeSessionRef.current = null;

      Promise.resolve().then(async () => {
        await cancelActiveRender();
        await destroyPdfSession(sessionToDestroy);
      });
    };
  }, [open, documentId, filename, cancelActiveRender, clearStageDom]);

  // Reset scroll position to top when changing pages
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = 0;
      containerRef.current.scrollLeft = 0;
    }
  }, [currentPage]);

  // Render active page atomically: single canvas + single aligned textLayer + aligned highlights
  const renderPage = useCallback(async () => {
    if (!open || loading || !isDocUsable(pdfDoc) || !canvasRef.current || !containerRef.current) return;

    const seq = ++renderSeqRef.current;
    const sessionId = sessionSeqRef.current;

    // 1. Cancel and await prior render & textLayer before touching canvas or context
    await cancelActiveRender();
    if (seq !== renderSeqRef.current || sessionId !== sessionSeqRef.current || !isDocUsable(pdfDoc)) {
      return;
    }

    const pdfjsLib = await import("pdfjs-dist");
    if (seq !== renderSeqRef.current || sessionId !== sessionSeqRef.current || !isDocUsable(pdfDoc)) {
      return;
    }

    const safePage = Math.max(1, Math.min(currentPage, pdfDoc.numPages || 1));
    pdfDiagLog("Rendering PDF page", { sessionId, seq, page: safePage, numPages: pdfDoc.numPages });

    const page = await pdfDoc.getPage(safePage);
    if (seq !== renderSeqRef.current || sessionId !== sessionSeqRef.current || !isDocUsable(pdfDoc)) {
      return;
    }

    const nativeRotation = normalizeDegrees(page.rotate || 0);
    setEmptyPageNotice(false);

    const [textContent, opList] = await Promise.all([
      page.getTextContent(),
      page.getOperatorList(),
    ]);
    if (seq !== renderSeqRef.current || sessionId !== sessionSeqRef.current || !isDocUsable(pdfDoc)) {
      return;
    }

    const hasText = textContent.items.some(
      (item) => "str" in item && typeof item.str === "string" && item.str.trim().length > 0
    );
    const hasOperators = Array.isArray(opList?.fnArray) && opList.fnArray.length > 0;
    const isEmptyPage = !hasText && !hasOperators;

    let autoCorrection = autoCorrectionCacheRef.current.get(safePage);
    if (autoCorrection === undefined) {
      const nativeViewport = page.getViewport({ scale: 1.0, rotation: nativeRotation });
      autoCorrection =
        nativeRotation === 0
          ? detectUpsideDownCorrection(
              textContent.items as TextItemLike[],
              nativeViewport.transform,
              pdfjsLib.Util.transform
            )
          : 0;
      autoCorrectionCacheRef.current.set(safePage, autoCorrection);
    }

    const manualOffset = manualRotations[safePage] ?? 0;
    const totalRotation = normalizeDegrees(nativeRotation + autoCorrection + manualOffset);
    setEffectiveRotation(totalRotation);

    const unscaled = page.getViewport({ scale: 1.0, rotation: totalRotation });
    if (
      !Number.isFinite(unscaled.width) ||
      !Number.isFinite(unscaled.height) ||
      unscaled.width <= 0 ||
      unscaled.height <= 0
    ) {
      throw new Error(`Invalid PDF page dimensions on page ${safePage}.`);
    }

    const cw = containerSize.width || containerRef.current.clientWidth || 720;
    const ch = containerSize.height || containerRef.current.clientHeight || 560;
    const effectiveScale = computeFitScale({
      fitMode,
      manualZoom: zoom,
      unscaledWidth: unscaled.width,
      unscaledHeight: unscaled.height,
      containerWidth: cw,
      containerHeight: ch,
    });
    activeScaleRef.current = effectiveScale;
    setDisplayScale(effectiveScale);

    const viewport = page.getViewport({ scale: effectiveScale, rotation: totalRotation });
    const dpr = computeSafeDpr(viewport.width, viewport.height);
    const displayWidth = Math.max(1, Math.round(viewport.width));
    const displayHeight = Math.max(1, Math.round(viewport.height));
    setPageSize({ width: displayWidth, height: displayHeight });

    const canvas = canvasRef.current;
    const textDiv = textLayerDivRef.current;
    const overlay = highlightRef.current;
    if (!canvas) return;

    // 2. Clean all three layers atomically before painting with locked aspect ratio
    canvas.width = Math.max(1, Math.round(viewport.width * dpr));
    canvas.height = Math.max(1, Math.round(viewport.height * dpr));
    canvas.style.width = `${displayWidth}px`;
    canvas.style.height = `${displayHeight}px`;
    canvas.style.maxWidth = "none";

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      throw new Error("Unable to initialize 2D canvas rendering context.");
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (textDiv) {
      textDiv.innerHTML = "";
    }
    if (overlay) {
      overlay.innerHTML = "";
      overlay.style.width = `${displayWidth}px`;
      overlay.style.height = `${displayHeight}px`;
    }

    const renderTransform = dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined;
    const task = page.render({
      canvas,
      viewport,
      transform: renderTransform,
    });
    renderTaskRef.current = task;

    try {
      await task.promise;
    } catch (err: unknown) {
      if (isAbortOrCancellationError(err)) {
        return;
      }
      throw err;
    } finally {
      if (renderTaskRef.current === task) {
        renderTaskRef.current = null;
      }
    }

    if (seq !== renderSeqRef.current || sessionId !== sessionSeqRef.current || !isDocUsable(pdfDoc)) {
      return;
    }
    if (canvas.width < 1 || canvas.height < 1) {
      throw new Error(`Canvas backing store failed to initialize on page ${safePage}.`);
    }
    setEmptyPageNotice(isEmptyPage);

    // 3. Render invisible aligned PDF.js TextLayer matching the exact same viewport
    if (textDiv) {
      textDiv.style.setProperty("--scale-factor", String(effectiveScale));
      textDiv.style.setProperty("--total-scale-factor", String(effectiveScale));
      pdfjsLib.setLayerDimensions(textDiv, viewport);

      const textLayer = new pdfjsLib.TextLayer({
        textContentSource: textContent,
        container: textDiv,
        viewport,
      });
      textLayerTaskRef.current = textLayer;
      try {
        await textLayer.render();
      } catch {
        // Ignore cancellation
      } finally {
        if (textLayerTaskRef.current === textLayer) {
          textLayerTaskRef.current = null;
        }
      }
    }

    if (seq !== renderSeqRef.current || sessionId !== sessionSeqRef.current || !isDocUsable(pdfDoc)) {
      return;
    }

    // 4. Render aligned, merged, non-overlapping yellow evidence highlights on the cited page
    if (overlay && evidence && safePage === (initialPage || 1)) {
      const rects = buildEvidenceHighlightRects(
        textContent.items as TextItemLike[],
        evidence,
        viewport.transform,
        effectiveScale,
        pdfjsLib.Util.transform
      );
      for (const rect of rects) {
        const box = document.createElement("div");
        box.style.position = "absolute";
        box.style.left = `${rect.left}px`;
        box.style.top = `${rect.top}px`;
        box.style.width = `${rect.width}px`;
        box.style.height = `${rect.height}px`;
        box.style.background = "rgba(250, 204, 21, 0.36)";
        box.style.borderRadius = "3px";
        box.style.pointerEvents = "none";
        overlay.appendChild(box);
      }
    }

    pdfDiagLog("PDF page render complete", {
      sessionId,
      seq,
      page: safePage,
      displayWidth,
      displayHeight,
      effectiveScale,
      totalRotation,
      textItems: textContent.items.length,
    });
  }, [
    open,
    loading,
    pdfDoc,
    currentPage,
    zoom,
    fitMode,
    manualRotations,
    evidence,
    initialPage,
    containerSize,
    isDocUsable,
    cancelActiveRender,
  ]);

  useEffect(() => {
    const activeSessionId = sessionSeqRef.current;
    renderPage().catch((err: unknown) => {
      if (activeSessionId !== sessionSeqRef.current || isAbortOrCancellationError(err)) {
        pdfDiagLog("Ignored stale/cancelled render error", { activeSessionId });
        return;
      }
      pdfDiagError("PDF page render failed", err, {
        activeSessionId,
        documentId,
        currentPage,
      });
      setError(formatPdfErrorMessage(err));
    });
    return () => {
      renderSeqRef.current += 1;
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch {
          // ignore
        }
      }
      if (textLayerTaskRef.current) {
        try {
          textLayerTaskRef.current.cancel();
        } catch {
          // ignore
        }
      }
    };
  }, [renderPage, documentId, currentPage]);

  const handleDownload = () => {
    if (!pdfBlob) return;
    const url = URL.createObjectURL(pdfBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "document.pdf";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
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
                {uploadedAt ? ` • Uploaded ${formatISTWithTz(uploadedAt)}` : " • Asia/Kolkata (IST)"}
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
              disabled={loading || !pdfDoc}
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
              disabled={loading || !pdfDoc}
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
              disabled={loading || !pdfDoc}
              onClick={() => setFitMode("width")}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-xs font-medium transition-colors ${fitMode === "width"
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
              disabled={loading || !pdfDoc}
              onClick={() => setFitMode("page")}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-xs font-medium transition-colors ${fitMode === "page"
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
        {evidence && currentPage === (initialPage || 1) && (
          <div className="border-b border-amber-200 bg-amber-50/70 px-5 py-2 text-xs text-amber-900">
            <span className="font-semibold">Cited Evidence (Page {initialPage || 1}):</span> {evidence}
          </div>
        )}

        {/* Empty source page notice (only when page lacks text, images, and vector ops) */}
        {emptyPageNotice && !loading && !error && (
          <div className="border-b border-neutral-200 bg-neutral-50 px-5 py-2 text-xs text-[#555555]">
            Page {currentPage} contains no renderable text, image, or vector graphics operators in the original PDF.
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
            <div className="min-w-full w-fit flex justify-center">
              <div
                className="arthalens-pdf-stage relative shadow-lg border border-[#E8E8E8] bg-white"
                style={
                  pageSize
                    ? {
                        width: `${pageSize.width}px`,
                        height: `${pageSize.height}px`,
                        flexShrink: 0,
                      }
                    : {
                        width: "0px",
                        height: "0px",
                        opacity: 0,
                        overflow: "hidden",
                      }
                }
              >
                <canvas
                  ref={canvasRef}
                  className="block max-w-none"
                  style={
                    pageSize
                      ? {
                          width: `${pageSize.width}px`,
                          height: `${pageSize.height}px`,
                          maxWidth: "none",
                        }
                      : undefined
                  }
                />
                <div ref={textLayerDivRef} className="textLayer" />
                <div ref={highlightRef} className="absolute inset-0 pointer-events-none z-[2]" />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
