import type {
  AtlasResponse,
  CorpusRecordPage,
  Dataset,
  Filters,
  RecordFilters,
  SemanticSearchRequest,
  SemanticSearchResponse,
} from "../types/dataset";
export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail = "") {
    super("No se pudo consultar el catálogo.");
    this.status = status;
    this.detail = detail;
  }
}
export function queryString(filters: Partial<Filters>): string {
  const params = new URLSearchParams();
  for (const key of ["language", "modality", "task"] as const)
    if (filters[key]) params.set(key, filters[key]!);
  return params.toString();
}
async function request<T>(path: string, signal?: AbortSignal, init?: RequestInit): Promise<T> {
  const base = process.env.NEXT_PUBLIC_API_URL;
  if (!base)
    throw new Error("Configura NEXT_PUBLIC_API_URL para conectar el catálogo.");
  const response = await fetch(base.replace(/\/$/, "") + "/api/v1" + path, {
    ...init,
    signal,
    cache: "no-store",
  });
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail = payload && typeof payload === "object" && "detail" in payload &&
      typeof payload.detail === "string" ? payload.detail : "";
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}
export const listDatasets = (filters: Partial<Filters>, signal?: AbortSignal) =>
  request<Dataset[]>("/datasets?" + queryString(filters), signal);
export const getDataset = (id: string, signal?: AbortSignal) =>
  request<Dataset>("/datasets/" + encodeURIComponent(id), signal);

export function buildRecordsPath(id: string, filters: RecordFilters): string {
  const params = new URLSearchParams({
    limit: String(filters.limit),
    offset: String(filters.offset),
  });
  if (filters.q?.trim()) params.set("q", filters.q.trim());
  if (filters.language) params.set("language", filters.language);
  return `/datasets/${encodeURIComponent(id)}/records?${params}`;
}

export const getDatasetRecords = (
  id: string,
  filters: RecordFilters,
  signal?: AbortSignal,
) => request<CorpusRecordPage>(buildRecordsPath(id, filters), signal);

export function semanticSearch(
  datasetId: string, query: string, limit = 10, signal?: AbortSignal,
): Promise<SemanticSearchResponse> {
  if (!query.trim()) return Promise.reject(new Error("Escribe una consulta."));
  const body: SemanticSearchRequest = { dataset_id: datasetId, query: query.trim(), limit };
  return request<SemanticSearchResponse>("/search/semantic", signal, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const SEMANTIC_NOT_LOCAL =
  "Para utilizar búsqueda semántica, primero debe existir una copia local procesada del dataset.";

export function semanticErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "Este dataset ya no está disponible en el catálogo.";
    if (error.status === 503) return "El modelo de búsqueda semántica no está disponible. Contacta con quien administra el servicio.";
    if (error.status === 409) {
      if (error.detail.includes("not available locally")) return SEMANTIC_NOT_LOCAL;
      if (error.detail.includes("is stale")) return "El índice semántico está desactualizado y debe reconstruirse.";
      if (error.detail.includes("was not found")) return "Este dataset está disponible localmente, pero todavía no tiene un índice semántico construido.";
      if (error.detail.includes("does not match")) return "El modelo configurado no coincide con el índice semántico. Es necesario revisar la configuración o reconstruirlo.";
    }
  }
  return "No pudimos realizar la búsqueda semántica. Comprueba la conexión e inténtalo nuevamente.";
}

export const ATLAS_LIMITS = [250, 500, 1000, 2000] as const;
export const ATLAS_DEFAULT_LIMIT = 1000;

export function buildAtlasPath(datasetId: string, limit: number): string {
  const params = new URLSearchParams({ limit: String(limit) });
  return `/datasets/${encodeURIComponent(datasetId)}/atlas?${params}`;
}

export const getDatasetAtlas = (
  datasetId: string,
  limit: number = ATLAS_DEFAULT_LIMIT,
  signal?: AbortSignal,
) => request<AtlasResponse>(buildAtlasPath(datasetId, limit), signal);

export const ATLAS_NOT_LOCAL =
  "Para ver el Atlas Vivo, primero debe existir una copia local procesada del dataset.";
export const ATLAS_MISSING = "Este dataset todavía no tiene un Atlas construido.";
export const ATLAS_STALE = "El Atlas está desactualizado y debe reconstruirse.";
export const ATLAS_NO_INDEX =
  "Este dataset todavía no tiene un índice semántico. Es necesario construirlo antes que el Atlas.";

export function atlasErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "Este dataset ya no está disponible en el catálogo.";
    if (error.status === 409) {
      if (error.detail.includes("not available locally")) return ATLAS_NOT_LOCAL;
      if (error.detail.startsWith("Semantic index")) return ATLAS_NO_INDEX;
      if (error.detail.includes("is stale")) return ATLAS_STALE;
      if (error.detail.includes("was not found")) return ATLAS_MISSING;
    }
  }
  return "No pudimos cargar el Atlas. Comprueba la conexión e inténtalo nuevamente.";
}
