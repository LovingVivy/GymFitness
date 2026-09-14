from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.routes import health
from app.main import app

client = TestClient(app)


def test_live_returns_request_id() -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "test-request"})
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert response.headers["X-Request-ID"] == "test-request"


def test_ready_when_database_responds(monkeypatch) -> None:
    monkeypatch.setattr(health, "ping_database", lambda: None)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_503_when_database_fails(monkeypatch) -> None:
    def fail() -> None:
        raise OperationalError("SELECT 1", {}, Exception("offline"))

    monkeypatch.setattr(health, "ping_database", fail)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
