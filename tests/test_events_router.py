import io
from datetime import datetime, timedelta

import cv2
import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.services.media_service import get_media_storage


def _qr_png_bytes(text: str) -> bytes:
    encoder = cv2.QRCodeEncoder.create()
    matrix = encoder.encode(text)
    scale = 10
    big = cv2.resize(
        matrix, (matrix.shape[1] * scale, matrix.shape[0] * scale), interpolation=cv2.INTER_NEAREST
    )
    padded = cv2.copyMakeBorder(big, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    ok, buf = cv2.imencode(".png", padded)
    return buf.tobytes()


def _plain_png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), color="blue").save(buffer, format="PNG")
    return buffer.getvalue()


def _event_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Trail run",
        "category": "sports",
        "location_name": "Central Park",
        "latitude": 40.0,
        "longitude": -73.0,
        "starts_at": (datetime.utcnow() + timedelta(days=1)).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_list_events_requires_auth(client: TestClient) -> None:
    response = client.get("/events/")

    assert response.status_code == 401


def test_create_and_list_event(client: TestClient, auth_headers: dict[str, str]) -> None:
    create_response = client.post("/events/", headers=auth_headers, json=_event_payload())
    assert create_response.status_code == 201

    list_response = client.get("/events/", headers=auth_headers)
    assert list_response.status_code == 200
    titles = [event["title"] for event in list_response.json()]
    assert "Trail run" in titles


def test_get_event_returns_404_for_unknown_id(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.get("/events/999", headers=auth_headers)

    assert response.status_code == 404


def test_get_event_returns_created_event(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_response = client.post("/events/", headers=auth_headers, json=_event_payload())
    event_id = create_response.json()["id"]

    response = client.get(f"/events/{event_id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == event_id


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "s3cret-pass", "display_name": email, "accepted_terms": True, "phone_number": f"5{abs(hash(email)) % 10**9:09d}"},
    )
    response = client.post("/auth/login", json={"email": email, "password": "s3cret-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_event_attendee_count_reflects_distinct_swipers(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_response = client.post("/events/", headers=auth_headers, json=_event_payload())
    event_id = create_response.json()["id"]
    assert create_response.json()["attendee_count"] == 0

    swiper_headers = _register_and_login(client, "swiper@example.com")
    target_headers = _register_and_login(client, "target@example.com")
    target_id = client.get("/users/me", headers=target_headers).json()["id"]
    client.post(
        "/swipes/",
        headers=swiper_headers,
        json={"target_id": target_id, "event_id": event_id, "direction": "like"},
    )

    detail_response = client.get(f"/events/{event_id}", headers=auth_headers)
    assert detail_response.json()["attendee_count"] == 1

    list_response = client.get("/events/", headers=auth_headers)
    listed = next(e for e in list_response.json() if e["id"] == event_id)
    assert listed["attendee_count"] == 1


def test_attend_event_marks_user_as_attending(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_response = client.post("/events/", headers=auth_headers, json=_event_payload())
    event_id = create_response.json()["id"]

    attend_response = client.post(f"/events/{event_id}/attend", headers=auth_headers)

    assert attend_response.status_code == 200
    assert attend_response.json()["is_attending"] is True
    assert attend_response.json()["attendee_count"] == 1

    detail_response = client.get(f"/events/{event_id}", headers=auth_headers)
    assert detail_response.json()["is_attending"] is True


def test_attend_event_is_idempotent(client: TestClient, auth_headers: dict[str, str]) -> None:
    create_response = client.post("/events/", headers=auth_headers, json=_event_payload())
    event_id = create_response.json()["id"]

    client.post(f"/events/{event_id}/attend", headers=auth_headers)
    second_response = client.post(f"/events/{event_id}/attend", headers=auth_headers)

    assert second_response.json()["attendee_count"] == 1


def test_attend_event_returns_404_for_unknown_event(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/events/999/attend", headers=auth_headers)

    assert response.status_code == 404


def test_check_in_confirms_attendance_when_nearby(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_response = client.post(
        "/events/",
        headers=auth_headers,
        json=_event_payload(
            latitude=41.0,
            longitude=29.0,
            starts_at=(datetime.utcnow() + timedelta(minutes=5)).isoformat(),
        ),
    )
    event_id = create_response.json()["id"]

    response = client.post(
        f"/events/{event_id}/check-in",
        headers=auth_headers,
        json={"latitude": 41.001, "longitude": 29.001},
    )

    assert response.status_code == 200
    assert response.json()["is_checked_in"] is True


def test_check_in_rejects_when_too_far(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_response = client.post(
        "/events/",
        headers=auth_headers,
        json=_event_payload(
            latitude=41.0,
            longitude=29.0,
            starts_at=(datetime.utcnow() + timedelta(minutes=5)).isoformat(),
        ),
    )
    event_id = create_response.json()["id"]

    response = client.post(
        f"/events/{event_id}/check-in",
        headers=auth_headers,
        json={"latitude": 48.85, "longitude": 2.35},
    )

    assert response.status_code == 400


def test_create_event_returns_429_after_daily_limit(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.post("/events/", headers=auth_headers, json=_event_payload(title="One"))
    client.post("/events/", headers=auth_headers, json=_event_payload(title="Two"))

    response = client.post("/events/", headers=auth_headers, json=_event_payload(title="Three"))

    assert response.status_code == 429


def test_upload_ticket_with_readable_qr_verifies_attendance(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    get_media_storage.cache_clear()

    create_response = client.post(
        "/events/", headers=auth_headers, json=_event_payload(is_paid=True)
    )
    event_id = create_response.json()["id"]

    response = client.post(
        f"/events/{event_id}/ticket",
        headers=auth_headers,
        files={"file": ("ticket.png", io.BytesIO(_qr_png_bytes("TICKET-XYZ")), "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["is_ticket_verified"] is True

    get_settings.cache_clear()
    get_media_storage.cache_clear()


def test_upload_ticket_with_unreadable_image_returns_422(
    client: TestClient, auth_headers: dict[str, str], tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    get_settings.cache_clear()
    get_media_storage.cache_clear()

    create_response = client.post(
        "/events/", headers=auth_headers, json=_event_payload(is_paid=True)
    )
    event_id = create_response.json()["id"]

    response = client.post(
        f"/events/{event_id}/ticket",
        headers=auth_headers,
        files={"file": ("blank.png", io.BytesIO(_plain_png_bytes()), "image/png")},
    )

    assert response.status_code == 422

    get_settings.cache_clear()
    get_media_storage.cache_clear()


def test_list_attending_events_returns_only_joined_events(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    joined_response = client.post("/events/", headers=auth_headers, json=_event_payload(title="Joined"))
    joined_id = joined_response.json()["id"]
    client.post("/events/", headers=auth_headers, json=_event_payload(title="Not Joined"))

    client.post(f"/events/{joined_id}/attend", headers=auth_headers)

    response = client.get("/events/me/attending", headers=auth_headers)

    assert response.status_code == 200
    titles = [event["title"] for event in response.json()]
    assert titles == ["Joined"]


def test_read_event_is_attending_false_for_non_attendee(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    create_response = client.post("/events/", headers=auth_headers, json=_event_payload())
    event_id = create_response.json()["id"]

    response = client.get(f"/events/{event_id}", headers=auth_headers)

    assert response.json()["is_attending"] is False
