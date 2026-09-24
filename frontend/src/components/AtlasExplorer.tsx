"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  ATLAS_DEFAULT_LIMIT,
  ATLAS_LIMITS,
  ATLAS_NOT_LOCAL,
  atlasErrorMessage,
  getDatasetAtlas,
} from "@/services/api";
import type { Dataset } from "@/types/dataset";
import AtlasView, { type AtlasState } from "./AtlasView";

export const ATLAS_EXPLANATION =
  "Cada punto representa un registro del corpus. Los puntos cercanos tienen representaciones " +
  "semánticas similares, pero la visualización 2D es una aproximación y pierde información.";

export default function AtlasExplorer({ dataset }: { dataset: Dataset }) {
  const notLocal = dataset.metadata?.available_locally === false;
  const [opened, setOpened] = useState(false);
  const [limit, setLimit] = useState<number>(ATLAS_DEFAULT_LIMIT);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<AtlasState>(
    notLocal ? { status: "unavailable", message: ATLAS_NOT_LOCAL } : { status: "idle" },
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  useEffect(() => {
    if (!opened || notLocal) return;
    const controller = new AbortController();
    setState({ status: "loading" });
    setHoveredId(null);
    getDatasetAtlas(dataset.id, limit, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setState({ status: "ready", response });
        setSelectedId((current) =>
          response.items.some((point) => point.record_id === current) ? current : null,
        );
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        const known = error instanceof ApiError && (error.status === 404 || error.status === 409);
        const message = atlasErrorMessage(error);
        setState(known ? { status: "unavailable", message } : { status: "error", message });
      });
    return () => controller.abort();
  }, [dataset.id, limit, attempt, opened, notLocal]);

  return (
    <section className="explorer" id="atlas" aria-labelledby="atlas-title">
      <div className="explorer-title">
        <div>
          <p className="eyebrow">ATLAS VIVO</p>
          <h2 id="atlas-title">Atlas Vivo</h2>
        </div>
        <p>{ATLAS_EXPLANATION}</p>
      </div>
      <p className="atlas-help">
        La cercanía no implica significado idéntico, y los ejes no tienen una interpretación
        lingüística. La calidad depende del modelo de embeddings, que no está evaluado para
        todas las lenguas y variedades.
      </p>
      {!notLocal && (
        <div className="atlas-controls">
          <label htmlFor="atlas-limit">
            Puntos a solicitar
            <select
              id="atlas-limit"
              value={limit}
              disabled={state.status === "loading"}
              onChange={(event) => setLimit(Number(event.target.value))}
            >
              {ATLAS_LIMITS.map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
          {!opened && (
            <button type="button" onClick={() => setOpened(true)}>Abrir Atlas Vivo</button>
          )}
        </div>
      )}
      <AtlasView
        state={state}
        selectedId={selectedId}
        hoveredId={hoveredId}
        onSelect={setSelectedId}
        onHover={setHoveredId}
        onRetry={() => setAttempt((value) => value + 1)}
      />
    </section>
  );
}
