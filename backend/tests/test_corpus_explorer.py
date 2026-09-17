"""Text search, pagination, and traceability for the Corpus Explorer."""

from copy import deepcopy

from app.services.dataset_service import DatasetService
from tests.conftest import SAMPLE_DATASET_ID


def test_search_text_case_insensitive(service: DatasetService) -> None:
    page = service.get_dataset_records(SAMPLE_DATASET_ID, q="SENTENCE 001")
    assert page.total == 1
    assert page.items[0].source_record_id == "synthetic-source-record-001"


def test_search_translation(service: DatasetService) -> None:
    page = service.get_dataset_records(SAMPLE_DATASET_ID, q="spanish translation")
    assert page.total == 1
    assert page.items[0].id == "synthetic-record-002"


def test_search_without_matches(service: DatasetService) -> None:
    page = service.get_dataset_records(SAMPLE_DATASET_ID, q="absent phrase")
    assert page.items == []
    assert page.total == 0


def test_search_then_paginate_and_preserve_traceability(
    service: DatasetService,
) -> None:
    page = service.get_dataset_records(
        SAMPLE_DATASET_ID, q="synthetic", limit=1, offset=1
    )
    assert page.total == 3
    assert page.items[0].dataset_id == SAMPLE_DATASET_ID
    assert page.items[0].source_record_id == "synthetic-source-record-002"


def test_search_does_not_modify_original_records(service: DatasetService) -> None:
    before = deepcopy(service.repository.list_records(SAMPLE_DATASET_ID))
    service.get_dataset_records(SAMPLE_DATASET_ID, q="SYNTHETIC")
    assert service.repository.list_records(SAMPLE_DATASET_ID) == before
