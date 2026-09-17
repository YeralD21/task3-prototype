"""Acceso a datasets canónicos almacenados en archivos JSON locales."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from app.schemas.canonical import CorpusRecord, Dataset


class DatasetRepositoryError(Exception):
    """Error controlado al acceder a la fuente del Dataset Registry."""


class DatasetSourceNotFoundError(DatasetRepositoryError):
    """La ruta configurada para el Registry no existe."""


class InvalidDatasetSourceError(DatasetRepositoryError):
    """Un archivo del Registry no contiene JSON canónico válido."""


class DatasetNotFoundError(DatasetRepositoryError):
    """El identificador solicitado no existe en el Registry."""


class DatasetRepository(Protocol):
    """Contrato mínimo que desacopla los servicios del almacenamiento."""

    def list_datasets(self) -> list[Dataset]: ...

    def get_dataset(self, dataset_id: str) -> Dataset: ...

    def list_records(self, dataset_id: str) -> list[CorpusRecord]: ...


class LocalDatasetRepository:
    """Carga colecciones canónicas desde sobres JSON en un directorio local."""

    def __init__(self, source_directories: Path | Sequence[Path]) -> None:
        if isinstance(source_directories, Path):
            self.source_directories = (source_directories,)
        else:
            self.source_directories = tuple(source_directories)

    def list_datasets(self) -> list[Dataset]:
        return [dataset for dataset, _ in self._load_collections()]

    def get_dataset(self, dataset_id: str) -> Dataset:
        for dataset, _ in self._load_collections():
            if dataset.id == dataset_id:
                return dataset
        raise DatasetNotFoundError(f"Dataset '{dataset_id}' was not found.")

    def list_records(self, dataset_id: str) -> list[CorpusRecord]:
        for dataset, records in self._load_collections():
            if dataset.id == dataset_id:
                return [record for record in records if record.dataset_id == dataset_id]
        raise DatasetNotFoundError(f"Dataset '{dataset_id}' was not found.")

    def _load_collections(self) -> list[tuple[Dataset, list[CorpusRecord]]]:
        collections: list[tuple[Dataset, list[CorpusRecord]]] = []
        dataset_ids: set[str] = set()
        for source_directory in self.source_directories:
            if not source_directory.is_dir():
                raise DatasetSourceNotFoundError(
                    f"Dataset source directory does not exist: {source_directory}"
                )
            for source_file in sorted(source_directory.rglob("*.json")):
                dataset, records = self._load_file(source_file)
                if dataset.id in dataset_ids:
                    raise InvalidDatasetSourceError(
                        f"Duplicate dataset id '{dataset.id}' in local registry."
                    )
                dataset_ids.add(dataset.id)
                collections.append((dataset, records))
        return collections

    @staticmethod
    def _load_file(source_file: Path) -> tuple[Dataset, list[CorpusRecord]]:
        try:
            with source_file.open(encoding="utf-8") as file:
                payload = json.load(file)
            is_envelope = isinstance(payload, dict) and "dataset" in payload
            dataset_payload = payload["dataset"] if is_envelope else payload
            record_payloads = payload.get("records", []) if is_envelope else []
            dataset = Dataset.model_validate(dataset_payload)
            records = [CorpusRecord.model_validate(item) for item in record_payloads]
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValidationError,
        ) as error:
            raise InvalidDatasetSourceError(
                f"Invalid dataset source file: {source_file.name}"
            ) from error

        mismatched = [record.id for record in records if record.dataset_id != dataset.id]
        if mismatched:
            raise InvalidDatasetSourceError(
                f"Records in {source_file.name} reference a different dataset."
            )
        return dataset, records
