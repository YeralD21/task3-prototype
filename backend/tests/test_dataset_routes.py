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
    assert len(response.json()) == 3


def test_records_endpoint_pagination(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/datasets/{SAMPLE_DATASET_ID}/records",
        params={"limit": 1, "offset": 2},
    )

    assert response.status_code == 200
    assert [record["id"] for record in response.json()] == ["synthetic-record-003"]


def test_records_endpoint_language_filter(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/datasets/{SAMPLE_DATASET_ID}/records",
        params={"language": "und"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 3
