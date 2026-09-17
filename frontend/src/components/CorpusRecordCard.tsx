import { recordTranslation, text } from "@/services/display";
import type { CorpusRecord } from "@/types/dataset";

export default function CorpusRecordCard({ record }: { record: CorpusRecord }) {
  const translation = recordTranslation(record.translation);
  const split =
    typeof record.metadata?.split === "string" ? record.metadata.split : null;
  return (
    <article className="record-card">
      <div className="record-heading">
        <span className="eyebrow">
          {text(record.language?.name)} ·{" "}
          {text(record.language_code ?? record.language?.iso_code)}
        </span>
        {split && <span className="tag">Split: {split}</span>}
      </div>
      <p className="record-text">{record.text}</p>
      {record.language_variety && (
        <p>Variedad: {record.language_variety.name}</p>
      )}
      {translation && (
        <div className="translation">
          <span className="eyebrow">
            TRADUCCIÓN · {text(record.translation_language?.name)}
          </span>
          <p>{translation}</p>
        </div>
      )}
      <dl className="record-trace">
        <div>
          <dt>Registro original</dt>
          <dd>{record.source_record_id}</dd>
        </div>
        <div>
          <dt>Dataset</dt>
          <dd>{record.dataset_id}</dd>
        </div>
        <div>
          <dt>Fuente</dt>
          <dd>
            {text(
              record.provenance.source_name ?? record.provenance.organization,
            )}
          </dd>
        </div>
        <div>
          <dt>Audio</dt>
          <dd>
            {record.audio_id
              ? `Disponible · ${record.audio_id}`
              : "No disponible"}
          </dd>
        </div>
      </dl>
    </article>
  );
}
