export type FitMode = "width" | "page" | "custom";

export interface TextItemLike {
  str?: string;
  width?: number;
  height?: number;
  transform?: number[];
}

export interface HighlightRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function normalizeDegrees(deg: number): number {
  const m = deg % 360;
  return m < 0 ? m + 360 : m;
}

/**
 * Inspect text items under the PDF's native rotation viewport.
 * Returns 180 only when dominant readable horizontal text runs upside down on screen;
 * leaves upright 0°/90°/180°/270° pages and image-only scanned PDFs untouched (0).
 */
export function detectUpsideDownCorrection(
  items: TextItemLike[],
  baseViewportTransform: number[],
  utilTransform: (m1: number[], m2: number[]) => number[]
): number {
  let sumDx = 0;
  let sumDy = 0;
  let sumAy = 0;
  let totalWeight = 0;
  let readableCount = 0;

  for (const item of items) {
    const str = (item.str || "").trim();
    if (str.length < 3 || !Array.isArray(item.transform) || item.transform.length < 6) continue;
    const tx = utilTransform(baseViewportTransform, item.transform);
    const uLen = Math.hypot(tx[0], tx[1]);
    const vLen = Math.hypot(tx[2], tx[3]);
    if (uLen < 1e-3 || vLen < 1e-3) continue;

    const dx = tx[0] / uLen;
    const dy = tx[1] / uLen;
    const ay = tx[3] / vLen;

    // Ignore diagonal watermarks (~35-55 deg) when determining primary reading axis
    if (Math.abs(dx) < 0.85 && Math.abs(dy) < 0.85) continue;

    readableCount += 1;
    const weight = str.length;
    sumDx += dx * weight;
    sumDy += dy * weight;
    sumAy += ay * weight;
    totalWeight += weight;
  }

  if (readableCount < 3 || totalWeight === 0) return 0;
  const avgDx = sumDx / totalWeight;
  const avgDy = sumDy / totalWeight;
  const avgAy = sumAy / totalWeight;

  if (Math.abs(avgDx) >= Math.abs(avgDy) && avgDx < -0.75 && avgAy > 0.75) {
    return 180;
  }
  return 0;
}

export function computeFitScale(params: {
  fitMode: FitMode;
  manualZoom: number;
  unscaledWidth: number;
  unscaledHeight: number;
  containerWidth: number;
  containerHeight: number;
}): number {
  const safeW = Math.max(1, params.unscaledWidth);
  const safeH = Math.max(1, params.unscaledHeight);
  const padX = params.containerWidth >= 640 ? 48 : 32;
  const padY = params.containerHeight >= 640 ? 48 : 32;
  // Reserve 20px for vertical scrollbar so Fit Width never triggers horizontal overflow
  const availWidth = Math.max(180, params.containerWidth - padX - 20);
  const availHeight = Math.max(180, params.containerHeight - padY - 8);

  let scale = params.manualZoom;
  if (params.fitMode === "width") {
    scale = availWidth / safeW;
  } else if (params.fitMode === "page") {
    scale = Math.min(availWidth / safeW, availHeight / safeH);
  }
  return Math.max(0.25, Math.min(3.5, scale));
}

/**
 * Compute pixel-accurate highlight rectangle for a PDF.js TextItem under `viewportTransform`
 * across any rotation (0°, 90°, 180°, 270°) and zoom scale, covering both ascenders & descenders.
 */
export function computeHighlightRect(
  item: TextItemLike,
  viewportTransform: number[],
  effectiveScale: number,
  utilTransform: (m1: number[], m2: number[]) => number[]
): HighlightRect | null {
  if (!Array.isArray(item.transform) || item.transform.length < 6) return null;
  const tx = utilTransform(viewportTransform, item.transform);
  const uLen = Math.hypot(tx[0], tx[1]);
  const vLen = Math.hypot(tx[2], tx[3]);
  if (uLen < 1e-3 || vLen < 1e-3) return null;

  const ux = tx[0] / uLen;
  const uy = tx[1] / uLen;
  const vx = tx[2] / vLen;
  const vy = tx[3] / vLen;

  // Exclude rotated diagonal watermarks (~35-55 deg) from document highlights
  if (Math.abs(ux) < 0.85 && Math.abs(uy) < 0.85) return null;

  const spanW = Math.max(8, (item.width || 0) * effectiveScale);
  const fontPx = Math.max(vLen, (item.height || 0) * effectiveScale, 8);
  const ascender = fontPx * 0.92;
  const descender = fontPx * 0.24;

  const bx = tx[4] - vx * descender;
  const by = tx[5] - vy * descender;
  const totalH = ascender + descender;

  const p0x = bx;
  const p0y = by;
  const p1x = bx + ux * spanW;
  const p1y = by + uy * spanW;
  const p2x = bx + vx * totalH;
  const p2y = by + vy * totalH;
  const p3x = p1x + vx * totalH;
  const p3y = p1y + vy * totalH;

  const minX = Math.min(p0x, p1x, p2x, p3x) - 1;
  const maxX = Math.max(p0x, p1x, p2x, p3x) + 1;
  const minY = Math.min(p0y, p1y, p2y, p3y) - 1;
  const maxY = Math.max(p0y, p1y, p2y, p3y) + 1;

  return {
    left: minX,
    top: minY,
    width: Math.max(6, maxX - minX),
    height: Math.max(6, maxY - minY),
  };
}

const GENERIC_STOPWORDS = new Set([
  "page",
  "document",
  "this",
  "that",
  "with",
  "from",
  "uploaded",
  "record",
  "records",
  "details",
  "policy",
  "section",
  "amount",
  "information",
  "found",
  "needs",
  "verification",
  "confirmed",
  "summary",
  "statement",
  "report",
  "account",
]);

/**
 * Select high-signal text items matching `evidence` (preferring IDs, numbers, and multi-word phrases)
 * and merge adjacent overlapping boxes so translucent yellow highlights stay crisp and non-stacking.
 */
export function buildEvidenceHighlightRects(
  items: TextItemLike[],
  evidence: string | undefined,
  viewportTransform: number[],
  effectiveScale: number,
  utilTransform: (m1: number[], m2: number[]) => number[]
): HighlightRect[] {
  const cleanEv = (evidence || "").trim();
  if (!cleanEv) return [];

  // Extract strong anchors: masked/full refs (DEMO-LI-8841209), rupee amounts, dates, or specific words
  const strongTokens = Array.from(
    new Set(
      (
        cleanEv.match(
          /\b(?:[A-Z]{2,6}-(?:LI|FD|SB|PL)-[A-Z0-9X]{3,16}|₹\s?[\d,]+(?:\.\d{1,2})?|\d{2}-[A-Za-z]{3}-\d{4})\b/gi
        ) || []
      ).map((t) => t.toLowerCase().trim())
    )
  );

  const specificWords = Array.from(
    new Set(
      cleanEv
        .toLowerCase()
        .split(/[^a-z0-9₹.,/-]+/)
        .filter((w) => w.length >= 4 && !GENERIC_STOPWORDS.has(w))
    )
  ).slice(0, 6);

  const rawRects: HighlightRect[] = [];
  for (const item of items) {
    const str = (item.str || "").trim();
    if (!str) continue;
    const low = str.toLowerCase();

    const matchedStrong = strongTokens.some((tok) => low.includes(tok));
    const matchedSpecific =
      specificWords.length > 0 &&
      (specificWords.filter((w) => low.includes(w)).length >= 2 ||
        (specificWords.length === 1 && low.includes(specificWords[0])) ||
        specificWords.some((w) => w.length >= 7 && low.includes(w)));

    if (!matchedStrong && !matchedSpecific) continue;

    const rect = computeHighlightRect(item, viewportTransform, effectiveScale, utilTransform);
    if (rect) rawRects.push(rect);
  }

  // Fallback to best single keyword match only if strong/phrase match yielded nothing
  if (rawRects.length === 0 && specificWords.length > 0) {
    for (const item of items) {
      const str = (item.str || "").trim();
      if (!str) continue;
      const low = str.toLowerCase();
      if (!specificWords.some((w) => low.includes(w))) continue;
      const rect = computeHighlightRect(item, viewportTransform, effectiveScale, utilTransform);
      if (rect) rawRects.push(rect);
      if (rawRects.length >= 8) break;
    }
  }

  if (rawRects.length === 0) return [];

  // Merge overlapping/adjacent rects on the same visual row to avoid stacked alpha darkening
  const sorted = [...rawRects].sort((a, b) => a.top - b.top || a.left - b.left);
  const merged: HighlightRect[] = [];
  for (const r of sorted) {
    const prev = merged[merged.length - 1];
    if (
      prev &&
      Math.abs(prev.top - r.top) <= Math.min(prev.height, r.height) * 0.55 &&
      r.left <= prev.left + prev.width + 6
    ) {
      const right = Math.max(prev.left + prev.width, r.left + r.width);
      const bottom = Math.max(prev.top + prev.height, r.top + r.height);
      prev.left = Math.min(prev.left, r.left);
      prev.top = Math.min(prev.top, r.top);
      prev.width = right - prev.left;
      prev.height = bottom - prev.top;
    } else {
      merged.push({ ...r });
    }
  }
  return merged;
}
