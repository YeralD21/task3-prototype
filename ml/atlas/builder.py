"""Construye coordenadas 2D a partir de un índice semántico existente.

Solo lee embeddings.npy y records.jsonl: no recalcula embeddings ni carga modelos.
"""

import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np

from app.repositories.atlas_repository import ATLAS_DIRECTORY, COORDINATES_FILE, MANIFEST_FILE
from app.repositories.semantic_index_repository import (
    LocalSemanticIndexRepository,
    semantic_index_fingerprint,
)
from ml.atlas.reducers import DimensionalityReducer

ATLAS_FORMAT_VERSION = 1


class AtlasBuildError(RuntimeError):
    """El índice semántico no puede convertirse en un Atlas válido."""


@dataclass(frozen=True)
class AtlasBuildResult:
    dataset_id: str
    destination: Path
    reducer: str
    record_count: int
    source_records_fingerprint: str
    semantic_index_fingerprint: str


class AtlasBuilder:
    def __init__(self, reducer: DimensionalityReducer) -> None:
        self.reducer = reducer

    def build(self, dataset_id: str, processed_root: Path) -> AtlasBuildResult:
        processed_root = Path(processed_root).resolve()
        dataset_directory = processed_root / dataset_id
        semantic_directory = dataset_directory / "semantic"
        index = LocalSemanticIndexRepository(processed_root).load(dataset_id)
        index_fingerprint = semantic_index_fingerprint(semantic_directory)
        if len(index.source_record_ids) != len(index.record_ids):
            raise AtlasBuildError("Semantic index mapping lacks source record ids.")

        reduction = self.reducer.fit_transform(index.embeddings)
        coordinates = np.asarray(reduction.coordinates, dtype=np.float64)
        if coordinates.shape != (len(index.record_ids), 2) or not np.isfinite(coordinates).all():
            raise AtlasBuildError("Reducer must return one finite (x, y) pair per record.")
        if semantic_index_fingerprint(semantic_directory) != index_fingerprint:
            raise AtlasBuildError("Semantic index changed while the atlas was being built.")

        manifest = {
            "atlas_format_version": ATLAS_FORMAT_VERSION,
            "dataset_id": dataset_id,
            "reducer": self.reducer.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_embedding_provider": index.manifest.get("embedding_provider"),
            "source_embedding_model": index.manifest.get("model_name"),
            "source_embedding_dimension": int(index.embeddings.shape[1]),
            "record_count": len(index.record_ids),
            "source_records_fingerprint": index.manifest["source_records_fingerprint"],
            "semantic_index_fingerprint": index_fingerprint,
            "parameters": self.reducer.parameters,
            "diagnostics": reduction.diagnostics,
        }
        rows = (
            {
                "record_id": record_id,
                "dataset_id": dataset_id,
                "source_record_id": source_record_id,
                "x": float(x),
                "y": float(y),
            }
            for record_id, source_record_id, (x, y) in zip(
                index.record_ids, index.source_record_ids, coordinates
            )
        )
        destination = dataset_directory / ATLAS_DIRECTORY
        self._publish(destination, rows, manifest)
        return AtlasBuildResult(
            dataset_id,
            destination,
            self.reducer.name,
            len(index.record_ids),
            manifest["source_records_fingerprint"],
            index_fingerprint,
        )

    @staticmethod
    def _publish(destination: Path, rows, manifest: dict[str, object]) -> None:
        temporary = Path(tempfile.mkdtemp(prefix=".atlas-", dir=destination.parent))
        backup = destination.parent / f".atlas.backup-{uuid4().hex}"
        try:
            with (temporary / COORDINATES_FILE).open("w", encoding="utf-8", newline="\n") as file:
                for row in rows:
                    file.write(json.dumps(row, ensure_ascii=False) + "\n")
            (temporary / MANIFEST_FILE).write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            if destination.exists():
                destination.replace(backup)
            try:
                temporary.replace(destination)
            except BaseException:
                if backup.exists():
                    backup.replace(destination)
                raise
            if backup.exists():
                shutil.rmtree(backup)
        except BaseException:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise
