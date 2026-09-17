"""Contrato mínimo y proveedor determinista para embeddings."""

import hashlib
import re
from typing import Protocol

import numpy as np


class EmbeddingProvider(Protocol):
    """Convierte texto en vectores sin imponer una librería de ML."""

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def embed_text(self, text: str) -> np.ndarray: ...

    def embed_texts(self, texts: list[str]) -> np.ndarray: ...


class FakeEmbeddingProvider:
    """Bag-of-tokens estable para pruebas; no representa calidad semántica real."""

    provider_name = "fake"

    def __init__(self, dimension: int = 32, model_name: str = "deterministic-token-hash-v1") -> None:
        if dimension < 1:
            raise ValueError("dimension must be positive")
        self.dimension = dimension
        self.model_name = model_name

    def embed_text(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype=np.float32)
        for token in re.findall(r"\w+", text.casefold(), flags=re.UNICODE):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimension] += 1.0
        return vector

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        return np.stack([self.embed_text(text) for text in texts])

