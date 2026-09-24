"""Evaluación ligera y reproducible de proveedores de embeddings."""

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np

from app.embeddings.provider import EmbeddingProvider
from app.services.semantic_search_service import cosine_similarities


class BenchmarkValidationError(ValueError):
    """El benchmark no tiene la estructura o referencias esperadas."""


@dataclass(frozen=True)
class BenchmarkRecord:
    id: str
    text: str
    topic: str


@dataclass(frozen=True)
class BenchmarkQuery:
    id: str
    text: str
    relevant_record_ids: frozenset[str]


@dataclass(frozen=True)
class EmbeddingBenchmark:
    name: str
    records: tuple[BenchmarkRecord, ...]
    queries: tuple[BenchmarkQuery, ...]


@dataclass(frozen=True)
class EvaluationResult:
    model_name: str
    dimension: int
    precision_at_k: float
    recall_at_k: float
    mrr: float
    load_seconds: float
    embedding_seconds: float
    search_seconds: float
    k: int


def load_benchmark(path: Path) -> EmbeddingBenchmark:
    """Carga y valida el benchmark sintético versionado."""

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        records = tuple(BenchmarkRecord(**item) for item in payload["records"])
        queries = tuple(
            BenchmarkQuery(
                id=item["id"],
                text=item["text"],
                relevant_record_ids=frozenset(item["relevant_record_ids"]),
            )
            for item in payload["queries"]
        )
        name = payload["name"]
        synthetic = payload["synthetic"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise BenchmarkValidationError(f"Cannot load benchmark: {path}") from error
    record_ids = [record.id for record in records]
    query_ids = [query.id for query in queries]
    if synthetic is not True:
        raise BenchmarkValidationError("Only explicitly synthetic benchmarks are accepted.")
    if not name or not records or not queries:
        raise BenchmarkValidationError("Benchmark name, records and queries are required.")
    if len(record_ids) != len(set(record_ids)) or len(query_ids) != len(set(query_ids)):
        raise BenchmarkValidationError("Benchmark ids must be unique.")
    known = set(record_ids)
    if any(not query.relevant_record_ids or not query.relevant_record_ids <= known for query in queries):
        raise BenchmarkValidationError("Ground truth references unknown or empty records.")
    return EmbeddingBenchmark(name=name, records=records, queries=queries)


def precision_at_k(ranked_ids: list[str], relevant_ids: frozenset[str], k: int) -> float:
    _validate_metric_input(relevant_ids, k)
    return len(set(ranked_ids[:k]) & relevant_ids) / k


def recall_at_k(ranked_ids: list[str], relevant_ids: frozenset[str], k: int) -> float:
    _validate_metric_input(relevant_ids, k)
    return len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids)


def reciprocal_rank(ranked_ids: list[str], relevant_ids: frozenset[str]) -> float:
    if not relevant_ids:
        raise ValueError("relevant_ids must not be empty")
    return next(
        (1.0 / rank for rank, record_id in enumerate(ranked_ids, start=1) if record_id in relevant_ids),
        0.0,
    )


def _validate_metric_input(relevant_ids: frozenset[str], k: int) -> None:
    if k < 1 or not relevant_ids:
        raise ValueError("k must be positive and relevant_ids must not be empty")


def rank_records(
    record_vectors: np.ndarray, query_vector: np.ndarray, record_ids: list[str]
) -> list[str]:
    """Ordena identificadores por coseno descendente de manera estable."""

    if record_vectors.shape[0] != len(record_ids):
        raise ValueError("record_ids must match the embedding rows")
    scores = cosine_similarities(record_vectors, query_vector)
    return [record_ids[index] for index in np.argsort(-scores, kind="stable")]


def evaluate_provider(
    provider: EmbeddingProvider,
    benchmark: EmbeddingBenchmark,
    *,
    k: int = 5,
    load_seconds: float = 0.0,
) -> EvaluationResult:
    """Evalúa un proveedor ya construido; no inicia red ni descarga modelos."""

    if not 1 <= k <= len(benchmark.records):
        raise ValueError("k must be between 1 and the record count")
    embedding_start = perf_counter()
    record_vectors = np.asarray(
        provider.embed_texts([record.text for record in benchmark.records]), dtype=np.float32
    )
    query_vectors = np.asarray(
        provider.embed_texts([query.text for query in benchmark.queries]), dtype=np.float32
    )
    embedding_seconds = perf_counter() - embedding_start
    if (
        record_vectors.ndim != 2
        or query_vectors.ndim != 2
        or record_vectors.shape[0] != len(benchmark.records)
        or query_vectors.shape[0] != len(benchmark.queries)
        or record_vectors.shape[1] != query_vectors.shape[1]
    ):
        raise ValueError("Provider returned incompatible embedding matrices.")

    precisions: list[float] = []
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    record_ids = [record.id for record in benchmark.records]
    search_start = perf_counter()
    for query, query_vector in zip(benchmark.queries, query_vectors, strict=True):
        ranked_ids = rank_records(record_vectors, query_vector, record_ids)
        precisions.append(precision_at_k(ranked_ids, query.relevant_record_ids, k))
        recalls.append(recall_at_k(ranked_ids, query.relevant_record_ids, k))
        reciprocal_ranks.append(reciprocal_rank(ranked_ids, query.relevant_record_ids))
    search_seconds = perf_counter() - search_start
    return EvaluationResult(
        model_name=provider.model_name,
        dimension=int(record_vectors.shape[1]),
        precision_at_k=float(np.mean(precisions)),
        recall_at_k=float(np.mean(recalls)),
        mrr=float(np.mean(reciprocal_ranks)),
        load_seconds=load_seconds,
        embedding_seconds=embedding_seconds,
        search_seconds=search_seconds,
        k=k,
    )
