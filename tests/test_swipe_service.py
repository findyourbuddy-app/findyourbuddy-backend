from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.swipe import SwipeDirection
from app.models.user import User
from app.schemas.event import EventCreate
from app.schemas.swipe import SwipeCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.schemas.user import UserUpdate
from app.services.event_service import create_event
from app.services.safety_service import block_user
from app.services.subscription_service import grant_premium
from app.services.swipe_service import (
    BlockedUserError,
    DailySuperLikeLimitExceededError,
    DailySwipeLimitExceededError,
    DuplicateSwipeError,
    list_incoming_likes,
    list_swipe_candidates,
    record_swipe,
)
from app.services.user_service import update_profile


def _register(db_session: Session, email: str) -> int:
    user = register_user(
        db_session,
        UserCreate(email=email, password="s3cret-pass", display_name=email, accepted_terms=True),
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


def test_record_swipe_bypasses_daily_limit_for_premium_user(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DAILY_SWIPE_LIMIT", "1")
    get_settings.cache_clear()

    swiper_id = _register(db_session, "swiper@example.com")
    grant_premium(db_session, swiper_id)
    event_id = _create_event(db_session, swiper_id)
    target_ids = [
        _register(db_session, "t1@example.com"),
        _register(db_session, "t2@example.com"),
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

    get_settings.cache_clear()


def test_record_swipe_raises_when_super_like_limit_reached(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DAILY_SUPER_LIKE_LIMIT", "1")
    get_settings.cache_clear()

    swiper_id = _register(db_session, "swiper@example.com")
    event_id = _create_event(db_session, swiper_id)
    target_ids = [
        _register(db_session, "t1@example.com"),
        _register(db_session, "t2@example.com"),
    ]

    record_swipe(
        db_session,
        swiper_id,
        SwipeCreate(target_id=target_ids[0], event_id=event_id, direction=SwipeDirection.SUPER_LIKE),
    )

    with pytest.raises(DailySuperLikeLimitExceededError):
        record_swipe(
            db_session,
            swiper_id,
            SwipeCreate(
                target_id=target_ids[1], event_id=event_id, direction=SwipeDirection.SUPER_LIKE
            ),
        )

    get_settings.cache_clear()


def test_record_swipe_super_like_gets_higher_limit_for_premium(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DAILY_SUPER_LIKE_LIMIT", "1")
    monkeypatch.setenv("PREMIUM_DAILY_SUPER_LIKE_LIMIT", "2")
    get_settings.cache_clear()

    swiper_id = _register(db_session, "swiper@example.com")
    grant_premium(db_session, swiper_id)
    event_id = _create_event(db_session, swiper_id)
    target_ids = [
        _register(db_session, "t1@example.com"),
        _register(db_session, "t2@example.com"),
    ]

    record_swipe(
        db_session,
        swiper_id,
        SwipeCreate(target_id=target_ids[0], event_id=event_id, direction=SwipeDirection.SUPER_LIKE),
    )
    record_swipe(
        db_session,
        swiper_id,
        SwipeCreate(target_id=target_ids[1], event_id=event_id, direction=SwipeDirection.SUPER_LIKE),
    )

    get_settings.cache_clear()


def test_super_like_creates_match_on_mutual_interest(db_session: Session) -> None:
    from app.services.matching_service import try_create_match

    user_a_id = _register(db_session, "a@example.com")
    user_b_id = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a_id)

    record_swipe(
        db_session,
        user_a_id,
        SwipeCreate(target_id=user_b_id, event_id=event_id, direction=SwipeDirection.SUPER_LIKE),
    )
    record_swipe(
        db_session,
        user_b_id,
        SwipeCreate(target_id=user_a_id, event_id=event_id, direction=SwipeDirection.LIKE),
    )

    match = try_create_match(db_session, user_a_id, user_b_id, event_id)

    assert match is not None


def test_list_incoming_likes_includes_super_likes(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    super_liker_id = _register(db_session, "superliker@example.com")
    event_id = _create_event(db_session, user_id)

    record_swipe(
        db_session,
        super_liker_id,
        SwipeCreate(target_id=user_id, event_id=event_id, direction=SwipeDirection.SUPER_LIKE),
    )

    liker_ids = {
        item["user"].id for item in list_incoming_likes(db_session, event_id=event_id, user_id=user_id)
    }

    assert liker_ids == {super_liker_id}


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


def test_list_incoming_likes_returns_unreciprocated_likers(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    liker_id = _register(db_session, "liker@example.com")
    passer_id = _register(db_session, "passer@example.com")
    event_id = _create_event(db_session, user_id)

    record_swipe(
        db_session,
        liker_id,
        SwipeCreate(target_id=user_id, event_id=event_id, direction=SwipeDirection.LIKE),
    )
    record_swipe(
        db_session,
        passer_id,
        SwipeCreate(target_id=user_id, event_id=event_id, direction=SwipeDirection.PASS),
    )

    liker_ids = {
        item["user"].id for item in list_incoming_likes(db_session, event_id=event_id, user_id=user_id)
    }

    assert liker_ids == {liker_id}


def test_list_incoming_likes_excludes_already_matched_users(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    liker_id = _register(db_session, "liker@example.com")
    event_id = _create_event(db_session, user_id)

    record_swipe(
        db_session,
        liker_id,
        SwipeCreate(target_id=user_id, event_id=event_id, direction=SwipeDirection.LIKE),
    )
    record_swipe(
        db_session,
        user_id,
        SwipeCreate(target_id=liker_id, event_id=event_id, direction=SwipeDirection.LIKE),
    )

    liker_ids = {
        item["user"].id for item in list_incoming_likes(db_session, event_id=event_id, user_id=user_id)
    }

    assert liker_ids == set()


def test_list_incoming_likes_excludes_blocked_users(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    liker_id = _register(db_session, "liker@example.com")
    event_id = _create_event(db_session, user_id)
    record_swipe(
        db_session,
        liker_id,
        SwipeCreate(target_id=user_id, event_id=event_id, direction=SwipeDirection.LIKE),
    )
    block_user(db_session, user_id, liker_id)

    liker_ids = {
        item["user"].id for item in list_incoming_likes(db_session, event_id=event_id, user_id=user_id)
    }

    assert liker_ids == set()


def test_list_swipe_candidates_filters_by_age_range(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    grant_premium(db_session, swiper_id)
    young_id = _register(db_session, "young@example.com")
    old_id = _register(db_session, "old@example.com")
    unset_id = _register(db_session, "unset@example.com")
    event_id = _create_event(db_session, swiper_id)
    update_profile(db_session, db_session.get(User, young_id), UserUpdate(age=20))
    update_profile(db_session, db_session.get(User, old_id), UserUpdate(age=45))

    candidate_ids = {
        user.id
        for user in list_swipe_candidates(
            db_session, event_id=event_id, swiper_id=swiper_id, min_age=25, max_age=50
        )
    }

    assert candidate_ids == {old_id}
    assert young_id not in candidate_ids
    assert unset_id not in candidate_ids


def test_list_swipe_candidates_ignores_age_filter_for_non_premium(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    young_id = _register(db_session, "young@example.com")
    old_id = _register(db_session, "old@example.com")
    event_id = _create_event(db_session, swiper_id)
    update_profile(db_session, db_session.get(User, young_id), UserUpdate(age=20))
    update_profile(db_session, db_session.get(User, old_id), UserUpdate(age=45))

    candidate_ids = {
        user.id
        for user in list_swipe_candidates(
            db_session, event_id=event_id, swiper_id=swiper_id, min_age=25, max_age=50
        )
    }

    assert candidate_ids == {young_id, old_id}


def test_list_swipe_candidates_applies_age_filter_for_premium(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    grant_premium(db_session, swiper_id)
    young_id = _register(db_session, "young@example.com")
    old_id = _register(db_session, "old@example.com")
    event_id = _create_event(db_session, swiper_id)
    update_profile(db_session, db_session.get(User, young_id), UserUpdate(age=20))
    update_profile(db_session, db_session.get(User, old_id), UserUpdate(age=45))

    candidate_ids = {
        user.id
        for user in list_swipe_candidates(
            db_session, event_id=event_id, swiper_id=swiper_id, min_age=25, max_age=50
        )
    }

    assert candidate_ids == {old_id}


def test_list_swipe_candidates_boosts_premium_users_first(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    regular_id = _register(db_session, "regular@example.com")
    boosted_id = _register(db_session, "boosted@example.com")
    event_id = _create_event(db_session, swiper_id)
    grant_premium(db_session, boosted_id)

    candidate_ids = [
        user.id
        for user in list_swipe_candidates(db_session, event_id=event_id, swiper_id=swiper_id)
    ]

    assert candidate_ids.index(boosted_id) < candidate_ids.index(regular_id)


def test_list_swipe_candidates_filters_by_distance(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    grant_premium(db_session, swiper_id)
    nearby_id = _register(db_session, "nearby@example.com")
    far_id = _register(db_session, "far@example.com")
    event_id = _create_event(db_session, swiper_id)
    # Istanbul-ish coordinates for swiper + nearby, and a far-away point for "far".
    update_profile(
        db_session, db_session.get(User, swiper_id), UserUpdate(latitude=41.0, longitude=29.0)
    )
    update_profile(
        db_session, db_session.get(User, nearby_id), UserUpdate(latitude=41.01, longitude=29.01)
    )
    update_profile(
        db_session, db_session.get(User, far_id), UserUpdate(latitude=48.85, longitude=2.35)
    )

    candidate_ids = {
        user.id
        for user in list_swipe_candidates(
            db_session, event_id=event_id, swiper_id=swiper_id, max_distance_km=10
        )
    }

    assert candidate_ids == {nearby_id}
    assert far_id not in candidate_ids


def test_list_swipe_candidates_orders_by_recommendation_score(db_session: Session) -> None:
    swiper_id = _register(db_session, "swiper@example.com")
    better_match_id = _register(db_session, "better@example.com")
    worse_match_id = _register(db_session, "worse@example.com")
    event_id = _create_event(db_session, swiper_id)

    update_profile(
        db_session,
        db_session.get(User, swiper_id),
        UserUpdate(age=25, interests=["jazz", "coffee", "art"]),
    )
    update_profile(
        db_session,
        db_session.get(User, better_match_id),
        UserUpdate(age=26, interests=["jazz", "coffee", "football"]),
    )
    update_profile(
        db_session,
        db_session.get(User, worse_match_id),
        UserUpdate(age=35, interests=["football", "tennis", "art"]),
    )

    candidates = list_swipe_candidates(db_session, event_id=event_id, swiper_id=swiper_id)
    candidate_ids = [user.id for user in candidates]

    # better_match_id should be ordered first because of higher Jaccard similarity and lower age difference
    assert candidate_ids.index(better_match_id) < candidate_ids.index(worse_match_id)
