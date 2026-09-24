import type {
  LocalArtifactStatus,
  PlaybookCompatibility,
  PlaybookTaskId,
  PlaybookVariety,
} from "../types/dataset";

export const TASK_LABELS: Record<PlaybookTaskId, string> = {
  machine_translation: "Traducción automática",
  automatic_speech_recognition: "Reconocimiento automático del habla (ASR)",
  semantic_search: "Búsqueda semántica",
  corpus_exploration: "Exploración del corpus",
  language_modeling: "Modelado del lenguaje",
  linguistic_research: "Investigación lingüística",
  educational_use: "Uso educativo",
};

/** Texto y símbolo explícitos para no depender del color. */
export const COMPATIBILITY: Record<
  PlaybookCompatibility,
  { label: string; symbol: string; description: string }
> = {
  compatible: {
    label: "Compatible",
    symbol: "✓",
    description: "Técnicamente compatible según la metadata registrada.",
  },
  potential: {
    label: "Potencial",
    symbol: "◐",
    description: "Podría servir, pero faltan datos o condiciones por confirmar.",
  },
  not_applicable: {
    label: "No aplicable",
    symbol: "—",
    description: "Los datos registrados no cubren los requisitos de esta tarea.",
  },
  unknown: {
    label: "Desconocido",
    symbol: "?",
    description: "La metadata no permite determinar la compatibilidad.",
  },
};

/** `null` significa no determinado: nunca se convierte en sí o no. */
export function permissionStatus(value: boolean | null): string {
  if (value === null) return "No determinado";
  return value ? "Sí" : "No";
}

export const VARIETY_STATUS: Record<PlaybookVariety["status"], string> = {
  specified: "Variedad registrada",
  partial: "Variedad documentada solo en parte del corpus",
  unspecified: "No especificada",
};

export function availabilityLabel(value: boolean | null): string {
  if (value === null) return "No determinado";
  return value ? "Copia local procesada disponible" : "No disponible localmente";
}

export const ARTIFACT_STATUS: Record<LocalArtifactStatus, string> = {
  available: "Disponible",
  stale: "Desactualizado",
  missing: "No construido",
  unknown: "No determinado",
};
