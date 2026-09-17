"""Pruebas del contrato canónico independiente de la base de datos."""

import pytest
from pydantic import ValidationError

from app.schemas.canonical import (
    AudioResource,
    CorpusRecord,
    Dataset,
    Language,
    LanguageVariety,
    LicenseInfo,
    ProvenanceInfo,
)


def unknown_provenance() -> ProvenanceInfo:
    return ProvenanceInfo()


def test_create_valid_dataset() -> None:
    dataset = Dataset(
        id="dataset-development",
        name="Synthetic development dataset",
        languages=[Language(name="Synthetic source language", iso_code="und")],
        modalities=["text"],
        license=LicenseInfo(),
        provenance=unknown_provenance(),
    )

    assert dataset.name == "Synthetic development dataset"


def test_create_text_only_record() -> None:
    record = CorpusRecord(
        id="record-001",
        dataset_id="dataset-development",
        source_record_id="source-001",
        provenance=unknown_provenance(),
        text="[synthetic source-language sentence 001]",
    )

    assert record.translation is None
    assert record.audio_id is None


def test_create_record_with_translation() -> None:
    record = CorpusRecord(
        id="record-002",
        dataset_id="dataset-development",
        source_record_id="source-002",
        provenance=unknown_provenance(),
        text="[synthetic source-language sentence 002]",
        translation="[synthetic Spanish translation 002]",
        translation_language=Language(name="Spanish", iso_code="es"),
    )

    assert record.translation_language.iso_code == "es"


def test_create_record_with_audio() -> None:
    audio = AudioResource(id="audio-001", dataset_id="dataset-development")
    record = CorpusRecord(
        id="record-003",
        dataset_id="dataset-development",
        source_record_id="source-003",
        provenance=unknown_provenance(),
        text="[synthetic source-language sentence 003]",
        audio_id=audio.id,
    )

    assert record.audio_id == "audio-001"


def test_unknown_values_accept_null() -> None:
    dataset = Dataset(
        id="dataset-development",
        name="Synthetic development dataset",
        description=None,
        languages=None,
        record_count=None,
        license=LicenseInfo(name=None),
        provenance=unknown_provenance(),
    )

    assert dataset.languages is None
    assert dataset.record_count is None

    language_without_code = Language(name="Source-declared language", iso_code=None)
    assert language_without_code.iso_code is None


def test_record_preserves_dataset_id() -> None:
    record = CorpusRecord(
        id="record-001",
        dataset_id="original-dataset-reference",
        source_record_id="source-001",
        provenance=unknown_provenance(),
        text="[synthetic source-language sentence 001]",
    )

    assert record.dataset_id == "original-dataset-reference"


def test_record_preserves_source_record_id() -> None:
    record = CorpusRecord(
        id="record-001",
        dataset_id="dataset-development",
        source_record_id="source-system-id-001",
        provenance=unknown_provenance(),
        text="[synthetic source-language sentence 001]",
    )

    assert record.source_record_id == "source-system-id-001"


def test_unknown_license_does_not_imply_permissions() -> None:
    license_info = LicenseInfo()

    assert license_info.commercial_use is None
    assert license_info.redistribution is None
    assert license_info.derivatives is None


def test_language_variety_representation() -> None:
    variety = LanguageVariety(
        id="source-variety-001",
        name="Source-declared variety",
        language_code="und",
        region=None,
        glottocode=None,
    )

    assert variety.name == "Source-declared variety"
    assert variety.region is None


def test_reject_record_without_source_identifier() -> None:
    with pytest.raises(ValidationError):
        CorpusRecord(
            id="record-invalid",
            dataset_id="dataset-development",
            provenance=unknown_provenance(),
            text="[synthetic source-language sentence invalid]",
        )


def test_reject_negative_audio_duration() -> None:
    with pytest.raises(ValidationError):
        AudioResource(
            id="audio-invalid",
            dataset_id="dataset-development",
            duration_seconds=-1,
        )
