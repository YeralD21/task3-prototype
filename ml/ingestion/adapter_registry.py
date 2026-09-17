"""Registro pequeño y explícito de adaptadores de ingestión soportados."""

from collections.abc import Callable
from pathlib import Path

from ml.ingestion.base_adapter import CorpusAdapter
from ml.ingestion.adapters.americas_nlp_adapter import AmericasNLPAdapter
from ml.ingestion.adapters.common_voice_adapter import CommonVoiceAdapter

AdapterFactory = Callable[[Path], CorpusAdapter]


def _americas_nlp(source: Path) -> CorpusAdapter:
    return AmericasNLPAdapter(source, splits=("train", "dev", "test"))


ADAPTERS: dict[str, AdapterFactory] = {
    "americas_nlp": _americas_nlp,
    "common_voice": CommonVoiceAdapter,
}


class UnknownAdapterError(ValueError):
    """El nombre solicitado no corresponde a un adaptador registrado."""


def create_adapter(name: str, source: Path) -> CorpusAdapter:
    """Construye un adaptador conocido para una fuente local."""

    try:
        factory = ADAPTERS[name]
    except KeyError as error:
        available = ", ".join(sorted(ADAPTERS))
        raise UnknownAdapterError(
            f"Unknown adapter '{name}'. Available adapters: {available}."
        ) from error
    return factory(Path(source))

