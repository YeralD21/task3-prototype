"""Casos de uso del Dataset Registry."""

from app.repositories.dataset_repository import DatasetRepository
from app.schemas.canonical import CorpusRecord, Dataset, Language, LanguageVariety


class CorpusRecordPage:
    """Resultado filtrado antes de convertirlo en una respuesta HTTP."""

    def __init__(self, items: list[CorpusRecord], total: int) -> None:
        self.items = items
        self.total = total


class DatasetService:
    """Coordina consultas y filtros sin conocer el almacenamiento concreto."""

    def __init__(self, repository: DatasetRepository) -> None:
        self.repository = repository

    def list_datasets(
        self,
        *,
        language: str | None = None,
        variety: str | None = None,
        modality: str | None = None,
        task: str | None = None,
        domain: str | None = None,
    ) -> list[Dataset]:
        datasets = self.repository.list_datasets()
        return [
            dataset
            for dataset in datasets
            if self._matches_language(dataset.languages, language)
            and self._matches_variety(dataset.language_varieties, variety)
            and self._matches_value(dataset.modalities, modality)
            and self._matches_value(dataset.tasks, task)
            and self._matches_value(dataset.domains, domain)
        ]

    def get_dataset(self, dataset_id: str) -> Dataset:
        return self.repository.get_dataset(dataset_id)

    def get_dataset_records(
        self,
        dataset_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        language: str | None = None,
        language_variety: str | None = None,
        q: str | None = None,
    ) -> CorpusRecordPage:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if offset < 0:
            raise ValueError("offset must be non-negative")

        records = self.repository.list_records(dataset_id)
        filtered = [
            record
            for record in records
            if self._record_matches_language(record, language)
            and self._matches_variety(
                [record.language_variety] if record.language_variety else None,
                language_variety,
            )
            and self._record_matches_query(record, q)
        ]
        return CorpusRecordPage(filtered[offset : offset + limit], len(filtered))

    @staticmethod
    def _record_matches_query(record: CorpusRecord, query: str | None) -> bool:
        if query is None or not query.strip():
            return True
        normalized = query.strip().casefold()
        return normalized in record.text.casefold() or normalized in (
            record.translation or ""
        ).casefold()

    @classmethod
    def _matches_language(
        cls, languages: list[Language] | None, expected: str | None
    ) -> bool:
        if expected is None:
            return True
        normalized = expected.casefold()
        return any(
            normalized in {language.name.casefold(), (language.iso_code or "").casefold()}
            for language in languages or []
        )

    @staticmethod
    def _matches_variety(
        varieties: list[LanguageVariety] | None, expected: str | None
    ) -> bool:
        if expected is None:
            return True
        normalized = expected.casefold()
        return any(
            normalized
            in {
                variety.id.casefold(),
                variety.name.casefold(),
                (variety.language_code or "").casefold(),
            }
            for variety in varieties or []
        )

    @staticmethod
    def _matches_value(values: list[str] | None, expected: str | None) -> bool:
        if expected is None:
            return True
        normalized = expected.casefold()
        return any(value.casefold() == normalized for value in values or [])

    @classmethod
    def _record_matches_language(cls, record: CorpusRecord, expected: str | None) -> bool:
        if expected is None:
            return True
        normalized = expected.casefold()
        candidates = {(record.language_code or "").casefold()}
        if record.language:
            candidates.add(record.language.name.casefold())
            candidates.add((record.language.iso_code or "").casefold())
        return normalized in candidates
