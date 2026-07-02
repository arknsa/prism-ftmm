"""Health endpoint tests (Phase 0)."""

from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient

client = TestClient(create_app())


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["app_env"] in {"local", "production"}
    # No DATABASE_URL in the test environment -> DB is reported as unconfigured.
    assert body["database"] in {"connected", "unconfigured", "error"}
