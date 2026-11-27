import type {
  PDFDocumentLoadingTask,
  PDFDocumentProxy,
  PDFWorker,
} from "pdfjs-dist";

export const PDF_WORKER_SRC = "/pdf.worker.min.mjs";
export const PDF_STANDARD_FONT_URL = "/standard_fonts/";
export const PDF_CMAP_URL = "/cmaps/";
export const PDF_ICC_URL = "/iccs/";
export const PDF_WASM_URL = "/wasm/";

const MAX_CANVAS_AREA_PX = 16_777_216; // 16 MP browser-safe backing store limit
const MAX_CANVAS_EDGE_PX = 8192;

export function pdfDiagLog(stage: string, details?: Record<string, unknown>): void {
  if (process.env.NODE_ENV === "production") return;
  if (details) {
    console.debug(`[ArthaLens PDF] ${stage}`, details);
  } else {
    console.debug(`[ArthaLens PDF] ${stage}`);
  }
}

export function pdfDiagError(stage: string, err: unknown, details?: Record<string, unknown>): void {
  if (process.env.NODE_ENV === "production") return;
  const errInfo =
    err instanceof Error
      ? { name: err.name, message: err.message, stack: err.stack }
      : { error: String(err) };
  console.error(`[ArthaLens PDF] ${stage}`, { ...details, ...errInfo });
}

/**
 * Verify binary payload contains a valid `%PDF-` signature within the first 1024 bytes.
 */
export function hasValidPdfSignature(bytes: Uint8Array): boolean {
  if (!bytes || bytes.byteLength < 8) return false;
  const limit = Math.min(bytes.byteLength - 5, 1024);
  for (let i = 0; i <= limit; i++) {
    if (
      bytes[i] === 0x25 && // %
      bytes[i + 1] === 0x50 && // P
      bytes[i + 2] === 0x44 && // D
      bytes[i + 3] === 0x46 && // F
      bytes[i + 4] === 0x2d // -
    ) {
      return true;
    }
  }
  return false;
}

export function configurePdfWorkerSource(pdfjsLib: typeof import("pdfjs-dist")): void {
  if (pdfjsLib.GlobalWorkerOptions.workerSrc !== PDF_WORKER_SRC) {
    pdfjsLib.GlobalWorkerOptions.workerSrc = PDF_WORKER_SRC;
    pdfDiagLog("Configured GlobalWorkerOptions.workerSrc", {
      workerSrc: PDF_WORKER_SRC,
      apiVersion: pdfjsLib.version,
    });
  }
}

/**
 * Initialize an isolated PDFWorker and await readiness before creating a loading task.
 */
export async function initializeIsolatedPdfWorker(
  pdfjsLib: typeof import("pdfjs-dist"),
  sessionId: number,
  isCancelled: () => boolean
): Promise<PDFWorker> {
  configurePdfWorkerSource(pdfjsLib);
  pdfDiagLog("Initializing PDF.js worker", { sessionId, workerSrc: PDF_WORKER_SRC });

  const worker = new pdfjsLib.PDFWorker();
  try {
    await worker.promise;
    if (isCancelled() || worker.destroyed || !worker.messageHandler) {
      worker.destroy();
      throw new DOMException("PDF worker initialization cancelled", "AbortError");
    }
    pdfDiagLog("PDF.js worker ready", {
      sessionId,
      destroyed: worker.destroyed,
      hasMessageHandler: Boolean(worker.messageHandler),
    });
    return worker;
  } catch (err) {
    try {
      worker.destroy();
    } catch {
      // ignore cleanup error
    }
    throw err;
  }
}

export interface PdfSessionHandle {
  sessionId: number;
  loadingTask: PDFDocumentLoadingTask;
  worker: PDFWorker;
  doc: PDFDocumentProxy | null;
}

/**
 * Destroy a PDF.js loading task and its isolated worker cleanly in sequence without racing cleanup().
 */
export async function destroyPdfSession(session: Partial<PdfSessionHandle> | null): Promise<void> {
  if (!session) return;
  const { sessionId, loadingTask, worker } = session;
  pdfDiagLog("Destroying PDF session", { sessionId });
  try {
    if (loadingTask) {
      await loadingTask.destroy().catch(() => {});
    }
  } finally {
    if (worker) {
      try {
        worker.destroy();
      } catch {
        // ignore worker termination error
      }
    }
  }
}

/**
 * Clamp backing canvas DPR so ultra-large or unusual page dimensions stay within GPU canvas limits.
 */
export function computeSafeDpr(viewportWidth: number, viewportHeight: number): number {
  const baseDpr = typeof window !== "undefined" ? Math.min(window.devicePixelRatio || 1, 3) : 1;
  const safeW = Math.max(1, viewportWidth);
  const safeH = Math.max(1, viewportHeight);
  const edgeCap = Math.min(MAX_CANVAS_EDGE_PX / safeW, MAX_CANVAS_EDGE_PX / safeH);
  const areaCap = Math.sqrt(MAX_CANVAS_AREA_PX / (safeW * safeH));
  return Math.max(0.5, Math.min(baseDpr, edgeCap, areaCap));
}

export function isAbortOrCancellationError(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const name = "name" in err ? String(err.name) : "";
  const msg = "message" in err ? String(err.message) : "";
  return (
    name === "AbortError" ||
    name === "RenderingCancelledException" ||
    msg.includes("Loading aborted") ||
    msg.includes("Worker was destroyed") ||
    msg.includes("Transport destroyed")
  );
}

/**
 * Translate PDF.js and network errors into clear, accurate user-facing messages.
 */
export function formatPdfErrorMessage(err: unknown): string {
  if (!(err instanceof Error)) {
    return "Failed to load original PDF document.";
  }
  const msg = err.message || "";
  if (err.name === "PasswordException") {
    return "This PDF is password-protected or encrypted. Please upload an unlocked PDF to preview it.";
  }
  if (err.name === "InvalidPDFException") {
    return "This PDF file appears corrupted, truncated, or uses an invalid PDF structure.";
  }
  if (err.name === "MissingPDFException") {
    return "Original PDF file could not be found.";
  }
  if (msg.includes("sendWithPromise")) {
    return "PDF worker session was interrupted before rendering finished. Please reopen the document.";
  }
  return msg || "Failed to load original PDF document.";
}
