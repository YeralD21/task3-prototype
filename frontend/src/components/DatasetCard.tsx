import Link from "next/link";
import type { Dataset } from "@/types/dataset";
import { availability, label, number, text, values } from "@/services/display";
export default function DatasetCard({ dataset: d }: { dataset: Dataset }) {
  return (
    <article className="card">
      <div className="card-top">
        <span className="eyebrow">{values(d.modalities)}</span>
        <span className="tag">
          {d.metadata?.synthetic === true
            ? "Muestra sintética"
            : d.metadata?.cataloged === true
              ? "Catalogado"
              : "Catálogo no especificado"}
        </span>
      </div>
      <h2>
        <Link href={"/datasets/" + encodeURIComponent(d.id)}>{d.name}</Link>
      </h2>
      <p className="languages">
        {d.languages
          ?.map((l) => l.name + (l.iso_code ? " (" + l.iso_code + ")" : ""))
          .join(" · ") || "No especificado"}
      </p>
      <p>
        {d.language_varieties
          ?.map(
            (v) =>
              v.name +
              (Array.isArray(v.metadata?.splits)
                ? " · " + v.metadata.splits.join("/")
                : ""),
          )
          .join(" · ") || "Variedad no especificada"}
      </p>
      <div className="tags">
        {d.tasks?.map((t) => (
          <span className="tag" key={t}>
            {label(t)}
          </span>
        )) ?? <span>No especificado</span>}
      </div>
      <dl className="card-meta">
        <div>
          <dt>Publicado por</dt>
          <dd>{text(d.source_organization)}</dd>
        </div>
        <div>
          <dt>Licencia</dt>
          <dd>{d.license.name || "Licencia no determinada"}</dd>
        </div>
      </dl>
      {(d.record_count != null || d.audio_hours != null) && (
        <p className="stats">
          {d.record_count != null && (
            <span>{number(d.record_count)} registros</span>
          )}
          {d.audio_hours != null && (
            <span>{number(d.audio_hours)} h de audio</span>
          )}
        </p>
      )}
      <p className="availability">{availability(d.metadata)}</p>
      <Link
        className="card-link"
        href={"/datasets/" + encodeURIComponent(d.id)}
      >
        Explorar recurso <span aria-hidden="true">↗</span>
        <span className="sr-only">: {d.name}</span>
      </Link>
    </article>
  );
}
