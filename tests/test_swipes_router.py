from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.config import get_settings


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "s3cret-pass", "display_name": email},
    )
    response = client.post("/auth/login", json={"email": email, "password": "s3cret-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_event(client: TestClient, headers: dict[str, str]) -> int:
    response = client.post(
        "/events/",
        headers=headers,
        json={
            "title": "Trail run",
            "category": "sports",
            "location_name": "Central Park",
            "latitude": 40.0,
            "longitude": -73.0,
            "starts_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
        },
    )
    return response.json()["id"]


def test_create_swipe_returns_201(client: TestClient) -> None:
    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_headers = _register_and_login(client, "target@example.com")
    target_id = client.get("/users/me", headers=target_headers).json()["id"]
    event_id = _create_event(client, swiper_headers)

    response = client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_id, "event_id": event_id, "direction": "like"},
    )

    assert response.status_code == 201


def test_create_swipe_rejects_duplicate(client: TestClient) -> None:
    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_headers = _register_and_login(client, "target@example.com")
    target_id = client.get("/users/me", headers=target_headers).json()["id"]
    event_id = _create_event(client, swiper_headers)
    payload = {"target_id": target_id, "event_id": event_id, "direction": "like"}

    client.post("/swipes/", headers=swiper_headers, json=payload)
    response = client.post("/swipes/", headers=swiper_headers, json=payload)

    assert response.status_code == 409


def test_create_swipe_returns_429_when_daily_limit_reached(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("DAILY_SWIPE_LIMIT", "1")
    get_settings.cache_clear()

    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_1 = _register_and_login(client, "target1@example.com")
    target_2_id = client.get(
        "/users/me", headers=_register_and_login(client, "target2@example.com")
    ).json()["id"]
    target_1_id = client.get("/users/me", headers=target_1).json()["id"]
    event_id = _create_event(client, swiper_headers)

    client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_1_id, "event_id": event_id, "direction": "like"},
    )
    response = client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_2_id, "event_id": event_id, "direction": "like"},
    )

    assert response.status_code == 429
    get_settings.cache_clear()


def test_get_candidates_excludes_self(client: TestClient) -> None:
    swiper_headers = _register_and_login(client, "swiper@example.com")
    _register_and_login(client, "other@example.com")
    event_id = _create_event(client, swiper_headers)
    swiper_id = client.get("/users/me", headers=swiper_headers).json()["id"]

    response = client.get(
        "/swipes/candidates", headers=swiper_headers, params={"event_id": event_id}
    )

    assert response.status_code == 200
    candidate_ids = [user["id"] for user in response.json()]
    assert swiper_id not in candidate_ids
