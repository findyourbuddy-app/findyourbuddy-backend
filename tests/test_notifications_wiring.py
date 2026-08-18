from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import FakeNotificationSender


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "s3cret-pass", "display_name": email, "accepted_terms": True, "phone_number": f"5{abs(hash(email)) % 10**9:09d}"},
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


def test_mutual_like_notifies_both_users(
    client: TestClient, notification_sender: FakeNotificationSender
) -> None:
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
    assert notification_sender.sent == []

    client.post(
        "/swipes/",
        headers=b_headers,
        json={"target_id": a_id, "event_id": event_id, "direction": "like"},
    )

    notified_user_ids = {user_id for user_id, _, _ in notification_sender.sent}
    assert notified_user_ids == {a_id, b_id}


def test_new_message_notifies_the_other_participant(
    client: TestClient, notification_sender: FakeNotificationSender
) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    event_id = _create_event(client, a_headers)
    client.post(
        "/swipes/", headers=a_headers, json={"target_id": b_id, "event_id": event_id, "direction": "like"}
    )
    client.post(
        "/swipes/", headers=b_headers, json={"target_id": a_id, "event_id": event_id, "direction": "like"}
    )
    match_id = client.get("/matches/", headers=a_headers).json()[0]["id"]
    notification_sender.sent.clear()

    client.post(f"/matches/{match_id}/messages/", headers=a_headers, json={"content": "hey"})

    assert notification_sender.sent == [(b_id, "Yeni Mesaj 💬", "Sana yeni bir mesaj geldi.")]
