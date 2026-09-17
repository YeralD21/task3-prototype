"""Catalog integration without the adapter module's socket-blocking fixture.

TestClient dispatches HTTP in-process, but its event loop may need a local
socketpair on Windows. Keep these checks separate from offline adapter tests.
"""

from fastapi.testclient import TestClient

from app.api.routes.datasets import get_dataset_service
from app.main import app

DATASET_ID = "americasnlp-2021-aymara-spanish"


def test_default_api_catalog_and_existing_filters() -> None:
    # No dependency override: exercise the actual configured repository paths.
    get_dataset_service.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/datasets")
            assert response.status_code == 200
            ids = {item["id"] for item in response.json()}
            common_voice = "common-voice-scripted-speech-qxp-26.0"
            assert {common_voice, DATASET_ID} <= ids
            for query, expected in [
                ({"language": "qxp"}, common_voice),
                ({"language": "aym"}, DATASET_ID),
                ({"modality": "audio"}, common_voice),
                ({"modality": "parallel_text"}, DATASET_ID),
                ({"task": "machine_translation"}, DATASET_ID),
            ]:
                filtered = client.get("/api/v1/datasets", params=query)
                assert filtered.status_code == 200
                assert expected in {item["id"] for item in filtered.json()}
                if query in ({"language": "qxp"}, {"modality": "audio"}):
                    assert DATASET_ID not in {item["id"] for item in filtered.json()}
                if query in ({"language": "aym"}, {"modality": "parallel_text"}):
                    assert common_voice not in {item["id"] for item in filtered.json()}
            empty_page = client.get(f"/api/v1/datasets/{DATASET_ID}/records").json()
            assert empty_page["items"] == []
            assert empty_page["total"] == 0
    finally:
        get_dataset_service.cache_clear()
