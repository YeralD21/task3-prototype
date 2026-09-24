import { useMemo, type KeyboardEvent } from "react";
import {
  ATLAS_KEY_STEPS,
  explainedVariance,
  formatInteger,
  formatPercent,
  readingOrder,
  reducerLabel,
  scaleAtlasPoints,
  stepSelection,
  type AtlasStep,
} from "@/services/atlas";
import type { AtlasResponse } from "@/types/dataset";
import AtlasPlot from "./AtlasPlot";
import AtlasPointDetails from "./AtlasPointDetails";

export type AtlasState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "unavailable"; message: string }
  | { status: "error"; message: string }
  | { status: "ready"; response: AtlasResponse };

interface AtlasViewProps {
  state: AtlasState;
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (recordId: string | null) => void;
  onHover: (recordId: string | null) => void;
  onRetry: () => void;
}

function AtlasSummary({ response }: { response: AtlasResponse }) {
  const variance = response.reducer === "pca" ? explainedVariance(response.diagnostics) : null;
  return (
    <p className="atlas-meta">
      <span>Reductor: {reducerLabel(response.reducer)}</span>
      <span>
        {formatInteger(response.returned_records)} de {formatInteger(response.total_records)} puntos visibles
        {response.sampling.applied && " (muestra reproducible)"}
      </span>
      {variance !== null && (
        <span>Varianza conservada por los 2 ejes: {formatPercent(variance)}</span>
      )}
    </p>
  );
}

function ReadyAtlas({ response, selectedId, hoveredId, onSelect, onHover }:
  Omit<AtlasViewProps, "state" | "onRetry"> & { response: AtlasResponse }) {
  const scaled = useMemo(() => scaleAtlasPoints(response.items), [response]);
  const order = useMemo(() => readingOrder(response.items), [response]);
  const selected = response.items.find((point) => point.record_id === selectedId) ?? null;
  const step = (direction: AtlasStep) => onSelect(stepSelection(order, selectedId, direction));
  const handleKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    if (event.key === "Escape") {
      onSelect(null);
      return;
    }
    const direction = ATLAS_KEY_STEPS[event.key];
    if (!direction) return;
    event.preventDefault();
    step(direction);
  };
  if (!response.items.length)
    return <p className="notice">El Atlas no contiene puntos para mostrar.</p>;
  return (
    <>
      <AtlasSummary response={response} />
      <p id="atlas-keyboard-help" className="atlas-help">
        Pasa el cursor sobre un punto para ver un resumen y haz clic para seleccionarlo.
        Con el mapa enfocado, las flechas recorren los puntos de izquierda a derecha y Escape
        limpia la selección.
      </p>
      <div className="atlas-layout">
        <AtlasPlot
          points={scaled}
          selectedId={selectedId}
          hoveredId={hoveredId}
          onSelect={onSelect}
          onHover={onHover}
          onKeyDown={handleKeyDown}
        />
        <AtlasPointDetails
          point={selected}
          position={selected ? order.indexOf(selected.record_id) + 1 : 0}
          total={order.length}
          onPrevious={() => step("previous")}
          onNext={() => step("next")}
        />
      </div>
    </>
  );
}

export default function AtlasView({ state, onRetry, ...interaction }: AtlasViewProps) {
  return (
    <div aria-live="polite" aria-busy={state.status === "loading"}>
      {state.status === "loading" && <p className="notice">Cargando el Atlas…</p>}
      {state.status === "unavailable" && <p className="notice">{state.message}</p>}
      {state.status === "error" && (
        <div className="notice" role="alert">
          <p>{state.message}</p>
          <button type="button" onClick={onRetry}>Reintentar</button>
        </div>
      )}
      {state.status === "ready" && <ReadyAtlas response={state.response} {...interaction} />}
    </div>
  );
}
