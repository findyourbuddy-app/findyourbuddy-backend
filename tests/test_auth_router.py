from fastapi.testclient import TestClient


def _register(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "ada@example.com", "password": "s3cret-pass", "display_name": "Ada"},
    )
    assert response.status_code == 201


def test_register_returns_created_user(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={"email": "ada@example.com", "password": "s3cret-pass", "display_name": "Ada"},
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
        json={"email": "ada@example.com", "password": "other-pass", "display_name": "Ada2"},
    )

    assert response.status_code == 409


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
