from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.event import Event
from app.models.user import User


def _event_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Trail run",
        "category": "sports",
        "location_name": "Central Park",
        "latitude": 40.0,
        "longitude": -73.0,
        "starts_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
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
        json={"email": email, "password": "S3cret-pass", "display_name": email, "accepted_terms": True, "phone_number": f"5{abs(hash(email)) % 10**9:09d}"},
    )
    response = client.post("/auth/login", json={"email": email, "password": "S3cret-pass"})
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
            starts_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
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
            starts_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        ),
    )
    event_id = create_response.json()["id"]

    response = client.post(
        f"/events/{event_id}/check-in",
        headers=auth_headers,
        json={"latitude": 48.85, "longitude": 2.35},
    )

    assert response.status_code == 400


def test_create_event_returns_429_after_weekly_limit(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    client.post("/events/", headers=auth_headers, json=_event_payload(title="One"))
    client.post("/events/", headers=auth_headers, json=_event_payload(title="Two"))
    client.post("/events/", headers=auth_headers, json=_event_payload(title="Three"))

    response = client.post("/events/", headers=auth_headers, json=_event_payload(title="Four"))

    assert response.status_code == 429


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


def test_create_event_sanitizes_xss_description(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    xss_payload = _event_payload(
        title="XSS Test Event",
        description="Great event <script>alert(1)</script> Join us!",
    )
    create_response = client.post("/events/", headers=auth_headers, json=xss_payload)
    assert create_response.status_code == 201
    event_id = create_response.json()["id"]

    get_response = client.get(f"/events/{event_id}", headers=auth_headers)
    assert get_response.status_code == 200
    cleaned_desc = get_response.json()["description"]
    assert "<script>" not in cleaned_desc
    assert "</script>" not in cleaned_desc
    assert "alert(1)" in cleaned_desc


def test_rate_event_and_impact_trust_score(
    client: TestClient, auth_headers: dict[str, str], db_session: Session
) -> None:
    creator = User(
        email="eventcreator@example.com",
        hashed_password="hash",
        display_name="Creator User",
        referral_code="CREATOR123",
        phone_number="+905550000000",
        trust_score=50,
    )
    db_session.add(creator)
    db_session.commit()
    db_session.refresh(creator)

    event = Event(
        title="Test Creator Event",
        category="coffee",
        location_name="Istanbul",
        latitude=41.0,
        longitude=28.9,
        starts_at=datetime.now(timezone.utc),
        creator_id=creator.id,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    response = client.post(
        f"/events/{event.id}/rate",
        headers=auth_headers,
        json={"rating": 5, "comment": "Awesome event!"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    db_session.refresh(creator)
    assert creator.trust_score == 53


