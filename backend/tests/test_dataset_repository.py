"""Pruebas de acceso local a datasets."""

from pathlib import Path

import pytest

from app.repositories.dataset_repository import (
    DatasetSourceNotFoundError,
    InvalidDatasetSourceError,
    LocalDatasetRepository,
)
from tests.conftest import SAMPLE_DATASET_ID


def test_repository_preserves_record_traceability(
    repository: LocalDatasetRepository,
) -> None:
    record = repository.list_records(SAMPLE_DATASET_ID)[0]

    assert record.dataset_id == SAMPLE_DATASET_ID
    assert record.source_record_id == "synthetic-source-record-001"
    assert record.provenance.source_name == "task3-prototype synthetic fixture"


def test_repository_handles_missing_source(tmp_path: Path) -> None:
    repository = LocalDatasetRepository(tmp_path / "missing")

    with pytest.raises(DatasetSourceNotFoundError):
        repository.list_datasets()


def test_repository_handles_invalid_json(tmp_path: Path) -> None:
    (tmp_path / "invalid.json").write_text("{not valid json", encoding="utf-8")
    repository = LocalDatasetRepository(tmp_path)

    with pytest.raises(InvalidDatasetSourceError):
        repository.list_datasets()
