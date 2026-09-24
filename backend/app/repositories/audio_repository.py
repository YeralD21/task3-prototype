"""Lectura de referencias de audio materializadas; nunca abre ni copia los clips."""

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.schemas.canonical import AudioResource

AUDIO_RESOURCES_FILE = "audio-resources.jsonl"
INGESTION_MANIFEST_FILE = "ingestion-manifest.json"


class InvalidAudioIndexError(RuntimeError):
    """Las referencias de audio materializadas no son válidas."""


@dataclass(frozen=True)
class LocalAudioIndex:
    resources: dict[str, AudioResource]
    source_root: Path | None


class LocalAudioRepository:
    """Carga audio-resources.jsonl y la carpeta fuente registrada en la ingestión.

    Guarda en memoria el último índice por dataset mientras los archivos no cambien,
    porque el navegador pide el mismo audio varias veces (peticiones Range).
    """

    def __init__(self, processed_root: Path) -> None:
        self.processed_root = Path(processed_root)
        self._cache: dict[str, tuple[tuple[int, int, int, int], LocalAudioIndex]] = {}

    def load(self, dataset_id: str) -> LocalAudioIndex:
        directory = self.processed_root / dataset_id
        resources_path = directory / AUDIO_RESOURCES_FILE
        manifest_path = directory / INGESTION_MANIFEST_FILE
        key = (*self._signature(resources_path), *self._signature(manifest_path))
        cached = self._cache.get(dataset_id)
        if cached and cached[0] == key:
            return cached[1]
        index = LocalAudioIndex(
            self._load_resources(resources_path, dataset_id), self._source_root(manifest_path)
        )
        self._cache[dataset_id] = (key, index)
        return index

    @staticmethod
    def _signature(path: Path) -> tuple[int, int]:
        try:
            stat = path.stat()
        except OSError:
            return (-1, -1)
        return (stat.st_mtime_ns, stat.st_size)

    @staticmethod
    def _load_resources(path: Path, dataset_id: str) -> dict[str, AudioResource]:
        if not path.is_file():
            return {}
        resources: dict[str, AudioResource] = {}
        try:
            with path.open(encoding="utf-8") as file:
                for line in file:
                    resource = AudioResource.model_validate_json(line)
                    if resource.dataset_id != dataset_id or resource.id in resources:
                        raise ValueError("audio resource does not belong to the dataset")
                    resources[resource.id] = resource
        except (OSError, UnicodeError, ValueError, ValidationError) as error:
            raise InvalidAudioIndexError(
                f"Audio references for dataset '{dataset_id}' are invalid."
            ) from error
        return resources

    @staticmethod
    def _source_root(manifest_path: Path) -> Path | None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        source = manifest.get("source_path") if isinstance(manifest, dict) else None
        return Path(source) if isinstance(source, str) and source else None
