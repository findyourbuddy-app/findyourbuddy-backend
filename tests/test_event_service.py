from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.bookmark import Bookmark
from app.models.swipe import SwipeDirection
from app.models.user import User
from app.schemas.event import EventCreate
from app.schemas.swipe import SwipeCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.bookmark_service import create_bookmark
import pytest

from app.services.event_service import (
    EventCheckInOutsideWindowError,
    EventCheckInTooFarError,
    WeeklyEventCreationLimitExceededError,
    check_in_to_event,
    create_event,
    delete_expired_events,
    is_checked_in,
    is_ticket_verified,
    list_events,
)
from app.services.matching_service import try_create_match
from app.services.swipe_service import record_swipe


def _create_user(db_session: Session, email: str = "ada@example.com") -> int:
    user = register_user(
        db_session,
        UserCreate(email=email, password="s3cret-pass", display_name=email, accepted_terms=True, phone_number=f"5{abs(hash(email)) % 10**9:09d}"),
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
            is_premium=True,
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


def test_create_event_enforces_weekly_limit_for_free_users(db_session: Session) -> None:
    creator_id = _create_user(db_session)
    create_event(db_session, _event_data(title="One"), creator_id)
    create_event(db_session, _event_data(title="Two"), creator_id)
    create_event(db_session, _event_data(title="Three"), creator_id)

    with pytest.raises(WeeklyEventCreationLimitExceededError):
        create_event(db_session, _event_data(title="Four"), creator_id)


def test_create_event_weekly_limit_does_not_apply_to_premium(db_session: Session) -> None:
    creator_id = _create_user(db_session)
    for i in range(4):
        create_event(db_session, _event_data(title=f"Event {i}"), creator_id, is_premium=True)


def test_create_event_consumes_purchased_credit_past_weekly_limit(db_session: Session) -> None:
    creator_id = _create_user(db_session)
    creator = db_session.get(User, creator_id)
    creator.event_credits_balance = 1
    db_session.commit()
    create_event(db_session, _event_data(title="One"), creator_id)
    create_event(db_session, _event_data(title="Two"), creator_id)
    create_event(db_session, _event_data(title="Three"), creator_id)

    # The 4th creation goes past the weekly limit but should be allowed by
    # spending the purchased credit instead of raising.
    create_event(db_session, _event_data(title="Four"), creator_id)

    db_session.refresh(creator)
    assert creator.event_credits_balance == 0
    with pytest.raises(WeeklyEventCreationLimitExceededError):
        create_event(db_session, _event_data(title="Five"), creator_id)


def test_check_in_succeeds_near_event_during_window(db_session: Session) -> None:
    creator_id = _create_user(db_session, "creator@example.com")
    attendee_id = _create_user(db_session, "attendee@example.com")
    event = create_event(
        db_session,
        _event_data(
            title="Nearby now",
            latitude=41.0,
            longitude=29.0,
            starts_at=datetime.utcnow() + timedelta(minutes=5),
        ),
        creator_id,
    )

    check_in_to_event(db_session, event.id, attendee_id, latitude=41.001, longitude=29.001)

    assert is_checked_in(db_session, event.id, attendee_id) is True


def test_check_in_rejects_too_far_from_event(db_session: Session) -> None:
    creator_id = _create_user(db_session, "creator@example.com")
    attendee_id = _create_user(db_session, "attendee@example.com")
    event = create_event(
        db_session,
        _event_data(
            title="Far away",
            latitude=41.0,
            longitude=29.0,
            starts_at=datetime.utcnow() + timedelta(minutes=5),
        ),
        creator_id,
    )

    with pytest.raises(EventCheckInTooFarError):
        check_in_to_event(db_session, event.id, attendee_id, latitude=48.85, longitude=2.35)

    assert is_checked_in(db_session, event.id, attendee_id) is False


def test_check_in_rejects_outside_time_window(db_session: Session) -> None:
    creator_id = _create_user(db_session, "creator@example.com")
    attendee_id = _create_user(db_session, "attendee@example.com")
    event = create_event(
        db_session,
        _event_data(
            title="Not yet",
            latitude=41.0,
            longitude=29.0,
            starts_at=datetime.utcnow() + timedelta(days=3),
        ),
        creator_id,
    )

    with pytest.raises(EventCheckInOutsideWindowError):
        check_in_to_event(db_session, event.id, attendee_id, latitude=41.0, longitude=29.0)


def test_is_ticket_verified_false_when_never_submitted(db_session: Session) -> None:
    creator_id = _create_user(db_session, "creator@example.com")
    attendee_id = _create_user(db_session, "attendee@example.com")
    event = create_event(db_session, _event_data(title="Paid gig"), creator_id)

    assert is_ticket_verified(db_session, event.id, attendee_id) is False
