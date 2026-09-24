"""Contratos HTTP para búsqueda semántica."""

from pydantic import BaseModel, Field

from app.schemas.public import PublicCorpusRecord


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    limit: int = Field(default=10, ge=1, le=100)


class SemanticSearchResultItem(BaseModel):
    record: PublicCorpusRecord
    score: float


class SemanticSearchResponse(BaseModel):
    query: str
    dataset_id: str
    items: list[SemanticSearchResultItem]

