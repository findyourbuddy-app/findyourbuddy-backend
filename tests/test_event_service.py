from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.bookmark import Bookmark
from app.models.swipe import SwipeDirection
from app.schemas.event import EventCreate
from app.schemas.swipe import SwipeCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.bookmark_service import create_bookmark
from app.services.event_service import create_event, delete_expired_events, list_events
from app.services.matching_service import try_create_match
from app.services.swipe_service import record_swipe


def _create_user(db_session: Session, email: str = "ada@example.com") -> int:
    user = register_user(
        db_session,
        UserCreate(email=email, password="s3cret-pass", display_name=email, accepted_terms=True),
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


def test_list_events_respects_skip_and_limit(db_session: Session) -> None:
    creator_id = _create_user(db_session)
    for i in range(5):
        create_event(
            db_session,
            _event_data(title=f"Event {i}", starts_at=datetime.utcnow() + timedelta(days=i + 1)),
            creator_id,
        )

    results = list_events(db_session, skip=1, limit=2)

    assert [event.title for event in results] == ["Event 1", "Event 2"]


def test_list_events_can_include_past_events(db_session: Session) -> None:
    creator_id = _create_user(db_session)
    create_event(
        db_session,
        _event_data(title="Yesterday", starts_at=datetime.utcnow() - timedelta(days=1)),
        creator_id,
    )

    results = list_events(db_session, upcoming_only=False)

    assert len(results) == 1


def test_delete_expired_events_removes_old_unmatched_events(db_session: Session) -> None:
    creator_id = _create_user(db_session)
    old_event = create_event(
        db_session,
        _event_data(title="Old", starts_at=datetime.utcnow() - timedelta(days=40)),
        creator_id,
    )
    create_event(
        db_session,
        _event_data(title="Recent", starts_at=datetime.utcnow() - timedelta(days=5)),
        creator_id,
    )

    deleted_count = delete_expired_events(db_session, retention_days=30)

    assert deleted_count == 1
    remaining_titles = {event.title for event in list_events(db_session, upcoming_only=False)}
    assert remaining_titles == {"Recent"}
    assert old_event.id not in {event.id for event in list_events(db_session, upcoming_only=False)}


def test_delete_expired_events_also_removes_related_swipes_and_bookmarks(
    db_session: Session,
) -> None:
    creator_id = _create_user(db_session, "creator@example.com")
    target_id = _create_user(db_session, "target@example.com")
    event = create_event(
        db_session,
        _event_data(title="Old", starts_at=datetime.utcnow() - timedelta(days=40)),
        creator_id,
    )
    record_swipe(
        db_session,
        creator_id,
        SwipeCreate(target_id=target_id, event_id=event.id, direction=SwipeDirection.PASS),
    )
    create_bookmark(db_session, creator_id, event.id)

    delete_expired_events(db_session, retention_days=30)

    assert db_session.query(Bookmark).filter(Bookmark.event_id == event.id).count() == 0


def test_delete_expired_events_preserves_events_with_a_match(db_session: Session) -> None:
    creator_id = _create_user(db_session, "creator@example.com")
    target_id = _create_user(db_session, "target@example.com")
    event = create_event(
        db_session,
        _event_data(title="Old but matched", starts_at=datetime.utcnow() - timedelta(days=40)),
        creator_id,
    )
    record_swipe(
        db_session,
        creator_id,
        SwipeCreate(target_id=target_id, event_id=event.id, direction=SwipeDirection.LIKE),
    )
    record_swipe(
        db_session,
        target_id,
        SwipeCreate(target_id=creator_id, event_id=event.id, direction=SwipeDirection.LIKE),
    )
    try_create_match(db_session, target_id, creator_id, event.id)

    deleted_count = delete_expired_events(db_session, retention_days=30)

    assert deleted_count == 0
    assert event.id in {e.id for e in list_events(db_session, upcoming_only=False)}
