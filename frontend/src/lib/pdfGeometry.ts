export type FitMode = "width" | "page" | "custom";

export interface TextItemLike {
  str?: string;
  width?: number;
  height?: number;
  transform?: number[];
}

export function normalizeDegrees(deg: number): number {
  const m = deg % 360;
  return m < 0 ? m + 360 : m;
}

/**
 * Inspect text items under the PDF's native rotation viewport.
 * Returns 180 only when dominant readable text runs upside down on screen;
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

  for (const item of items) {
    const str = (item.str || "").trim();
    if (!str || !Array.isArray(item.transform) || item.transform.length < 6) continue;
    const tx = utilTransform(baseViewportTransform, item.transform);
    const uLen = Math.hypot(tx[0], tx[1]);
    const vLen = Math.hypot(tx[2], tx[3]);
    if (uLen < 1e-3 || vLen < 1e-3) continue;

    const dx = tx[0] / uLen;
    const dy = tx[1] / uLen;
    const ay = tx[3] / vLen;

    // Ignore diagonal watermarks (~35-55 deg) when determining primary reading axis
    if (Math.abs(dx) < 0.85 && Math.abs(dy) < 0.85) continue;

    const weight = str.length;
    sumDx += dx * weight;
    sumDy += dy * weight;
    sumAy += ay * weight;
    totalWeight += weight;
  }

  if (totalWeight === 0) return 0;
  const avgDx = sumDx / totalWeight;
  const avgDy = sumDy / totalWeight;
  const avgAy = sumAy / totalWeight;

  if (Math.abs(avgDx) >= Math.abs(avgDy) && avgDx < -0.5 && avgAy > 0.5) {
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
  const padX = params.containerWidth >= 640 ? 48 : 32;
  const padY = params.containerHeight >= 640 ? 48 : 32;
  const availWidth = Math.max(180, params.containerWidth - padX - 20);
  const availHeight = Math.max(180, params.containerHeight - padY - 8);

  let scale = params.manualZoom;
  if (params.fitMode === "width") {
    scale = availWidth / params.unscaledWidth;
  } else if (params.fitMode === "page") {
    scale = Math.min(availWidth / params.unscaledWidth, availHeight / params.unscaledHeight);
  }
  return Math.max(0.25, Math.min(3.5, scale));
}

export function computeHighlightRect(
  item: TextItemLike,
  viewportTransform: number[],
  effectiveScale: number,
  utilTransform: (m1: number[], m2: number[]) => number[]
): { left: number; top: number; width: number; height: number } | null {
  if (!Array.isArray(item.transform) || item.transform.length < 6) return null;
  const tx = utilTransform(viewportTransform, item.transform);
  const uLen = Math.hypot(tx[0], tx[1]);
  const vLen = Math.hypot(tx[2], tx[3]);
  if (uLen < 1e-3 || vLen < 1e-3) return null;

  const ux = tx[0] / uLen;
  const uy = tx[1] / uLen;
  const vx = tx[2] / vLen;
  const vy = tx[3] / vLen;

  const spanW = Math.max(10, (item.width || 0) * effectiveScale);
  const spanH = Math.max(vLen, (item.height || 0) * effectiveScale, 10) * 1.15;

  const p0x = tx[4];
  const p0y = tx[5];
  const p1x = p0x + ux * spanW;
  const p1y = p0y + uy * spanW;
  const p2x = p0x + vx * spanH;
  const p2y = p0y + vy * spanH;
  const p3x = p1x + vx * spanH;
  const p3y = p1y + vy * spanH;

  const minX = Math.min(p0x, p1x, p2x, p3x) - 1;
  const maxX = Math.max(p0x, p1x, p2x, p3x) + 1;
  const minY = Math.min(p0y, p1y, p2y, p3y) - 1;
  const maxY = Math.max(p0y, p1y, p2y, p3y) + 1;

  return {
    left: minX,
    top: minY,
    width: Math.max(8, maxX - minX),
    height: Math.max(8, maxY - minY),
  };
}
