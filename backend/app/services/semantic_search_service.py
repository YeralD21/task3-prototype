"""Ranking semántico local sobre índices NumPy materializados."""

from dataclasses import dataclass

import numpy as np

from app.embeddings.provider import EmbeddingProvider
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.semantic_index_repository import (
    InvalidSemanticIndexError,
    LocalSemanticIndexRepository,
    SemanticIndexModelMismatchError,
)
from app.schemas.canonical import CorpusRecord


class DatasetNotAvailableLocallyError(RuntimeError):
    """El dataset existe en catálogo pero no tiene registros procesados."""


@dataclass(frozen=True)
class SemanticSearchItem:
    record: CorpusRecord
    score: float


def cosine_similarities(matrix: np.ndarray, query: np.ndarray) -> np.ndarray:
    """Calcula coseno por fila; una norma cero produce similitud cero."""

    matrix = np.asarray(matrix, dtype=np.float32)
    query = np.asarray(query, dtype=np.float32)
    if matrix.ndim != 2 or query.ndim != 1 or matrix.shape[1] != query.shape[0]:
        raise ValueError("Embedding dimensions do not match.")
    denominator = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
    scores = np.zeros(matrix.shape[0], dtype=np.float32)
    np.divide(matrix @ query, denominator, out=scores, where=denominator != 0)
    return scores


class SemanticSearchService:
    def __init__(
        self,
        dataset_repository: DatasetRepository,
        index_repository: LocalSemanticIndexRepository,
        provider: EmbeddingProvider,
    ) -> None:
        self.dataset_repository = dataset_repository
        self.index_repository = index_repository
        self.provider = provider

    def search(self, query: str, dataset_id: str, limit: int = 10) -> list[SemanticSearchItem]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        dataset = self.dataset_repository.get_dataset(dataset_id)
        if not (dataset.metadata or {}).get("available_locally", False):
            raise DatasetNotAvailableLocallyError(
                f"Dataset '{dataset_id}' is not available locally."
            )
        index = self.index_repository.load(dataset_id)
        if (
            index.manifest["embedding_provider"] != self.provider.provider_name
            or index.manifest["model_name"] != self.provider.model_name
        ):
            raise SemanticIndexModelMismatchError(
                "The configured embedding provider does not match the semantic index."
            )
        query_vector = np.asarray(self.provider.embed_text(query.strip()), dtype=np.float32)
        scores = cosine_similarities(index.embeddings, query_vector)
        records_by_id = {
            record.id: record for record in self.dataset_repository.list_records(dataset_id)
        }
        try:
            ordered = np.argsort(-scores, kind="stable")[:limit]
            return [
                SemanticSearchItem(records_by_id[index.record_ids[position]], float(scores[position]))
                for position in ordered
            ]
        except KeyError as error:
            raise InvalidSemanticIndexError(
                "Semantic index references an unavailable record."
            ) from error
