"""Endpoints de Corpus Radio: listado de registros con audio y audio controlado."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.repositories.audio_repository import InvalidAudioIndexError, LocalAudioRepository
from app.repositories.dataset_repository import (
    DatasetNotFoundError,
    DatasetRepositoryError,
    LocalDatasetRepository,
)
from app.schemas.radio import RadioPage
from app.services.corpus_radio_service import (
    RADIO_DEFAULT_LIMIT,
    RADIO_MAX_LIMIT,
    AudioFileMissingError,
    AudioUnavailableError,
    CorpusRadioService,
    RadioRecordNotFoundError,
    RecordWithoutAudioError,
)
from app.services.semantic_search_service import DatasetNotAvailableLocallyError

router = APIRouter(prefix="/datasets", tags=["corpus-radio"])

# Reproducción en línea: sin nombre de archivo, sin caché persistente y sin sniffing.
AUDIO_HEADERS = {
    "Content-Disposition": "inline",
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
}


@lru_cache
def get_corpus_radio_service() -> CorpusRadioService:
    settings = get_settings()
    datasets = LocalDatasetRepository(
        [settings.dataset_registry_path, settings.dataset_catalog_path],
        processed_directory=settings.dataset_processed_path,
    )
    return CorpusRadioService(
        datasets, LocalAudioRepository(settings.dataset_processed_path), settings.dataset_raw_path
    )


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, (DatasetNotFoundError, RadioRecordNotFoundError, RecordWithoutAudioError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, AudioFileMissingError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, (DatasetNotAvailableLocallyError, AudioUnavailableError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    if isinstance(error, InvalidAudioIndexError):
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Dataset registry source could not be loaded.",
    )


CONTROLLED_ERRORS = (
    DatasetRepositoryError,
    DatasetNotAvailableLocallyError,
    RadioRecordNotFoundError,
    RecordWithoutAudioError,
    AudioFileMissingError,
    AudioUnavailableError,
    InvalidAudioIndexError,
)


@router.get("/{dataset_id}/radio", response_model=RadioPage)
def list_radio(
    dataset_id: str,
    limit: int = Query(default=RADIO_DEFAULT_LIMIT, ge=1, le=RADIO_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    service: CorpusRadioService = Depends(get_corpus_radio_service),
) -> RadioPage:
    try:
        return service.list_radio(dataset_id, limit, offset)
    except CONTROLLED_ERRORS as error:
        raise _http_error(error) from None


@router.get("/{dataset_id}/records/{source_record_id:path}/audio")
def get_record_audio(
    dataset_id: str,
    source_record_id: str,
    service: CorpusRadioService = Depends(get_corpus_radio_service),
) -> FileResponse:
    try:
        resolved = service.resolve_audio(dataset_id, source_record_id)
    except CONTROLLED_ERRORS as error:
        raise _http_error(error) from None
    # FileResponse de Starlette atiende Range (206/416) para permitir avanzar y retroceder.
    return FileResponse(resolved.path, media_type=resolved.media_type, headers=AUDIO_HEADERS)
