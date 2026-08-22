import logging
import re

from fastapi.testclient import TestClient

from app.main import app


def _register(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "ada@example.com",
            "password": "S3cret-pass",
            "display_name": "Ada",
            "accepted_terms": True,
            "phone_number": "5000000001",
        },
    )
    assert response.status_code == 201


def test_register_returns_created_user(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "ada@example.com",
            "password": "S3cret-pass",
            "display_name": "Ada",
            "accepted_terms": True,
            "phone_number": "5000000001",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/auth/register",
        json={
            "email": "ada@example.com",
            "password": "Other-pass1",
            "display_name": "Ada2",
            "accepted_terms": True,
            "phone_number": "5000000002",
        },
    )

    assert response.status_code == 409


def test_register_rejects_duplicate_phone_number(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/auth/register",
        json={
            "email": "other@example.com",
            "password": "Other-pass1",
            "display_name": "Other",
            "accepted_terms": True,
            "phone_number": "5000000001",
        },
    )

    assert response.status_code == 409


def test_login_returns_access_token(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "S3cret-pass"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_rejects_wrong_password(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "wrong-pass"}
    )

    assert response.status_code == 401


def test_password_reset_request_returns_200_for_any_email(
    client: TestClient,
) -> None:
    _register(client)

    known = client.post("/auth/password-reset/request", json={"email": "ada@example.com"})
    unknown = client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})

    # Both return 200 to prevent email enumeration
    assert known.status_code == 200
    assert unknown.status_code == 200
    assert "reset_code" not in known.json()
    assert "message" in known.json()


def test_password_reset_confirm_rejects_invalid_token(client: TestClient) -> None:
    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": "NewSecret1!"},
    )

    assert response.status_code == 400


def test_password_reset_confirm_allows_login_with_new_password(
    client: TestClient, caplog
) -> None:
    _register(client)

    caplog.set_level(logging.INFO, logger="app.core.password_reset")
    client.post("/auth/password-reset/request", json={"email": "ada@example.com"})
    match = re.search(r"token=(\S+)", caplog.text)
    assert match is not None
    token = match.group(1)

    confirm = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": "NewSecret1!"},
    )
    assert confirm.status_code == 204

    login = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "NewSecret1!"}
    )
    assert login.status_code == 200


def test_change_password_allows_login_with_new_password(client: TestClient) -> None:
    _register(client)
    login = client.post("/auth/login", json={"email": "ada@example.com", "password": "S3cret-pass"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "S3cret-pass", "new_password": "NewSecret1!"},
    )
    assert response.status_code == 204

    old_login = client.post("/auth/login", json={"email": "ada@example.com", "password": "S3cret-pass"})
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "NewSecret1!"}
    )
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(client: TestClient) -> None:
    _register(client)
    login = client.post("/auth/login", json={"email": "ada@example.com", "password": "S3cret-pass"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "wrong-pass", "new_password": "NewSecret1!"},
    )

    assert response.status_code == 400


def test_change_password_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/auth/change-password",
        json={"current_password": "S3cret-pass", "new_password": "NewSecret1!"},
    )

    assert response.status_code == 401


def test_register_rejects_weak_password_no_uppercase(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "weak@example.com",
            "password": "weakpass1",
            "display_name": "Weak",
            "accepted_terms": True,
        },
    )
    assert response.status_code == 422


def test_register_rejects_weak_password_too_short(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "weak@example.com",
            "password": "Short1",
            "display_name": "Weak",
            "accepted_terms": True,
        },
    )
    assert response.status_code == 422


def test_register_rejects_weak_password_no_digit(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "weak@example.com",
            "password": "WeakPassword",
            "display_name": "Weak",
            "accepted_terms": True,
        },
    )
    assert response.status_code == 422
