"""Integración del pipeline local usando exclusivamente fixtures sintéticos."""

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes.datasets import get_dataset_service
from app.main import app
from app.repositories.dataset_repository import LocalDatasetRepository
from app.services.dataset_service import DatasetService
from ml.ingestion.adapter_registry import UnknownAdapterError
from ml.ingestion.pipeline import IngestionError, ingest_dataset
from tests.conftest import PROJECT_ROOT

FIXTURES = Path(__file__).parent / "fixtures"
CATALOG = PROJECT_ROOT / "datasets" / "registry"
AMERICAS_ID = "americasnlp-2021-aymara-spanish"
COMMON_VOICE_ID = "common-voice-scripted-speech-qxp-26.0"


def _tree_digest(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_ingest_americas_nlp_creates_traceable_utf8_artifacts(tmp_path: Path) -> None:
    source = FIXTURES / "americas_nlp"
    before = _tree_digest(source)

    result = ingest_dataset("americas_nlp", source, tmp_path / "processed")
    destination = result.destination

    assert result.dataset_id == AMERICAS_ID
    assert result.record_count == 6
    assert (destination / "dataset.json").is_file()
    assert (destination / "records.jsonl").is_file()
    assert (destination / "ingestion-manifest.json").is_file()
    records = _jsonl(destination / "records.jsonl")
    assert {record["dataset_id"] for record in records} == {AMERICAS_ID}
    assert records[0]["source_record_id"] == "train.aym:1"
    assert {record["metadata"]["split"] for record in records} == {"train", "dev", "test"}
    assert "Aymara" in (destination / "records.jsonl").read_text(encoding="utf-8")
    assert _tree_digest(source) == before

    manifest = json.loads((destination / "ingestion-manifest.json").read_text("utf-8"))
    assert manifest["record_count"] == 6
    assert manifest["source_files"] == [
        "train.aym", "train.es", "dev.aym", "dev.es", "test.aym", "test.es"
    ]
    assert "text" not in manifest and "translation" not in manifest


def test_ingest_common_voice_references_audio_without_copying(tmp_path: Path) -> None:
    result = ingest_dataset(
        "common_voice", FIXTURES / "common_voice", tmp_path / "processed"
    )

    assert result.dataset_id == COMMON_VOICE_ID
    assert result.record_count == 2
    assert result.audio_resource_count == 1
    assert result.speaker_count == 1
    assert result.warnings
    assert not list(result.destination.rglob("*.mp3"))
    audio = _jsonl(result.destination / "audio-resources.jsonl")[0]
    assert audio["source_audio_id"] == "synthetic-clip-001.mp3"
    assert "fixtures" in audio["path_or_url"]
    assert "á" in (result.destination / "records.jsonl").read_text(encoding="utf-8")
    speakers = _jsonl(result.destination / "speakers.jsonl")
    assert speakers[0]["metadata"]["do_not_attempt_reidentification"] is True


def test_reingestion_safely_replaces_materialization(tmp_path: Path) -> None:
    output = tmp_path / "processed"
    first = ingest_dataset("common_voice", FIXTURES / "common_voice", output)
    (first.destination / "obsolete.txt").write_text("old", encoding="utf-8")

    second = ingest_dataset("common_voice", FIXTURES / "common_voice", output)

    assert second.destination == first.destination
    assert not (second.destination / "obsolete.txt").exists()
    assert len(_jsonl(second.destination / "records.jsonl")) == 2
    assert not list(output.glob(".*.backup-*"))


def test_missing_input_and_unknown_adapter_are_reported(tmp_path: Path) -> None:
    with pytest.raises(IngestionError, match="does not exist"):
        ingest_dataset("common_voice", tmp_path / "missing", tmp_path / "processed")
    with pytest.raises(UnknownAdapterError, match="Unknown adapter"):
        ingest_dataset("not_registered", tmp_path / "missing", tmp_path / "processed")


def test_output_cannot_modify_source(tmp_path: Path) -> None:
    source = FIXTURES / "common_voice"
    with pytest.raises(IngestionError, match="immutable source"):
        ingest_dataset("common_voice", source, source / "processed")


def test_repository_merges_catalog_and_processed_records(tmp_path: Path) -> None:
    output = tmp_path / "processed"
    ingest_dataset("americas_nlp", FIXTURES / "americas_nlp", output)
    repository = LocalDatasetRepository(CATALOG, processed_directory=output)

    dataset = repository.get_dataset(AMERICAS_ID)
    records = repository.list_records(AMERICAS_ID)

    assert dataset.metadata["cataloged"] is True
    assert dataset.metadata["available_locally"] is True
    assert len(records) == 6
    assert records[0].source_record_id == "train.aym:1"


def test_corpus_explorer_reads_and_searches_processed_records(tmp_path: Path) -> None:
    output = tmp_path / "processed"
    ingest_dataset("americas_nlp", FIXTURES / "americas_nlp", output)
    service = DatasetService(LocalDatasetRepository(CATALOG, processed_directory=output))
    app.dependency_overrides[get_dataset_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/datasets/{AMERICAS_ID}/records",
                params={"q": "translation train 002", "limit": 1},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["dataset_id"] == AMERICAS_ID
    assert payload["items"][0]["metadata"]["split"] == "train"
