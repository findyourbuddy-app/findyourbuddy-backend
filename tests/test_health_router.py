import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User


def test_liveness_returns_ok(client: TestClient) -> None:
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_db_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_ok(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


def test_readiness_includes_firebase_check(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert "firebase" in body["checks"]


def test_readiness_reports_redis_down_as_degraded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.routers.health as health_module

    monkeypatch.setattr(health_module, "_probe_redis", lambda url: "error")

    response = client.get("/health/ready")

    assert response.status_code == 200  # still serving, just slower
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"] == "error"


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "S3cret-pass", "display_name": email, "accepted_terms": True},
    )
    token = client.post("/auth/login", json={"email": email, "password": "S3cret-pass"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_metrics_rejects_anonymous_scrape(client: TestClient) -> None:
    assert client.get("/health/metrics").status_code == 401


def test_metrics_accepts_configured_api_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "metrics_api_key", "scrape-secret")

    response = client.get("/health/metrics", headers={"X-Metrics-Api-Key": "scrape-secret"})

    assert response.status_code == 200
    assert "findyourbuddy_up" in response.text


def test_metrics_rejects_wrong_api_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "metrics_api_key", "scrape-secret")

    response = client.get("/health/metrics", headers={"X-Metrics-Api-Key": "nope"})

    assert response.status_code == 401


def test_metrics_still_allows_staff_jwt(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "metrics_api_key", "scrape-secret")
    headers = _register_and_login(client, "staff@example.com")
    user_id = client.get("/users/me", headers=headers).json()["id"]
    db_session.get(User, user_id).is_staff = True
    db_session.commit()

    assert client.get("/health/metrics", headers=headers).status_code == 200
    assert client.get("/health/metrics", headers=_register_and_login(client, "plain@example.com")).status_code == 403
