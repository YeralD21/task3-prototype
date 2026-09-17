import type { Dataset } from "@/types/dataset";
import {
  availability,
  number,
  permission,
  safeUrl,
  text,
  values,
} from "@/services/display";
function Row({ name, value }: { name: string; value: string }) {
  return (
    <div>
      <dt>{name}</dt>
      <dd>{value}</dd>
    </div>
  );
}
export default function DatasetMetadata({ dataset: d }: { dataset: Dataset }) {
  const url = safeUrl(d.source_url ?? d.provenance.source_url);
  return (
    <>
      <div className="detail-title">
        <p className="eyebrow">FICHA DEL RECURSO</p>
        <h1>{d.name}</h1>
        <p>
          {values(d.modalities)} · {values(d.tasks)}
        </p>
      </div>
      <section className="source-panel">
        <div>
          <p className="eyebrow">FUENTE Y PROCEDENCIA</p>
          <h2>{text(d.source_organization ?? d.provenance.organization)}</h2>
          <p>{text(d.provenance.source_name)}</p>
        </div>
        {url && (
          <a
            className="button"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Ver fuente oficial ↗
            <span className="sr-only"> (nueva pestaña)</span>
          </a>
        )}
        <dl>
          <Row
            name="URL oficial"
            value={text(d.source_url ?? d.provenance.source_url)}
          />
          <Row name="Cita" value={text(d.citation ?? d.provenance.citation)} />
          <Row
            name="Procedencia documentada"
            value={text(d.provenance.notes)}
          />
        </dl>
      </section>
      <div className="detail-grid">
        <div>
          <section className="panel">
            <h2>Resumen</h2>
            <p>{text(d.description)}</p>
            {d.metadata?.synthetic === true && (
              <p className="warning">
                Datos sintéticos, exclusivamente para desarrollo.
              </p>
            )}
          </section>
          <section className="panel">
            <h2>Idioma y variedad</h2>
            <dl>
              <Row
                name="Idiomas"
                value={
                  d.languages
                    ?.map((l) => l.name + " · " + text(l.iso_code))
                    .join(", ") || "No especificado"
                }
              />
              <Row name="Países" value={values(d.countries)} />
              <Row name="Regiones" value={values(d.regions)} />
            </dl>
            {d.language_varieties?.length ? (
              d.language_varieties.map((v) => (
                <div key={v.id}>
                  <h3>{v.name}</h3>
                  <p>Código: {text(v.language_code)}</p>
                  {Array.isArray(v.metadata?.splits) && (
                    <p>
                      Documentada solo para: {v.metadata.splits.join(", ")}.
                    </p>
                  )}
                  {typeof v.metadata?.notes === "string" && (
                    <p>{v.metadata.notes}</p>
                  )}
                </div>
              ))
            ) : (
              <p>Variedad no especificada.</p>
            )}
          </section>
          <section className="panel">
            <h2>Modalidades y usos potenciales</h2>
            <dl>
              <Row name="Modalidades" value={values(d.modalities)} />
              <Row name="Usos potenciales" value={values(d.tasks)} />
              <Row name="Dominios" value={values(d.domains)} />
            </dl>
          </section>
          <section className="panel">
            <h2>Estadísticas</h2>
            <dl className="stat-grid">
              <Row name="Registros" value={number(d.record_count)} />
              <Row name="Horas de audio" value={number(d.audio_hours)} />
              <Row
                name="Hablantes / contribuyentes"
                value={number(d.speaker_count)}
              />
              <Row name="Tokens" value={number(d.token_count)} />
            </dl>
            {typeof d.metadata?.release_version === "string" && (
              <p>Versión de la fuente: {d.metadata.release_version}</p>
            )}
          </section>
        </div>
        <div>
          <section className="panel license">
            <p className="eyebrow">REUTILIZACIÓN RESPONSABLE</p>
            <h2>Licencia y condiciones</h2>
            <h3>{d.license.name || "Licencia no determinada"}</h3>
            {!d.license.name && (
              <p className="warning">
                No se han confirmado los permisos de reutilización. Consulta las
                condiciones con la fuente.
              </p>
            )}
            <dl>
              <Row
                name="Uso comercial"
                value={permission(d.license.commercial_use)}
              />
              <Row
                name="Redistribución"
                value={permission(d.license.redistribution)}
              />
              <Row
                name="Obras derivadas"
                value={permission(d.license.derivatives)}
              />
              <Row
                name="Atribución requerida"
                value={permission(d.license.attribution_required)}
              />
            </dl>
            <p>{text(d.license.notes)}</p>
            {safeUrl(d.license.url) && (
              <a
                href={safeUrl(d.license.url)!}
                target="_blank"
                rel="noopener noreferrer"
              >
                Consultar licencia (nueva pestaña) ↗
              </a>
            )}
          </section>
          <section className="panel">
            <h2>Disponibilidad local</h2>
            <p>{availability(d.metadata)}</p>
            <p>
              Estado de catálogo:{" "}
              {permission(
                typeof d.metadata?.cataloged === "boolean"
                  ? d.metadata.cataloged
                  : null,
              )}
              .
            </p>
            <p>
              El acceso al corpus se gestiona con su proveedor. Este sitio no
              ofrece descargas de corpus.
            </p>
          </section>
          <section className="panel">
            <h2>Limitaciones y notas</h2>
            <p>
              {typeof d.metadata?.notes === "string"
                ? d.metadata.notes
                : "No se han registrado notas adicionales."}
            </p>
            <p>
              La presencia en el catálogo no garantiza calidad, cobertura o
              adecuación para todos los usos. Revisa la documentación original.
            </p>
          </section>
        </div>
      </div>
    </>
  );
}
