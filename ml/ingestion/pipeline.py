"""Pipeline reproducible de fuente local a artefactos canónicos procesados."""

import json
import shutil
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas.canonical import AudioResource, CorpusRecord, Dataset, Speaker
from ml.ingestion.adapter_registry import create_adapter
from ml.ingestion.base_adapter import CorpusAdapter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = PROJECT_ROOT / "data" / "raw"


class IngestionError(RuntimeError):
    """Error controlado antes de publicar una materialización."""


@dataclass(frozen=True)
class IngestionResult:
    dataset_id: str
    destination: Path
    record_count: int
    audio_resource_count: int
    speaker_count: int
    warnings: tuple[str, ...]


def ingest_dataset(adapter_name: str, source: Path, output: Path) -> IngestionResult:
    """Valida y publica una materialización; una reingestión la reemplaza completa."""

    source = Path(source).resolve()
    output = Path(output).resolve()
    adapter = create_adapter(adapter_name, source)
    _validate_paths(source, output)

    dataset = Dataset.model_validate(adapter.load_metadata())
    records = _validated_items(adapter.load_records(), CorpusRecord, dataset.id)
    audio_resources = _load_optional(adapter, "load_audio_resources", AudioResource, dataset.id)
    speakers = _load_optional(adapter, "load_speakers", Speaker, dataset.id)
    warnings = _warnings(audio_resources)

    materialized_metadata = dict(dataset.metadata or {})
    materialized_metadata["available_locally"] = True
    materialized = dataset.model_copy(
        update={
            "record_count": len(records),
            "speaker_count": len(speakers) if speakers else dataset.speaker_count,
            "metadata": materialized_metadata,
        }
    )
    destination = output / dataset.id
    manifest = {
        "dataset_id": dataset.id,
        "adapter": adapter_name,
        "source_path": str(source),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "audio_resource_count": len(audio_resources),
        "speaker_count": len(speakers),
        "warnings": warnings,
        "source_files": _source_files(adapter_name, source),
    }
    _publish(
        output,
        destination,
        materialized,
        records,
        audio_resources,
        speakers,
        manifest,
    )
    return IngestionResult(
        dataset_id=dataset.id,
        destination=destination,
        record_count=len(records),
        audio_resource_count=len(audio_resources),
        speaker_count=len(speakers),
        warnings=tuple(warnings),
    )


def _validate_paths(source: Path, output: Path) -> None:
    if not source.is_dir():
        raise IngestionError(f"Source directory does not exist: {source}")
    if _is_relative_to(output, source):
        raise IngestionError("Output directory cannot be inside the immutable source directory.")
    if _is_relative_to(output, RAW_ROOT.resolve()):
        raise IngestionError("Output directory cannot be inside data/raw.")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _validated_items(
    items: Iterable[Any], model: type[CorpusRecord] | type[AudioResource] | type[Speaker], dataset_id: str
) -> list[Any]:
    validated = [model.model_validate(item) for item in items]
    for item in validated:
        if item.dataset_id != dataset_id:
            raise IngestionError(
                f"{model.__name__} '{item.id}' references dataset '{item.dataset_id}', "
                f"expected '{dataset_id}'."
            )
    return validated


def _load_optional(
    adapter: CorpusAdapter,
    method_name: str,
    model: type[AudioResource] | type[Speaker],
    dataset_id: str,
) -> list[Any]:
    loader = getattr(adapter, method_name, None)
    return _validated_items(loader(), model, dataset_id) if loader else []


def _warnings(resources: list[AudioResource]) -> list[str]:
    missing = sum(
        1
        for resource in resources
        if resource.path_or_url and not Path(resource.path_or_url).is_file()
    )
    return (
        [f"{missing} referenced audio file(s) were not found; references were preserved."]
        if missing
        else []
    )


def _source_files(adapter_name: str, source: Path) -> list[str]:
    if adapter_name == "americas_nlp":
        return [f"{split}.{language}" for split in ("train", "dev", "test") for language in ("aym", "es")]
    if adapter_name == "common_voice":
        return ["validated.tsv"]
    return []


def _publish(
    output: Path,
    destination: Path,
    dataset: Dataset,
    records: list[CorpusRecord],
    audio_resources: list[AudioResource],
    speakers: list[Speaker],
    manifest: dict[str, Any],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{dataset.id}-", dir=output))
    backup = output / f".{dataset.id}.backup-{uuid4().hex}"
    try:
        _write_json(temporary / "dataset.json", dataset.model_dump(mode="json"))
        _write_jsonl(temporary / "records.jsonl", records)
        if audio_resources:
            _write_jsonl(temporary / "audio-resources.jsonl", audio_resources)
        if speakers:
            _write_jsonl(temporary / "speakers.jsonl", speakers)
        _write_json(temporary / "ingestion-manifest.json", manifest)
        if destination.exists():
            destination.replace(backup)
        try:
            temporary.replace(destination)
        except BaseException:
            if backup.exists():
                backup.replace(destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_jsonl(path: Path, items: Iterable[Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for item in items:
            validated = type(item).model_validate(item)
            file.write(json.dumps(validated.model_dump(mode="json"), ensure_ascii=False))
            file.write("\n")

