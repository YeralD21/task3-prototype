"""Endpoints del Dataset Playbook: reglas sobre metadata, sin modelos ni red."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.repositories.dataset_repository import (
    DatasetNotFoundError,
    DatasetRepositoryError,
    LocalDatasetRepository,
)
from app.schemas.playbook import DatasetPlaybook, PlaybookDiscovery, PlaybookTask
from app.services.playbook_service import PlaybookService

router = APIRouter(tags=["playbook"])


@lru_cache
def get_playbook_service() -> PlaybookService:
    settings = get_settings()
    datasets = LocalDatasetRepository(
        [settings.dataset_registry_path, settings.dataset_catalog_path],
        processed_directory=settings.dataset_processed_path,
    )
    return PlaybookService(datasets, settings.dataset_processed_path)


def _registry_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Dataset registry source could not be loaded.",
    )


@router.get("/datasets/{dataset_id}/playbook", response_model=DatasetPlaybook)
def get_dataset_playbook(
    dataset_id: str, service: PlaybookService = Depends(get_playbook_service)
) -> DatasetPlaybook:
    try:
        return service.get_playbook(dataset_id)
    except DatasetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    except DatasetRepositoryError:
        raise _registry_error() from None


@router.get("/playbook/datasets", response_model=PlaybookDiscovery)
def discover_datasets(
    task: PlaybookTask = Query(),
    service: PlaybookService = Depends(get_playbook_service),
) -> PlaybookDiscovery:
    try:
        return service.discover(task)
    except DatasetRepositoryError:
        raise _registry_error() from None
