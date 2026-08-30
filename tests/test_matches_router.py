from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "S3cret-pass", "display_name": email, "accepted_terms": True, "phone_number": f"5{abs(hash(email)) % 10**9:09d}"},
    )
    response = client.post("/auth/login", json={"email": email, "password": "S3cret-pass"})
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
            "starts_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )
    return response.json()["id"]


def test_mutual_like_creates_match_visible_via_api(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    event_id = _create_event(client, a_headers)

    client.post(
        "/swipes/",
        headers=a_headers,
        json={"target_id": b_id, "event_id": event_id, "direction": "like"},
    )
    assert client.get("/matches/", headers=a_headers).json() == []

    client.post(
        "/swipes/",
        headers=b_headers,
        json={"target_id": a_id, "event_id": event_id, "direction": "like"},
    )

    matches = client.get("/matches/", headers=a_headers).json()
    assert len(matches) == 1
    assert {matches[0]["user_a_id"], matches[0]["user_b_id"]} == {a_id, b_id}
    assert matches[0]["other_user"]["id"] == b_id
    assert matches[0]["other_user"]["display_name"] == "b@example.com"
    assert matches[0]["last_message"] is None


def test_general_browse_mutual_like_creates_match_with_null_event(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    b_id = client.get("/users/me", headers=b_headers).json()["id"]

    client.post("/swipes/", headers=a_headers, json={"target_id": b_id, "direction": "like"})
    client.post("/swipes/", headers=b_headers, json={"target_id": a_id, "direction": "like"})

    response = client.get("/matches/", headers=a_headers)
    assert response.status_code == 200
    matches = response.json()
    assert len(matches) == 1
    assert matches[0]["event_id"] is None
    assert matches[0]["event_title"] is None
    assert matches[0]["other_user"]["id"] == b_id


def test_match_response_includes_last_message_after_chatting(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    event_id = _create_event(client, a_headers)

    client.post(
        "/swipes/",
        headers=a_headers,
        json={"target_id": b_id, "event_id": event_id, "direction": "like"},
    )
    client.post(
        "/swipes/",
        headers=b_headers,
        json={"target_id": a_id, "event_id": event_id, "direction": "like"},
    )
    match_id = client.get("/matches/", headers=a_headers).json()[0]["id"]

    client.post(
        f"/matches/{match_id}/messages/", headers=a_headers, json={"content": "Selam!"}
    )

    matches = client.get("/matches/", headers=b_headers).json()
    assert matches[0]["last_message"]["content"] == "Selam!"
    assert matches[0]["last_message"]["sender_id"] == a_id
    assert matches[0]["other_user"]["id"] == a_id
