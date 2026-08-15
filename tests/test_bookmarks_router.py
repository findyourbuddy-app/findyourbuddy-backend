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


def test_create_bookmark_returns_201(client: TestClient) -> None:
    headers = _register_and_login(client, "user@example.com")
    event_id = _create_event(client, headers)

    response = client.post(f"/bookmarks/{event_id}", headers=headers)

    assert response.status_code == 201
    assert response.json()["event"]["id"] == event_id


def test_create_bookmark_for_unknown_event_returns_404(client: TestClient) -> None:
    headers = _register_and_login(client, "user@example.com")

    response = client.post("/bookmarks/999", headers=headers)

    assert response.status_code == 404


def test_create_duplicate_bookmark_returns_409(client: TestClient) -> None:
    headers = _register_and_login(client, "user@example.com")
    event_id = _create_event(client, headers)
    client.post(f"/bookmarks/{event_id}", headers=headers)

    response = client.post(f"/bookmarks/{event_id}", headers=headers)

    assert response.status_code == 409


def test_list_my_bookmarks_returns_bookmarked_events(client: TestClient) -> None:
    headers = _register_and_login(client, "user@example.com")
    event_id = _create_event(client, headers)
    client.post(f"/bookmarks/{event_id}", headers=headers)

    response = client.get("/bookmarks/", headers=headers)

    assert response.status_code == 200
    assert [b["event"]["id"] for b in response.json()] == [event_id]


def test_delete_bookmark_returns_204(client: TestClient) -> None:
    headers = _register_and_login(client, "user@example.com")
    event_id = _create_event(client, headers)
    client.post(f"/bookmarks/{event_id}", headers=headers)

    response = client.delete(f"/bookmarks/{event_id}", headers=headers)

    assert response.status_code == 204
    assert client.get("/bookmarks/", headers=headers).json() == []


def test_delete_unknown_bookmark_returns_404(client: TestClient) -> None:
    headers = _register_and_login(client, "user@example.com")
    event_id = _create_event(client, headers)

    response = client.delete(f"/bookmarks/{event_id}", headers=headers)

    assert response.status_code == 404
