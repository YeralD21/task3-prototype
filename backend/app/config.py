"""Configuración de la aplicación cargada desde el entorno."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Variables configurables del backend."""

    app_name: str = "task3-prototype"
    app_env: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = "postgresql://task3:task3@localhost:5432/task3"
    dataset_registry_path: Path = PROJECT_ROOT / "data" / "samples"
    dataset_catalog_path: Path = PROJECT_ROOT / "datasets" / "registry"
    dataset_processed_path: Path = PROJECT_ROOT / "data" / "processed"
    # Única raíz desde la que Corpus Radio puede leer audio original.
    dataset_raw_path: Path = PROJECT_ROOT / "data" / "raw"
    embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia reutilizable de la configuración."""

    return Settings()
