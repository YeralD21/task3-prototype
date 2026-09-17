"""Pruebas HTTP del Dataset Registry."""

from fastapi.testclient import TestClient

from tests.conftest import SAMPLE_DATASET_ID


def test_list_datasets(client: TestClient) -> None:
    response = client.get("/api/v1/datasets")

    assert response.status_code == 200
    assert response.json()[0]["id"] == SAMPLE_DATASET_ID


def test_get_existing_dataset(client: TestClient) -> None:
    response = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}")

    assert response.status_code == 200
    assert response.json()["license"]["commercial_use"] is None


def test_get_missing_dataset_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/missing-dataset")

    assert response.status_code == 404
    assert "was not found" in response.json()["detail"]


def test_list_dataset_records(client: TestClient) -> None:
    response = client.get(f"/api/v1/datasets/{SAMPLE_DATASET_ID}/records")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 3
    assert response.json()["total"] == 3


def test_records_endpoint_pagination(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/datasets/{SAMPLE_DATASET_ID}/records",
        params={"limit": 1, "offset": 2},
    )

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["items"]] == ["synthetic-record-003"]


def test_records_endpoint_language_filter(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/datasets/{SAMPLE_DATASET_ID}/records",
        params={"language": "und"},
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 3


def test_records_endpoint_text_query_and_pagination(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/datasets/{SAMPLE_DATASET_ID}/records",
        params={"q": "SYNTHETIC", "limit": 1, "offset": 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["limit"] == 1
    assert payload["offset"] == 1
    assert payload["items"][0]["source_record_id"] == "synthetic-source-record-002"
