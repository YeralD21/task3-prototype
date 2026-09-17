"""Proveedor real opcional basado en Sentence Transformers."""

from typing import Any

import numpy as np


class EmbeddingProviderUnavailableError(RuntimeError):
    """La dependencia o el modelo configurado no está disponible."""


class SentenceTransformerProvider:
    """Carga un modelo bajo demanda; la librería puede descargarlo si no está en caché."""

    provider_name = "sentence_transformers"

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: Any | None = None

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise EmbeddingProviderUnavailableError(
                    "sentence-transformers is not installed; install requirements-ml.txt."
                ) from error
            try:
                self._model = SentenceTransformer(self.model_name)
            except Exception as error:
                raise EmbeddingProviderUnavailableError(
                    f"Embedding model '{self.model_name}' could not be loaded."
                ) from error
        return self._model

    def embed_text(self, text: str) -> np.ndarray:
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        vectors = self._load_model().encode(texts, convert_to_numpy=True)
        return np.asarray(vectors, dtype=np.float32)

