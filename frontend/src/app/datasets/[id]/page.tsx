"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, getDataset } from "@/services/api";
import DatasetMetadata from "@/components/DatasetMetadata";
import CorpusExplorer from "@/components/CorpusExplorer";
import SemanticSearch from "@/components/SemanticSearch";
import type { Dataset } from "@/types/dataset";
export default function Detail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [state, setState] = useState("loading");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    getDataset(id, controller.signal)
      .then((d) => {
        if (!controller.signal.aborted) {
          setDataset(d);
          setState("ready");
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted)
          setState(
            e instanceof ApiError && e.status === 404 ? "missing" : "error",
          );
      });
    return () => controller.abort();
  }, [id, retry]);
  return (
    <div className="detail">
      <Link className="back" href="/">
        ← Volver al catálogo
      </Link>
      {state === "loading" && (
        <p className="notice" role="status">
          Cargando el recurso…
        </p>
      )}
      {state === "missing" && (
        <div className="notice">
          <h1>Dataset no encontrado</h1>
          <p>
            Este recurso no figura en el catálogo. Vuelve a la colección para
            explorar los disponibles.
          </p>
        </div>
      )}
      {state === "error" && (
        <div className="notice" role="alert">
          <h1>No pudimos cargar el recurso</h1>
          <p>Comprueba que la API esté disponible e inténtalo de nuevo.</p>
          <button onClick={() => setRetry(retry + 1)}>Reintentar</button>
        </div>
      )}
      {state === "ready" && dataset && (
        <>
          <DatasetMetadata dataset={dataset} />
          <CorpusExplorer dataset={dataset} />
          <SemanticSearch key={dataset.id} dataset={dataset} />
        </>
      )}
    </div>
  );
}
