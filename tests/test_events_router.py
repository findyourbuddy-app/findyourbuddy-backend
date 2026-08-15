from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def _event_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Trail run",
        "category": "sports",
        "location_name": "Central Park",
        "latitude": 40.0,
        "longitude": -73.0,
        "starts_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_list_events_requires_auth(client: TestClient) -> None:
    response = client.get("/events/")

    assert response.status_code == 401


def test_create_and_list_event(client: TestClient, auth_headers: dict[str, str]) -> None:
    create_response = client.post("/events/", headers=auth_headers, json=_event_payload())
    assert create_response.status_code == 201

    list_response = client.get("/events/", headers=auth_headers)
    assert list_response.status_code == 200
    titles = [event["title"] for event in list_response.json()]
    assert "Trail run" in titles


def test_get_event_returns_404_for_unknown_id(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/events/999", headers=auth_headers)

    assert response.status_code == 404


def test_get_event_returns_created_event(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_response = client.post("/events/", headers=auth_headers, json=_event_payload())
    event_id = create_response.json()["id"]

    response = client.get(f"/events/{event_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == event_id


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "s3cret-pass", "display_name": email, "accepted_terms": True},
    )
    response = client.post("/auth/login", json={"email": email, "password": "s3cret-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_event_attendee_count_reflects_distinct_swipers(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_response = client.post("/events/", headers=auth_headers, json=_event_payload())
    event_id = create_response.json()["id"]
    assert create_response.json()["attendee_count"] == 0

    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_headers = _register_and_login(client, "target@example.com")
    target_id = client.get("/users/me", headers=target_headers).json()["id"]
    client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_id, "event_id": event_id, "direction": "like"},
    )

    detail_response = client.get(f"/events/{event_id}", headers=auth_headers)
    assert detail_response.json()["attendee_count"] == 1

    list_response = client.get("/events/", headers=auth_headers)
    listed = next(e for e in list_response.json() if e["id"] == event_id)
    assert listed["attendee_count"] == 1
