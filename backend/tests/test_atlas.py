"""Atlas Vivo: reducción 2D, artefactos, frescura y endpoint con datos sintéticos."""

import hashlib
import json
import socket
import sys
import types
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.routes.atlas import get_atlas_service
from app.embeddings.provider import FakeEmbeddingProvider
from app.main import app
from app.repositories.atlas_repository import (
    InvalidAtlasError,
    LocalAtlasRepository,
    StaleAtlasError,
)
from app.repositories.dataset_repository import LocalDatasetRepository
from app.repositories.semantic_index_repository import (
    SemanticIndexNotFoundError,
    StaleSemanticIndexError,
    records_fingerprint,
    semantic_index_fingerprint,
)
from app.schemas.atlas import AtlasPoint
from app.services.atlas_service import ATLAS_MAX_LIMIT, AtlasService, sample_points
from ml.atlas.builder import AtlasBuilder
from ml.atlas.reducers import (
    InvalidEmbeddingsError,
    PCAReducer,
    ReducerUnavailableError,
    UMAPReducer,
    create_reducer,
)
from ml.embeddings.indexer import SemanticIndexer
from scripts.build_atlas import main as build_atlas_main
from tests.conftest import PROJECT_ROOT, SAMPLE_DATASET_ID

SAMPLE_FILE = PROJECT_ROOT / "data" / "samples" / "canonical-development-sample.json"
RECORD_COUNT = 40


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access forbidden in atlas tests")

    monkeypatch.setattr(socket, "create_connection", reject)


def write_processed_dataset(root: Path, count: int) -> Path:
    payload = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
    template = payload["records"][0]
    destination = root / SAMPLE_DATASET_ID
    destination.mkdir(parents=True)
    (destination / "dataset.json").write_text(
        json.dumps(payload["dataset"], ensure_ascii=False), encoding="utf-8"
    )
    with (destination / "records.jsonl").open("w", encoding="utf-8", newline="\n") as file:
        for position in range(1, count + 1):
            record = {
                **template,
                "id": f"synthetic-record-{position:03d}",
                "source_record_id": f"synthetic-source-record-{position:03d}",
                "text": f"synthetic topic {position % 4} sentence {position:03d}",
            }
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return root


@pytest.fixture
def processed_root(tmp_path: Path) -> Path:
    root = write_processed_dataset(tmp_path / "processed", RECORD_COUNT)
    SemanticIndexer(FakeEmbeddingProvider(dimension=16)).build(SAMPLE_DATASET_ID, root)
    return root


@pytest.fixture
def atlas_root(processed_root: Path) -> Path:
    AtlasBuilder(PCAReducer()).build(SAMPLE_DATASET_ID, processed_root)
    return processed_root


def atlas_service(root: Path) -> AtlasService:
    datasets = LocalDatasetRepository(
        PROJECT_ROOT / "data" / "samples", processed_directory=root
    )
    return AtlasService(datasets, LocalAtlasRepository(root))


@pytest.fixture
def client_for() -> Iterator:
    def build(service: AtlasService) -> TestClient:
        app.dependency_overrides[get_atlas_service] = lambda: service
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()


def read_coordinates(root: Path) -> list[dict]:
    path = root / SAMPLE_DATASET_ID / "atlas" / "coordinates.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def read_manifest(root: Path) -> dict:
    path = root / SAMPLE_DATASET_ID / "atlas" / "atlas-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


# --- Reductores -----------------------------------------------------------------


def test_pca_returns_one_xy_pair_per_row() -> None:
    embeddings = np.random.default_rng(7).normal(size=(25, 12)).astype(np.float32)
    result = PCAReducer().fit_transform(embeddings)
    assert result.coordinates.shape == (25, 2)
    assert np.isfinite(result.coordinates).all()
    assert len(result.diagnostics["explained_variance_ratio"]) == 2


def test_pca_is_deterministic_and_sign_stable() -> None:
    embeddings = np.random.default_rng(11).normal(size=(30, 8))
    first = PCAReducer().fit_transform(embeddings).coordinates
    second = PCAReducer().fit_transform(embeddings.copy()).coordinates
    assert np.array_equal(first, second)
    flipped = PCAReducer().fit_transform(-embeddings).coordinates
    assert np.allclose(np.abs(flipped), np.abs(first))


def test_pca_recovers_dominant_direction() -> None:
    positions = np.linspace(-5.0, 5.0, 11)
    direction = np.asarray([3.0, 4.0, 0.0]) / 5.0
    embeddings = positions[:, np.newaxis] * direction
    result = PCAReducer().fit_transform(embeddings)
    assert np.allclose(np.abs(result.coordinates[:, 0]), np.abs(positions))
    assert np.allclose(result.coordinates[:, 1], 0.0)
    assert result.diagnostics["explained_variance_ratio"][0] == pytest.approx(1.0)


def test_pca_pads_low_rank_input_with_zeros() -> None:
    single_column = PCAReducer().fit_transform(np.asarray([[1.0], [2.0], [4.0]]))
    single_row = PCAReducer().fit_transform(np.asarray([[1.0, 2.0, 3.0]]))
    assert single_column.coordinates.shape == (3, 2)
    assert np.allclose(single_column.coordinates[:, 1], 0.0)
    assert np.allclose(single_row.coordinates, 0.0)


@pytest.mark.parametrize(
    "embeddings",
    [
        np.zeros(5),
        np.zeros((0, 4)),
        np.zeros((3, 0)),
        np.zeros((2, 2, 2)),
        np.asarray([[1.0, np.nan], [0.0, 1.0]]),
        np.asarray([[1.0, np.inf], [0.0, 1.0]]),
        np.asarray([["a", "b"], ["c", "d"]]),
    ],
    ids=["1d", "no-rows", "no-columns", "3d", "nan", "inf", "strings"],
)
def test_pca_rejects_invalid_input(embeddings: np.ndarray) -> None:
    with pytest.raises(InvalidEmbeddingsError):
        PCAReducer().fit_transform(embeddings)


def test_invalid_reducer_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="n_components"):
        PCAReducer(n_components=0)
    with pytest.raises(ValueError, match="Unknown reducer"):
        create_reducer("tsne")


def test_umap_without_optional_dependency_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "umap", None)
    with pytest.raises(ReducerUnavailableError, match="umap-learn"):
        UMAPReducer().fit_transform(np.random.default_rng(0).normal(size=(10, 4)))


def test_umap_receives_explicit_random_state(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeUMAP:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def fit_transform(self, matrix: np.ndarray) -> np.ndarray:
            return matrix[:, :2]

    monkeypatch.setitem(sys.modules, "umap", types.SimpleNamespace(UMAP=FakeUMAP))
    result = UMAPReducer(n_neighbors=50, random_state=123).fit_transform(np.ones((6, 3)))
    assert captured["random_state"] == 123
    assert captured["transform_seed"] == 123
    assert captured["n_neighbors"] == 5
    assert result.diagnostics["effective_n_neighbors"] == 5
    assert result.coordinates.shape == (6, 2)


# --- Construcción y artefactos -----------------------------------------------------


def test_build_writes_traceable_coordinates(atlas_root: Path) -> None:
    rows = read_coordinates(atlas_root)
    mapping = [
        json.loads(line)
        for line in (atlas_root / SAMPLE_DATASET_ID / "semantic" / "records.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(rows) == RECORD_COUNT
    assert set(rows[0]) == {"record_id", "dataset_id", "source_record_id", "x", "y"}
    for row, source in zip(rows, mapping):
        assert row["record_id"] == source["record_id"]
        assert row["source_record_id"] == source["source_record_id"]
        assert row["dataset_id"] == SAMPLE_DATASET_ID
        assert isinstance(row["x"], float) and isinstance(row["y"], float)


def test_manifest_describes_source_and_reducer(atlas_root: Path) -> None:
    manifest = read_manifest(atlas_root)
    assert manifest["dataset_id"] == SAMPLE_DATASET_ID
    assert manifest["reducer"] == "pca"
    assert manifest["created_at"]
    assert manifest["source_embedding_provider"] == "fake"
    assert manifest["source_embedding_model"] == "deterministic-token-hash-v1"
    assert manifest["source_embedding_dimension"] == 16
    assert manifest["record_count"] == RECORD_COUNT
    assert manifest["parameters"]["n_components"] == 2
    assert 0.0 <= manifest["diagnostics"]["explained_variance_ratio_total"] <= 1.0


def test_manifest_fingerprints_match_sources(atlas_root: Path) -> None:
    dataset_directory = atlas_root / SAMPLE_DATASET_ID
    manifest = read_manifest(atlas_root)
    records_bytes = (dataset_directory / "records.jsonl").read_bytes()
    assert manifest["source_records_fingerprint"] == hashlib.sha256(records_bytes).hexdigest()
    assert manifest["source_records_fingerprint"] == records_fingerprint(
        dataset_directory / "records.jsonl"
    )
    assert manifest["semantic_index_fingerprint"] == semantic_index_fingerprint(
        dataset_directory / "semantic"
    )


def test_build_does_not_modify_embeddings_or_records(processed_root: Path) -> None:
    dataset_directory = processed_root / SAMPLE_DATASET_ID
    watched = [
        dataset_directory / "records.jsonl",
        dataset_directory / "semantic" / "embeddings.npy",
        dataset_directory / "semantic" / "records.jsonl",
        dataset_directory / "semantic" / "index-manifest.json",
    ]
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in watched}
    AtlasBuilder(PCAReducer()).build(SAMPLE_DATASET_ID, processed_root)
    AtlasBuilder(PCAReducer()).build(SAMPLE_DATASET_ID, processed_root)
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in watched} == before


def test_rebuild_is_deterministic_and_replaces_atlas(atlas_root: Path) -> None:
    path = atlas_root / SAMPLE_DATASET_ID / "atlas" / "coordinates.jsonl"
    first = path.read_bytes()
    AtlasBuilder(PCAReducer()).build(SAMPLE_DATASET_ID, atlas_root)
    assert path.read_bytes() == first
    leftovers = [item.name for item in (atlas_root / SAMPLE_DATASET_ID).iterdir()]
    assert not any(name.startswith(".atlas") for name in leftovers)


def test_build_requires_semantic_index(tmp_path: Path) -> None:
    root = write_processed_dataset(tmp_path / "processed", 3)
    with pytest.raises(SemanticIndexNotFoundError):
        AtlasBuilder(PCAReducer()).build(SAMPLE_DATASET_ID, root)
    assert not (root / SAMPLE_DATASET_ID / "atlas").exists()


def test_build_rejects_stale_semantic_index(processed_root: Path) -> None:
    records_path = processed_root / SAMPLE_DATASET_ID / "records.jsonl"
    records_path.write_bytes(records_path.read_bytes() + b"\n")
    with pytest.raises(StaleSemanticIndexError):
        AtlasBuilder(PCAReducer()).build(SAMPLE_DATASET_ID, processed_root)


def test_cli_builds_atlas(processed_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = build_atlas_main(
        ["--dataset", SAMPLE_DATASET_ID, "--processed-root", str(processed_root)]
    )
    assert exit_code == 0
    assert "Reducer: pca" in capsys.readouterr().out
    assert len(read_coordinates(processed_root)) == RECORD_COUNT


def test_cli_reports_missing_index(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = write_processed_dataset(tmp_path / "processed", 3)
    with pytest.raises(SystemExit) as exit_info:
        build_atlas_main(["--dataset", SAMPLE_DATASET_ID, "--processed-root", str(root)])
    assert exit_info.value.code == 1
    assert "Atlas build failed" in capsys.readouterr().err


# --- Frescura -------------------------------------------------------------------------


def test_atlas_is_stale_when_records_change(atlas_root: Path) -> None:
    records_path = atlas_root / SAMPLE_DATASET_ID / "records.jsonl"
    records_path.write_bytes(records_path.read_bytes() + b"\n")
    with pytest.raises(StaleAtlasError, match="records changed"):
        LocalAtlasRepository(atlas_root).load(SAMPLE_DATASET_ID)


def test_atlas_is_stale_when_embeddings_change(atlas_root: Path) -> None:
    SemanticIndexer(FakeEmbeddingProvider(dimension=24)).build(SAMPLE_DATASET_ID, atlas_root)
    with pytest.raises(StaleAtlasError, match="embeddings changed"):
        LocalAtlasRepository(atlas_root).load(SAMPLE_DATASET_ID)


def test_atlas_is_stale_when_embedding_values_change(atlas_root: Path) -> None:
    path = atlas_root / SAMPLE_DATASET_ID / "semantic" / "embeddings.npy"
    matrix = np.load(path, allow_pickle=False)
    matrix[0, 0] += 1.0
    np.save(path, matrix, allow_pickle=False)
    with pytest.raises(StaleAtlasError, match="embeddings changed"):
        LocalAtlasRepository(atlas_root).load(SAMPLE_DATASET_ID)


def test_corrupt_coordinates_are_invalid(atlas_root: Path) -> None:
    path = atlas_root / SAMPLE_DATASET_ID / "atlas" / "coordinates.jsonl"
    path.write_text(path.read_text(encoding="utf-8").replace('"x": ', '"x": "nan-', 1))
    with pytest.raises(InvalidAtlasError):
        LocalAtlasRepository(atlas_root).load(SAMPLE_DATASET_ID)


# --- Muestreo -------------------------------------------------------------------------


def test_sampling_is_reproducible_nested_and_order_preserving() -> None:
    points = [
        AtlasPoint(
            record_id=f"r-{position}", dataset_id="d", source_record_id=f"s-{position}",
            x=float(position), y=0.0,
        )
        for position in range(100)
    ]
    small = sample_points(points, 10)
    large = sample_points(points, 30)
    assert sample_points(points, 10) == small
    assert sample_points(list(reversed(points)), 10) == list(reversed(small))
    assert {point.record_id for point in small} <= {point.record_id for point in large}
    assert [point.x for point in small] == sorted(point.x for point in small)
    assert sample_points(points, 500) == points


# --- Endpoint -----------------------------------------------------------------------------


def test_endpoint_returns_full_atlas(atlas_root: Path, client_for) -> None:
    with client_for(atlas_service(atlas_root)) as client:
        response = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == SAMPLE_DATASET_ID
    assert payload["reducer"] == "pca"
    assert payload["total_records"] == payload["returned_records"] == RECORD_COUNT
    assert payload["sampling"] == {"applied": False, "method": "none"}
    assert payload["source_embedding_dimension"] == 16
    assert payload["items"][0]["source_record_id"] == "synthetic-source-record-001"
    assert payload["items"] == read_coordinates(atlas_root)


def test_endpoint_samples_reproducibly_above_limit(atlas_root: Path, client_for) -> None:
    with client_for(atlas_service(atlas_root)) as client:
        first = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas", params={"limit": 10})
        second = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas", params={"limit": 10})
    assert first.status_code == 200
    payload = first.json()
    assert payload["limit"] == 10
    assert payload["returned_records"] == len(payload["items"]) == 10
    assert payload["total_records"] == RECORD_COUNT
    assert payload["sampling"] == {"applied": True, "method": "sha256_record_id"}
    assert payload["items"] == second.json()["items"]


@pytest.mark.parametrize("limit", [0, -1, ATLAS_MAX_LIMIT + 1, "many"])
def test_endpoint_rejects_invalid_limit(atlas_root: Path, client_for, limit: object) -> None:
    with client_for(atlas_service(atlas_root)) as client:
        response = client.get(
            f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas", params={"limit": limit}
        )
    assert response.status_code == 422


def test_endpoint_accepts_maximum_limit(atlas_root: Path, client_for) -> None:
    with client_for(atlas_service(atlas_root)) as client:
        response = client.get(
            f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas", params={"limit": ATLAS_MAX_LIMIT}
        )
    assert response.status_code == 200


def test_endpoint_reports_missing_dataset(atlas_root: Path, client_for) -> None:
    with client_for(atlas_service(atlas_root)) as client:
        response = client.get("/api/v1/datasets/missing-dataset/atlas")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset 'missing-dataset' was not found."


def test_endpoint_reports_dataset_not_available_locally(tmp_path: Path, client_for) -> None:
    empty_root = tmp_path / "processed"
    empty_root.mkdir()
    with client_for(atlas_service(empty_root)) as client:
        response = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas")
    assert response.status_code == 409
    assert "not available locally" in response.json()["detail"]


def test_endpoint_reports_missing_atlas(processed_root: Path, client_for) -> None:
    with client_for(atlas_service(processed_root)) as client:
        response = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas")
    assert response.status_code == 409
    assert response.json()["detail"] == f"Atlas for dataset '{SAMPLE_DATASET_ID}' was not found."


def test_endpoint_reports_missing_semantic_index(atlas_root: Path, client_for) -> None:
    (atlas_root / SAMPLE_DATASET_ID / "semantic" / "embeddings.npy").unlink()
    with client_for(atlas_service(atlas_root)) as client:
        response = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas")
    assert response.status_code == 409
    assert "Semantic index" in response.json()["detail"]


def test_endpoint_reports_stale_atlas(atlas_root: Path, client_for) -> None:
    SemanticIndexer(FakeEmbeddingProvider(dimension=24)).build(SAMPLE_DATASET_ID, atlas_root)
    with client_for(atlas_service(atlas_root)) as client:
        response = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas")
    assert response.status_code == 409
    assert "stale" in response.json()["detail"]


def test_endpoint_hides_internal_details_for_invalid_atlas(
    atlas_root: Path, client_for
) -> None:
    (atlas_root / SAMPLE_DATASET_ID / "atlas" / "atlas-manifest.json").write_text(
        "{not json", encoding="utf-8"
    )
    with client_for(atlas_service(atlas_root)) as client:
        response = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/atlas")
    assert response.status_code == 500
    assert response.json() == {"detail": f"Atlas for dataset '{SAMPLE_DATASET_ID}' is invalid."}
    assert "Traceback" not in response.text
    assert str(atlas_root) not in response.text
