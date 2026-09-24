"use client";

import { useEffect, useRef, useState } from "react";
import { semanticSearch, semanticErrorMessage, SEMANTIC_NOT_LOCAL } from "../services/api";
import type { Dataset } from "../types/dataset";
import SemanticSearchResults, { type SemanticSearchState } from "./SemanticSearchResults";

export default function SemanticSearch({ dataset }: { dataset: Dataset }) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<SemanticSearchState>({ status: "idle" });
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  const notLocal = dataset.metadata?.available_locally === false;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim() || notLocal || pending.current) return;
    const controller = new AbortController();
    pending.current = controller;
    setState({ status: "loading", query: query.trim() });
    try {
      const response = await semanticSearch(dataset.id, query, 10, controller.signal);
      if (!controller.signal.aborted) setState({ status: "ready", response });
    } catch (error: unknown) {
      if (!controller.signal.aborted) setState({ status: "error", message: semanticErrorMessage(error) });
    } finally {
      if (pending.current === controller) pending.current = null;
    }
  }

  return (
    <section className="explorer" aria-labelledby="semantic-title">
      <div className="explorer-title">
        <div>
          <p className="eyebrow">CORPUS EXPLORER</p>
          <h2 id="semantic-title">Búsqueda semántica</h2>
        </div>
        <p>La búsqueda textual encuentra coincidencias de palabras.
          La semántica busca registros conceptualmente relacionados mediante embeddings.</p>
      </div>
      <p id="semantic-help">Hasta 10 resultados sobre el texto original.
        La similitud semántica no es una probabilidad de acierto y puede ser negativa.
        La calidad depende del modelo y del idioma.</p>
      {notLocal ? <p className="notice">{SEMANTIC_NOT_LOCAL}</p> : (
        <form className="record-search semantic-form" onSubmit={submit}>
          <label htmlFor="semantic-query">Consulta semántica
            <input id="semantic-query" value={query} aria-describedby="semantic-help"
              onChange={(event) => setQuery(event.target.value)}
              disabled={state.status === "loading"} />
          </label>
          <button type="submit" disabled={!query.trim() || state.status === "loading"}>
            {state.status === "loading" ? "Buscando…" : "Buscar semánticamente"}
          </button>
        </form>
      )}
      <SemanticSearchResults state={state} />
    </section>
  );
}
