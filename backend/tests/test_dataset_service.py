"""Pruebas de filtros y paginación del Dataset Registry."""

from app.services.dataset_service import DatasetService
from tests.conftest import SAMPLE_DATASET_ID


def test_filter_datasets_by_language(service: DatasetService) -> None:
    datasets = service.list_datasets(language="und")

    assert [dataset.id for dataset in datasets] == [SAMPLE_DATASET_ID]


def test_filter_datasets_by_modality(service: DatasetService) -> None:
    datasets = service.list_datasets(modality="audio")

    assert [dataset.id for dataset in datasets] == [SAMPLE_DATASET_ID]


def test_filter_datasets_by_task(service: DatasetService) -> None:
    datasets = service.list_datasets(task="machine_translation")

    assert [dataset.id for dataset in datasets] == [SAMPLE_DATASET_ID]


def test_paginate_records(service: DatasetService) -> None:
    records = service.get_dataset_records(SAMPLE_DATASET_ID, limit=1, offset=1)

    assert len(records) == 1
    assert records[0].id == "synthetic-record-002"
