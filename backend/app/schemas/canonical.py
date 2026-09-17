"""Modelos canónicos públicos para datasets y registros lingüísticos."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CanonicalModel(BaseModel):
    """Base común que rechaza campos accidentales sin exigir metadata completa."""

    model_config = ConfigDict(extra="forbid")


class Language(CanonicalModel):
    """Idioma declarado por la fuente, sin restringirlo a un catálogo cerrado."""

    name: str = Field(min_length=1, description="Nombre del idioma según la fuente.")
    iso_code: str | None = Field(
        default=None, min_length=1, description="Código ISO declarado, si está disponible."
    )


class LanguageVariety(CanonicalModel):
    """Variedad lingüística conservada con el nivel de detalle disponible."""

    id: str = Field(min_length=1, description="Identificador estable de la variedad.")
    name: str = Field(min_length=1, description="Nombre de la variedad según la fuente.")
    language_code: str | None = Field(default=None, description="Código del idioma base.")
    region: str | None = None
    country: str | None = None
    glottocode: str | None = None
    metadata: dict[str, Any] | None = None


class LicenseInfo(CanonicalModel):
    """Licencia y permisos explícitos; ``None`` significa desconocido."""

    name: str | None = None
    url: str | None = None
    commercial_use: bool | None = None
    redistribution: bool | None = None
    derivatives: bool | None = None
    attribution_required: bool | None = None
    notes: str | None = None


class ProvenanceInfo(CanonicalModel):
    """Información necesaria para rastrear un recurso hasta su fuente."""

    source_name: str | None = None
    source_url: str | None = None
    organization: str | None = None
    original_dataset_id: str | None = None
    citation: str | None = None
    retrieved_at: datetime | None = None
    notes: str | None = None


class Speaker(CanonicalModel):
    """Hablante descrito únicamente con información aportada por la fuente."""

    id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    source_speaker_id: str | None = None
    language: Language | None = None
    language_variety: LanguageVariety | None = None
    region: str | None = None
    metadata: dict[str, Any] | None = None


class AudioResource(CanonicalModel):
    """Referencia a audio sin copiar ni transformar el recurso original."""

    id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    source_audio_id: str | None = None
    path_or_url: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    mime_type: str | None = None
    sample_rate: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] | None = None


class Dataset(CanonicalModel):
    """Metadata de un corpus como colección, separada de sus registros."""

    id: str = Field(min_length=1, description="Identificador canónico del dataset.")
    name: str = Field(min_length=1)
    description: str | None = None
    languages: list[Language] | None = None
    language_varieties: list[LanguageVariety] | None = None
    countries: list[str] | None = None
    regions: list[str] | None = None
    modalities: list[str] | None = None
    tasks: list[str] | None = None
    domains: list[str] | None = None
    source_url: str | None = None
    source_organization: str | None = None
    license: LicenseInfo = Field(description="Licencia explícita, incluso si es desconocida.")
    provenance: ProvenanceInfo = Field(description="Procedencia declarada del dataset.")
    citation: str | None = None
    record_count: int | None = Field(default=None, ge=0)
    token_count: int | None = Field(default=None, ge=0)
    speaker_count: int | None = Field(default=None, ge=0)
    audio_hours: float | None = Field(default=None, ge=0)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class CorpusRecord(CanonicalModel):
    """Unidad de corpus trazable hasta el dataset y registro originales."""

    id: str = Field(min_length=1, description="Identificador canónico del registro.")
    dataset_id: str = Field(min_length=1, description="Dataset canónico de pertenencia.")
    source_record_id: str = Field(
        min_length=1, description="Identificador conservado desde la fuente original."
    )
    provenance: ProvenanceInfo = Field(description="Procedencia del registro.")
    language: Language | None = None
    language_code: str | None = None
    language_variety: LanguageVariety | None = None
    text: str = Field(min_length=1)
    translation: str | None = None
    translation_language: Language | None = None
    audio_id: str | None = None
    speaker_id: str | None = None
    metadata: dict[str, Any] | None = None
