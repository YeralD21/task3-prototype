"""Indexador de CorpusRecord materializados, independiente del modelo."""

import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np

from app.embeddings.provider import EmbeddingProvider
from app.repositories.semantic_index_repository import records_fingerprint
from app.schemas.canonical import CorpusRecord


class SemanticIndexingError(RuntimeError):
    """La materialización no puede convertirse en un índice válido."""


@dataclass(frozen=True)
class SemanticIndexResult:
    dataset_id: str
    destination: Path
    dimension: int
    record_count: int
    fingerprint: str


class SemanticIndexer:
    """Crea y publica embeddings locales sin modificar records.jsonl."""

    strategy = "text_only"

    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    def build(self, dataset_id: str, processed_root: Path) -> SemanticIndexResult:
        dataset_directory = Path(processed_root).resolve() / dataset_id
        records_path = dataset_directory / "records.jsonl"
        if not records_path.is_file():
            raise SemanticIndexingError(
                f"Processed records for dataset '{dataset_id}' were not found."
            )
        fingerprint = records_fingerprint(records_path)
        records = self._load_records(records_path, dataset_id)
        if not records:
            raise SemanticIndexingError("No indexable records were found.")
        if len({record.id for record in records}) != len(records):
            raise SemanticIndexingError("Canonical records contain duplicate ids.")
        embeddings = np.asarray(
            self.provider.embed_texts([record.text for record in records]),
            dtype=np.float32,
        )
        if (
            embeddings.ndim != 2
            or embeddings.shape[0] != len(records)
            or embeddings.shape[1] < 1
            or not np.isfinite(embeddings).all()
        ):
            raise SemanticIndexingError("Embedding provider returned an invalid matrix.")
        manifest = {
            "dataset_id": dataset_id,
            "embedding_provider": self.provider.provider_name,
            "model_name": self.provider.model_name,
            "dimension": int(embeddings.shape[1]),
            "record_count": len(records),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_records_fingerprint": fingerprint,
            "strategy": self.strategy,
        }
        destination = dataset_directory / "semantic"
        self._publish(destination, embeddings, records, manifest)
        return SemanticIndexResult(
            dataset_id, destination, int(embeddings.shape[1]), len(records), fingerprint
        )

    @staticmethod
    def _load_records(path: Path, dataset_id: str) -> list[CorpusRecord]:
        records: list[CorpusRecord] = []
        try:
            with path.open(encoding="utf-8") as file:
                for line in file:
                    if not line.strip():
                        raise ValueError("records.jsonl contains a blank line")
                    record = CorpusRecord.model_validate_json(line)
                    if record.dataset_id != dataset_id:
                        raise ValueError("record references a different dataset")
                    records.append(record)
        except (OSError, UnicodeError, ValueError) as error:
            raise SemanticIndexingError(f"Cannot load canonical records: {path}") from error
        return records

    @staticmethod
    def _publish(
        destination: Path,
        embeddings: np.ndarray,
        records: list[CorpusRecord],
        manifest: dict[str, object],
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".semantic-", dir=destination.parent))
        backup = destination.parent / f".semantic.backup-{uuid4().hex}"
        try:
            np.save(temporary / "embeddings.npy", embeddings, allow_pickle=False)
            with (temporary / "records.jsonl").open("w", encoding="utf-8", newline="\n") as file:
                for record in records:
                    mapping = {
                        "record_id": record.id,
                        "dataset_id": record.dataset_id,
                        "source_record_id": record.source_record_id,
                    }
                    file.write(json.dumps(mapping, ensure_ascii=False) + "\n")
            (temporary / "index-manifest.json").write_text(
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
