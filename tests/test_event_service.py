from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.schemas.event import EventCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.event_service import create_event, list_events


def _create_user(db_session: Session) -> int:
    user = register_user(
        db_session,
        UserCreate(email="ada@example.com", password="s3cret-pass", display_name="Ada"),
    )
    return user.id


def _event_data(**overrides: object) -> EventCreate:
    defaults: dict[str, object] = {
        "title": "Trail run",
        "category": "sports",
        "location_name": "Central Park",
        "latitude": 40.0,
        "longitude": -73.0,
        "starts_at": datetime.utcnow() + timedelta(days=1),
    }
    defaults.update(overrides)
    return EventCreate(**defaults)


def test_list_events_filters_by_category(db_session: Session) -> None:
    creator_id = _create_user(db_session)
    create_event(db_session, _event_data(category="sports"), creator_id)
    create_event(db_session, _event_data(category="music", title="Concert"), creator_id)

    results = list_events(db_session, category="sports")

    assert [event.category for event in results] == ["sports"]


def test_list_events_excludes_past_events_by_default(db_session: Session) -> None:
    creator_id = _create_user(db_session)
    create_event(
        db_session,
        _event_data(title="Yesterday", starts_at=datetime.utcnow() - timedelta(days=1)),
        creator_id,
    )
    create_event(
        db_session,
        _event_data(title="Tomorrow", starts_at=datetime.utcnow() + timedelta(days=1)),
        creator_id,
    )

    results = list_events(db_session)

    assert [event.title for event in results] == ["Tomorrow"]


def test_list_events_can_include_past_events(db_session: Session) -> None:
    creator_id = _create_user(db_session)
    create_event(
        db_session,
        _event_data(title="Yesterday", starts_at=datetime.utcnow() - timedelta(days=1)),
        creator_id,
    )

    results = list_events(db_session, upcoming_only=False)

    assert len(results) == 1
