"""Dataset Playbook: reglas deterministas sobre metadata, sin red ni modelos."""

import json
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes.playbook import get_playbook_service
from app.embeddings.provider import FakeEmbeddingProvider
from app.main import app
from app.repositories.dataset_repository import DatasetNotFoundError, LocalDatasetRepository
from app.schemas.canonical import Dataset
from app.schemas.playbook import PlaybookTask
from app.services.playbook_rules import UNKNOWN_LOCAL, assess_all
from app.services.playbook_service import PlaybookService
from ml.atlas.builder import AtlasBuilder
from ml.atlas.reducers import PCAReducer
from ml.embeddings.indexer import SemanticIndexer
from tests.conftest import PROJECT_ROOT, SAMPLE_DATASET_ID

REGISTRY = PROJECT_ROOT / "datasets" / "registry"
SAMPLES = PROJECT_ROOT / "data" / "samples"
AMERICAS = "americasnlp-2021-aymara-spanish"
COMMON_VOICE = "common-voice-scripted-speech-qxp-26.0"
PERMISSIONS = ("commercial_use", "redistribution", "derivatives", "attribution_required")


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access forbidden in playbook tests")

    monkeypatch.setattr(socket, "create_connection", reject)


def synthetic_dataset(dataset_id: str, modalities: list[str] | None, **extra: object) -> dict:
    return {
        "id": dataset_id,
        "name": f"Synthetic {dataset_id}",
        "modalities": modalities,
        "license": {"notes": "Synthetic fixture; no permissions implied."},
        "provenance": {"source_name": "task3-prototype synthetic fixture"},
        "metadata": {"synthetic": True, "development_only": True, "available_locally": False},
        **extra,
    }


@pytest.fixture
def synthetic_catalog(tmp_path: Path) -> Path:
    directory = tmp_path / "catalog"
    directory.mkdir()
    for payload in (
        synthetic_dataset("zz-text-only", ["text"]),
        synthetic_dataset("aa-audio-only", ["audio"]),
        synthetic_dataset("mm-no-modalities", None),
        synthetic_dataset("bb-parallel", ["parallel_text"]),
    ):
        (directory / f"{payload['id']}.json").write_text(json.dumps(payload), encoding="utf-8")
    return directory


@pytest.fixture
def catalog_service() -> PlaybookService:
    return PlaybookService(LocalDatasetRepository([SAMPLES, REGISTRY]), None)


@pytest.fixture
def synthetic_service(synthetic_catalog: Path) -> PlaybookService:
    return PlaybookService(LocalDatasetRepository([synthetic_catalog, REGISTRY]), None)


def tasks_by_id(service: PlaybookService, dataset_id: str) -> dict[str, dict]:
    playbook = service.get_playbook(dataset_id).model_dump(mode="json")
    return {task["task"]: task for task in playbook["tasks"]}


@pytest.fixture
def processed_root(tmp_path: Path) -> Path:
    payload = json.loads((SAMPLES / "canonical-development-sample.json").read_text(encoding="utf-8"))
    destination = tmp_path / "processed" / SAMPLE_DATASET_ID
    destination.mkdir(parents=True)
    (destination / "dataset.json").write_text(json.dumps(payload["dataset"]), encoding="utf-8")
    with (destination / "records.jsonl").open("w", encoding="utf-8", newline="\n") as file:
        for record in payload["records"]:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return tmp_path / "processed"


def local_service(root: Path) -> PlaybookService:
    return PlaybookService(LocalDatasetRepository(SAMPLES, processed_directory=root), root)


@pytest.fixture
def client_for() -> Iterator:
    def build(service: PlaybookService) -> TestClient:
        app.dependency_overrides[get_playbook_service] = lambda: service
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()


# --- Compatibilidad técnica -----------------------------------------------------------


def test_parallel_dataset_is_compatible_with_machine_translation(
    catalog_service: PlaybookService,
) -> None:
    task = tasks_by_id(catalog_service, AMERICAS)["machine_translation"]
    assert task["compatibility"] == "compatible"
    assert "Contiene texto paralelo (modalidad parallel_text)." in task["reasons"]
    assert any("Aymara (aym) como texto fuente → Spanish (es)" in r for r in task["reasons"])
    assert any("splits tienen orígenes distintos" in item for item in task["limitations"])
    assert task["data_requirements"]


def test_audio_with_transcriptions_is_compatible_with_asr(catalog_service: PlaybookService) -> None:
    task = tasks_by_id(catalog_service, COMMON_VOICE)["automatic_speech_recognition"]
    assert task["compatibility"] == "compatible"
    assert "Contiene audio." in task["reasons"]
    assert "Contiene texto (transcripciones) asociado al audio." in task["reasons"]
    assert "Idiomas registrados: Quechua (qxp)." in task["reasons"]
    assert any("34.88" in reason for reason in task["reasons"])
    assert any("reidentificar" in note for note in task["license_notes"])
    assert any("no debe volver a alojarse" in note for note in task["license_notes"])


@pytest.mark.parametrize("dataset_id", [AMERICAS, "zz-text-only"])
def test_asr_is_not_applicable_to_text_only_datasets(
    synthetic_service: PlaybookService, dataset_id: str
) -> None:
    task = tasks_by_id(synthetic_service, dataset_id)["automatic_speech_recognition"]
    assert task["compatibility"] == "not_applicable"
    assert task["limitations"] == ["No contiene audio registrado."]
    assert task["license_notes"] == [] and task["next_steps"] == []


def test_audio_without_text_is_only_potential_for_asr(synthetic_service: PlaybookService) -> None:
    tasks = tasks_by_id(synthetic_service, "aa-audio-only")
    assert tasks["automatic_speech_recognition"]["compatibility"] == "potential"
    assert tasks["semantic_search"]["compatibility"] == "not_applicable"
    assert tasks["machine_translation"]["compatibility"] == "not_applicable"


def test_semantic_search_is_compatible_with_text(synthetic_service: PlaybookService) -> None:
    for dataset_id in (AMERICAS, COMMON_VOICE, "zz-text-only"):
        task = tasks_by_id(synthetic_service, dataset_id)["semantic_search"]
        assert task["compatibility"] == "compatible"
        assert any("no está evaluado" in item for item in task["limitations"])


def test_language_modeling_and_education_are_never_asserted_compatible(
    synthetic_service: PlaybookService,
) -> None:
    for dataset_id in (AMERICAS, COMMON_VOICE, "zz-text-only"):
        tasks = tasks_by_id(synthetic_service, dataset_id)
        assert tasks["language_modeling"]["compatibility"] == "potential"
        assert tasks["educational_use"]["compatibility"] == "potential"
        assert any("no autoriza expresamente usos educativos" in note
                   for note in tasks["educational_use"]["license_notes"])


def test_unknown_modalities_make_every_task_unknown(synthetic_service: PlaybookService) -> None:
    tasks = tasks_by_id(synthetic_service, "mm-no-modalities")
    assert {task["compatibility"] for task in tasks.values()} == {"unknown"}


# --- Licencia: técnica separada de permisos ------------------------------------------------


def test_null_license_remains_unknown(catalog_service: PlaybookService) -> None:
    license_summary = catalog_service.get_playbook(AMERICAS).license
    assert license_summary.known is False
    assert license_summary.name is None
    mt = tasks_by_id(catalog_service, AMERICAS)["machine_translation"]
    assert any("licencia no está determinada" in note for note in mt["license_notes"])
    assert any("Verifique la licencia" in step for step in mt["next_steps"])


def test_null_permissions_are_not_converted_to_booleans(
    catalog_service: PlaybookService, client_for
) -> None:
    with client_for(catalog_service) as client:
        americas = client.get(f"/api/v1/datasets/{AMERICAS}/playbook").json()
        common_voice = client.get(f"/api/v1/datasets/{COMMON_VOICE}/playbook").json()
    assert all(americas["license"][key] is None for key in PERMISSIONS)
    notes = [note for task in americas["tasks"] for note in task["license_notes"]]
    assert "Redistribución: no determinado con la información disponible." in notes
    assert not any(note.startswith(("Redistribución: sí", "Redistribución: no,")) for note in notes)
    assert common_voice["license"]["redistribution"] is False
    assert common_voice["license"]["commercial_use"] is True
    cv_notes = [note for task in common_voice["tasks"] for note in task["license_notes"]]
    assert "Redistribución: no, según la metadata registrada." in cv_notes


def test_technical_compatibility_never_claims_training_permission(
    catalog_service: PlaybookService,
) -> None:
    for dataset_id in (AMERICAS, COMMON_VOICE):
        for task in catalog_service.get_playbook(dataset_id).tasks:
            text = " ".join(task.reasons + task.license_notes + task.next_steps).casefold()
            assert "puede utilizarse para entrenamiento" not in text
            assert "mejor" not in text and "best" not in text
            if task.compatibility != "not_applicable" and task.task in {
                PlaybookTask.MACHINE_TRANSLATION, PlaybookTask.AUTOMATIC_SPEECH_RECOGNITION
            }:
                assert any("no implica permiso" in note for note in task.license_notes)


# --- Variedad y procedencia --------------------------------------------------------------


def test_varieties_are_preserved_without_generalization(synthetic_service: PlaybookService) -> None:
    common_voice = synthetic_service.get_playbook(COMMON_VOICE).variety
    assert common_voice.status == "specified"
    assert [item.id for item in common_voice.varieties] == ["qxp"]
    assert "Puno Quechua" in common_voice.note and "otras variedades de Quechua" in common_voice.note

    americas = synthetic_service.get_playbook(AMERICAS).variety
    assert americas.status == "partial"
    assert americas.varieties[0].metadata["splits"] == ["dev", "test"]
    assert "solo para: dev, test" in americas.note
    assert "No la atribuya a todo el corpus" in americas.note

    unspecified = synthetic_service.get_playbook("zz-text-only").variety
    assert unspecified.status == "unspecified" and unspecified.varieties == []
    mt = tasks_by_id(synthetic_service, AMERICAS)["machine_translation"]
    assert americas.note in mt["limitations"]


def test_provenance_is_preserved(catalog_service: PlaybookService) -> None:
    raw = json.loads((REGISTRY / "aymara" / "americasnlp-aymara-spanish.json").read_text("utf-8"))
    provenance = catalog_service.get_playbook(AMERICAS).provenance.model_dump(mode="json")
    assert provenance["provenance"] == raw["provenance"]
    assert provenance["source_organization"] == raw["source_organization"]
    assert provenance["source_url"] == raw["source_url"]
    assert provenance["documentation_url"] == raw["metadata"]["documentation_url"]
    assert provenance["citation"] == raw["citation"]


# --- Estado local ---------------------------------------------------------------------------


def test_catalog_only_dataset_suggests_official_acquisition(catalog_service: PlaybookService) -> None:
    playbook = catalog_service.get_playbook(COMMON_VOICE)
    assert playbook.local.available_locally is False
    assert playbook.local.semantic_index == "unknown"
    asr = tasks_by_id(catalog_service, COMMON_VOICE)["automatic_speech_recognition"]
    assert asr["next_steps"][0] == (
        "Obtenga el recurso desde la fuente oficial y ejecute el pipeline de ingestión."
    )


def test_undetermined_availability_is_not_reported_as_false(catalog_service: PlaybookService) -> None:
    assert catalog_service.get_playbook(SAMPLE_DATASET_ID).local.available_locally is None


def test_local_dataset_reports_missing_available_and_stale_artifacts(processed_root: Path) -> None:
    service = local_service(processed_root)
    before = service.get_playbook(SAMPLE_DATASET_ID)
    assert before.local.model_dump() == {
        "available_locally": True, "semantic_index": "missing", "atlas": "missing"
    }
    search = next(task for task in before.tasks if task.task is PlaybookTask.SEMANTIC_SEARCH)
    assert "Construya el índice semántico para habilitar búsqueda por similitud." in search.next_steps
    assert not any("pipeline de ingestión" in step for step in search.next_steps)

    SemanticIndexer(FakeEmbeddingProvider()).build(SAMPLE_DATASET_ID, processed_root)
    AtlasBuilder(PCAReducer()).build(SAMPLE_DATASET_ID, processed_root)
    ready = service.get_playbook(SAMPLE_DATASET_ID)
    assert (ready.local.semantic_index, ready.local.atlas) == ("available", "available")
    search = next(task for task in ready.tasks if task.task is PlaybookTask.SEMANTIC_SEARCH)
    assert "Índice semántico local disponible." in search.reasons

    records = processed_root / SAMPLE_DATASET_ID / "records.jsonl"
    records.write_text(
        records.read_text(encoding="utf-8").replace("sentence 001", "sentence 001 edited"),
        encoding="utf-8",
    )
    stale = service.get_playbook(SAMPLE_DATASET_ID)
    assert (stale.local.semantic_index, stale.local.atlas) == ("stale", "stale")
    search = next(task for task in stale.tasks if task.task is PlaybookTask.SEMANTIC_SEARCH)
    assert "El índice semántico está desactualizado: reconstrúyalo." in search.next_steps


def test_compatibility_does_not_depend_on_local_state(processed_root: Path) -> None:
    dataset = LocalDatasetRepository(SAMPLES).get_dataset(SAMPLE_DATASET_ID)
    local = local_service(processed_root).get_playbook(SAMPLE_DATASET_ID)
    catalog = assess_all(dataset, UNKNOWN_LOCAL)
    assert [task.compatibility for task in local.tasks] == [task.compatibility for task in catalog]


# --- Determinismo y endpoints ----------------------------------------------------------------


def test_rules_are_deterministic(catalog_service: PlaybookService) -> None:
    first = catalog_service.get_playbook(AMERICAS).model_dump_json()
    second = PlaybookService(LocalDatasetRepository([SAMPLES, REGISTRY]), None)
    assert second.get_playbook(AMERICAS).model_dump_json() == first
    assert [task.task.value for task in catalog_service.get_playbook(AMERICAS).tasks] == [
        task.value for task in PlaybookTask
    ]


def test_missing_dataset_is_reported(catalog_service: PlaybookService, client_for) -> None:
    with pytest.raises(DatasetNotFoundError):
        catalog_service.get_playbook("missing-dataset")
    with client_for(catalog_service) as client:
        response = client.get("/api/v1/datasets/missing-dataset/playbook")
    assert response.status_code == 404
    assert response.json() == {"detail": "Dataset 'missing-dataset' was not found."}


def test_dataset_playbook_endpoint(catalog_service: PlaybookService, client_for) -> None:
    with client_for(catalog_service) as client:
        response = client.get(f"/api/v1/datasets/{COMMON_VOICE}/playbook")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == COMMON_VOICE
    assert payload["license"]["name"] == "CC0-1.0"
    assert payload["languages"] == [{"name": "Quechua", "iso_code": "qxp"}]
    assert "No es asesoría legal" in payload["disclaimer"]
    assert {task["compatibility"] for task in payload["tasks"]} <= {
        "compatible", "potential", "not_applicable", "unknown"
    }
    assert set(payload["tasks"][0]) == {
        "task", "compatibility", "reasons", "limitations", "license_notes",
        "data_requirements", "next_steps",
    }


def test_task_discovery_groups_without_ranking(synthetic_service: PlaybookService, client_for) -> None:
    with client_for(synthetic_service) as client:
        response = client.get("/api/v1/playbook/datasets", params={"task": "machine_translation"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ordering"] == "dataset_id"
    assert [item["dataset_id"] for item in payload["compatible"]] == [AMERICAS, "bb-parallel"]
    assert payload["potential"] == []
    assert [item["dataset_id"] for item in payload["unknown"]] == ["mm-no-modalities"]
    assert payload["not_applicable_count"] == 3
    for item in payload["compatible"]:
        assert set(item) == {
            "dataset_id", "dataset_name", "compatibility", "reasons", "limitations",
            "available_locally", "license_known",
        }
        assert not any(isinstance(value, float) for value in item.values())


def test_task_discovery_order_is_independent_of_catalog_order(synthetic_catalog: Path) -> None:
    forward = PlaybookService(LocalDatasetRepository([synthetic_catalog, REGISTRY]), None)
    backward = PlaybookService(LocalDatasetRepository([REGISTRY, synthetic_catalog]), None)
    for task in PlaybookTask:
        assert forward.discover(task) == backward.discover(task)
    speech = forward.discover(PlaybookTask.AUTOMATIC_SPEECH_RECOGNITION)
    assert [item.dataset_id for item in speech.compatible] == [COMMON_VOICE]
    assert [item.dataset_id for item in speech.potential] == ["aa-audio-only"]


def test_task_discovery_rejects_unknown_task(catalog_service: PlaybookService, client_for) -> None:
    with client_for(catalog_service) as client:
        assert client.get("/api/v1/playbook/datasets", params={"task": "best"}).status_code == 422
        assert client.get("/api/v1/playbook/datasets").status_code == 422
