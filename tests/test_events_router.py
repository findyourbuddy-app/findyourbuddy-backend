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
