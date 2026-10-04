import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_service_status(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import main

    monkeypatch.setattr(main, "check_database", lambda: True)
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
