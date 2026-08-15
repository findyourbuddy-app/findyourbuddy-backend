import io
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings


def _valid_png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


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


def test_create_swipe_returns_201(client: TestClient) -> None:
    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_headers = _register_and_login(client, "target@example.com")
    target_id = client.get("/users/me", headers=target_headers).json()["id"]
    event_id = _create_event(client, swiper_headers)

    response = client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_id, "event_id": event_id, "direction": "like"},
    )

    assert response.status_code == 201


def test_create_swipe_omits_match_when_not_mutual(client: TestClient) -> None:
    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_headers = _register_and_login(client, "target@example.com")
    target_id = client.get("/users/me", headers=target_headers).json()["id"]
    event_id = _create_event(client, swiper_headers)

    response = client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_id, "event_id": event_id, "direction": "like"},
    )

    body = response.json()
    assert body["match_id"] is None
    assert body["matched_user"] is None


def test_create_swipe_returns_match_details_on_mutual_like(client: TestClient) -> None:
    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_headers = _register_and_login(client, "target@example.com")
    swiper_id = client.get("/users/me", headers=swiper_headers).json()["id"]
    target_id = client.get("/users/me", headers=target_headers).json()["id"]
    event_id = _create_event(client, swiper_headers)

    client.post(
        "/swipes/",
        headers=target_headers,
        json={"target_id": swiper_id, "event_id": event_id, "direction": "like"},
    )
    response = client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_id, "event_id": event_id, "direction": "like"},
    )

    body = response.json()
    assert body["match_id"] is not None
    assert body["matched_user"]["id"] == target_id
    assert body["matched_user"]["display_name"] == "target@example.com"


def test_create_swipe_rejects_duplicate(client: TestClient) -> None:
    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_headers = _register_and_login(client, "target@example.com")
    target_id = client.get("/users/me", headers=target_headers).json()["id"]
    event_id = _create_event(client, swiper_headers)
    payload = {"target_id": target_id, "event_id": event_id, "direction": "like"}

    client.post("/swipes/", headers=swiper_headers, json=payload)
    response = client.post("/swipes/", headers=swiper_headers, json=payload)

    assert response.status_code == 409


def test_create_swipe_returns_429_when_daily_limit_reached(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("DAILY_SWIPE_LIMIT", "1")
    get_settings.cache_clear()

    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_1 = _register_and_login(client, "target1@example.com")
    target_2_id = client.get(
        "/users/me", headers=_register_and_login(client, "target2@example.com")
    ).json()["id"]
    target_1_id = client.get("/users/me", headers=target_1).json()["id"]
    event_id = _create_event(client, swiper_headers)

    client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_1_id, "event_id": event_id, "direction": "like"},
    )
    response = client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_2_id, "event_id": event_id, "direction": "like"},
    )

    assert response.status_code == 429
    get_settings.cache_clear()


def test_create_swipe_bypasses_daily_limit_for_premium_user(
    client: TestClient, db_session, monkeypatch
) -> None:
    from app.services.subscription_service import grant_premium

    monkeypatch.setenv("DAILY_SWIPE_LIMIT", "1")
    get_settings.cache_clear()

    swiper_headers = _register_and_login(client, "swiper@example.com")
    swiper_id = client.get("/users/me", headers=swiper_headers).json()["id"]
    grant_premium(db_session, swiper_id)
    target_1_id = client.get(
        "/users/me", headers=_register_and_login(client, "target1@example.com")
    ).json()["id"]
    target_2_id = client.get(
        "/users/me", headers=_register_and_login(client, "target2@example.com")
    ).json()["id"]
    event_id = _create_event(client, swiper_headers)

    client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_1_id, "event_id": event_id, "direction": "like"},
    )
    response = client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_2_id, "event_id": event_id, "direction": "like"},
    )

    assert response.status_code == 201
    get_settings.cache_clear()


def test_get_candidates_excludes_self(client: TestClient) -> None:
    swiper_headers = _register_and_login(client, "swiper@example.com")
    _register_and_login(client, "other@example.com")
    event_id = _create_event(client, swiper_headers)
    swiper_id = client.get("/users/me", headers=swiper_headers).json()["id"]

    response = client.get(
        "/swipes/candidates", headers=swiper_headers, params={"event_id": event_id}
    )

    assert response.status_code == 200
    candidate_ids = [user["id"] for user in response.json()]
    assert swiper_id not in candidate_ids


def test_get_likes_received_does_not_require_premium(client: TestClient) -> None:
    user_headers = _register_and_login(client, "user@example.com")
    event_id = _create_event(client, user_headers)

    response = client.get(
        "/swipes/likes-received", headers=user_headers, params={"event_id": event_id}
    )

    assert response.status_code == 200


def test_get_likes_received_returns_unreciprocated_likers(
    client: TestClient, db_session
) -> None:
    from app.services.subscription_service import grant_premium

    user_headers = _register_and_login(client, "user@example.com")
    liker_headers = _register_and_login(client, "liker@example.com")
    user_id = client.get("/users/me", headers=user_headers).json()["id"]
    liker_id = client.get("/users/me", headers=liker_headers).json()["id"]
    event_id = _create_event(client, user_headers)
    grant_premium(db_session, user_id)

    client.post(
        "/swipes/",
        headers=liker_headers,
        json={"target_id": user_id, "event_id": event_id, "direction": "like"},
    )

    response = client.get(
        "/swipes/likes-received", headers=user_headers, params={"event_id": event_id}
    )

    assert response.status_code == 200
    liker_ids = [item["user"]["id"] for item in response.json()]
    assert liker_ids == [liker_id]


def test_get_candidates_includes_gallery_photos(
    client: TestClient, tmp_path, monkeypatch
) -> None:
    from app.services.media_service import get_media_storage

    get_settings.cache_clear()
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    get_media_storage.cache_clear()

    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_headers = _register_and_login(client, "target@example.com")
    event_id = _create_event(client, swiper_headers)

    client.post(
        "/users/me/photos",
        headers=target_headers,
        files={"file": ("gallery1.png", io.BytesIO(_valid_png_bytes()), "image/png")},
    )

    response = client.get(
        "/swipes/candidates", headers=swiper_headers, params={"event_id": event_id}
    )

    assert response.status_code == 200
    candidate = next(u for u in response.json() if u["display_name"] == "target@example.com")
    assert len(candidate["photos"]) == 1

    get_settings.cache_clear()
    get_media_storage.cache_clear()


def test_get_quota_reflects_usage_for_free_user(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("DAILY_SWIPE_LIMIT", "5")
    monkeypatch.setenv("DAILY_SUPER_LIKE_LIMIT", "1")
    get_settings.cache_clear()

    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_id = client.get(
        "/users/me", headers=_register_and_login(client, "target@example.com")
    ).json()["id"]
    event_id = _create_event(client, swiper_headers)

    client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_id, "event_id": event_id, "direction": "super_like"},
    )

    response = client.get("/swipes/quota", headers=swiper_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["is_premium"] is False
    assert body["swipes_used_today"] == 1
    assert body["swipe_limit"] == 5
    assert body["super_likes_used_today"] == 1
    assert body["super_like_limit"] == 1

    get_settings.cache_clear()


def test_get_quota_has_no_swipe_limit_for_premium_user(
    client: TestClient, db_session, monkeypatch
) -> None:
    from app.services.subscription_service import grant_premium

    swiper_headers = _register_and_login(client, "swiper@example.com")
    swiper_id = client.get("/users/me", headers=swiper_headers).json()["id"]
    grant_premium(db_session, swiper_id)

    response = client.get("/swipes/quota", headers=swiper_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["is_premium"] is True
    assert body["swipe_limit"] is None
