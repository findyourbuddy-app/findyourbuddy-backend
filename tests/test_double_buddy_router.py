from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "S3cret-pass",
            "display_name": email.split("@")[0],
            "accepted_terms": True,
            "phone_number": f"5{abs(hash(email)) % 10**9:09d}",
        },
    )
    resp = client.post("/auth/login", json={"email": email, "password": "S3cret-pass"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_get_double_buddy_returns_none_when_no_pair(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/double-buddy/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() is None


def test_invite_creates_pair(client: TestClient) -> None:
    alice = _register_and_login(client, "alice@example.com")
    bob_headers = _register_and_login(client, "bob@example.com")
    bob_id = client.get("/users/me", headers=bob_headers).json()["id"]

    response = client.post("/double-buddy/invite", json={"partner_id": bob_id}, headers=alice)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "accepted"
    assert data["user_2_id"] == bob_id


def test_invite_self_returns_400(client: TestClient, auth_headers: dict[str, str]) -> None:
    me_id = client.get("/users/me", headers=auth_headers).json()["id"]
    response = client.post("/double-buddy/invite", json={"partner_id": me_id}, headers=auth_headers)
    assert response.status_code == 400


def test_invite_nonexistent_user_returns_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/double-buddy/invite", json={"partner_id": 99999}, headers=auth_headers)
    assert response.status_code == 404


def test_get_double_buddy_after_invite(client: TestClient) -> None:
    alice = _register_and_login(client, "alice2@example.com")
    bob_headers = _register_and_login(client, "bob2@example.com")
    bob_id = client.get("/users/me", headers=bob_headers).json()["id"]

    client.post("/double-buddy/invite", json={"partner_id": bob_id}, headers=alice)

    response = client.get("/double-buddy/me", headers=alice)
    assert response.status_code == 200
    assert response.json()["user_2_id"] == bob_id


def test_disband_removes_pair(client: TestClient) -> None:
    alice = _register_and_login(client, "alice3@example.com")
    bob_headers = _register_and_login(client, "bob3@example.com")
    bob_id = client.get("/users/me", headers=bob_headers).json()["id"]

    client.post("/double-buddy/invite", json={"partner_id": bob_id}, headers=alice)
    disband = client.delete("/double-buddy/disband", headers=alice)
    assert disband.status_code == 204

    response = client.get("/double-buddy/me", headers=alice)
    assert response.json() is None


def test_invite_replaces_existing_pair(client: TestClient) -> None:
    alice = _register_and_login(client, "alice4@example.com")
    bob_headers = _register_and_login(client, "bob4@example.com")
    charlie_headers = _register_and_login(client, "charlie4@example.com")
    bob_id = client.get("/users/me", headers=bob_headers).json()["id"]
    charlie_id = client.get("/users/me", headers=charlie_headers).json()["id"]

    client.post("/double-buddy/invite", json={"partner_id": bob_id}, headers=alice)
    client.post("/double-buddy/invite", json={"partner_id": charlie_id}, headers=alice)

    response = client.get("/double-buddy/me", headers=alice)
    assert response.json()["user_2_id"] == charlie_id
