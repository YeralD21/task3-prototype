"""Reductores de dimensionalidad intercambiables para proyectar embeddings."""

from dataclasses import dataclass, field
from importlib import metadata
from typing import Any, Protocol

import numpy as np


class InvalidEmbeddingsError(ValueError):
    """La matriz recibida no puede reducirse."""


class ReducerUnavailableError(RuntimeError):
    """La dependencia opcional del reductor no está instalada."""


@dataclass(frozen=True)
class ReductionResult:
    coordinates: np.ndarray
    diagnostics: dict[str, Any] = field(default_factory=dict)


class DimensionalityReducer(Protocol):
    """Convierte una matriz N×D en coordenadas N×n_components."""

    @property
    def name(self) -> str: ...

    @property
    def parameters(self) -> dict[str, Any]: ...

    def fit_transform(self, embeddings: np.ndarray) -> ReductionResult: ...


def validate_embeddings(embeddings: np.ndarray, minimum_rows: int = 1) -> np.ndarray:
    """Devuelve una copia float64 o rechaza matrices vacías, no numéricas o no finitas."""

    try:
        matrix = np.array(embeddings, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise InvalidEmbeddingsError("Embeddings must be numeric.") from error
    if matrix.ndim != 2:
        raise InvalidEmbeddingsError("Embeddings must be a 2-D matrix.")
    if matrix.shape[0] < minimum_rows or matrix.shape[1] < 1:
        raise InvalidEmbeddingsError(
            f"Embeddings must have at least {minimum_rows} row(s) and one column."
        )
    if not np.isfinite(matrix).all():
        raise InvalidEmbeddingsError("Embeddings must contain only finite values.")
    return matrix


class PCAReducer:
    """PCA exacta en NumPy con signo canónico para que la salida sea determinista.

    Las componentes son los autovectores principales de la matriz de dispersión
    centrada. Cada componente se orienta para que su carga de mayor valor
    absoluto sea positiva. Si el rango es menor que n_components, las columnas
    restantes se completan con ceros.
    """

    name = "pca"

    def __init__(self, n_components: int = 2) -> None:
        if n_components < 1:
            raise ValueError("n_components must be positive")
        self.n_components = n_components

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "n_components": self.n_components,
            "centered": True,
            "whiten": False,
            "solver": "numpy.linalg.eigh(scatter_matrix)",
            "sign_convention": "largest_absolute_loading_positive",
        }

    def fit_transform(self, embeddings: np.ndarray) -> ReductionResult:
        matrix = validate_embeddings(embeddings)
        centered = matrix - matrix.mean(axis=0)
        eigenvalues, eigenvectors = np.linalg.eigh(centered.T @ centered)
        order = np.argsort(-eigenvalues, kind="stable")
        available = min(self.n_components, matrix.shape[1])
        components = eigenvectors[:, order[:available]].T
        pivots = np.argmax(np.abs(components), axis=1)
        signs = np.sign(components[np.arange(available), pivots])
        signs[signs == 0] = 1.0
        components *= signs[:, np.newaxis]

        coordinates = np.zeros((matrix.shape[0], self.n_components), dtype=np.float64)
        coordinates[:, :available] = centered @ components.T
        variances = np.clip(eigenvalues[order], 0.0, None)
        total = float(variances.sum())
        ratios = [
            float(variances[position] / total) if total > 0 and position < available else 0.0
            for position in range(self.n_components)
        ]
        return ReductionResult(
            coordinates,
            {
                "explained_variance_ratio": ratios,
                "explained_variance_ratio_total": float(sum(ratios)),
                "implementation": f"numpy {np.__version__}",
            },
        )


class UMAPReducer:
    """UMAP opcional; requiere `umap-learn` y fija random_state para reproducibilidad."""

    name = "umap"

    def __init__(
        self,
        n_components: int = 2,
        n_neighbors: int = 15,
        min_dist: float = 0.1,
        metric: str = "cosine",
        random_state: int = 42,
    ) -> None:
        if n_components < 1:
            raise ValueError("n_components must be positive")
        if n_neighbors < 2:
            raise ValueError("n_neighbors must be at least 2")
        if not 0.0 <= min_dist <= 1.0:
            raise ValueError("min_dist must be between 0 and 1")
        self.n_components = n_components
        self.n_neighbors = n_neighbors
        self.min_dist = min_dist
        self.metric = metric
        self.random_state = random_state

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "n_components": self.n_components,
            "n_neighbors": self.n_neighbors,
            "min_dist": self.min_dist,
            "metric": self.metric,
            "random_state": self.random_state,
            "n_jobs": 1,
        }

    def fit_transform(self, embeddings: np.ndarray) -> ReductionResult:
        matrix = validate_embeddings(embeddings, minimum_rows=self.n_components + 2)
        try:
            import umap
        except ImportError as error:
            raise ReducerUnavailableError(
                "UMAP requires the optional 'umap-learn' package."
            ) from error
        effective_neighbors = min(self.n_neighbors, matrix.shape[0] - 1)
        model = umap.UMAP(
            n_components=self.n_components,
            n_neighbors=effective_neighbors,
            min_dist=self.min_dist,
            metric=self.metric,
            random_state=self.random_state,
            transform_seed=self.random_state,
            n_jobs=1,
        )
        coordinates = np.asarray(model.fit_transform(matrix), dtype=np.float64)
        try:
            version = metadata.version("umap-learn")
        except metadata.PackageNotFoundError:
            version = "unknown"
        return ReductionResult(
            coordinates,
            {
                "effective_n_neighbors": effective_neighbors,
                "implementation": f"umap-learn {version}",
            },
        )


REDUCERS: dict[str, type] = {"pca": PCAReducer, "umap": UMAPReducer}


def create_reducer(name: str, **parameters: Any) -> DimensionalityReducer:
    try:
        reducer_class = REDUCERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown reducer '{name}'. Available: {', '.join(sorted(REDUCERS))}."
        ) from None
    return reducer_class(**parameters)
