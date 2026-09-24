"""Corpus Radio con una copia raw sintética: audio local, rutas seguras y privacidad."""

import json
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes.radio import get_corpus_radio_service
from app.main import app
from app.repositories.audio_repository import LocalAudioRepository
from app.repositories.dataset_repository import DatasetNotFoundError, LocalDatasetRepository
from app.services.corpus_radio_service import (
    AudioFileMissingError,
    AudioUnavailableError,
    CorpusRadioService,
    RadioRecordNotFoundError,
    RecordWithoutAudioError,
)
from app.services.semantic_search_service import DatasetNotAvailableLocallyError
from ml.ingestion.pipeline import ingest_dataset
from tests.conftest import PROJECT_ROOT

REGISTRY = PROJECT_ROOT / "datasets" / "registry"
COMMON_VOICE = "common-voice-scripted-speech-qxp-26.0"
AMERICAS = "americasnlp-2021-aymara-spanish"
MP3_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x00synthetic-not-real-audio-" + bytes(range(64))
WAV_BYTES = b"RIFF\x24\x00\x00\x00WAVEfmt synthetic-not-real-audio"
TSV_HEADER = "client_id\tpath\tsentence\tup_votes\tdown_votes\tage\tgender\taccents\tlocale\tsegment\n"
ROWS = [
    ("synthetic-client-a", "clip-001.mp3", "[synthetic sentence 001]"),
    ("synthetic-client-a", "clip-002.mp3", "[synthetic sentence 002 missing file]"),
    ("synthetic-client-b", "clip-003.wav", "[synthetic sentence 003 wav]"),
    ("synthetic-client-b", "", "[synthetic sentence 004 without audio]"),
    ("synthetic-client-b", "clip-005.txt", "[synthetic sentence 005 unsupported]"),
]


@pytest.fixture(autouse=True)
def prohibit_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access forbidden in corpus radio tests")

    monkeypatch.setattr(socket, "create_connection", reject)


@pytest.fixture
def raw_root(tmp_path: Path) -> Path:
    source = tmp_path / "raw" / "quechua" / "common-voice-puno"
    (source / "clips").mkdir(parents=True)
    with (source / "validated.tsv").open("w", encoding="utf-8", newline="") as file:
        file.write(TSV_HEADER)
        for client, clip, sentence in ROWS:
            file.write(f"{client}\t{clip}\t{sentence}\t1\t0\tsixties\tsynthetic-gender\tsynthetic-accent\tqxp\t\n")
    (source / "clips" / "clip-001.mp3").write_bytes(MP3_BYTES)
    (source / "clips" / "clip-003.wav").write_bytes(WAV_BYTES)
    (source / "clips" / "clip-005.txt").write_bytes(b"not audio")
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.mp3").write_bytes(b"ID3 secret outside the source")
    return tmp_path / "raw"


@pytest.fixture
def processed_root(tmp_path: Path, raw_root: Path) -> Path:
    ingest_dataset("common_voice", raw_root / "quechua" / "common-voice-puno", tmp_path / "processed")
    return tmp_path / "processed"


def radio_service(processed_root: Path, raw_root: Path) -> CorpusRadioService:
    datasets = LocalDatasetRepository(REGISTRY, processed_directory=processed_root)
    return CorpusRadioService(datasets, LocalAudioRepository(processed_root), raw_root)


@pytest.fixture
def service(processed_root: Path, raw_root: Path) -> CorpusRadioService:
    return radio_service(processed_root, raw_root)


@pytest.fixture
def client(service: CorpusRadioService) -> Iterator[TestClient]:
    app.dependency_overrides[get_corpus_radio_service] = lambda: service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def rewrite_resource(processed_root: Path, clip: str, path_or_url: str) -> None:
    path = processed_root / COMMON_VOICE / "audio-resources.jsonl"
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        resource = json.loads(line)
        if resource["source_audio_id"] == clip:
            resource["path_or_url"] = path_or_url
        lines.append(json.dumps(resource))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audio_path(clip: str) -> str:
    return f"/api/v1/datasets/{COMMON_VOICE}/records/{clip}/audio"


# --- Listado ---------------------------------------------------------------------------


def test_radio_lists_records_with_audio_and_their_status(service: CorpusRadioService) -> None:
    page = service.list_radio(COMMON_VOICE, limit=10)
    assert page.contains_audio is True
    assert page.total == 4
    statuses = {item.record.source_record_id: item.audio_status for item in page.items}
    assert statuses == {
        "clip-001.mp3": "available",
        "clip-002.mp3": "missing_file",
        "clip-003.wav": "available",
        "clip-005.txt": "unsupported_format",
    }
    first = page.items[0]
    assert first.has_audio is True
    assert first.audio_url == audio_path("clip-001.mp3")
    assert first.media_type == "audio/mpeg"
    assert page.items[1].audio_url is None


def test_radio_preserves_language_variety_provenance_and_source_ids(
    service: CorpusRadioService,
) -> None:
    record = service.list_radio(COMMON_VOICE).items[0].record
    assert record.source_record_id == "clip-001.mp3"
    assert record.dataset_id == COMMON_VOICE
    assert record.language_code == "qxp"
    assert record.language_variety is not None
    assert record.language_variety.name == "Puno Quechua / Punu qhichwa"
    assert record.provenance.organization == "Mozilla Foundation / Common Voice"
    assert record.provenance.original_dataset_id == "common-voice-scripted-speech-26.0-qxp"


def test_radio_does_not_expose_paths_or_sensitive_attributes(client: TestClient, raw_root: Path) -> None:
    response = client.get(f"/api/v1/datasets/{COMMON_VOICE}/radio")
    assert response.status_code == 200
    body = response.text
    for forbidden in (str(raw_root), str(raw_root).replace("\\", "\\\\"), "clips", "sixties",
                      "synthetic-gender", "synthetic-accent"):
        assert forbidden not in body, forbidden
    items = response.json()["items"]
    assert all(
        item["audio_url"] is None or item["audio_url"].startswith("/api/v1/datasets/")
        for item in items
    )
    assert all("speaker_id" not in item["record"] for item in items)
    assert items[0]["record"]["metadata"] == {"up_votes": "1", "down_votes": "0", "locale": "qxp"}


def test_radio_view_does_not_alter_stored_canonical_records(
    client: TestClient, processed_root: Path
) -> None:
    records_path = processed_root / COMMON_VOICE / "records.jsonl"
    before = records_path.read_bytes()
    assert client.get(f"/api/v1/datasets/{COMMON_VOICE}/radio").status_code == 200
    assert client.get(audio_path("clip-001.mp3")).status_code == 200
    assert records_path.read_bytes() == before
    stored = json.loads(before.decode("utf-8").splitlines()[0])
    assert stored["speaker_id"] == f"{COMMON_VOICE}:speaker:synthetic-client-a"
    assert stored["metadata"]["accents"] == "synthetic-accent"


def test_radio_pagination(client: TestClient) -> None:
    first = client.get(f"/api/v1/datasets/{COMMON_VOICE}/radio", params={"limit": 2}).json()
    second = client.get(
        f"/api/v1/datasets/{COMMON_VOICE}/radio", params={"limit": 2, "offset": 2}
    ).json()
    assert (first["total"], first["limit"], first["offset"]) == (4, 2, 0)
    assert [item["record"]["source_record_id"] for item in first["items"]] == [
        "clip-001.mp3", "clip-002.mp3"
    ]
    assert [item["record"]["source_record_id"] for item in second["items"]] == [
        "clip-003.wav", "clip-005.txt"
    ]
    beyond = client.get(f"/api/v1/datasets/{COMMON_VOICE}/radio", params={"offset": 50}).json()
    assert beyond["items"] == [] and beyond["total"] == 4
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        assert client.get(f"/api/v1/datasets/{COMMON_VOICE}/radio", params=params).status_code == 422


def test_text_dataset_reports_no_audio(client: TestClient) -> None:
    response = client.get(f"/api/v1/datasets/{AMERICAS}/radio")
    assert response.status_code == 200
    assert response.json() == {
        "dataset_id": AMERICAS, "contains_audio": False, "items": [], "total": 0,
        "limit": 20, "offset": 0,
    }


def test_catalog_only_audio_dataset_is_not_local(raw_root: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty-processed"
    empty.mkdir()
    service = radio_service(empty, raw_root)
    with pytest.raises(DatasetNotAvailableLocallyError):
        service.list_radio(COMMON_VOICE)
    app.dependency_overrides[get_corpus_radio_service] = lambda: service
    try:
        with TestClient(app) as client:
            listing = client.get(f"/api/v1/datasets/{COMMON_VOICE}/radio")
            audio = client.get(audio_path("clip-001.mp3"))
    finally:
        app.dependency_overrides.clear()
    assert listing.status_code == audio.status_code == 409
    assert listing.json()["detail"] == f"Dataset '{COMMON_VOICE}' is not available locally."


def test_missing_dataset(client: TestClient, service: CorpusRadioService) -> None:
    with pytest.raises(DatasetNotFoundError):
        service.list_radio("missing-dataset")
    assert client.get("/api/v1/datasets/missing-dataset/radio").status_code == 404
    assert client.get("/api/v1/datasets/missing-dataset/records/x/audio").status_code == 404


# --- Audio ----------------------------------------------------------------------------------


def test_existing_mp3_is_served_inline_with_content_type(client: TestClient) -> None:
    response = client.get(audio_path("clip-001.mp3"))
    assert response.status_code == 200
    assert response.content == MP3_BYTES
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.headers["content-disposition"] == "inline"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in response.headers["cache-control"]


def test_other_formats_are_not_assumed_to_be_mp3(client: TestClient) -> None:
    response = client.get(audio_path("clip-003.wav"))
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    unsupported = client.get(audio_path("clip-005.txt"))
    assert unsupported.status_code == 409


def test_range_requests_support_seeking(client: TestClient) -> None:
    partial = client.get(audio_path("clip-001.mp3"), headers={"Range": "bytes=3-9"})
    assert partial.status_code == 206
    assert partial.content == MP3_BYTES[3:10]
    assert partial.headers["content-range"] == f"bytes 3-9/{len(MP3_BYTES)}"
    beyond = client.get(audio_path("clip-001.mp3"), headers={"Range": f"bytes={len(MP3_BYTES)}-"})
    assert beyond.status_code == 416


def test_missing_file_is_reported_without_failing_the_listing(
    client: TestClient, service: CorpusRadioService
) -> None:
    with pytest.raises(AudioFileMissingError):
        service.resolve_audio(COMMON_VOICE, "clip-002.mp3")
    response = client.get(audio_path("clip-002.mp3"))
    assert response.status_code == 404
    assert response.json() == {"detail": "Audio for record 'clip-002.mp3' is not available locally."}
    assert client.get(f"/api/v1/datasets/{COMMON_VOICE}/radio").status_code == 200


def test_record_without_audio_and_unknown_record(client: TestClient, service: CorpusRadioService) -> None:
    with pytest.raises(RecordWithoutAudioError):
        service.resolve_audio(COMMON_VOICE, "validated.tsv:row:5")
    with pytest.raises(RadioRecordNotFoundError):
        service.resolve_audio(COMMON_VOICE, "does-not-exist.mp3")
    assert client.get(audio_path("does-not-exist.mp3")).status_code == 404


# --- Seguridad --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reference",
    ["../../../../outside/secret.mp3", "OUTSIDE_ABSOLUTE", "https://example.org/clip.mp3"],
    ids=["relative-traversal", "absolute-outside", "remote-url"],
)
def test_tampered_references_outside_the_source_are_blocked(
    processed_root: Path, raw_root: Path, tmp_path: Path, reference: str
) -> None:
    secret = tmp_path / "outside" / "secret.mp3"
    rewrite_resource(processed_root, "clip-001.mp3", str(secret) if reference == "OUTSIDE_ABSOLUTE" else reference)
    service = radio_service(processed_root, raw_root)
    assert service.list_radio(COMMON_VOICE).items[0].audio_status == "unavailable"
    with pytest.raises(AudioUnavailableError):
        service.resolve_audio(COMMON_VOICE, "clip-001.mp3")
    app.dependency_overrides[get_corpus_radio_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.get(audio_path("clip-001.mp3"))
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 409
    assert b"secret" not in response.content
    assert str(tmp_path) not in response.text


def test_source_outside_authorized_raw_root_is_blocked(processed_root: Path, tmp_path: Path) -> None:
    other_root = tmp_path / "another-raw-root"
    other_root.mkdir()
    service = radio_service(processed_root, other_root)
    assert {item.audio_status for item in service.list_radio(COMMON_VOICE).items} == {"unavailable"}
    with pytest.raises(AudioUnavailableError):
        service.resolve_audio(COMMON_VOICE, "clip-001.mp3")


@pytest.mark.parametrize(
    "record_id",
    ["..%2F..%2F..%2Foutside%2Fsecret.mp3", "../../outside/secret.mp3", "C:%5CWindows%5Cwin.ini"],
)
def test_client_supplied_ids_are_never_used_as_paths(client: TestClient, record_id: str) -> None:
    response = client.get(f"/api/v1/datasets/{COMMON_VOICE}/records/{record_id}/audio")
    assert response.status_code == 404
    # Sin codificar, el cliente HTTP resuelve «../» antes de enviar y ninguna ruta coincide.
    assert response.headers["content-type"] == "application/json"
    detail = response.json()["detail"]
    assert detail == "Not Found" or "was not found in dataset" in detail
    assert b"ID3 secret outside the source" not in response.content


def test_symlink_escape_is_blocked(processed_root: Path, raw_root: Path, tmp_path: Path) -> None:
    link = raw_root / "quechua" / "common-voice-puno" / "clips" / "linked.mp3"
    try:
        link.symlink_to(tmp_path / "outside" / "secret.mp3")
    except OSError:
        pytest.skip("symbolic links are not permitted in this environment")
    rewrite_resource(processed_root, "clip-001.mp3", str(link))
    service = radio_service(processed_root, raw_root)
    with pytest.raises(AudioUnavailableError):
        service.resolve_audio(COMMON_VOICE, "clip-001.mp3")


def test_ingestion_never_copies_audio_into_processed(processed_root: Path) -> None:
    files = [path.name for path in (processed_root / COMMON_VOICE).rglob("*")]
    assert not [name for name in files if name.endswith((".mp3", ".wav"))]
