import io
import json
from datetime import datetime, timedelta, timezone

import iyzipay
from fastapi.testclient import TestClient
from PIL import Image


def _valid_png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


def _mock_purchase_via_iyzico(
    client: TestClient, monkeypatch, user_id: int, item_type: str, quantity: int, token: str
) -> None:
    """Simulates a completed Iyzico checkout by mocking CheckoutForm.retrieve
    and hitting the callback directly -- purchases only take effect once the
    callback verifies payment, not from the checkout-session call itself."""
    dummy_body = json.dumps(
        {
            "status": "success",
            "paymentStatus": "SUCCESS",
            "conversationId": f"purchase_{item_type}_{quantity}_{user_id}_12345678",
        }
    ).encode("utf-8")

    class FakeHTTPResponse:
        @staticmethod
        def read():
            return dummy_body

    class MockRetrieve:
        @staticmethod
        def retrieve(request_data, options):
            return FakeHTTPResponse()

    monkeypatch.setattr(iyzipay, "CheckoutForm", lambda: MockRetrieve())
    response = client.post("/users/me/purchase/callback", data={"token": token})
    assert response.status_code == 200


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
    from datetime import date

    birth_date = date.today().replace(year=date.today().year - 27)
    response = client.patch(
        "/users/me",
        headers=auth_headers,
        json={
            "date_of_birth": birth_date.isoformat(),
            "bio": "Loves trails",
            "interests": ["hiking"],
        },
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
    monkeypatch.setenv("MEDIA_STORAGE_BACKEND", "local")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

    from app.services.media_service import get_media_storage

    get_media_storage.cache_clear()

    response = client.post(
        "/users/me/photo",
        headers=auth_headers,
        files={"file": ("avatar.png", io.BytesIO(_valid_png_bytes()), "image/png")},
    )

    assert response.status_code == 200
    photo_url = response.json()["photo_url"]
    assert photo_url.startswith("http://127.0.0.1:8000/media/")
    assert photo_url.endswith(".jpg")

    get_settings.cache_clear()
    get_media_storage.cache_clear()


def test_upload_profile_photo_rejects_non_image_file(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    from app.config import get_settings
    from app.services.media_service import get_media_storage

    get_settings.cache_clear()
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    get_media_storage.cache_clear()

    response = client.post(
        "/users/me/photo",
        headers=auth_headers,
        files={"file": ("not-an-image.png", io.BytesIO(b"not actually an image"), "image/png")},
    )

    assert response.status_code == 422

    get_settings.cache_clear()
    get_media_storage.cache_clear()


def test_upload_profile_photo_rejects_oversized_file(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    from app.config import get_settings
    from app.services.media_service import get_media_storage

    get_settings.cache_clear()
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    get_media_storage.cache_clear()

    oversized = b"\x00" * (8 * 1024 * 1024 + 1)
    response = client.post(
        "/users/me/photo",
        headers=auth_headers,
        files={"file": ("huge.png", io.BytesIO(oversized), "image/png")},
    )

    assert response.status_code == 413

    get_settings.cache_clear()
    get_media_storage.cache_clear()


def test_upload_and_list_gallery_photos(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    from app.config import get_settings
    from app.services.media_service import get_media_storage

    get_settings.cache_clear()
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    get_media_storage.cache_clear()

    upload_response = client.post(
        "/users/me/photos",
        headers=auth_headers,
        files={"file": ("gallery1.png", io.BytesIO(_valid_png_bytes()), "image/png")},
    )

    assert upload_response.status_code == 201
    assert upload_response.json()["position"] == 0

    list_response = client.get("/users/me/photos", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_settings.cache_clear()
    get_media_storage.cache_clear()


def test_gallery_photo_upload_rejects_beyond_limit(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    from app.config import get_settings
    from app.services.media_service import get_media_storage

    get_settings.cache_clear()
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    get_media_storage.cache_clear()

    for _ in range(6):
        response = client.post(
            "/users/me/photos",
            headers=auth_headers,
            files={"file": ("gallery.png", io.BytesIO(_valid_png_bytes()), "image/png")},
        )
        assert response.status_code == 201

    overflow_response = client.post(
        "/users/me/photos",
        headers=auth_headers,
        files={"file": ("overflow.png", io.BytesIO(_valid_png_bytes()), "image/png")},
    )

    assert overflow_response.status_code == 409

    get_settings.cache_clear()
    get_media_storage.cache_clear()


def test_delete_gallery_photo(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    from app.config import get_settings
    from app.services.media_service import get_media_storage

    get_settings.cache_clear()
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    get_media_storage.cache_clear()

    upload_response = client.post(
        "/users/me/photos",
        headers=auth_headers,
        files={"file": ("gallery1.png", io.BytesIO(_valid_png_bytes()), "image/png")},
    )
    photo_id = upload_response.json()["id"]

    delete_response = client.delete(f"/users/me/photos/{photo_id}", headers=auth_headers)
    assert delete_response.status_code == 204
    assert client.get("/users/me/photos", headers=auth_headers).json() == []

    get_settings.cache_clear()
    get_media_storage.cache_clear()


def test_delete_unknown_gallery_photo_returns_404(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.delete("/users/me/photos/999", headers=auth_headers)

    assert response.status_code == 404


def test_export_current_user_data_includes_own_records(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    from datetime import datetime, timedelta

    client.post(
        "/events/",
        headers=auth_headers,
        json={
            "title": "Trail run",
            "category": "sports",
            "location_name": "Central Park",
            "latitude": 40.0,
            "longitude": -73.0,
            "starts_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )

    response = client.get("/users/me/export", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["email"] == "ada@example.com"
    assert len(body["events_created"]) == 1
    assert body["events_created"][0]["title"] == "Trail run"
    assert body["matches"] == []
    assert body["messages_sent"] == []
    # Event creation approval sends the creator a notification -- see
    # llm_moderation_service.send_event_approval_email.
    assert len(body["notifications"]) == 1
    assert "onayland" in body["notifications"][0]["body"]
    assert body["bookmarks"] == []
    assert "exported_at" in body


def test_export_requires_auth(client: TestClient) -> None:
    response = client.get("/users/me/export")

    assert response.status_code == 401


def test_delete_current_user_returns_204(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.delete("/users/me", headers=auth_headers)

    assert response.status_code == 204


def test_delete_current_user_invalidates_token(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.delete("/users/me", headers=auth_headers)

    response = client.get("/users/me", headers=auth_headers)

    assert response.status_code == 401


def test_register_device_token_returns_201(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/users/me/device-tokens",
        headers=auth_headers,
        json={"token": "ExponentPushToken[abc]"},
    )

    assert response.status_code == 201
    assert response.json()["token"] == "ExponentPushToken[abc]"


def test_unregister_device_token_returns_204(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.post(
        "/users/me/device-tokens",
        headers=auth_headers,
        json={"token": "ExponentPushToken[abc]"},
    )

    response = client.delete(
        "/users/me/device-tokens/ExponentPushToken[abc]", headers=auth_headers
    )

    assert response.status_code == 204


def test_boost_user_without_credits_returns_403(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/users/me/boost", headers=auth_headers)
    assert response.status_code == 403


def test_purchase_items_credits_balance(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    user_id = client.get("/users/me", headers=auth_headers).json()["id"]

    _mock_purchase_via_iyzico(client, monkeypatch, user_id, "boost", 2, token="tok-boost")
    response = client.get("/users/me", headers=auth_headers)
    assert response.json()["boosts_balance"] == 2

    _mock_purchase_via_iyzico(client, monkeypatch, user_id, "super_likes", 5, token="tok-super")
    response = client.get("/users/me", headers=auth_headers)
    assert response.json()["extra_super_likes"] == 5


def test_boost_user_with_credits_succeeds(
    client: TestClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    user_id = client.get("/users/me", headers=auth_headers).json()["id"]

    # First buy a boost
    _mock_purchase_via_iyzico(client, monkeypatch, user_id, "boost", 1, token="tok-boost-2")

    # Boost profile
    response = client.post("/users/me/boost", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["boosts_balance"] == 0
    assert body["boosted_until"] is not None
