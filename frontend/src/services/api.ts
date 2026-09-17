import type { Dataset, Filters } from "../types/dataset";
export class ApiError extends Error {
  status: number;
  constructor(status: number) {
    super("No se pudo consultar el catálogo.");
    this.status = status;
  }
}
export function queryString(filters: Partial<Filters>): string {
  const params = new URLSearchParams();
  for (const key of ["language", "modality", "task"] as const)
    if (filters[key]) params.set(key, filters[key]!);
  return params.toString();
}
async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const base = process.env.NEXT_PUBLIC_API_URL;
  if (!base)
    throw new Error("Configura NEXT_PUBLIC_API_URL para conectar el catálogo.");
  const response = await fetch(base.replace(/\/$/, "") + "/api/v1" + path, {
    signal,
    cache: "no-store",
  });
  if (!response.ok) throw new ApiError(response.status);
  return response.json() as Promise<T>;
}
export const listDatasets = (filters: Partial<Filters>, signal?: AbortSignal) =>
  request<Dataset[]>("/datasets?" + queryString(filters), signal);
export const getDataset = (id: string, signal?: AbortSignal) =>
  request<Dataset>("/datasets/" + encodeURIComponent(id), signal);
