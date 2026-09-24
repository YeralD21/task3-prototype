"""Lectura y validación del índice semántico materializado localmente."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


class SemanticIndexError(RuntimeError):
    """Error controlado al cargar un índice semántico local."""


class SemanticIndexNotFoundError(SemanticIndexError):
    """El dataset no tiene un índice semántico publicado."""


class StaleSemanticIndexError(SemanticIndexError):
    """El índice no corresponde al records.jsonl actual."""


class InvalidSemanticIndexError(SemanticIndexError):
    """Los artefactos del índice no son coherentes entre sí."""


class SemanticIndexModelMismatchError(SemanticIndexError):
    """El proveedor configurado no corresponde al usado para indexar."""


@dataclass(frozen=True)
class LocalSemanticIndex:
    embeddings: np.ndarray
    record_ids: tuple[str, ...]
    manifest: dict[str, Any]
    source_record_ids: tuple[str, ...] = ()


def records_fingerprint(records_path: Path) -> str:
    """Calcula SHA-256 sobre los bytes exactos del archivo canónico."""

    digest = hashlib.sha256()
    with records_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


SEMANTIC_INDEX_FINGERPRINT_FILES = ("embeddings.npy", "records.jsonl")


def semantic_index_fingerprint(semantic_directory: Path) -> str:
    """SHA-256 de la matriz y del mapeo de filas; cambia si cambia un embedding o su orden."""

    digest = hashlib.sha256()
    for name in SEMANTIC_INDEX_FINGERPRINT_FILES:
        path = Path(semantic_directory) / name
        digest.update(f"{name}\n{path.stat().st_size}\n".encode("utf-8"))
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


class LocalSemanticIndexRepository:
    def __init__(self, processed_root: Path) -> None:
        self.processed_root = Path(processed_root)

    def load(self, dataset_id: str) -> LocalSemanticIndex:
        dataset_directory = self.processed_root / dataset_id
        records_path = dataset_directory / "records.jsonl"
        semantic_directory = dataset_directory / "semantic"
        embeddings_path = semantic_directory / "embeddings.npy"
        mapping_path = semantic_directory / "records.jsonl"
        manifest_path = semantic_directory / "index-manifest.json"
        if not records_path.is_file() or not all(
            path.is_file() for path in (embeddings_path, mapping_path, manifest_path)
        ):
            raise SemanticIndexNotFoundError(
                f"Semantic index for dataset '{dataset_id}' was not found."
            )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            embeddings = np.load(embeddings_path, allow_pickle=False)
            mappings = [json.loads(line) for line in mapping_path.read_text(encoding="utf-8").splitlines()]
            record_ids = tuple(item["record_id"] for item in mappings)
            source_record_ids = tuple(item["source_record_id"] for item in mappings)
        except (OSError, EOFError, UnicodeError, json.JSONDecodeError, KeyError, ValueError) as error:
            raise InvalidSemanticIndexError(
                f"Semantic index for dataset '{dataset_id}' is invalid."
            ) from error
        if manifest.get("source_records_fingerprint") != records_fingerprint(records_path):
            raise StaleSemanticIndexError(
                f"Semantic index for dataset '{dataset_id}' is stale."
            )
        expected = manifest.get("record_count")
        dimension = manifest.get("dimension")
        if (
            manifest.get("dataset_id") != dataset_id
            or embeddings.ndim != 2
            or embeddings.shape != (expected, dimension)
            or len(record_ids) != expected
            or len(set(record_ids)) != len(record_ids)
            or any(item.get("dataset_id") != dataset_id for item in mappings)
            or not np.isfinite(embeddings).all()
        ):
            raise InvalidSemanticIndexError(
                f"Semantic index for dataset '{dataset_id}' has inconsistent metadata."
            )
        return LocalSemanticIndex(embeddings, record_ids, manifest, source_record_ids)
