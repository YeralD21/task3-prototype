"""Lectura y validación del Atlas Vivo materializado localmente."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.repositories.semantic_index_repository import (
    SEMANTIC_INDEX_FINGERPRINT_FILES,
    SemanticIndexNotFoundError,
    records_fingerprint,
    semantic_index_fingerprint,
)
from app.schemas.atlas import AtlasPoint

ATLAS_DIRECTORY = "atlas"
COORDINATES_FILE = "coordinates.jsonl"
MANIFEST_FILE = "atlas-manifest.json"
REQUIRED_MANIFEST_FIELDS: dict[str, type] = {
    "dataset_id": str,
    "reducer": str,
    "created_at": str,
    "source_embedding_model": str,
    "source_embedding_dimension": int,
    "record_count": int,
    "source_records_fingerprint": str,
    "semantic_index_fingerprint": str,
    "parameters": dict,
}


class AtlasError(RuntimeError):
    """Error controlado al cargar un Atlas local."""


class AtlasNotFoundError(AtlasError):
    """El dataset no tiene un Atlas publicado."""


class StaleAtlasError(AtlasError):
    """El Atlas no corresponde a los registros o embeddings actuales."""


class InvalidAtlasError(AtlasError):
    """Los artefactos del Atlas no son coherentes entre sí."""


@dataclass(frozen=True)
class LocalAtlas:
    points: tuple[AtlasPoint, ...]
    manifest: dict[str, Any]


class LocalAtlasRepository:
    def __init__(self, processed_root: Path) -> None:
        self.processed_root = Path(processed_root)

    def load(self, dataset_id: str) -> LocalAtlas:
        dataset_directory = self.processed_root / dataset_id
        atlas_directory = dataset_directory / ATLAS_DIRECTORY
        coordinates_path = atlas_directory / COORDINATES_FILE
        manifest_path = atlas_directory / MANIFEST_FILE
        if not coordinates_path.is_file() or not manifest_path.is_file():
            raise AtlasNotFoundError(f"Atlas for dataset '{dataset_id}' was not found.")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise InvalidAtlasError(f"Atlas for dataset '{dataset_id}' is invalid.") from error
        if not isinstance(manifest, dict) or any(
            not isinstance(manifest.get(key), expected) or isinstance(manifest.get(key), bool)
            for key, expected in REQUIRED_MANIFEST_FIELDS.items()
        ):
            raise InvalidAtlasError(f"Atlas for dataset '{dataset_id}' is invalid.")

        self._ensure_fresh(dataset_id, dataset_directory, manifest)
        try:
            with coordinates_path.open(encoding="utf-8") as file:
                points = tuple(AtlasPoint.model_validate_json(line) for line in file)
        except (OSError, UnicodeError, ValidationError) as error:
            raise InvalidAtlasError(f"Atlas for dataset '{dataset_id}' is invalid.") from error
        if (
            manifest["dataset_id"] != dataset_id
            or manifest["record_count"] != len(points)
            or len({point.record_id for point in points}) != len(points)
            or any(point.dataset_id != dataset_id for point in points)
        ):
            raise InvalidAtlasError(
                f"Atlas for dataset '{dataset_id}' has inconsistent metadata."
            )
        return LocalAtlas(points, manifest)

    @staticmethod
    def _ensure_fresh(dataset_id: str, dataset_directory: Path, manifest: dict[str, Any]) -> None:
        records_path = dataset_directory / "records.jsonl"
        semantic_directory = dataset_directory / "semantic"
        if not records_path.is_file() or manifest["source_records_fingerprint"] != records_fingerprint(
            records_path
        ):
            raise StaleAtlasError(
                f"Atlas for dataset '{dataset_id}' is stale: canonical records changed."
            )
        if not all(
            (semantic_directory / name).is_file() for name in SEMANTIC_INDEX_FINGERPRINT_FILES
        ):
            raise SemanticIndexNotFoundError(
                f"Semantic index for dataset '{dataset_id}' was not found; "
                "the atlas cannot be verified."
            )
        if manifest["semantic_index_fingerprint"] != semantic_index_fingerprint(
            semantic_directory
        ):
            raise StaleAtlasError(
                f"Atlas for dataset '{dataset_id}' is stale: embeddings changed."
            )
