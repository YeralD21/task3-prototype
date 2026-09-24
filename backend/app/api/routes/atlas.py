"""Endpoint de lectura del Atlas Vivo."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import get_settings
from app.repositories.atlas_repository import (
    AtlasNotFoundError,
    InvalidAtlasError,
    LocalAtlasRepository,
    StaleAtlasError,
)
from app.repositories.dataset_repository import (
    DatasetNotFoundError,
    DatasetRepositoryError,
    LocalDatasetRepository,
)
from app.repositories.semantic_index_repository import SemanticIndexNotFoundError
from app.schemas.atlas import AtlasResponse, AtlasResponseItem, AtlasSampling
from app.services.atlas_service import (
    ATLAS_DEFAULT_LIMIT,
    ATLAS_MAX_LIMIT,
    SAMPLING_METHOD,
    AtlasService,
)
from app.services.semantic_search_service import DatasetNotAvailableLocallyError

router = APIRouter(prefix="/datasets", tags=["atlas"])


@lru_cache
def get_atlas_service() -> AtlasService:
    settings = get_settings()
    datasets = LocalDatasetRepository(
        [settings.dataset_registry_path, settings.dataset_catalog_path],
        processed_directory=settings.dataset_processed_path,
    )
    return AtlasService(datasets, LocalAtlasRepository(settings.dataset_processed_path))


@router.get("/{dataset_id}/atlas", response_model=AtlasResponse)
def get_dataset_atlas(
    dataset_id: str,
    limit: int = Query(default=ATLAS_DEFAULT_LIMIT, ge=1, le=ATLAS_MAX_LIMIT),
    service: AtlasService = Depends(get_atlas_service),
) -> AtlasResponse:
    try:
        view = service.get_atlas(dataset_id, limit)
    except DatasetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    except (
        DatasetNotAvailableLocallyError,
        AtlasNotFoundError,
        SemanticIndexNotFoundError,
        StaleAtlasError,
    ) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    except InvalidAtlasError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)
        ) from None
    except DatasetRepositoryError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dataset registry source could not be loaded.",
        ) from None
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from None
    manifest = view.atlas.manifest
    return AtlasResponse(
        dataset_id=dataset_id,
        reducer=manifest["reducer"],
        created_at=manifest["created_at"],
        source_embedding_model=manifest["source_embedding_model"],
        source_embedding_dimension=manifest["source_embedding_dimension"],
        parameters=manifest["parameters"],
        diagnostics=diagnostics if isinstance(diagnostics := manifest.get("diagnostics"), dict) else {},
        total_records=len(view.atlas.points),
        returned_records=len(view.points),
        limit=limit,
        sampling=AtlasSampling(
            applied=view.sampled, method=SAMPLING_METHOD if view.sampled else "none"
        ),
        items=[
            AtlasResponseItem(**point.model_dump(), record=record)
            for point, record in zip(view.points, view.records)
        ],
    )
