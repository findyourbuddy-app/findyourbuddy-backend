import logging
import re

from fastapi.testclient import TestClient

from app.core.sms import get_sms_sender
from app.main import app


def _register(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "ada@example.com",
            "password": "s3cret-pass",
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
            "password": "s3cret-pass",
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
            "password": "other-pass",
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
            "password": "other-pass",
            "display_name": "Other",
            "accepted_terms": True,
            "phone_number": "5000000001",
        },
    )

    assert response.status_code == 409


def test_register_auto_verifies_phone_when_no_sms_provider_configured(client: TestClient) -> None:
    # No real SMS provider is wired up in tests (LoggingSmsSender), so the
    # user can never receive the code -- registration must not trap them
    # behind an unreachable verification screen.
    response = client.post(
        "/auth/register",
        json={
            "email": "ada@example.com",
            "password": "s3cret-pass",
            "display_name": "Ada",
            "accepted_terms": True,
            "phone_number": "5000000001",
        },
    )

    assert response.json()["phone_verified"] is True


class _FakeRealSmsSender:
    """Stands in for a configured provider (e.g. Netgsm) so the manual
    verify-code flow can still be exercised in tests."""

    def send(self, user, code: str) -> None:
        logging.getLogger("app.core.sms").info(
            "phone verification code phone=%s code=%s", user.phone_number, code
        )


def test_verify_phone_with_correct_code_succeeds(client: TestClient, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.core.sms")
    app.dependency_overrides[get_sms_sender] = lambda: _FakeRealSmsSender()
    try:
        _register(client)
        login = client.post("/auth/login", json={"email": "ada@example.com", "password": "s3cret-pass"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/users/me", headers=headers).json()["phone_verified"] is False

        match = re.search(r"code=(\d{6})", caplog.text)
        assert match is not None
        code = match.group(1)

        response = client.post("/auth/phone/verify", headers=headers, json={"code": code})

        assert response.status_code == 204
        assert client.get("/users/me", headers=headers).json()["phone_verified"] is True
    finally:
        del app.dependency_overrides[get_sms_sender]


def test_verify_phone_with_wrong_code_fails(client: TestClient) -> None:
    app.dependency_overrides[get_sms_sender] = lambda: _FakeRealSmsSender()
    try:
        _register(client)
        login = client.post("/auth/login", json={"email": "ada@example.com", "password": "s3cret-pass"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        response = client.post("/auth/phone/verify", headers=headers, json={"code": "000000"})

        assert response.status_code == 400
    finally:
        del app.dependency_overrides[get_sms_sender]


def test_resend_phone_code_requires_authentication(client: TestClient) -> None:
    response = client.post("/auth/phone/resend")

    assert response.status_code == 401


def test_login_returns_access_token(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "s3cret-pass"}
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


def test_password_reset_request_returns_204_for_known_and_unknown_email(
    client: TestClient,
) -> None:
    _register(client)

    known = client.post("/auth/password-reset/request", json={"email": "ada@example.com"})
    unknown = client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})

    assert known.status_code == 204
    assert unknown.status_code == 204


def test_password_reset_confirm_rejects_invalid_token(client: TestClient) -> None:
    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": "new-secret-pass"},
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
        json={"token": token, "new_password": "new-secret-pass"},
    )
    assert confirm.status_code == 204

    login = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "new-secret-pass"}
    )
    assert login.status_code == 200


def test_change_password_allows_login_with_new_password(client: TestClient) -> None:
    _register(client)
    login = client.post("/auth/login", json={"email": "ada@example.com", "password": "s3cret-pass"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "s3cret-pass", "new_password": "new-secret-pass"},
    )
    assert response.status_code == 204

    old_login = client.post("/auth/login", json={"email": "ada@example.com", "password": "s3cret-pass"})
    assert old_login.status_code == 401

    new_login = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "new-secret-pass"}
    )
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(client: TestClient) -> None:
    _register(client)
    login = client.post("/auth/login", json={"email": "ada@example.com", "password": "s3cret-pass"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "wrong-pass", "new_password": "new-secret-pass"},
    )

    assert response.status_code == 400


def test_change_password_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/auth/change-password",
        json={"current_password": "s3cret-pass", "new_password": "new-secret-pass"},
    )

    assert response.status_code == 401
