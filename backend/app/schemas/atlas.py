"""Contratos del Atlas Vivo: coordenadas 2D trazables y su respuesta HTTP."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AtlasPoint(BaseModel):
    """Una fila de coordinates.jsonl; conserva la trazabilidad del registro."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class AtlasSampling(BaseModel):
    applied: bool
    method: Literal["none", "sha256_record_id"]


class AtlasResponse(BaseModel):
    dataset_id: str
    reducer: str
    created_at: str
    source_embedding_model: str
    source_embedding_dimension: int
    parameters: dict[str, Any]
    diagnostics: dict[str, Any]
    total_records: int
    returned_records: int
    limit: int
    sampling: AtlasSampling
    items: list[AtlasPoint]
