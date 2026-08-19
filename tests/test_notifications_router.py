from unittest.mock import patch

from datetime import datetime, timedelta
from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "s3cret-pass", "display_name": email, "accepted_terms": True, "phone_number": f"5{abs(hash(email)) % 10**9:09d}"},
    )
    response = client.post("/auth/login", json={"email": email, "password": "s3cret-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_event(client: TestClient, headers: dict[str, str]) -> int:
    with patch("app.services.llm_moderation_service.evaluate_event_with_llm", return_value=(True, None)):
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


def _create_mutual_match(client: TestClient, a_headers: dict, b_headers: dict) -> None:
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    event_id = _create_event(client, a_headers)
    client.post(
        "/swipes/", headers=a_headers, json={"target_id": b_id, "event_id": event_id, "direction": "like"}
    )
    client.post(
        "/swipes/", headers=b_headers, json={"target_id": a_id, "event_id": event_id, "direction": "like"}
    )


def test_list_my_notifications_returns_notifications_after_match(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    _create_mutual_match(client, a_headers, b_headers)

    response = client.get("/notifications/", headers=a_headers)

    assert response.status_code == 200
    titles = [n["title"] for n in response.json()]
    assert "Yeni Eşleşme! 🎉" in titles


def test_mark_my_notifications_read(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    _create_mutual_match(client, a_headers, b_headers)

    response = client.patch("/notifications/read", headers=a_headers)

    assert response.status_code == 200
    assert response.json()["count"] >= 1
    assert all(n["is_read"] for n in client.get("/notifications/", headers=a_headers).json())
