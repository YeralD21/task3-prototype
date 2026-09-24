import { safeUrl, text } from "@/services/display";
import {
  ARTIFACT_STATUS,
  availabilityLabel,
  permissionStatus,
  VARIETY_STATUS,
} from "@/services/playbook";
import type { DatasetPlaybook } from "@/types/dataset";

function Row({ name, children }: { name: string; children: React.ReactNode }) {
  return (
    <div>
      <dt>{name}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function Link({ value }: { value: string | null }) {
  const url = safeUrl(value);
  return url ? (
    <a href={url} target="_blank" rel="noopener noreferrer">
      {url}
      <span className="sr-only"> (nueva pestaña)</span>
    </a>
  ) : (
    <>No especificado</>
  );
}

/** Contexto común a todas las tareas: licencia, variedad, procedencia y estado local. */
export default function PlaybookContext({ playbook }: { playbook: DatasetPlaybook }) {
  const { license, variety, provenance, local } = playbook;
  return (
    <div className="playbook-context">
      <section className="panel license" aria-labelledby="playbook-license-title">
        <h3 id="playbook-license-title">Licencia registrada</h3>
        <p className="playbook-license-name">{license.name || "Licencia no determinada"}</p>
        {!license.known && (
          <p className="warning">
            Según la metadata registrada, la licencia no está determinada. El permiso no puede
            determinarse con la información disponible.
          </p>
        )}
        <dl>
          <Row name="Uso comercial">{permissionStatus(license.commercial_use)}</Row>
          <Row name="Redistribución">{permissionStatus(license.redistribution)}</Row>
          <Row name="Obras derivadas">{permissionStatus(license.derivatives)}</Row>
          <Row name="Atribución requerida">{permissionStatus(license.attribution_required)}</Row>
          {license.url && <Row name="Texto de la licencia"><Link value={license.url} /></Row>}
        </dl>
      </section>
      <section className="panel" aria-labelledby="playbook-variety-title">
        <h3 id="playbook-variety-title">Idioma y variedad</h3>
        <dl>
          <Row name="Idiomas">
            {playbook.languages.map((item) => `${item.name} (${text(item.iso_code)})`).join(", ") ||
              "No especificado"}
          </Row>
          <Row name="Variedad">
            {variety.varieties.length
              ? variety.varieties.map((item) => `${item.name} (${item.id})`).join(", ")
              : "No especificada"}
          </Row>
          <Row name="Alcance">{VARIETY_STATUS[variety.status]}</Row>
        </dl>
        <p className={variety.status === "specified" ? undefined : "warning"}>{variety.note}</p>
      </section>
      <section className="panel" aria-labelledby="playbook-provenance-title">
        <h3 id="playbook-provenance-title">Procedencia</h3>
        <dl>
          <Row name="Publica">{text(provenance.source_organization)}</Row>
          <Row name="Fuente original">{text(provenance.provenance.source_name)}</Row>
          <Row name="Identificador original">{text(provenance.provenance.original_dataset_id)}</Row>
          <Row name="URL de la fuente"><Link value={provenance.source_url} /></Row>
          {provenance.documentation_url && (
            <Row name="Documentación"><Link value={provenance.documentation_url} /></Row>
          )}
          <Row name="Cita">{text(provenance.citation)}</Row>
        </dl>
      </section>
      <section className="panel" aria-labelledby="playbook-local-title">
        <h3 id="playbook-local-title">Estado en esta instalación</h3>
        <dl>
          <Row name="Copia local">{availabilityLabel(local.available_locally)}</Row>
          {local.available_locally === true && (
            <>
              <Row name="Índice semántico">{ARTIFACT_STATUS[local.semantic_index]}</Row>
              <Row name="Atlas Vivo">{ARTIFACT_STATUS[local.atlas]}</Row>
            </>
          )}
        </dl>
      </section>
    </div>
  );
}
