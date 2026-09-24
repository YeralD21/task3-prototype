"""Corpus Radio: lista registros con audio local y resuelve cada clip de forma segura.

El cliente nunca aporta rutas. Un clip se localiza solo mediante
dataset_id → CorpusRecord (por source_record_id) → AudioResource (por audio_id),
y la ruta resultante debe quedar dentro de la carpeta fuente registrada en la
ingestión, que a su vez debe estar dentro de la raíz raw autorizada.
"""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from app.repositories.audio_repository import LocalAudioIndex, LocalAudioRepository
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.canonical import AudioResource, CorpusRecord, Dataset
from app.schemas.radio import AudioStatus, RadioItem, RadioPage
from app.services.semantic_search_service import DatasetNotAvailableLocallyError

RADIO_DEFAULT_LIMIT = 20
RADIO_MAX_LIMIT = 100

# Formatos que el navegador reproduce con <audio>; no se asume que todo sea MP3.
AUDIO_MEDIA_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".webm": "audio/webm",
}


class RadioRecordNotFoundError(LookupError):
    """El registro no existe en la copia local del dataset."""


class RecordWithoutAudioError(LookupError):
    """El registro no referencia audio."""


class AudioFileMissingError(LookupError):
    """El registro referencia audio, pero el archivo no está en la copia local."""


class AudioUnavailableError(RuntimeError):
    """La referencia no puede servirse desde esta instalación (formato, ubicación o fuente)."""


@dataclass(frozen=True)
class ResolvedAudio:
    status: AudioStatus
    path: Path | None = None
    media_type: str | None = None


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def audio_url(dataset_id: str, source_record_id: str) -> str:
    return (
        f"/api/v1/datasets/{quote(dataset_id, safe='')}/records/"
        f"{quote(source_record_id, safe='')}/audio"
    )


class CorpusRadioService:
    def __init__(
        self,
        dataset_repository: DatasetRepository,
        audio_repository: LocalAudioRepository,
        raw_root: Path,
    ) -> None:
        self.dataset_repository = dataset_repository
        self.audio_repository = audio_repository
        self.raw_root = Path(raw_root)

    def list_radio(
        self, dataset_id: str, limit: int = RADIO_DEFAULT_LIMIT, offset: int = 0
    ) -> RadioPage:
        if not 1 <= limit <= RADIO_MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {RADIO_MAX_LIMIT}")
        if offset < 0:
            raise ValueError("offset must be non-negative")
        dataset = self.dataset_repository.get_dataset(dataset_id)
        if not self._contains_audio(dataset):
            return RadioPage(
                dataset_id=dataset.id, contains_audio=False, items=[], total=0,
                limit=limit, offset=offset,
            )
        self._require_local(dataset)
        with_audio = [
            record for record in self.dataset_repository.list_records(dataset_id) if record.audio_id
        ]
        index = self.audio_repository.load(dataset_id)
        items = []
        for record in with_audio[offset : offset + limit]:
            resolved = self._resolve_record(record, index)
            items.append(
                RadioItem(
                    record=record,  # RadioItem aplica la vista pública
                    has_audio=True,
                    audio_status=resolved.status,
                    audio_url=(
                        audio_url(dataset.id, record.source_record_id)
                        if resolved.status == "available"
                        else None
                    ),
                    media_type=resolved.media_type,
                )
            )
        return RadioPage(
            dataset_id=dataset.id, contains_audio=True, items=items,
            total=len(with_audio), limit=limit, offset=offset,
        )

    def resolve_audio(self, dataset_id: str, source_record_id: str) -> ResolvedAudio:
        dataset = self.dataset_repository.get_dataset(dataset_id)
        self._require_local(dataset)
        matches = [
            record
            for record in self.dataset_repository.list_records(dataset_id)
            if record.source_record_id == source_record_id
        ]
        if len(matches) != 1:
            raise RadioRecordNotFoundError(
                f"Record '{source_record_id}' was not found in dataset '{dataset_id}'."
            )
        record = matches[0]
        if not record.audio_id:
            raise RecordWithoutAudioError(f"Record '{source_record_id}' has no audio.")
        resolved = self._resolve_record(record, self.audio_repository.load(dataset_id))
        if resolved.status == "missing_file":
            raise AudioFileMissingError(
                f"Audio for record '{source_record_id}' is not available locally."
            )
        if resolved.status != "available":
            raise AudioUnavailableError(
                f"Audio for record '{source_record_id}' cannot be served by this installation."
            )
        return resolved

    @staticmethod
    def _contains_audio(dataset: Dataset) -> bool:
        return "audio" in {value.casefold() for value in dataset.modalities or []}

    @staticmethod
    def _require_local(dataset: Dataset) -> None:
        if (dataset.metadata or {}).get("available_locally") is not True:
            raise DatasetNotAvailableLocallyError(
                f"Dataset '{dataset.id}' is not available locally."
            )

    def _resolve_record(self, record: CorpusRecord, index: LocalAudioIndex) -> ResolvedAudio:
        resource = index.resources.get(record.audio_id or "")
        if resource is None:
            return ResolvedAudio("unavailable")
        return self._resolve_resource(resource, index.source_root)

    def _resolve_resource(self, resource: AudioResource, source_root: Path | None) -> ResolvedAudio:
        reference = resource.path_or_url
        if not reference or "://" in reference or source_root is None:
            return ResolvedAudio("unavailable")
        raw_root = self.raw_root.resolve()
        source = source_root.resolve()
        if not _inside(source, raw_root):
            return ResolvedAudio("unavailable")
        candidate = Path(reference)
        path = (candidate if candidate.is_absolute() else source / candidate).resolve()
        # Se valida la contención antes de consultar el disco para no revelar qué existe fuera.
        if not _inside(path, source):
            return ResolvedAudio("unavailable")
        media_type = AUDIO_MEDIA_TYPES.get(path.suffix.lower())
        if media_type is None and (resource.mime_type or "").startswith("audio/"):
            media_type = resource.mime_type
        if media_type is None:
            return ResolvedAudio("unsupported_format")
        if not path.is_file():
            return ResolvedAudio("missing_file", media_type=media_type)
        return ResolvedAudio("available", path, media_type)
