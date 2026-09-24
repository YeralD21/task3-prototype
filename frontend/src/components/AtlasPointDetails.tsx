import { safeUrl } from "@/services/display";
import type { AtlasPoint } from "@/types/dataset";
import CorpusRecordCard from "./CorpusRecordCard";

interface AtlasPointDetailsProps {
  point: AtlasPoint | null;
  position: number;
  total: number;
  onPrevious: () => void;
  onNext: () => void;
}

const coordinate = (value: number) =>
  value.toLocaleString("es", { maximumFractionDigits: 3 });

function Provenance({ point }: { point: AtlasPoint }) {
  const provenance = point.record.provenance;
  const url = safeUrl(provenance.source_url);
  const rows: [string, string | null][] = [
    ["Organización", provenance.organization],
    ["Dataset original", provenance.original_dataset_id],
    ["Cita", provenance.citation],
    ["Obtenido", provenance.retrieved_at],
    ["Notas", provenance.notes],
  ];
  return (
    <dl className="atlas-provenance">
      {rows.filter(([, value]) => value?.trim()).map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
      {url && (
        <div>
          <dt>Fuente</dt>
          <dd><a href={url} rel="noreferrer" target="_blank">{url}</a></dd>
        </div>
      )}
      <div>
        <dt>Coordenadas en el mapa</dt>
        <dd>x = {coordinate(point.x)} · y = {coordinate(point.y)}</dd>
      </div>
    </dl>
  );
}

export default function AtlasPointDetails({
  point, position, total, onPrevious, onNext,
}: AtlasPointDetailsProps) {
  return (
    <aside className="atlas-details" aria-labelledby="atlas-details-title">
      <div className="atlas-details-heading">
        <h3 id="atlas-details-title">Registro seleccionado</h3>
        <div className="atlas-steps">
          <button type="button" className="secondary" onClick={onPrevious} disabled={!total}>
            Punto anterior
          </button>
          <button type="button" className="secondary" onClick={onNext} disabled={!total}>
            Punto siguiente
          </button>
        </div>
      </div>
      <div aria-live="polite">
        {point ? (
          <>
            <p className="atlas-position">
              Punto {position} de {total}, ordenados de izquierda a derecha.
            </p>
            <CorpusRecordCard record={point.record} />
            <Provenance point={point} />
          </>
        ) : (
          <p className="atlas-empty-selection">
            Selecciona un punto del mapa para ver su texto, traducción y procedencia.
            También puedes usar los botones o las flechas del teclado sobre el mapa.
          </p>
        )}
      </div>
    </aside>
  );
}
