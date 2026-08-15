from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.rate_limit import limiter


def test_login_returns_429_when_rate_limit_exceeded(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "3")
    get_settings.cache_clear()
    limiter.reset()
    try:
        client.post(
            "/auth/register",
            json={
                "email": "ada@example.com",
                "password": "s3cret-pass",
                "display_name": "Ada",
                "accepted_terms": True,
            },
        )

        login_payload = {"email": "ada@example.com", "password": "s3cret-pass"}
        for _ in range(3):
            response = client.post("/auth/login", json=login_payload)
            assert response.status_code == 200

        response = client.post("/auth/login", json=login_payload)
        assert response.status_code == 429
    finally:
        get_settings.cache_clear()
