import type { AtlasPoint, AtlasReducer } from "../types/dataset";

export interface PlotSize {
  width: number;
  height: number;
  padding: number;
}

export const ATLAS_PLOT: PlotSize = { width: 800, height: 520, padding: 32 };

export interface ScaledPoint {
  point: AtlasPoint;
  cx: number;
  cy: number;
}

const round = (value: number) => Math.round(value * 100) / 100;

/**
 * Convierte coordenadas del Atlas a coordenadas SVG sin modificar los puntos.
 *
 * Usa la misma escala en ambos ejes para no deformar las proporciones de la
 * proyección, centra la nube y respeta el padding. Un eje constante queda en el
 * centro; si ambos son constantes todos los puntos quedan en el centro. El eje
 * vertical se invierte para que `y` crezca hacia arriba.
 */
export function scaleAtlasPoints(
  points: readonly AtlasPoint[],
  size: PlotSize = ATLAS_PLOT,
): ScaledPoint[] {
  const finite = points.filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  if (!finite.length) return [];
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const { x, y } of finite) {
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  const innerWidth = Math.max(size.width - 2 * size.padding, 0);
  const innerHeight = Math.max(size.height - 2 * size.padding, 0);
  const scale = Math.min(
    maxX > minX ? innerWidth / (maxX - minX) : Infinity,
    maxY > minY ? innerHeight / (maxY - minY) : Infinity,
  );
  const factor = Number.isFinite(scale) ? scale : 0;
  const middleX = (minX + maxX) / 2;
  const middleY = (minY + maxY) / 2;
  return finite.map((point) => ({
    point,
    cx: round(size.width / 2 + (point.x - middleX) * factor),
    cy: round(size.height / 2 - (point.y - middleY) * factor),
  }));
}

/** Orden de lectura de izquierda a derecha (y de arriba abajo) para teclado y botones. */
export function readingOrder(points: readonly AtlasPoint[]): string[] {
  return [...points]
    .sort((a, b) => a.x - b.x || b.y - a.y || a.record_id.localeCompare(b.record_id))
    .map((point) => point.record_id);
}

export type AtlasStep = "previous" | "next" | "first" | "last";

export function stepSelection(
  order: readonly string[],
  currentId: string | null,
  step: AtlasStep,
): string | null {
  if (!order.length) return null;
  const position = currentId === null ? -1 : order.indexOf(currentId);
  if (step === "first" || (position === -1 && step === "next")) return order[0];
  if (step === "last" || (position === -1 && step === "previous")) return order[order.length - 1];
  const next = step === "next" ? position + 1 : position - 1;
  return order[Math.min(Math.max(next, 0), order.length - 1)];
}

export const ATLAS_KEY_STEPS: Record<string, AtlasStep> = {
  ArrowRight: "next",
  ArrowDown: "next",
  ArrowLeft: "previous",
  ArrowUp: "previous",
  Home: "first",
  End: "last",
};

export function truncate(value: string, max: number): string {
  const clean = value.trim().replace(/\s+/g, " ");
  return clean.length > max ? clean.slice(0, max - 1).trimEnd() + "…" : clean;
}

export function reducerLabel(reducer: AtlasReducer): string {
  if (reducer === "pca") return "PCA";
  if (reducer === "umap") return "UMAP";
  return reducer.toUpperCase();
}

export function explainedVariance(diagnostics: Record<string, unknown>): number | null {
  const total = diagnostics.explained_variance_ratio_total;
  return typeof total === "number" && Number.isFinite(total) ? total : null;
}

export const formatInteger = (value: number) => new Intl.NumberFormat("es-PE").format(value);

export const formatPercent = (ratio: number) =>
  new Intl.NumberFormat("es-PE", { style: "percent", maximumFractionDigits: 1 }).format(ratio);
