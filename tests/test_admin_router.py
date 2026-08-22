from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "S3cret-pass", "display_name": email, "accepted_terms": True, "phone_number": f"5{abs(hash(email)) % 10**9:09d}"},
    )
    response = client.post("/auth/login", json={"email": email, "password": "S3cret-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_staff(db_session: Session, user_id: int) -> None:
    staff_user = db_session.get(User, user_id)
    staff_user.is_staff = True
    db_session.commit()


def test_non_staff_cannot_list_users(client: TestClient) -> None:
    headers = _register_and_login(client, "a@example.com")

    response = client.get("/admin/users", headers=headers)

    assert response.status_code == 403


def test_staff_can_list_users(client: TestClient, db_session: Session) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    _register_and_login(client, "b@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    _make_staff(db_session, a_id)

    response = client.get("/admin/users", headers=a_headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_staff_can_deactivate_a_user(client: TestClient, db_session: Session) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    b_headers = _register_and_login(client, "b@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    b_id = client.get("/users/me", headers=b_headers).json()["id"]
    _make_staff(db_session, a_id)

    response = client.patch(
        f"/admin/users/{b_id}", headers=a_headers, json={"is_active": False}
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Deactivation blocks authenticated access (get_current_user checks is_active),
    # even though the password itself is left intact.
    assert client.get("/users/me", headers=b_headers).status_code == 401


def test_deactivating_unknown_user_returns_404(client: TestClient, db_session: Session) -> None:
    a_headers = _register_and_login(client, "a@example.com")
    a_id = client.get("/users/me", headers=a_headers).json()["id"]
    _make_staff(db_session, a_id)

    response = client.patch("/admin/users/999", headers=a_headers, json={"is_active": False})

    assert response.status_code == 404
