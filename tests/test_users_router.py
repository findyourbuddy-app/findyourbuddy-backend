import io

from fastapi.testclient import TestClient


def test_read_current_user_requires_auth(client: TestClient) -> None:
    response = client.get("/users/me")

    assert response.status_code == 401


def test_read_current_user_rejects_invalid_token(client: TestClient) -> None:
    response = client.get("/users/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_read_current_user_returns_profile(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/users/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


def test_update_current_user_applies_changes(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.patch(
        "/users/me",
        headers=auth_headers,
        json={"age": 27, "bio": "Loves trails", "interests": ["hiking"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["age"] == 27
    assert body["bio"] == "Loves trails"
    assert body["interests"] == ["hiking"]


def test_upload_profile_photo_sets_photo_url(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))

    from app.services.media_service import get_media_storage

    get_media_storage.cache_clear()

    response = client.post(
        "/users/me/photo",
        headers=auth_headers,
        files={"file": ("avatar.png", io.BytesIO(b"fake-image-bytes"), "image/png")},
    )

    assert response.status_code == 200
    photo_url = response.json()["photo_url"]
    assert photo_url.startswith("/media/")
    assert photo_url.endswith(".png")

    get_settings.cache_clear()
    get_media_storage.cache_clear()
