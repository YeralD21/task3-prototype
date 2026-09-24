"""Contratos del Dataset Playbook: compatibilidad técnica explicable, separada de permisos."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel

from app.schemas.canonical import Language, LanguageVariety, ProvenanceInfo


class PlaybookTask(str, Enum):
    MACHINE_TRANSLATION = "machine_translation"
    AUTOMATIC_SPEECH_RECOGNITION = "automatic_speech_recognition"
    SEMANTIC_SEARCH = "semantic_search"
    CORPUS_EXPLORATION = "corpus_exploration"
    LANGUAGE_MODELING = "language_modeling"
    LINGUISTIC_RESEARCH = "linguistic_research"
    EDUCATIONAL_USE = "educational_use"


Compatibility = Literal["compatible", "potential", "not_applicable", "unknown"]
VarietyStatus = Literal["specified", "partial", "unspecified"]
LocalArtifactStatus = Literal["available", "stale", "missing", "unknown"]


class TaskAssessment(BaseModel):
    """Evaluación de una tarea. `compatibility` es técnica; los permisos van en `license_notes`."""

    task: PlaybookTask
    compatibility: Compatibility
    reasons: list[str]
    limitations: list[str]
    license_notes: list[str]
    data_requirements: list[str]
    next_steps: list[str]


class LicenseSummary(BaseModel):
    """Permisos tal como están registrados: `None` significa no determinado."""

    known: bool
    name: str | None
    url: str | None
    commercial_use: bool | None
    redistribution: bool | None
    derivatives: bool | None
    attribution_required: bool | None
    notes: str | None


class VarietySummary(BaseModel):
    status: VarietyStatus
    varieties: list[LanguageVariety]
    note: str


class ProvenanceSummary(BaseModel):
    source_organization: str | None
    source_url: str | None
    documentation_url: str | None
    citation: str | None
    provenance: ProvenanceInfo


class LocalStatus(BaseModel):
    """Estado local detectado sin cargar modelos; los artefactos solo se revisan si hay copia local."""

    available_locally: bool | None
    semantic_index: LocalArtifactStatus
    atlas: LocalArtifactStatus


class DatasetPlaybook(BaseModel):
    dataset_id: str
    dataset_name: str
    languages: list[Language]
    variety: VarietySummary
    license: LicenseSummary
    provenance: ProvenanceSummary
    local: LocalStatus
    tasks: list[TaskAssessment]
    disclaimer: str


class PlaybookDatasetMatch(BaseModel):
    dataset_id: str
    dataset_name: str
    compatibility: Compatibility
    reasons: list[str]
    limitations: list[str]
    available_locally: bool | None
    license_known: bool


class PlaybookDiscovery(BaseModel):
    """Datasets agrupados por compatibilidad; dentro de cada grupo el orden es alfabético por id."""

    task: PlaybookTask
    data_requirements: list[str]
    ordering: Literal["dataset_id"]
    compatible: list[PlaybookDatasetMatch]
    potential: list[PlaybookDatasetMatch]
    unknown: list[PlaybookDatasetMatch]
    not_applicable_count: int
    disclaimer: str
