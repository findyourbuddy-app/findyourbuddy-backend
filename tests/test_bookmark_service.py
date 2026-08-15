from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.schemas.event import EventCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.bookmark_service import (
    AlreadyBookmarkedError,
    BookmarkNotFoundError,
    EventNotFoundError,
    create_bookmark,
    list_bookmarks,
    remove_bookmark,
)
from app.services.event_service import create_event


def _register(db_session: Session, email: str) -> int:
    return register_user(
        db_session,
        UserCreate(email=email, password="s3cret-pass", display_name=email, accepted_terms=True, phone_number=f"5{abs(hash(email)) % 10**9:09d}"),
    ).id


def _create_event(db_session: Session, creator_id: int) -> int:
    event = create_event(
        db_session,
        EventCreate(
            title="Trail run",
            category="sports",
            location_name="Central Park",
            latitude=40.0,
            longitude=-73.0,
            starts_at=datetime.utcnow() + timedelta(days=1),
        ),
        creator_id,
        is_premium=True,
    )
    return event.id


def test_create_bookmark(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    event_id = _create_event(db_session, user_id)

    bookmark = create_bookmark(db_session, user_id, event_id)

    assert bookmark.user_id == user_id
    assert bookmark.event_id == event_id


def test_create_bookmark_raises_for_unknown_event(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")

    with pytest.raises(EventNotFoundError):
        create_bookmark(db_session, user_id, 999)


def test_create_bookmark_raises_for_duplicate(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    event_id = _create_event(db_session, user_id)
    create_bookmark(db_session, user_id, event_id)

    with pytest.raises(AlreadyBookmarkedError):
        create_bookmark(db_session, user_id, event_id)


def test_remove_bookmark(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    event_id = _create_event(db_session, user_id)
    create_bookmark(db_session, user_id, event_id)

    remove_bookmark(db_session, user_id, event_id)

    assert list_bookmarks(db_session, user_id) == []


def test_remove_bookmark_raises_for_unknown_bookmark(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    event_id = _create_event(db_session, user_id)

    with pytest.raises(BookmarkNotFoundError):
        remove_bookmark(db_session, user_id, event_id)


def test_list_bookmarks_respects_skip_and_limit(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    event_ids = [_create_event(db_session, user_id) for _ in range(3)]
    for event_id in event_ids:
        create_bookmark(db_session, user_id, event_id)

    assert len(list_bookmarks(db_session, user_id, skip=0, limit=2)) == 2
    assert len(list_bookmarks(db_session, user_id, skip=2, limit=2)) == 1


def test_list_bookmarks_returns_only_my_bookmarks(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    other_id = _register(db_session, "other@example.com")
    event_id = _create_event(db_session, user_id)
    other_event_id = _create_event(db_session, other_id)
    create_bookmark(db_session, user_id, event_id)
    create_bookmark(db_session, other_id, other_event_id)

    result = list_bookmarks(db_session, user_id)

    assert len(result) == 1
    bookmark, event = result[0]
    assert bookmark.event_id == event_id
    assert event.id == event_id
