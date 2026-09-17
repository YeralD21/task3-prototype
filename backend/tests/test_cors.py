"""Allowed frontend origin receives CORS headers; other origins do not."""
from fastapi.testclient import TestClient
from app.main import app


def test_frontend_cors_origin() -> None:
    with TestClient(app) as client:
        response = client.get('/api/v1/health', headers={'Origin': 'http://localhost:3000'})
        assert response.headers['access-control-allow-origin'] == 'http://localhost:3000'
        response = client.get('/api/v1/health', headers={'Origin': 'https://unrelated.example'})
        assert 'access-control-allow-origin' not in response.headers
