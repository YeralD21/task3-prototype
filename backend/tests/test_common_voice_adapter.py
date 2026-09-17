"""Pruebas del adaptador local de Common Voice con TSV sintético."""

import socket
from pathlib import Path

import pytest

from ml.ingestion.adapters.common_voice_adapter import (
    CommonVoiceAdapter,
    CommonVoiceSourceNotFoundError,
)
from app.repositories.dataset_repository import LocalDatasetRepository
from tests.conftest import PROJECT_ROOT

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures" / "common_voice"
DATASET_ID = "common-voice-scripted-speech-qxp-26.0"


@pytest.fixture
def adapter() -> CommonVoiceAdapter:
    return CommonVoiceAdapter(FIXTURE_DIRECTORY)


def test_load_real_catalog_metadata(adapter: CommonVoiceAdapter) -> None:
    dataset = adapter.load_metadata()

    assert dataset.id == DATASET_ID
    assert dataset.license.name == "CC0-1.0"
    assert dataset.metadata["cataloged"] is True


def test_parse_synthetic_tsv_row(adapter: CommonVoiceAdapter) -> None:
    records = adapter.load_records()

    assert records[0].text == "[synthetic source sentence 001]"
    assert records[0].metadata["synthetic"] == "true"


def test_create_corpus_record_with_traceability(adapter: CommonVoiceAdapter) -> None:
    record = adapter.load_records()[0]

    assert record.dataset_id == DATASET_ID
    assert record.source_record_id == "synthetic-clip-001.mp3"
    assert record.provenance.original_dataset_id == "common-voice-scripted-speech-26.0-qxp"


def test_create_audio_resource_from_clip_path(adapter: CommonVoiceAdapter) -> None:
    resources = adapter.load_audio_resources()

    assert len(resources) == 1
    assert resources[0].source_audio_id == "synthetic-clip-001.mp3"
    assert resources[0].path_or_url == str(
        FIXTURE_DIRECTORY / "clips" / "synthetic-clip-001.mp3"
    )


def test_handle_row_without_audio(adapter: CommonVoiceAdapter) -> None:
    records = adapter.load_records()

    assert records[1].audio_id is None
    assert records[1].source_record_id == "validated.tsv:row:3"


def test_preserve_qxp_variety(adapter: CommonVoiceAdapter) -> None:
    record = adapter.load_records()[0]

    assert record.language_code == "qxp"
    assert record.language_variety.id == "qxp"
    assert record.language_variety.name == "Puno Quechua / Punu qhichwa"


def test_optional_fields_can_be_missing(adapter: CommonVoiceAdapter) -> None:
    record = adapter.load_records()[1]

    assert record.speaker_id is None
    assert record.translation is None


def test_create_only_pseudonymous_speaker(adapter: CommonVoiceAdapter) -> None:
    speakers = adapter.load_speakers()

    assert len(speakers) == 1
    assert speakers[0].source_speaker_id == "synthetic-client-001"
    assert speakers[0].metadata["do_not_attempt_reidentification"] is True


def test_report_missing_dataset_directory(tmp_path: Path) -> None:
    adapter = CommonVoiceAdapter(tmp_path / "common-voice-puno")

    with pytest.raises(CommonVoiceSourceNotFoundError, match="manually obtained"):
        adapter.load_records()


def test_adapter_does_not_use_network(
    adapter: CommonVoiceAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access is not allowed")

    monkeypatch.setattr(socket, "create_connection", reject_network)

    assert adapter.load_metadata().id == DATASET_ID
    assert len(adapter.load_records()) == 2


def test_manifest_lives_in_registry() -> None:
    manifest = (
        PROJECT_ROOT
        / "datasets"
        / "registry"
        / "quechua"
        / "common-voice-puno-quechua.json"
    )

    assert manifest.is_file()


def test_registry_catalogs_dataset_without_local_corpus() -> None:
    repository = LocalDatasetRepository(
        [PROJECT_ROOT / "data" / "samples", PROJECT_ROOT / "datasets" / "registry"]
    )

    dataset = repository.get_dataset(DATASET_ID)

    assert dataset.metadata["available_locally"] is False
    assert repository.list_records(DATASET_ID) == []
