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


def test_block_user_returns_201(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    b_id = client.get("/users/me", headers=b_headers).json()["id"]

    response = client.post(f"/users/{b_id}/block", headers=a_headers)

    assert response.status_code == 201


def test_blocking_same_user_twice_returns_409(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    client.post(f"/users/{b_id}/block", headers=a_headers)

    response = client.post(f"/users/{b_id}/block", headers=a_headers)

    assert response.status_code == 409


def test_blocking_self_returns_400(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]

    response = client.post(f"/users/{a_id}/block", headers=a_headers)

    assert response.status_code == 400


def test_blocking_prevents_swiping(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    event_id = _create_event(client, a_headers)
    client.post(f"/users/{b_id}/block", headers=a_headers)

    response = client.post(
        "/swipes/",
        headers=a_headers,
        json={"target_id": b_id, "event_id": event_id, "direction": "like"},
    )

    assert response.status_code == 403


def test_blocked_user_excluded_from_candidates(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    event_id = _create_event(client, a_headers)
    client.post(f"/users/{b_id}/block", headers=a_headers)

    response = client.get(
        "/swipes/candidates", headers=a_headers, params={"event_id": event_id}
    )

    candidate_ids = [user["id"] for user in response.json()]
    assert b_id not in candidate_ids


def test_create_report_returns_201(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    b_id = client.get("/users/me", headers=b_headers).json()["id"]

    response = client.post(
        "/reports",
        headers=a_headers,
        json={"reported_user_id": b_id, "reason": "harassment", "description": "rude messages"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_reporting_self_returns_400(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]

    response = client.post(
        "/reports", headers=a_headers, json={"reported_user_id": a_id, "reason": "other"}
    )

    assert response.status_code == 400
