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


def _id(client: TestClient, headers: dict[str, str]) -> int:
    return client.get("/users/me", headers=headers).json()["id"]


def test_get_double_buddy_returns_none_when_no_pair(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/double-buddy/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() is None


def test_invite_creates_pending_pair(client: TestClient) -> None:
    alice = _register_and_login(client, "alice@example.com")
    bob = _register_and_login(client, "bob@example.com")
    bob_id = _id(client, bob)

    response = client.post("/double-buddy/invite", json={"partner_id": bob_id}, headers=alice)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "pending"
    assert data["user_2_id"] == bob_id
    assert data["is_incoming"] is False


def test_invitee_sees_incoming_invite(client: TestClient) -> None:
    alice = _register_and_login(client, "alice2@example.com")
    bob = _register_and_login(client, "bob2@example.com")
    bob_id = _id(client, bob)

    client.post("/double-buddy/invite", json={"partner_id": bob_id}, headers=alice)

    response = client.get("/double-buddy/me", headers=bob)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending"
    assert body["is_incoming"] is True


def test_accept_invite_makes_pair_active_for_both(client: TestClient) -> None:
    alice = _register_and_login(client, "alice3@example.com")
    bob = _register_and_login(client, "bob3@example.com")
    bob_id = _id(client, bob)

    pair_id = client.post(
        "/double-buddy/invite", json={"partner_id": bob_id}, headers=alice
    ).json()["id"]

    accept = client.post(
        f"/double-buddy/{pair_id}/respond", json={"accept": True}, headers=bob
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"

    for headers in (alice, bob):
        me = client.get("/double-buddy/me", headers=headers).json()
        assert me["status"] == "accepted"
        assert me["is_incoming"] is False


def test_reject_invite_removes_it(client: TestClient) -> None:
    alice = _register_and_login(client, "alice4@example.com")
    bob = _register_and_login(client, "bob4@example.com")
    bob_id = _id(client, bob)

    pair_id = client.post(
        "/double-buddy/invite", json={"partner_id": bob_id}, headers=alice
    ).json()["id"]

    reject = client.post(
        f"/double-buddy/{pair_id}/respond", json={"accept": False}, headers=bob
    )
    assert reject.status_code == 200

    assert client.get("/double-buddy/me", headers=alice).json() is None
    assert client.get("/double-buddy/me", headers=bob).json() is None


def test_only_invitee_can_respond(client: TestClient) -> None:
    alice = _register_and_login(client, "alice5@example.com")
    bob = _register_and_login(client, "bob5@example.com")
    bob_id = _id(client, bob)

    pair_id = client.post(
        "/double-buddy/invite", json={"partner_id": bob_id}, headers=alice
    ).json()["id"]

    denied = client.post(
        f"/double-buddy/{pair_id}/respond", json={"accept": True}, headers=alice
    )
    assert denied.status_code == 404


def test_cannot_invite_when_already_paired(client: TestClient) -> None:
    alice = _register_and_login(client, "alice6@example.com")
    bob = _register_and_login(client, "bob6@example.com")
    charlie = _register_and_login(client, "charlie6@example.com")
    bob_id = _id(client, bob)
    charlie_id = _id(client, charlie)

    pair_id = client.post(
        "/double-buddy/invite", json={"partner_id": bob_id}, headers=alice
    ).json()["id"]
    client.post(f"/double-buddy/{pair_id}/respond", json={"accept": True}, headers=bob)

    blocked = client.post(
        "/double-buddy/invite", json={"partner_id": charlie_id}, headers=alice
    )
    assert blocked.status_code == 409


def test_invite_self_returns_400(client: TestClient, auth_headers: dict[str, str]) -> None:
    me_id = client.get("/users/me", headers=auth_headers).json()["id"]
    response = client.post("/double-buddy/invite", json={"partner_id": me_id}, headers=auth_headers)
    assert response.status_code == 400


def test_invite_nonexistent_user_returns_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/double-buddy/invite", json={"partner_id": 99999}, headers=auth_headers)
    assert response.status_code == 404


def test_reinvite_replaces_previous_pending_invite(client: TestClient) -> None:
    alice = _register_and_login(client, "alice7@example.com")
    bob = _register_and_login(client, "bob7@example.com")
    charlie = _register_and_login(client, "charlie7@example.com")
    bob_id = _id(client, bob)
    charlie_id = _id(client, charlie)

    client.post("/double-buddy/invite", json={"partner_id": bob_id}, headers=alice)
    client.post("/double-buddy/invite", json={"partner_id": charlie_id}, headers=alice)

    assert client.get("/double-buddy/me", headers=alice).json()["user_2_id"] == charlie_id
    assert client.get("/double-buddy/me", headers=bob).json() is None


def test_disband_removes_pair(client: TestClient) -> None:
    alice = _register_and_login(client, "alice8@example.com")
    bob = _register_and_login(client, "bob8@example.com")
    bob_id = _id(client, bob)

    pair_id = client.post(
        "/double-buddy/invite", json={"partner_id": bob_id}, headers=alice
    ).json()["id"]
    client.post(f"/double-buddy/{pair_id}/respond", json={"accept": True}, headers=bob)

    disband = client.delete("/double-buddy/disband", headers=alice)
    assert disband.status_code == 204

    assert client.get("/double-buddy/me", headers=alice).json() is None
    assert client.get("/double-buddy/me", headers=bob).json() is None
