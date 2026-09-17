const labels: Record<string, string> = {
  audio: "Audio",
  text: "Texto",
  parallel_text: "Texto paralelo",
  automatic_speech_recognition: "Reconocimiento de voz (ASR)",
  machine_translation: "Traducción automática",
  language_modeling: "Modelado del lenguaje",
  semantic_search: "Búsqueda semántica",
  linguistic_research: "Investigación lingüística",
  education: "Educación",
};
export const label = (value: string) => labels[value] ?? value;
export const text = (value: string | null | undefined) =>
  value?.trim() || "No especificado";
export const values = (items: string[] | null | undefined) =>
  items?.length ? items.map(label).join(" · ") : "No especificado";
export const number = (value: number | null | undefined) =>
  value == null
    ? "No especificado"
    : new Intl.NumberFormat("es-PE", { maximumFractionDigits: 2 }).format(
        value,
      );
export const permission = (value: boolean | null | undefined) =>
  value == null ? "No especificado" : value ? "Sí" : "No";
export function safeUrl(value: string | null | undefined): string | null {
  try {
    const url = new URL(value ?? "");
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
export function availability(metadata: Record<string, unknown> | null): string {
  if (metadata?.available_locally === true) return "Disponible localmente";
  if (metadata?.cataloged === true && metadata.available_locally === false)
    return "Catalogado — requiere obtener datos desde la fuente oficial";
  return "Disponibilidad local no especificada";
}
