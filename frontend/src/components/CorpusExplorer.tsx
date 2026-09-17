"use client";

import { useEffect, useState } from "react";
import { getDatasetRecords } from "@/services/api";
import { emptyRecordsMessage, safeUrl } from "@/services/display";
import type { CorpusRecordPage, Dataset } from "@/types/dataset";
import CorpusRecordCard from "./CorpusRecordCard";
import Pagination from "./Pagination";
import RecordSearch from "./RecordSearch";

const LIMIT = 20;

export default function CorpusExplorer({ dataset }: { dataset: Dataset }) {
  const [draftQuery, setDraftQuery] = useState("");
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<CorpusRecordPage | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    getDatasetRecords(
      dataset.id,
      { q: query, language, limit: LIMIT, offset },
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) {
          setPage(result);
          setState("ready");
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setState("error");
      });
    return () => controller.abort();
  }, [dataset.id, language, offset, query, retry]);

  const sourceUrl = safeUrl(
    dataset.source_url ?? dataset.provenance.source_url,
  );
  const submit = () => {
    setOffset(0);
    setQuery(draftQuery.trim());
  };
  return (
    <section className="explorer" aria-labelledby="explorer-title">
      <div className="explorer-title">
        <div>
          <p className="eyebrow">CORPUS EXPLORER</p>
          <h2 id="explorer-title">Explorar registros</h2>
        </div>
        <p>Búsqueda textual simple sobre el texto y su traducción.</p>
      </div>
      <RecordSearch
        query={draftQuery}
        language={language}
        languages={dataset.languages}
        onQueryChange={setDraftQuery}
        onLanguageChange={(value) => {
          setLanguage(value);
          setOffset(0);
        }}
        onSubmit={submit}
      />
      <div aria-live="polite" aria-busy={state === "loading"}>
        {state === "loading" && (
          <div className="notice">Cargando registros…</div>
        )}
        {state === "error" && (
          <div className="notice" role="alert">
            <h3>No pudimos consultar los registros</h3>
            <p>Comprueba que la API esté disponible e inténtalo nuevamente.</p>
            <button onClick={() => setRetry((value) => value + 1)}>
              Reintentar
            </button>
          </div>
        )}
        {state === "ready" && page?.total === 0 && (
          <div className="notice empty-records">
            <h3>
              {emptyRecordsMessage(
                dataset.metadata?.available_locally,
                Boolean(query || language),
              )}
            </h3>
            {!query &&
              !language &&
              dataset.metadata?.available_locally === false && (
                <p>
                  Obtén el recurso desde la fuente oficial y colócalo en la ruta
                  indicada por su documentación.
                </p>
              )}
            {sourceUrl && (
              <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                Ver fuente oficial ↗
              </a>
            )}
          </div>
        )}
        {state === "ready" && page && page.total > 0 && (
          <>
            <div className="record-list">
              {page.items.map((record) => (
                <CorpusRecordCard key={record.id} record={record} />
              ))}
            </div>
            <Pagination
              total={page.total}
              limit={page.limit}
              offset={page.offset}
              onChange={setOffset}
            />
          </>
        )}
      </div>
    </section>
  );
}
