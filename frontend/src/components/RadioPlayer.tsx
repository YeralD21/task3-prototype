"use client";

import { useState } from "react";
import { radioAudioSource } from "@/services/api";
import { recordTranslation, safeUrl, text } from "@/services/display";
import { AUDIO_STATUS_MESSAGES } from "@/services/radio";
import type { RadioItem } from "@/types/dataset";

function AudioElement({ item }: { item: RadioItem }) {
  const [failed, setFailed] = useState(false);
  const source = item.audio_status === "available" ? radioAudioSource(item.audio_url) : null;
  if (item.audio_status !== "available")
    return <p className="notice radio-audio-status">{AUDIO_STATUS_MESSAGES[item.audio_status]}</p>;
  if (!source || failed)
    return (
      <p className="notice radio-audio-status" role="alert">
        No se pudo reproducir el audio de este registro.
      </p>
    );
  return (
    <audio
      className="radio-audio"
      controls
      preload="metadata"
      controlsList="nodownload"
      src={source}
      aria-describedby="radio-transcript"
      onError={() => setFailed(true)}
    >
      Tu navegador no puede reproducir audio.
    </audio>
  );
}

export default function RadioPlayer({
  item, position, total, onPrevious, onNext,
}: {
  item: RadioItem;
  position: number;
  total: number;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const { record } = item;
  const translation = recordTranslation(record.translation);
  const split = typeof record.metadata?.split === "string" ? record.metadata.split : null;
  const provenance = record.provenance;
  const sourceUrl = safeUrl(provenance.source_url);
  return (
    <article className="radio-player" aria-labelledby="radio-position">
      <div className="radio-controls">
        <button type="button" className="secondary" onClick={onPrevious} disabled={position <= 1}>
          ← Registro anterior
        </button>
        <p id="radio-position" className="radio-position" aria-live="polite">
          Registro {position} de {total}
        </p>
        <button type="button" className="secondary" onClick={onNext} disabled={position >= total}>
          Registro siguiente →
        </button>
      </div>
      {/* key: cada registro crea un reproductor nuevo, sin reproducción automática */}
      <AudioElement key={record.id} item={item} />
      <div id="radio-transcript">
        <p className="eyebrow">TRANSCRIPCIÓN</p>
        <p className="record-text">{record.text}</p>
      </div>
      {translation && (
        <div className="translation">
          <span className="eyebrow">TRADUCCIÓN · {text(record.translation_language?.name)}</span>
          <p>{translation}</p>
        </div>
      )}
      <dl className="record-trace">
        <div>
          <dt>Idioma</dt>
          <dd>{text(record.language?.name)} · {text(record.language_code ?? record.language?.iso_code)}</dd>
        </div>
        <div>
          <dt>Variedad</dt>
          <dd>{record.language_variety ? record.language_variety.name : "No especificada"}</dd>
        </div>
        {split && (
          <div>
            <dt>Split</dt>
            <dd>{split}</dd>
          </div>
        )}
        <div>
          <dt>Registro original</dt>
          <dd>{record.source_record_id}</dd>
        </div>
        <div>
          <dt>Dataset</dt>
          <dd>{record.dataset_id}</dd>
        </div>
        <div>
          <dt>Formato</dt>
          <dd>{item.media_type ?? "No determinado"}</dd>
        </div>
      </dl>
      <dl className="record-trace radio-provenance">
        <div>
          <dt>Fuente</dt>
          <dd>{text(provenance.source_name)}</dd>
        </div>
        <div>
          <dt>Organización</dt>
          <dd>{text(provenance.organization)}</dd>
        </div>
        <div>
          <dt>Dataset original</dt>
          <dd>{text(provenance.original_dataset_id)}</dd>
        </div>
        {sourceUrl && (
          <div>
            <dt>URL de la fuente</dt>
            <dd>
              <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                {sourceUrl}
                <span className="sr-only"> (nueva pestaña)</span>
              </a>
            </dd>
          </div>
        )}
        {provenance.notes && (
          <div>
            <dt>Procedencia del registro</dt>
            <dd>{provenance.notes}</dd>
          </div>
        )}
      </dl>
    </article>
  );
}
