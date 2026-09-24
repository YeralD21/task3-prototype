"""Contratos de Corpus Radio: registros con audio sin exponer rutas del sistema."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.public import PublicCorpusRecord

AudioStatus = Literal["available", "missing_file", "unsupported_format", "unavailable"]


class RadioItem(BaseModel):
    record: PublicCorpusRecord
    has_audio: bool
    audio_status: AudioStatus
    audio_url: str | None = Field(
        description="Ruta relativa al endpoint de audio controlado; nunca una ruta de archivo."
    )
    media_type: str | None


class RadioPage(BaseModel):
    dataset_id: str
    contains_audio: bool
    items: list[RadioItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
