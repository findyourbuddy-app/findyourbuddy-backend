from datetime import datetime, timedelta

from fastapi.testclient import TestClient


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


def _create_match(client: TestClient, a_headers: dict[str, str], b_headers: dict[str, str]) -> int:
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    event_id = _create_event(client, a_headers)
    client.post(
        "/swipes/", headers=a_headers, json={"target_id": b_id, "event_id": event_id, "direction": "like"}
    )
    client.post(
        "/swipes/", headers=b_headers, json={"target_id": a_id, "event_id": event_id, "direction": "like"}
    )
    return client.get("/matches/", headers=a_headers).json()[0]["id"]


def test_matched_users_can_exchange_messages(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    match_id = _create_match(client, a_headers, b_headers)

    response = client.post(
        f"/matches/{match_id}/messages/", headers=a_headers, json={"content": "hey"}
    )
    assert response.status_code == 201

    messages = client.get(f"/matches/{match_id}/messages/", headers=b_headers).json()
    assert [message["content"] for message in messages] == ["hey"]


def test_non_participant_cannot_read_messages(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    outsider_headers = _register_and_login(client, "outsider@example.com")
    match_id = _create_match(client, a_headers, b_headers)

    response = client.get(f"/matches/{match_id}/messages/", headers=outsider_headers)

    assert response.status_code == 403


def test_non_participant_cannot_send_message(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    outsider_headers = _register_and_login(client, "outsider@example.com")
    match_id = _create_match(client, a_headers, b_headers)

    response = client.post(
        f"/matches/{match_id}/messages/", headers=outsider_headers, json={"content": "hi"}
    )

    assert response.status_code == 403


def test_get_messages_returns_404_for_unknown_match(client: TestClient) -> None:
    headers = _register_and_login(client, "a@example.com")

    response = client.get("/matches/999/messages/", headers=headers)

    assert response.status_code == 404


def test_post_message_returns_404_for_unknown_match(client: TestClient) -> None:
    headers = _register_and_login(client, "a@example.com")

    response = client.post("/matches/999/messages/", headers=headers, json={"content": "hi"})

    assert response.status_code == 404


def test_message_with_banned_content_is_rejected(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    match_id = _create_match(client, a_headers, b_headers)

    response = client.post(
        f"/matches/{match_id}/messages/", headers=a_headers, json={"content": "this is a scam"}
    )

    assert response.status_code == 422


def test_mark_messages_as_read_returns_count_of_affected_messages(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    match_id = _create_match(client, a_headers, b_headers)
    client.post(f"/matches/{match_id}/messages/", headers=a_headers, json={"content": "hey"})
    client.post(f"/matches/{match_id}/messages/", headers=a_headers, json={"content": "there"})

    response = client.patch(f"/matches/{match_id}/messages/read", headers=b_headers)

    assert response.status_code == 200
    assert response.json()["count"] == 2

    messages = client.get(f"/matches/{match_id}/messages/", headers=b_headers).json()
    assert all(message["is_read"] for message in messages)


def test_non_participant_cannot_mark_messages_as_read(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    outsider_headers = _register_and_login(client, "outsider@example.com")
    match_id = _create_match(client, a_headers, b_headers)

    response = client.patch(f"/matches/{match_id}/messages/read", headers=outsider_headers)

    assert response.status_code == 403
