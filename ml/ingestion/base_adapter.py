"""Contrato mínimo para adaptar fuentes externas al modelo canónico."""

from typing import TYPE_CHECKING, Iterable, Protocol

if TYPE_CHECKING:
    from app.schemas.canonical import CorpusRecord, Dataset


class CorpusAdapter(Protocol):
    """Convierte una fuente externa sin modificar sus datos originales."""

    def load_metadata(self) -> "Dataset":
        """Carga y transforma la metadata de la colección."""
        ...

    def load_records(self) -> Iterable["CorpusRecord"]:
        """Carga registros canónicos conservando identificadores y procedencia."""
        ...
