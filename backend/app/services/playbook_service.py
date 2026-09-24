"""Casos de uso del Dataset Playbook: evaluación por dataset y descubrimiento por tarea."""

import json
from pathlib import Path

from app.repositories.atlas_repository import ATLAS_DIRECTORY, COORDINATES_FILE, MANIFEST_FILE
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.semantic_index_repository import (
    SEMANTIC_INDEX_FINGERPRINT_FILES,
    records_fingerprint,
    semantic_index_fingerprint,
)
from app.schemas.canonical import Dataset
from app.schemas.playbook import (
    DatasetPlaybook,
    LocalArtifactStatus,
    LocalStatus,
    PlaybookDatasetMatch,
    PlaybookDiscovery,
    PlaybookTask,
)
from app.services.playbook_rules import (
    DATA_REQUIREMENTS,
    DISCLAIMER,
    UNKNOWN_LOCAL,
    assess_all,
    assess_task,
    dataset_facts,
    license_summary,
    provenance_summary,
)


def _read_fingerprint(manifest_path: Path, key: str) -> str | None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    value = manifest.get(key) if isinstance(manifest, dict) else None
    return value if isinstance(value, str) else None


class PlaybookService:
    def __init__(self, dataset_repository: DatasetRepository, processed_root: Path | None) -> None:
        self.dataset_repository = dataset_repository
        self.processed_root = processed_root

    def get_playbook(self, dataset_id: str) -> DatasetPlaybook:
        dataset = self.dataset_repository.get_dataset(dataset_id)
        facts = dataset_facts(dataset)
        local = self.local_status(dataset)
        return DatasetPlaybook(
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            languages=list(dataset.languages or []),
            variety=facts.variety,
            license=license_summary(dataset),
            provenance=provenance_summary(dataset),
            local=local,
            tasks=assess_all(dataset, local),
            disclaimer=DISCLAIMER,
        )

    def discover(self, task: PlaybookTask) -> PlaybookDiscovery:
        """Agrupa por compatibilidad sin ordenar por calidad; cada grupo va en orden de id."""

        groups: dict[str, list[PlaybookDatasetMatch]] = {
            "compatible": [], "potential": [], "unknown": [], "not_applicable": []
        }
        for dataset in sorted(self.dataset_repository.list_datasets(), key=lambda item: item.id):
            # La compatibilidad no depende del estado local; no se inspeccionan artefactos aquí.
            assessment = assess_task(dataset_facts(dataset), task, UNKNOWN_LOCAL)
            groups[assessment.compatibility].append(
                PlaybookDatasetMatch(
                    dataset_id=dataset.id,
                    dataset_name=dataset.name,
                    compatibility=assessment.compatibility,
                    reasons=assessment.reasons,
                    limitations=assessment.limitations,
                    available_locally=self._available_locally(dataset),
                    license_known=bool(dataset.license.name),
                )
            )
        return PlaybookDiscovery(
            task=task,
            data_requirements=DATA_REQUIREMENTS[task],
            ordering="dataset_id",
            compatible=groups["compatible"],
            potential=groups["potential"],
            unknown=groups["unknown"],
            not_applicable_count=len(groups["not_applicable"]),
            disclaimer=DISCLAIMER,
        )

    @staticmethod
    def _available_locally(dataset: Dataset) -> bool | None:
        value = (dataset.metadata or {}).get("available_locally")
        return value if isinstance(value, bool) else None

    def local_status(self, dataset: Dataset) -> LocalStatus:
        """Detecta índice semántico y Atlas publicados y frescos mediante sus fingerprints."""

        available = self._available_locally(dataset)
        if available is not True or self.processed_root is None:
            return LocalStatus(available_locally=available, semantic_index="unknown", atlas="unknown")
        directory = Path(self.processed_root) / dataset.id
        records_path = directory / "records.jsonl"
        try:
            if not records_path.is_file():
                return LocalStatus(available_locally=True, semantic_index="unknown", atlas="unknown")
            current = records_fingerprint(records_path)
            semantic_directory = directory / "semantic"
            semantic = self._semantic_status(semantic_directory, current)
            atlas = self._atlas_status(directory / ATLAS_DIRECTORY, semantic_directory, current)
        except (OSError, UnicodeError, ValueError):
            return LocalStatus(available_locally=True, semantic_index="unknown", atlas="unknown")
        return LocalStatus(available_locally=True, semantic_index=semantic, atlas=atlas)

    @staticmethod
    def _semantic_status(semantic_directory: Path, records_fp: str) -> LocalArtifactStatus:
        manifest = semantic_directory / "index-manifest.json"
        files = [semantic_directory / name for name in SEMANTIC_INDEX_FINGERPRINT_FILES]
        if not manifest.is_file() or not all(path.is_file() for path in files):
            return "missing"
        fresh = _read_fingerprint(manifest, "source_records_fingerprint") == records_fp
        return "available" if fresh else "stale"

    @staticmethod
    def _atlas_status(
        atlas_directory: Path, semantic_directory: Path, records_fp: str
    ) -> LocalArtifactStatus:
        manifest = atlas_directory / MANIFEST_FILE
        if not manifest.is_file() or not (atlas_directory / COORDINATES_FILE).is_file():
            return "missing"
        if _read_fingerprint(manifest, "source_records_fingerprint") != records_fp:
            return "stale"
        if not all(
            (semantic_directory / name).is_file() for name in SEMANTIC_INDEX_FINGERPRINT_FILES
        ):
            return "stale"
        index_fp = _read_fingerprint(manifest, "semantic_index_fingerprint")
        return "available" if index_fp == semantic_index_fingerprint(semantic_directory) else "stale"
