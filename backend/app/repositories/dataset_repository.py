"""Acceso a datasets catalogados y materializaciones JSONL locales."""

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
    """Un archivo del Registry no contiene datos canónicos válidos."""


class DatasetNotFoundError(DatasetRepositoryError):
    """El identificador solicitado no existe en el Registry."""


class DatasetRepository(Protocol):
    def list_datasets(self) -> list[Dataset]: ...
    def get_dataset(self, dataset_id: str) -> Dataset: ...
    def list_records(self, dataset_id: str) -> list[CorpusRecord]: ...


class LocalDatasetRepository:
    """Fusiona metadata catalogada con registros materializados localmente."""

    def __init__(
        self,
        source_directories: Path | Sequence[Path],
        *,
        processed_directory: Path | None = None,
    ) -> None:
        if isinstance(source_directories, Path):
            self.source_directories = (source_directories,)
        else:
            self.source_directories = tuple(source_directories)
        self.processed_directory = processed_directory

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
                return records
        raise DatasetNotFoundError(f"Dataset '{dataset_id}' was not found.")

    def _load_collections(self) -> list[tuple[Dataset, list[CorpusRecord]]]:
        catalog: dict[str, tuple[Dataset, list[CorpusRecord]]] = {}
        for source_directory in self.source_directories:
            if not source_directory.is_dir():
                raise DatasetSourceNotFoundError(
                    f"Dataset source directory does not exist: {source_directory}"
                )
            for source_file in sorted(source_directory.rglob("*.json")):
                dataset, records = self._load_catalog_file(source_file)
                if dataset.id in catalog:
                    raise InvalidDatasetSourceError(
                        f"Duplicate dataset id '{dataset.id}' in local registry."
                    )
                catalog[dataset.id] = (dataset, records)

        for dataset_id, (processed_dataset, records) in self._load_processed().items():
            if dataset_id in catalog:
                catalog_dataset, _ = catalog[dataset_id]
                catalog[dataset_id] = (
                    self._with_availability(catalog_dataset),
                    records,
                )
            else:
                catalog[dataset_id] = (
                    self._with_availability(processed_dataset),
                    records,
                )
        return list(catalog.values())

    def _load_processed(self) -> dict[str, tuple[Dataset, list[CorpusRecord]]]:
        if self.processed_directory is None:
            return {}
        if not self.processed_directory.is_dir():
            raise DatasetSourceNotFoundError(
                f"Processed dataset directory does not exist: {self.processed_directory}"
            )
        materializations: dict[str, tuple[Dataset, list[CorpusRecord]]] = {}
        for dataset_file in sorted(self.processed_directory.glob("*/dataset.json")):
            if dataset_file.parent.name.startswith("."):
                continue
            dataset = self._load_dataset(dataset_file)
            records_file = dataset_file.parent / "records.jsonl"
            if not records_file.is_file():
                raise InvalidDatasetSourceError(
                    f"Processed dataset '{dataset.id}' has no records.jsonl."
                )
            records = self._load_jsonl(records_file, dataset.id)
            if dataset.id in materializations:
                raise InvalidDatasetSourceError(
                    f"Duplicate processed dataset id '{dataset.id}'."
                )
            materializations[dataset.id] = (dataset, records)
        return materializations

    @staticmethod
    def _with_availability(dataset: Dataset) -> Dataset:
        metadata = dict(dataset.metadata or {})
        metadata["available_locally"] = True
        return dataset.model_copy(update={"metadata": metadata})

    @classmethod
    def _load_catalog_file(cls, source_file: Path) -> tuple[Dataset, list[CorpusRecord]]:
        try:
            with source_file.open(encoding="utf-8") as file:
                payload = json.load(file)
            is_envelope = isinstance(payload, dict) and "dataset" in payload
            dataset_payload = payload["dataset"] if is_envelope else payload
            record_payloads = payload.get("records", []) if is_envelope else []
            dataset = Dataset.model_validate(dataset_payload)
            records = [CorpusRecord.model_validate(item) for item in record_payloads]
            cls._validate_record_datasets(records, dataset.id, source_file.name)
            return dataset, records
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

    @staticmethod
    def _load_dataset(source_file: Path) -> Dataset:
        try:
            return Dataset.model_validate_json(source_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValidationError) as error:
            raise InvalidDatasetSourceError(
                f"Invalid processed dataset file: {source_file}"
            ) from error

    @classmethod
    def _load_jsonl(cls, source_file: Path, dataset_id: str) -> list[CorpusRecord]:
        records: list[CorpusRecord] = []
        try:
            with source_file.open(encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    if not line.strip():
                        raise ValueError(f"Blank JSONL line {line_number}")
                    records.append(CorpusRecord.model_validate_json(line))
            cls._validate_record_datasets(records, dataset_id, source_file.name)
            return records
        except (OSError, UnicodeError, ValueError, ValidationError) as error:
            raise InvalidDatasetSourceError(
                f"Invalid processed records file: {source_file}"
            ) from error

    @staticmethod
    def _validate_record_datasets(
        records: list[CorpusRecord], dataset_id: str, source_name: str
    ) -> None:
        if any(record.dataset_id != dataset_id for record in records):
            raise InvalidDatasetSourceError(
                f"Records in {source_name} reference a different dataset."
            )
