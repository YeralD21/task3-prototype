"""Vista pública de CorpusRecord aplicada a todas las respuestas que devuelven registros."""

import json
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes.atlas import get_atlas_service
from app.api.routes.datasets import get_dataset_service
from app.api.routes.search import get_semantic_search_service
from app.embeddings.provider import FakeEmbeddingProvider
from app.main import app
from app.repositories.atlas_repository import LocalAtlasRepository
from app.repositories.dataset_repository import LocalDatasetRepository
from app.repositories.semantic_index_repository import LocalSemanticIndexRepository
from app.schemas.canonical import CorpusRecord
from app.schemas.public import PublicCorpusRecord, public_record
from app.services.atlas_service import AtlasService
from app.services.dataset_service import DatasetService
from app.services.semantic_search_service import SemanticSearchService
from ml.atlas.builder import AtlasBuilder
from ml.atlas.reducers import PCAReducer
from ml.embeddings.indexer import SemanticIndexer
from tests.conftest import PROJECT_ROOT, SAMPLE_DATASET_ID

SAMPLES = PROJECT_ROOT / "data" / "samples"
PRIVATE_VALUES = (
    "synthetic-speaker-secret",
    "synthetic-client-secret",
    "synthetic-accent-secret",
    "synthetic-age-secret",
    "synthetic-gender-secret",
    "synthetic-sex-secret",
)


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access forbidden in public record tests")

    monkeypatch.setattr(socket, "create_connection", reject)


def private_record(template: dict, position: int) -> dict:
    return {
        **template,
        "id": f"synthetic-record-{position:03d}",
        "source_record_id": f"synthetic-source-record-{position:03d}",
        "text": f"synthetic topic {position % 3} sentence {position:03d}",
        "translation": f"synthetic translation {position:03d}",
        "audio_id": f"{SAMPLE_DATASET_ID}:audio:clip-{position:03d}.mp3",
        "speaker_id": "synthetic-speaker-secret",
        "metadata": {
            "split": "train",
            "client_id": "synthetic-client-secret",
            "Accent": "synthetic-accent-secret",
            "accents": "synthetic-accent-secret",
            "age": "synthetic-age-secret",
            "gender": "synthetic-gender-secret",
            "SEX": "synthetic-sex-secret",
            "up_votes": "2",
        },
    }


@pytest.fixture
def processed_root(tmp_path: Path) -> Path:
    payload = json.loads((SAMPLES / "canonical-development-sample.json").read_text("utf-8"))
    destination = tmp_path / "processed" / SAMPLE_DATASET_ID
    destination.mkdir(parents=True)
    (destination / "dataset.json").write_text(json.dumps(payload["dataset"]), encoding="utf-8")
    with (destination / "records.jsonl").open("w", encoding="utf-8", newline="\n") as file:
        for position in range(1, 7):
            file.write(json.dumps(private_record(payload["records"][2], position)) + "\n")
    root = tmp_path / "processed"
    provider = FakeEmbeddingProvider(dimension=128)
    SemanticIndexer(provider).build(SAMPLE_DATASET_ID, root)
    AtlasBuilder(PCAReducer()).build(SAMPLE_DATASET_ID, root)
    return root


@pytest.fixture
def client(processed_root: Path) -> Iterator[TestClient]:
    datasets = LocalDatasetRepository(SAMPLES, processed_directory=processed_root)
    app.dependency_overrides[get_dataset_service] = lambda: DatasetService(datasets)
    app.dependency_overrides[get_semantic_search_service] = lambda: SemanticSearchService(
        datasets, LocalSemanticIndexRepository(processed_root), FakeEmbeddingProvider(dimension=128)
    )
    app.dependency_overrides[get_atlas_service] = lambda: AtlasService(
        datasets, LocalAtlasRepository(processed_root)
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def assert_public(record: dict, position: int | None = None) -> None:
    assert "speaker_id" not in record
    lowered = {key.casefold() for key in record["metadata"]}
    assert not lowered & {"client_id", "accent", "accents", "age", "gender", "sex"}
    assert not any(value in json.dumps(record) for value in PRIVATE_VALUES)
    assert record["dataset_id"] == SAMPLE_DATASET_ID
    assert record["metadata"]["split"] == "train"
    assert record["provenance"]["source_name"] == "task3-prototype synthetic fixture"
    assert record["language"] is not None
    assert record["translation"].startswith("synthetic translation")
    assert record["audio_id"].startswith(f"{SAMPLE_DATASET_ID}:audio:clip-")
    if position is not None:
        assert record["source_record_id"] == f"synthetic-source-record-{position:03d}"


# --- Función / schema reutilizable -------------------------------------------------------


def test_public_record_removes_private_fields_and_keeps_traceability() -> None:
    payload = json.loads((SAMPLES / "canonical-development-sample.json").read_text("utf-8"))
    canonical = CorpusRecord.model_validate(private_record(payload["records"][2], 1))
    public = public_record(canonical).model_dump(mode="json")
    assert_public(public, 1)
    assert public["metadata"] == {"split": "train", "up_votes": "2"}
    assert canonical.speaker_id == "synthetic-speaker-secret"
    assert canonical.metadata["accents"] == "synthetic-accent-secret"


def test_public_schema_also_sanitizes_plain_mappings() -> None:
    payload = json.loads((SAMPLES / "canonical-development-sample.json").read_text("utf-8"))
    raw = private_record(payload["records"][2], 2)
    assert_public(PublicCorpusRecord.model_validate(raw).model_dump(mode="json"), 2)
    assert raw["speaker_id"] == "synthetic-speaker-secret"
    only_private = {**raw, "metadata": {"client_id": "x"}}
    assert PublicCorpusRecord.model_validate(only_private).metadata is None


def test_public_schema_tracks_the_canonical_model() -> None:
    assert set(PublicCorpusRecord.model_fields) == set(CorpusRecord.model_fields) - {"speaker_id"}


# --- Endpoints públicos ----------------------------------------------------------------------


def test_records_endpoint_returns_public_view(client: TestClient) -> None:
    response = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/records", params={"limit": 50})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 6
    for position, record in enumerate(items, start=1):
        assert_public(record, position)
    filtered = client.get(
        f"/api/v1/datasets/{SAMPLE_DATASET_ID}/records", params={"q": "sentence 004"}
    ).json()
    assert [item["source_record_id"] for item in filtered["items"]] == ["synthetic-source-record-004"]


def test_semantic_search_still_works_with_public_view(client: TestClient) -> None:
    response = client.post(
        "/api/v1/search/semantic",
        json={"query": "sentence 005", "dataset_id": SAMPLE_DATASET_ID, "limit": 3},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["record"]["source_record_id"] == "synthetic-source-record-005"
    assert isinstance(items[0]["score"], float)
    for item in items:
        assert_public(item["record"])


def test_atlas_still_works_with_public_view(client: TestClient) -> None:
    response = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_records"] == 6
    for item in payload["items"]:
        assert item["source_record_id"] == item["record"]["source_record_id"]
        assert_public(item["record"])


def test_public_responses_never_modify_stored_records(client: TestClient, processed_root: Path) -> None:
    records_path = processed_root / SAMPLE_DATASET_ID / "records.jsonl"
    before = records_path.read_bytes()
    client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/records")
    client.post("/api/v1/search/semantic", json={"query": "sentence", "dataset_id": SAMPLE_DATASET_ID})
    client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas")
    assert records_path.read_bytes() == before
    stored = json.loads(before.decode("utf-8").splitlines()[0])
    assert stored["speaker_id"] == "synthetic-speaker-secret"
    assert stored["metadata"]["accents"] == "synthetic-accent-secret"
