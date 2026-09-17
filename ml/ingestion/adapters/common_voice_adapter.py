"""Adaptador local para Mozilla Common Voice Scripted Speech."""

import csv
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas.canonical import (
    AudioResource,
    CorpusRecord,
    Dataset,
    Language,
    LanguageVariety,
    ProvenanceInfo,
    Speaker,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = (
    PROJECT_ROOT / "datasets" / "registry" / "quechua" / "common-voice-puno-quechua.json"
)


class CommonVoiceAdapterError(Exception):
    """Error controlado al leer una copia local de Common Voice."""


class CommonVoiceSourceNotFoundError(CommonVoiceAdapterError):
    """La carpeta o el TSV configurado no está disponible localmente."""


class CommonVoiceSourceInvalidError(CommonVoiceAdapterError):
    """La metadata local no puede convertirse al contrato canónico."""


class CommonVoiceAdapter:
    """Convierte un TSV local de Common Voice sin descargar ni copiar recursos."""

    def __init__(
        self,
        dataset_directory: Path,
        *,
        manifest_path: Path = DEFAULT_MANIFEST_PATH,
        tsv_filename: str = "validated.tsv",
    ) -> None:
        self.dataset_directory = dataset_directory
        self.manifest_path = manifest_path
        self.tsv_filename = tsv_filename

    def load_metadata(self) -> Dataset:
        """Carga el manifiesto catalogado, aunque el corpus no esté montado."""

        try:
            with self.manifest_path.open(encoding="utf-8") as file:
                return Dataset.model_validate(json.load(file))
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as error:
            raise CommonVoiceSourceInvalidError(
                f"Common Voice manifest could not be loaded: {self.manifest_path}"
            ) from error

    def load_records(self) -> list[CorpusRecord]:
        """Convierte filas TSV en registros con procedencia e IDs originales."""

        dataset = self.load_metadata()
        language = self._language(dataset)
        variety = self._variety(dataset)
        records: list[CorpusRecord] = []
        for row_number, row in self._load_rows():
            sentence = self._optional(row.get("sentence"))
            if sentence is None:
                raise CommonVoiceSourceInvalidError(
                    f"Missing sentence in {self.tsv_filename} row {row_number}."
                )
            source_record_id = self._source_record_id(row, row_number)
            clip_path = self._optional(row.get("path"))
            records.append(
                CorpusRecord(
                    id=f"{dataset.id}:{source_record_id}",
                    dataset_id=dataset.id,
                    source_record_id=source_record_id,
                    provenance=self._record_provenance(dataset.provenance, row_number),
                    language=language,
                    language_code=language.iso_code,
                    language_variety=variety,
                    text=sentence,
                    audio_id=self._audio_id(dataset.id, clip_path) if clip_path else None,
                    speaker_id=self._speaker_id(dataset.id, row.get("client_id")),
                    metadata=self._row_metadata(row),
                )
            )
        return records

    def load_audio_resources(self) -> list[AudioResource]:
        """Crea referencias locales; no copia ni abre los clips."""

        dataset = self.load_metadata()
        resources: list[AudioResource] = []
        for _, row in self._load_rows():
            clip_path = self._optional(row.get("path"))
            if clip_path is None:
                continue
            resources.append(
                AudioResource(
                    id=self._audio_id(dataset.id, clip_path),
                    dataset_id=dataset.id,
                    source_audio_id=clip_path,
                    path_or_url=str(self.dataset_directory / "clips" / clip_path),
                    mime_type="audio/mpeg" if clip_path.lower().endswith(".mp3") else None,
                    metadata={"source_format": "common_voice_tsv"},
                )
            )
        return resources

    def load_speakers(self) -> list[Speaker]:
        """Conserva solo IDs seudónimos de fuente, sin inferir identidades."""

        dataset = self.load_metadata()
        language = self._language(dataset)
        variety = self._variety(dataset)
        source_ids = {
            source_id
            for _, row in self._load_rows()
            if (source_id := self._optional(row.get("client_id"))) is not None
        }
        return [
            Speaker(
                id=self._speaker_id(dataset.id, source_id) or "",
                dataset_id=dataset.id,
                source_speaker_id=source_id,
                language=language,
                language_variety=variety,
                metadata={
                    "source_identifier_is_pseudonymous": True,
                    "do_not_attempt_reidentification": True,
                },
            )
            for source_id in sorted(source_ids)
        ]

    def _load_rows(self) -> list[tuple[int, dict[str, str | None]]]:
        if not self.dataset_directory.is_dir():
            raise CommonVoiceSourceNotFoundError(
                "Common Voice directory was not found. Place the manually obtained "
                f"qxp dataset at: {self.dataset_directory}"
            )
        tsv_path = self.dataset_directory / self.tsv_filename
        if not tsv_path.is_file():
            raise CommonVoiceSourceNotFoundError(
                f"Common Voice TSV was not found: {tsv_path}"
            )
        try:
            with tsv_path.open(encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file, delimiter="\t")
                if not reader.fieldnames:
                    raise CommonVoiceSourceInvalidError(f"TSV has no header: {tsv_path}")
                return [(index, row) for index, row in enumerate(reader, start=2)]
        except (OSError, UnicodeError, csv.Error) as error:
            raise CommonVoiceSourceInvalidError(f"Could not parse TSV: {tsv_path}") from error

    def _source_record_id(self, row: dict[str, str | None], row_number: int) -> str:
        return self._optional(row.get("path")) or f"{self.tsv_filename}:row:{row_number}"

    @staticmethod
    def _optional(value: str | None) -> str | None:
        normalized = value.strip() if value else ""
        return normalized or None

    @staticmethod
    def _language(dataset: Dataset) -> Language:
        if not dataset.languages:
            raise CommonVoiceSourceInvalidError("Manifest does not declare a language.")
        return dataset.languages[0]

    @staticmethod
    def _variety(dataset: Dataset) -> LanguageVariety:
        if not dataset.language_varieties:
            raise CommonVoiceSourceInvalidError("Manifest does not declare a language variety.")
        return dataset.language_varieties[0]

    @staticmethod
    def _audio_id(dataset_id: str, clip_path: str) -> str:
        return f"{dataset_id}:audio:{clip_path}"

    @staticmethod
    def _speaker_id(dataset_id: str, source_id: str | None) -> str | None:
        normalized = source_id.strip() if source_id else ""
        return f"{dataset_id}:speaker:{normalized}" if normalized else None

    def _record_provenance(
        self, dataset_provenance: ProvenanceInfo, row_number: int
    ) -> ProvenanceInfo:
        return dataset_provenance.model_copy(
            update={
                "notes": (
                    f"Loaded locally from {self.tsv_filename} row {row_number}; "
                    "the source dataset remains external."
                )
            }
        )

    @staticmethod
    def _row_metadata(row: dict[str, str | None]) -> dict[str, Any] | None:
        excluded = {"client_id", "path", "sentence", "age", "gender", "sex"}
        metadata = {
            key: value
            for key, raw_value in row.items()
            if key not in excluded and (value := CommonVoiceAdapter._optional(raw_value))
        }
        return metadata or None
