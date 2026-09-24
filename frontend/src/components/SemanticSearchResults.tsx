import type { SemanticSearchResponse } from "../types/dataset";
import CorpusRecordCard from "./CorpusRecordCard";

export type SemanticSearchState =
  | { status: "idle" }
  | { status: "loading"; query: string }
  | { status: "error"; message: string }
  | { status: "ready"; response: SemanticSearchResponse };

export default function SemanticSearchResults({ state }: { state: SemanticSearchState }) {
  return (
    <div aria-live="polite" aria-busy={state.status === "loading"}>
      {state.status === "loading" && <p className="notice">Buscando registros relacionados…</p>}
      {state.status === "error" && <p className="notice" role="alert">{state.message}</p>}
      {state.status === "ready" && (
        <>
          <p>{state.response.items.length} resultados para «{state.response.query}».</p>
          {state.response.items.length === 0 ? (
            <p className="notice">No se encontraron registros relacionados con esta consulta.</p>
          ) : (
            <div className="record-list">
              {state.response.items.map(({ record, score }) => (
                <div key={record.id}>
                  <p className="semantic-score">
                    Similitud semántica: {(score * 100).toLocaleString("es", { maximumFractionDigits: 1 })}%
                  </p>
                  <CorpusRecordCard record={record} />
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
