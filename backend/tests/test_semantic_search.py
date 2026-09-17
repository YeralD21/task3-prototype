"""Índice y búsqueda semántica local con datos y embeddings sintéticos."""

import hashlib
import json
import socket
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.routes.search import get_semantic_search_service
from app.embeddings.provider import FakeEmbeddingProvider
from app.embeddings.sentence_transformer_provider import EmbeddingProviderUnavailableError
from app.main import app
from app.repositories.dataset_repository import DatasetNotFoundError, LocalDatasetRepository
from app.repositories.semantic_index_repository import (
    LocalSemanticIndexRepository,
    SemanticIndexModelMismatchError,
    SemanticIndexNotFoundError,
    StaleSemanticIndexError,
    records_fingerprint,
)
from app.services.semantic_search_service import (
    DatasetNotAvailableLocallyError,
    SemanticSearchService,
    cosine_similarities,
)
from ml.embeddings.indexer import SemanticIndexer
from tests.conftest import PROJECT_ROOT, SAMPLE_DATASET_ID

SAMPLE_FILE = PROJECT_ROOT / "data" / "samples" / "canonical-development-sample.json"


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access forbidden in semantic search tests")

    monkeypatch.setattr(socket, "create_connection", reject)


@pytest.fixture
def processed_root(tmp_path: Path) -> Path:
    payload = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    destination = tmp_path / "processed" / SAMPLE_DATASET_ID
    destination.mkdir(parents=True)
    (destination / "dataset.json").write_text(
        json.dumps(payload["dataset"], ensure_ascii=False), encoding="utf-8"
    )
    with (destination / "records.jsonl").open("w", encoding="utf-8", newline="\n") as file:
        for record in payload["records"]:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return tmp_path / "processed"


@pytest.fixture
def semantic_service(processed_root: Path) -> SemanticSearchService:
    provider = FakeEmbeddingProvider(dimension=128)
    SemanticIndexer(provider).build(SAMPLE_DATASET_ID, processed_root)
    datasets = LocalDatasetRepository(
        PROJECT_ROOT / "data" / "samples", processed_directory=processed_root
    )
    return SemanticSearchService(
        datasets, LocalSemanticIndexRepository(processed_root), provider
    )


def test_fake_provider_is_deterministic() -> None:
    first = FakeEmbeddingProvider(dimension=16).embed_text("Synthetic café")
    second = FakeEmbeddingProvider(dimension=16).embed_text("Synthetic café")
    assert np.array_equal(first, second)
    assert first.shape == (16,)


def test_indexer_creates_matrix_manifest_and_mapping(processed_root: Path) -> None:
    records_path = processed_root / SAMPLE_DATASET_ID / "records.jsonl"
    before = records_path.read_bytes()
    result = SemanticIndexer(FakeEmbeddingProvider(dimension=24)).build(
        SAMPLE_DATASET_ID, processed_root
    )

    matrix = np.load(result.destination / "embeddings.npy", allow_pickle=False)
    manifest = json.loads(
        (result.destination / "index-manifest.json").read_text(encoding="utf-8")
    )
    mappings = [
        json.loads(line)
        for line in (result.destination / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert matrix.shape == (3, 24)
    assert manifest["dimension"] == 24
    assert manifest["record_count"] == 3
    assert manifest["strategy"] == "text_only"
    assert manifest["source_records_fingerprint"] == hashlib.sha256(before).hexdigest()
    assert manifest["source_records_fingerprint"] == records_fingerprint(records_path)
    assert mappings[0]["dataset_id"] == SAMPLE_DATASET_ID
    assert mappings[0]["source_record_id"] == "synthetic-source-record-001"
    assert records_path.read_bytes() == before


def test_changed_records_make_index_stale(processed_root: Path) -> None:
    provider = FakeEmbeddingProvider()
    SemanticIndexer(provider).build(SAMPLE_DATASET_ID, processed_root)
    records_path = processed_root / SAMPLE_DATASET_ID / "records.jsonl"
    records_path.write_bytes(records_path.read_bytes() + b"\n")

    with pytest.raises(StaleSemanticIndexError, match="stale"):
        LocalSemanticIndexRepository(processed_root).load(SAMPLE_DATASET_ID)


def test_cosine_similarity_and_zero_norm() -> None:
    matrix = np.asarray([[1, 0], [1, 1], [0, 0]], dtype=np.float32)
    scores = cosine_similarities(matrix, np.asarray([1, 0], dtype=np.float32))
    assert scores == pytest.approx([1.0, 2**-0.5, 0.0])


def test_semantic_ranking_and_traceability(semantic_service: SemanticSearchService) -> None:
    items = semantic_service.search("sentence 002", SAMPLE_DATASET_ID, limit=2)
    assert len(items) == 2
    assert items[0].record.id == "synthetic-record-002"
    assert items[0].record.dataset_id == SAMPLE_DATASET_ID
    assert items[0].record.source_record_id == "synthetic-source-record-002"
    assert items[0].score >= items[1].score


@pytest.mark.parametrize("query", ["", "   "])
def test_empty_query_is_rejected(
    semantic_service: SemanticSearchService, query: str
) -> None:
    with pytest.raises(ValueError, match="query"):
        semantic_service.search(query, SAMPLE_DATASET_ID)


def test_missing_dataset_is_reported(semantic_service: SemanticSearchService) -> None:
    with pytest.raises(DatasetNotFoundError):
        semantic_service.search("query", "missing-dataset")


def test_cataloged_dataset_without_materialization_is_reported(tmp_path: Path) -> None:
    service = SemanticSearchService(
        LocalDatasetRepository(PROJECT_ROOT / "datasets" / "registry"),
        LocalSemanticIndexRepository(tmp_path),
        FakeEmbeddingProvider(),
    )
    with pytest.raises(DatasetNotAvailableLocallyError, match="not available locally"):
        service.search("query", "americasnlp-2021-aymara-spanish")


def test_missing_index_is_reported(processed_root: Path) -> None:
    datasets = LocalDatasetRepository(
        PROJECT_ROOT / "data" / "samples", processed_directory=processed_root
    )
    service = SemanticSearchService(
        datasets, LocalSemanticIndexRepository(processed_root), FakeEmbeddingProvider()
    )
    with pytest.raises(SemanticIndexNotFoundError, match="was not found"):
        service.search("query", SAMPLE_DATASET_ID)


def test_different_model_is_rejected(semantic_service: SemanticSearchService) -> None:
    semantic_service.provider = FakeEmbeddingProvider(model_name="different-model")
    with pytest.raises(SemanticIndexModelMismatchError, match="does not match"):
        semantic_service.search("query", SAMPLE_DATASET_ID)


def test_endpoint_reports_unavailable_provider(
    semantic_service: SemanticSearchService,
) -> None:
    class UnavailableProvider(FakeEmbeddingProvider):
        def embed_text(self, text: str) -> np.ndarray:
            raise EmbeddingProviderUnavailableError("configured provider unavailable")

    semantic_service.provider = UnavailableProvider(
        dimension=128, model_name="deterministic-token-hash-v1"
    )
    app.dependency_overrides[get_semantic_search_service] = lambda: semantic_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/search/semantic",
                json={"query": "query", "dataset_id": SAMPLE_DATASET_ID},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "configured provider unavailable"


def test_semantic_search_endpoint(semantic_service: SemanticSearchService) -> None:
    app.dependency_overrides[get_semantic_search_service] = lambda: semantic_service
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/search/semantic",
                json={
                    "query": "sentence 002",
                    "dataset_id": SAMPLE_DATASET_ID,
                    "limit": 1,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == SAMPLE_DATASET_ID
    assert payload["items"][0]["record"]["source_record_id"] == "synthetic-source-record-002"
    assert isinstance(payload["items"][0]["score"], float)


def test_endpoint_rejects_empty_query_and_invalid_limit(
    semantic_service: SemanticSearchService,
) -> None:
    app.dependency_overrides[get_semantic_search_service] = lambda: semantic_service
    try:
        with TestClient(app) as client:
            empty = client.post(
                "/api/v1/search/semantic",
                json={"query": " ", "dataset_id": SAMPLE_DATASET_ID},
            )
            invalid_limit = client.post(
                "/api/v1/search/semantic",
                json={"query": "query", "dataset_id": SAMPLE_DATASET_ID, "limit": 0},
            )
    finally:
        app.dependency_overrides.clear()

    assert empty.status_code == 422
    assert invalid_limit.status_code == 422
