"""Fixtures compartidos para el Dataset Registry."""

from collections.abc import Iterator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

from app.api.routes.datasets import get_dataset_service
from app.main import app
from app.repositories.dataset_repository import LocalDatasetRepository
from app.services.dataset_service import DatasetService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SAMPLE_DIRECTORY = PROJECT_ROOT / "data" / "samples"
SAMPLE_DATASET_ID = "synthetic-development-dataset"


@pytest.fixture
def repository() -> LocalDatasetRepository:
    return LocalDatasetRepository(SAMPLE_DIRECTORY)


@pytest.fixture
def service(repository: LocalDatasetRepository) -> DatasetService:
    return DatasetService(repository)


@pytest.fixture
def client(service: DatasetService) -> Iterator[TestClient]:
    app.dependency_overrides[get_dataset_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
