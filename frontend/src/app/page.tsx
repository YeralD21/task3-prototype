"use client";
import { useEffect, useState } from "react";
import DatasetCard from "@/components/DatasetCard";
import DatasetFilters from "@/components/DatasetFilters";
import { listDatasets } from "@/services/api";
import type { Dataset, Filters } from "@/types/dataset";
export default function Home() {
  const [filters, setFilters] = useState<Filters>({
    language: "",
    modality: "",
    task: "",
  });
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState("loading");
    listDatasets(filters, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setDatasets(data);
          setState("ready");
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setState("error");
      });
    return () => controller.abort();
  }, [filters, retry]);
  return (
    <>
      <section className="hero">
        <p className="eyebrow">CATÁLOGO DE DATOS · QUECHUA & AYMARA</p>
        <h1>
          Recursos lingüísticos
          <br />
          <em>indígenas</em>
        </h1>
        <p className="intro">
          Explora datasets de Quechua y Aymara para aprendizaje, investigación y
          desarrollo de tecnologías del lenguaje.
        </p>
        <p className="hero-note">
          Conoce su contenido, su origen y las condiciones para utilizarlos.
        </p>
      </section>
      <DatasetFilters filters={filters} onChange={setFilters} />
      <section
        className="results"
        aria-label="Resultados del catálogo"
        aria-busy={state === "loading"}
      >
        <div className="section-heading">
          <h2>Explora la colección</h2>
          <span role="status">
            {state === "ready"
              ? datasets.length + " recursos encontrados"
              : state === "loading"
                ? "Consultando catálogo…"
                : "Catálogo no disponible"}
          </span>
        </div>
        {state === "loading" && (
          <div className="notice">Cargando los recursos lingüísticos…</div>
        )}
        {state === "error" && (
          <div className="notice" role="alert">
            <h3>No pudimos conectar con el catálogo</h3>
            <p>Comprueba que la API esté disponible e inténtalo de nuevo.</p>
            <button onClick={() => setRetry(retry + 1)}>Reintentar</button>
          </div>
        )}
        {state === "ready" && !datasets.length && (
          <div className="notice">
            <h3>No hay recursos con estos filtros</h3>
            <p>
              Prueba otro idioma o elimina los filtros para explorar la
              colección.
            </p>
          </div>
        )}
        {state === "ready" && (
          <div className="grid">
            {datasets.map((d) => (
              <DatasetCard key={d.id} dataset={d} />
            ))}
          </div>
        )}
      </section>
      <aside className="footnote">
        <strong>Un catálogo, muchas procedencias.</strong> Cada recurso mantiene
        su idioma, variedad y fuente. Estar catalogado no significa que los
        datos estén alojados aquí ni que su reutilización esté autorizada.
      </aside>
    </>
  );
}
