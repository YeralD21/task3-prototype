"""Endpoints HTTP del Dataset Registry."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.repositories.dataset_repository import (
    DatasetNotFoundError,
    DatasetRepositoryError,
    LocalDatasetRepository,
)
from app.schemas.canonical import CorpusRecord, Dataset
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["datasets"])


@lru_cache
def get_dataset_service() -> DatasetService:
    """Construye el servicio local; puede sustituirse mediante dependencias."""

    settings = get_settings()
    repository = LocalDatasetRepository(
        [settings.dataset_registry_path, settings.dataset_catalog_path]
    )
    return DatasetService(repository)


def _raise_http_error(error: DatasetRepositoryError) -> None:
    if isinstance(error, DatasetNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Dataset registry source could not be loaded.",
    ) from None


@router.get("", response_model=list[Dataset])
def list_datasets(
    language: str | None = None,
    variety: str | None = None,
    modality: str | None = None,
    task: str | None = None,
    domain: str | None = None,
    service: DatasetService = Depends(get_dataset_service),
) -> list[Dataset]:
    try:
        return service.list_datasets(
            language=language,
            variety=variety,
            modality=modality,
            task=task,
            domain=domain,
        )
    except DatasetRepositoryError as error:
        _raise_http_error(error)


@router.get("/{dataset_id}", response_model=Dataset)
def get_dataset(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> Dataset:
    try:
        return service.get_dataset(dataset_id)
    except DatasetRepositoryError as error:
        _raise_http_error(error)


@router.get("/{dataset_id}/records", response_model=list[CorpusRecord])
def list_dataset_records(
    dataset_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    language: str | None = None,
    language_variety: str | None = None,
    service: DatasetService = Depends(get_dataset_service),
) -> list[CorpusRecord]:
    try:
        return service.get_dataset_records(
            dataset_id,
            limit=limit,
            offset=offset,
            language=language,
            language_variety=language_variety,
        )
    except DatasetRepositoryError as error:
        _raise_http_error(error)
