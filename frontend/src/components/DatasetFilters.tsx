import type { Filters } from "@/types/dataset";
export default function DatasetFilters({
  filters,
  onChange,
}: {
  filters: Filters;
  onChange: (value: Filters) => void;
}) {
  return (
    <section className="filters" aria-label="Filtrar recursos">
      <label>
        Idioma
        <select
          value={filters.language}
          onChange={(e) => onChange({ ...filters, language: e.target.value })}
        >
          <option value="">Todos los idiomas</option>
          <option value="qxp">Quechua — Puno (qxp)</option>
          <option value="aym">Aymara (aym)</option>
        </select>
      </label>
      <label>
        Tipo de recurso
        <select
          value={filters.modality}
          onChange={(e) => onChange({ ...filters, modality: e.target.value })}
        >
          <option value="">Todas las modalidades</option>
          <option value="audio">Audio</option>
          <option value="text">Texto</option>
          <option value="parallel_text">Texto paralelo</option>
        </select>
      </label>
      <label>
        Uso potencial
        <select
          value={filters.task}
          onChange={(e) => onChange({ ...filters, task: e.target.value })}
        >
          <option value="">Todos los usos</option>
          <option value="automatic_speech_recognition">
            Reconocimiento de voz (ASR)
          </option>
          <option value="machine_translation">Traducción automática</option>
        </select>
      </label>
      <button
        className="secondary"
        onClick={() => onChange({ language: "", modality: "", task: "" })}
      >
        Limpiar filtros
      </button>
    </section>
  );
}
