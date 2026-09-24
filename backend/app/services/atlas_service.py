"""Entrega coordenadas del Atlas con un límite explícito y muestreo reproducible."""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from app.repositories.atlas_repository import (
    InvalidAtlasError,
    LocalAtlas,
    LocalAtlasRepository,
)
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.atlas import AtlasPoint
from app.schemas.canonical import CorpusRecord
from app.services.semantic_search_service import DatasetNotAvailableLocallyError

ATLAS_DEFAULT_LIMIT = 2000
ATLAS_MAX_LIMIT = 5000
SAMPLING_METHOD = "sha256_record_id"


@dataclass(frozen=True)
class AtlasView:
    atlas: LocalAtlas
    points: list[AtlasPoint]
    records: list[CorpusRecord]
    sampled: bool


def sample_points(points: Sequence[AtlasPoint], limit: int) -> list[AtlasPoint]:
    """Elige los `limit` puntos con menor SHA-256 de record_id y conserva su orden.

    No depende del orden del archivo ni de semillas; una muestra con límite menor
    siempre está contenida en una con límite mayor.
    """

    if len(points) <= limit:
        return list(points)
    ranked = sorted(
        range(len(points)),
        key=lambda position: hashlib.sha256(points[position].record_id.encode("utf-8")).digest(),
    )
    return [points[position] for position in sorted(ranked[:limit])]


class AtlasService:
    def __init__(
        self, dataset_repository: DatasetRepository, atlas_repository: LocalAtlasRepository
    ) -> None:
        self.dataset_repository = dataset_repository
        self.atlas_repository = atlas_repository

    def get_atlas(self, dataset_id: str, limit: int = ATLAS_DEFAULT_LIMIT) -> AtlasView:
        if not 1 <= limit <= ATLAS_MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {ATLAS_MAX_LIMIT}")
        dataset = self.dataset_repository.get_dataset(dataset_id)
        if not (dataset.metadata or {}).get("available_locally", False):
            raise DatasetNotAvailableLocallyError(
                f"Dataset '{dataset_id}' is not available locally."
            )
        atlas = self.atlas_repository.load(dataset_id)
        points = sample_points(atlas.points, limit)
        records_by_id = {
            record.id: record for record in self.dataset_repository.list_records(dataset_id)
        }
        records = [records_by_id.get(point.record_id) for point in points]
        if any(
            record is None or record.source_record_id != point.source_record_id
            for point, record in zip(points, records)
        ):
            raise InvalidAtlasError(
                f"Atlas for dataset '{dataset_id}' references unavailable records."
            )
        return AtlasView(atlas, points, records, sampled=len(points) < len(atlas.points))
