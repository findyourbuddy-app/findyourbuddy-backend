from fastapi.testclient import TestClient


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
