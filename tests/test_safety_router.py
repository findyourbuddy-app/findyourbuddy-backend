from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "s3cret-pass", "display_name": email, "accepted_terms": True},
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


def test_blocking_hides_existing_match_and_denies_message_access(client: TestClient) -> None:
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

    client.post(f"/users/{b_id}/block", headers=a_headers)

    assert client.get("/matches/", headers=a_headers).json() == []
    assert client.get("/matches/", headers=b_headers).json() == []

    assert client.get(f"/matches/{match_id}/messages/", headers=a_headers).status_code == 403
    assert client.get(f"/matches/{match_id}/messages/", headers=b_headers).status_code == 403


def test_unblock_user_returns_204_and_restores_candidate_visibility(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    event_id = _create_event(client, a_headers)
    client.post(f"/users/{b_id}/block", headers=a_headers)

    response = client.delete(f"/users/{b_id}/block", headers=a_headers)
    assert response.status_code == 204

    candidates = client.get(
        "/swipes/candidates", headers=a_headers, params={"event_id": event_id}
    ).json()
    assert b_id in [user["id"] for user in candidates]


def test_list_my_blocks_returns_blocked_users(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    client.post(f"/users/{b_id}/block", headers=a_headers)

    response = client.get("/users/me/blocks", headers=a_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["blocked_user"]["id"] == b_id


def test_list_my_blocks_excludes_blocks_placed_on_me(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    client.post(f"/users/{a_id}/block", headers=b_headers)

    response = client.get("/users/me/blocks", headers=a_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_unblocking_a_non_blocked_user_returns_404(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    b_id = client.get("/users/me", headers=b_headers).json()["id"]

    response = client.delete(f"/users/{b_id}/block", headers=a_headers)

    assert response.status_code == 404


def test_non_staff_cannot_update_report_status(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    report_id = client.post(
        "/reports",
        headers=a_headers,
        json={"reported_user_id": b_id, "reason": "harassment"},
    ).json()["id"]

    response = client.patch(
        f"/reports/{report_id}", headers=a_headers, json={"status": "reviewed"}
    )

    assert response.status_code == 403


def test_staff_can_update_report_status(client: TestClient, db_session: Session) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    report_id = client.post(
        "/reports",
        headers=a_headers,
        json={"reported_user_id": b_id, "reason": "harassment"},
    ).json()["id"]

    staff_user = db_session.get(User, a_id)
    staff_user.is_staff = True
    db_session.commit()

    response = client.patch(
        f"/reports/{report_id}", headers=a_headers, json={"status": "reviewed"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "reviewed"


def test_updating_unknown_report_returns_404_for_staff(
    client: TestClient, db_session: Session
) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    staff_user = db_session.get(User, a_id)
    staff_user.is_staff = True
    db_session.commit()

    response = client.patch(
        "/reports/999", headers=a_headers, json={"status": "reviewed"}
    )

    assert response.status_code == 404


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


def test_non_staff_cannot_list_reports(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")

    response = client.get("/reports", headers=a_headers)

    assert response.status_code == 403


def test_staff_can_list_reports(client: TestClient, db_session: Session) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    client.post(
        "/reports", headers=a_headers, json={"reported_user_id": b_id, "reason": "harassment"}
    )

    staff_user = db_session.get(User, a_id)
    staff_user.is_staff = True
    db_session.commit()

    response = client.get("/reports", headers=a_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["reported_user_id"] == b_id


def test_reporting_self_returns_400(client: TestClient) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]

    response = client.post(
        "/reports", headers=a_headers, json={"reported_user_id": a_id, "reason": "other"}
    )

    assert response.status_code == 400
