from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.swipe import SwipeDirection
from app.schemas.event import EventCreate
from app.schemas.swipe import SwipeCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.event_service import create_event
from app.services.safety_service import block_user
from app.services.swipe_service import (
    BlockedUserError,
    DailySwipeLimitExceededError,
    DuplicateSwipeError,
    list_swipe_candidates,
    record_swipe,
)


def _register(db_session: Session, email: str) -> int:
    user = register_user(
        db_session, UserCreate(email=email, password="s3cret-pass", display_name=email)
    )
    return user.id


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
    )
    return event.id


def test_record_swipe_raises_when_daily_limit_reached(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DAILY_SWIPE_LIMIT", "2")
    get_settings.cache_clear()

    swiper_id = _register(db_session, "swiper@example.com")
    event_id = _create_event(db_session, swiper_id)
    target_ids = [
        _register(db_session, "t1@example.com"),
        _register(db_session, "t2@example.com"),
        _register(db_session, "t3@example.com"),
    ]

    record_swipe(
        db_session,
        swiper_id,
        SwipeCreate(target_id=target_ids[0], event_id=event_id, direction=SwipeDirection.LIKE),
    )
    record_swipe(
        db_session,
        swiper_id,
        SwipeCreate(target_id=target_ids[1], event_id=event_id, direction=SwipeDirection.LIKE),
    )

    with pytest.raises(DailySwipeLimitExceededError):
        record_swipe(
            db_session,
            swiper_id,
            SwipeCreate(
                target_id=target_ids[2], event_id=event_id, direction=SwipeDirection.LIKE
            ),
        )

    get_settings.cache_clear()


def test_record_swipe_raises_for_duplicate_target_and_event(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    target_id = _register(db_session, "target@example.com")
    event_id = _create_event(db_session, swiper_id)

    record_swipe(
        db_session,
        swiper_id,
        SwipeCreate(target_id=target_id, event_id=event_id, direction=SwipeDirection.LIKE),
    )

    with pytest.raises(DuplicateSwipeError):
        record_swipe(
            db_session,
            swiper_id,
            SwipeCreate(target_id=target_id, event_id=event_id, direction=SwipeDirection.PASS),
        )


def test_list_swipe_candidates_excludes_self_and_already_swiped(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    already_swiped_id = _register(db_session, "swiped@example.com")
    remaining_id = _register(db_session, "remaining@example.com")
    event_id = _create_event(db_session, swiper_id)

    record_swipe(
        db_session,
        swiper_id,
        SwipeCreate(
            target_id=already_swiped_id, event_id=event_id, direction=SwipeDirection.PASS
        ),
    )

    candidate_ids = {
        user.id for user in list_swipe_candidates(db_session, event_id=event_id, swiper_id=swiper_id)
    }

    assert swiper_id not in candidate_ids
    assert already_swiped_id not in candidate_ids
    assert remaining_id in candidate_ids


def test_record_swipe_rejects_blocked_user(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    blocked_id = _register(db_session, "blocked@example.com")
    event_id = _create_event(db_session, swiper_id)
    block_user(db_session, swiper_id, blocked_id)

    with pytest.raises(BlockedUserError):
        record_swipe(
            db_session,
            swiper_id,
            SwipeCreate(target_id=blocked_id, event_id=event_id, direction=SwipeDirection.LIKE),
        )


def test_record_swipe_rejects_user_who_blocked_the_swiper(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    blocker_id = _register(db_session, "blocker@example.com")
    event_id = _create_event(db_session, swiper_id)
    block_user(db_session, blocker_id, swiper_id)

    with pytest.raises(BlockedUserError):
        record_swipe(
            db_session,
            swiper_id,
            SwipeCreate(target_id=blocker_id, event_id=event_id, direction=SwipeDirection.LIKE),
        )


def test_list_swipe_candidates_excludes_blocked_users(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    blocked_id = _register(db_session, "blocked@example.com")
    remaining_id = _register(db_session, "remaining@example.com")
    event_id = _create_event(db_session, swiper_id)
    block_user(db_session, swiper_id, blocked_id)

    candidate_ids = {
        user.id
        for user in list_swipe_candidates(db_session, event_id=event_id, swiper_id=swiper_id)
    }

    assert blocked_id not in candidate_ids
    assert remaining_id in candidate_ids
