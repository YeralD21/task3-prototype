"""Vista pública de CorpusRecord para respuestas HTTP.

El modelo canónico almacenado en data/processed no se modifica: la ingestión conserva
todo lo que produce el adaptador. Esta vista se aplica solo al construir respuestas,
retirando el identificador seudónimo del hablante y atributos que ayudarían a
identificarlo, que ninguna funcionalidad pública necesita.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.canonical import (
    CanonicalModel,
    CorpusRecord,
    Language,
    LanguageVariety,
    ProvenanceInfo,
)

PRIVATE_RECORD_FIELDS = frozenset({"speaker_id"})
# Claves de metadata retiradas sin distinguir mayúsculas.
PRIVATE_METADATA_KEYS = frozenset(
    {"speaker_id", "client_id", "age", "gender", "sex", "accent", "accents"}
)


def public_record_data(record: CorpusRecord | Mapping[str, Any]) -> dict[str, Any]:
    """Devuelve una copia sin campos privados; nunca modifica el registro recibido."""

    data = record.model_dump() if isinstance(record, BaseModel) else dict(record)
    for field in PRIVATE_RECORD_FIELDS:
        data.pop(field, None)
    metadata = data.get("metadata")
    if isinstance(metadata, Mapping):
        cleaned = {
            key: value
            for key, value in metadata.items()
            if not (isinstance(key, str) and key.casefold() in PRIVATE_METADATA_KEYS)
        }
        data["metadata"] = cleaned or None
    return data


class PublicCorpusRecord(CanonicalModel):
    """CorpusRecord sin speaker_id ni atributos de hablante en metadata.

    Acepta un CorpusRecord (o su dict) y lo sanea al validarse, de modo que cualquier
    respuesta que declare este tipo queda protegida sin lógica adicional en las rutas.
    """

    id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    provenance: ProvenanceInfo
    language: Language | None = None
    language_code: str | None = None
    language_variety: LanguageVariety | None = None
    text: str = Field(min_length=1)
    translation: str | None = None
    translation_language: Language | None = None
    audio_id: str | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _sanitize(cls, data: Any) -> Any:
        if isinstance(data, (CorpusRecord, Mapping)):
            return public_record_data(data)
        return data


def public_record(record: CorpusRecord) -> PublicCorpusRecord:
    return PublicCorpusRecord.model_validate(record)
