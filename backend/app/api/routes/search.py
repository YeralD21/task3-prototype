"""Endpoint de búsqueda semántica local."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.embeddings.sentence_transformer_provider import (
    EmbeddingProviderUnavailableError,
    SentenceTransformerProvider,
)
from app.repositories.dataset_repository import (
    DatasetNotFoundError,
    DatasetRepositoryError,
    LocalDatasetRepository,
)
from app.repositories.semantic_index_repository import (
    InvalidSemanticIndexError,
    LocalSemanticIndexRepository,
    SemanticIndexModelMismatchError,
    SemanticIndexNotFoundError,
    StaleSemanticIndexError,
)
from app.schemas.semantic_search import (
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResultItem,
)
from app.services.semantic_search_service import (
    DatasetNotAvailableLocallyError,
    SemanticSearchService,
)

router = APIRouter(prefix="/search", tags=["search"])


@lru_cache
def get_semantic_search_service() -> SemanticSearchService:
    settings = get_settings()
    datasets = LocalDatasetRepository(
        [settings.dataset_registry_path, settings.dataset_catalog_path],
        processed_directory=settings.dataset_processed_path,
    )
    return SemanticSearchService(
        datasets,
        LocalSemanticIndexRepository(settings.dataset_processed_path),
        SentenceTransformerProvider(settings.embedding_model_name),
    )


@router.post("/semantic", response_model=SemanticSearchResponse)
def semantic_search(
    request: SemanticSearchRequest,
    service: SemanticSearchService = Depends(get_semantic_search_service),
) -> SemanticSearchResponse:
    try:
        items = service.search(request.query, request.dataset_id, request.limit)
    except DatasetNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    except (DatasetNotAvailableLocallyError, SemanticIndexNotFoundError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    except (StaleSemanticIndexError, SemanticIndexModelMismatchError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    except EmbeddingProviderUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from None
    except InvalidSemanticIndexError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)
        ) from None
    except DatasetRepositoryError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dataset registry source could not be loaded.",
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from None
    return SemanticSearchResponse(
        query=request.query,
        dataset_id=request.dataset_id,
        items=[SemanticSearchResultItem(record=item.record, score=item.score) for item in items],
    )

