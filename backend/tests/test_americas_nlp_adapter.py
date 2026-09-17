"""Offline tests for aligned text ingestion and the multi-provider catalog."""

import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes.datasets import get_dataset_service
from app.main import app
from ml.ingestion.adapters.americas_nlp_adapter import (
    AmericasNLPAdapter, AmericasNLPAdapterError,
)
from ml.ingestion.base_adapter import CorpusAdapter

FIXTURES = Path(__file__).parent / "fixtures/americas_nlp"
DATASET_ID = "americasnlp-2021-aymara-spanish"


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(*args: object, **kwargs: object) -> None:
        raise AssertionError("Network access forbidden in adapter tests")
    monkeypatch.setattr(socket, "create_connection", reject)
    monkeypatch.setattr(socket.socket, "connect", reject)
    monkeypatch.setattr(socket.socket, "connect_ex", reject)
    monkeypatch.setattr(socket, "getaddrinfo", reject)


def test_metadata_without_corpus(tmp_path: Path) -> None:
    adapter: CorpusAdapter = AmericasNLPAdapter(tmp_path / "missing")
    dataset = adapter.load_metadata()
    assert dataset.id == DATASET_ID
    assert dataset.metadata["cataloged"] is True
    assert dataset.metadata["available_locally"] is False
    assert dataset.license.name is None
    assert dataset.license.redistribution is None


@pytest.mark.parametrize("split", ["train", "dev", "test"])
def test_parallel_pairs_and_traceability(split: str) -> None:
    adapter = AmericasNLPAdapter(FIXTURES, splits=(split,), synthetic=True)
    records = adapter.load_records()
    assert len(records) == 2
    record = records[0]
    assert record.dataset_id == DATASET_ID
    assert record.source_record_id == f"{split}.aym:1"
    assert record.id == adapter.load_records()[0].id
    assert record.text == f"[synthetic development_only Aymara sentence {split} 001]"
    assert record.translation == f"[synthetic development_only Spanish translation {split} 001]"
    assert record.language.name == "Aymara"
    assert record.language_code == record.language.iso_code == "aym"
    assert record.translation_language.iso_code == "es"
    assert record.metadata["split"] == split
    assert record.metadata["synthetic"] is True
    assert record.metadata["development_only"] is True
    assert "Synthetic" in record.provenance.notes
    assert record.audio_id is None and record.speaker_id is None
    if split == "train":
        assert record.language_variety is None
    else:
        assert record.language_variety.id == "ayr"
        assert record.language_code == "aym"


def test_all_splits_keep_unique_ids() -> None:
    records = AmericasNLPAdapter(
        FIXTURES, splits=("train", "dev", "test"), synthetic=True
    ).load_records()
    assert len({r.id for r in records}) == 6
    assert {r.metadata["split"] for r in records} == {"train", "dev", "test"}


def test_preserve_text_and_upstream_source(tmp_path: Path) -> None:
    # Test-generated synthetic data; whitespace must not be normalized.
    (tmp_path / "train.aym").write_bytes(b"  [synthetic development_only]  \r\n")
    (tmp_path / "train.es").write_bytes(b" [synthetic development_only translation] \r\n")
    record = AmericasNLPAdapter(tmp_path).load_records()[0]
    assert record.text == "  [synthetic development_only]  "
    assert record.translation == " [synthetic development_only translation] "
    assert "Global Voices via OPUS" in record.provenance.notes


@pytest.mark.parametrize("split", ["dev", "test"])
def test_evaluation_source_not_global_voices(split: str) -> None:
    record = AmericasNLPAdapter(FIXTURES, splits=(split,)).load_records()[0]
    assert "AmericasNLI" in record.provenance.notes
    assert "Global Voices" not in record.provenance.notes


def test_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(AmericasNLPAdapterError, match="manually obtained"):
        AmericasNLPAdapter(tmp_path / "absent").load_records()


def test_missing_translation_file(tmp_path: Path) -> None:
    (tmp_path / "train.aym").write_text("[synthetic development_only]\n", encoding="utf-8")
    with pytest.raises(AmericasNLPAdapterError, match="train.es"):
        AmericasNLPAdapter(tmp_path).load_records()


@pytest.mark.parametrize(
    "source,target",
    [("one\ntwo\n", "one\n"), ("one\n", "one\ntwo\n"),
     ("\n", "one\n"), ("one\n", "  \n")],
)
def test_invalid_alignment(tmp_path: Path, source: str, target: str) -> None:
    (tmp_path / "train.aym").write_text(source, encoding="utf-8")
    (tmp_path / "train.es").write_text(target, encoding="utf-8")
    with pytest.raises(AmericasNLPAdapterError, match="line"):
        AmericasNLPAdapter(tmp_path, synthetic=True).load_records()


def test_invalid_encoding(tmp_path: Path) -> None:
    (tmp_path / "train.aym").write_bytes(b"\xff")
    (tmp_path / "train.es").write_text("synthetic development_only", encoding="utf-8")
    with pytest.raises(AmericasNLPAdapterError, match="UTF-8"):
        AmericasNLPAdapter(tmp_path).load_records()


@pytest.mark.parametrize("splits", [(), ("other",), ("train", "train")])
def test_invalid_split_selection(splits: tuple[str, ...]) -> None:
    with pytest.raises(AmericasNLPAdapterError):
        AmericasNLPAdapter(FIXTURES, splits=splits)


def test_default_api_catalog_and_existing_filters() -> None:
    # No dependency override: exercise the actual configured repository paths.
    get_dataset_service.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/datasets")
            assert response.status_code == 200
            ids = {item["id"] for item in response.json()}
            common_voice = "common-voice-scripted-speech-qxp-26.0"
            assert {common_voice, DATASET_ID} <= ids
            for query, expected in [
                ({"language": "qxp"}, common_voice),
                ({"language": "aym"}, DATASET_ID),
                ({"modality": "audio"}, common_voice),
                ({"modality": "parallel_text"}, DATASET_ID),
                ({"task": "machine_translation"}, DATASET_ID),
            ]:
                filtered = client.get("/api/v1/datasets", params=query)
                assert filtered.status_code == 200
                assert expected in {item["id"] for item in filtered.json()}
                if query in ({"language": "qxp"}, {"modality": "audio"}):
                    assert DATASET_ID not in {item["id"] for item in filtered.json()}
                if query in ({"language": "aym"}, {"modality": "parallel_text"}):
                    assert common_voice not in {item["id"] for item in filtered.json()}
            assert client.get(f"/api/v1/datasets/{DATASET_ID}/records").json() == []
    finally:
        get_dataset_service.cache_clear()
