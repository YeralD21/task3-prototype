import type { RadioAudioStatus } from "../types/dataset";

export interface RadioPosition {
  offset: number;
  index: number;
}

/** Avanza o retrocede un registro sobre el total, cruzando páginas si hace falta. */
export function stepRadio(
  position: RadioPosition,
  direction: "previous" | "next",
  total: number,
  pageSize: number,
): RadioPosition | null {
  const target = position.offset + position.index + (direction === "next" ? 1 : -1);
  if (target < 0 || target >= total) return null;
  return { offset: Math.floor(target / pageSize) * pageSize, index: target % pageSize };
}

export const AUDIO_STATUS_MESSAGES: Record<Exclude<RadioAudioStatus, "available">, string> = {
  missing_file: "El registro referencia audio, pero el archivo no está disponible localmente.",
  unsupported_format: "El formato de este audio no es compatible con el reproductor.",
  unavailable: "El audio de este registro no puede reproducirse desde esta instalación.",
};

export const RADIO_USAGE_NOTE =
  "El audio se reproduce desde la copia local de esta instalación: no se descarga ni se " +
  "redistribuye desde la plataforma. Respete las condiciones del proveedor y no intente " +
  "identificar a las personas que grabaron las voces.";
