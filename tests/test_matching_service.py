from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.swipe import SwipeDirection
from app.models.user import User
from app.schemas.event import EventCreate
from app.schemas.swipe import SwipeCreate
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth_service import register_user
from app.services.event_service import create_event
from app.services.matching_service import (
    list_matches_for_user,
    list_matches_with_details,
    try_create_match,
)
from app.services.message_service import send_message
from app.services.safety_service import block_user
from app.services.swipe_service import record_swipe
from app.services.user_service import update_profile


def _register(db_session: Session, email: str) -> int:
    return register_user(
        db_session,
        UserCreate(email=email, password="s3cret-pass", display_name=email, accepted_terms=True, phone_number=f"5{abs(hash(email)) % 10**9:09d}"),
    ).id


def _create_event(db_session: Session, creator_id: int) -> int:
    return create_event(
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
    ).id


def _swipe(db_session: Session, swiper_id: int, target_id: int, event_id: int, direction: SwipeDirection) -> None:
    record_swipe(
        db_session, swiper_id, SwipeCreate(target_id=target_id, event_id=event_id, direction=direction)
    )


def test_mutual_like_creates_a_match(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)

    _swipe(db_session, user_a, user_b, event_id, SwipeDirection.LIKE)
    assert try_create_match(db_session, user_a, user_b, event_id) is None

    _swipe(db_session, user_b, user_a, event_id, SwipeDirection.LIKE)
    match = try_create_match(db_session, user_b, user_a, event_id)

    assert match is not None
    assert {match.user_a_id, match.user_b_id} == {user_a, user_b}
    assert match.event_id == event_id


def test_one_sided_like_does_not_create_a_match(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)

    _swipe(db_session, user_a, user_b, event_id, SwipeDirection.LIKE)

    assert try_create_match(db_session, user_a, user_b, event_id) is None


def test_like_and_pass_does_not_create_a_match(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)

    _swipe(db_session, user_a, user_b, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_b, user_a, event_id, SwipeDirection.PASS)

    assert try_create_match(db_session, user_a, user_b, event_id) is None


def test_match_is_not_duplicated_on_repeated_calls(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)
    _swipe(db_session, user_a, user_b, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_b, user_a, event_id, SwipeDirection.LIKE)

    first_attempt = try_create_match(db_session, user_a, user_b, event_id)
    second_attempt = try_create_match(db_session, user_b, user_a, event_id)

    assert first_attempt is not None
    assert second_attempt is None


def test_match_score_rewards_shared_interests(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)
    update_profile(db_session, db_session.get(User, user_a), UserUpdate(interests=["hiking", "chess"]))
    update_profile(db_session, db_session.get(User, user_b), UserUpdate(interests=["hiking", "reading"]))

    _swipe(db_session, user_a, user_b, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_b, user_a, event_id, SwipeDirection.LIKE)
    match = try_create_match(db_session, user_a, user_b, event_id)

    assert match is not None
    assert match.score > 0


def test_match_score_is_higher_for_closer_users(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_close = _register(db_session, "close@example.com")
    user_far = _register(db_session, "far@example.com")
    event_id = _create_event(db_session, user_a)

    update_profile(db_session, db_session.get(User, user_a), UserUpdate(latitude=40.0, longitude=-73.0))
    update_profile(db_session, db_session.get(User, user_close), UserUpdate(latitude=40.01, longitude=-73.01))
    update_profile(db_session, db_session.get(User, user_far), UserUpdate(latitude=41.5, longitude=-74.5))

    _swipe(db_session, user_a, user_close, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_close, user_a, event_id, SwipeDirection.LIKE)
    close_match = try_create_match(db_session, user_a, user_close, event_id)

    _swipe(db_session, user_a, user_far, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_far, user_a, event_id, SwipeDirection.LIKE)
    far_match = try_create_match(db_session, user_a, user_far, event_id)

    assert close_match is not None
    assert far_match is not None
    assert close_match.score > far_match.score


def test_match_score_ignores_distance_when_coordinates_missing(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)

    _swipe(db_session, user_a, user_b, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_b, user_a, event_id, SwipeDirection.LIKE)
    match = try_create_match(db_session, user_a, user_b, event_id)

    assert match is not None
    assert match.score == 0.0


def test_list_matches_for_user_includes_matches_from_either_side(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    user_c = _register(db_session, "c@example.com")
    event_id = _create_event(db_session, user_a)

    _swipe(db_session, user_a, user_b, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_b, user_a, event_id, SwipeDirection.LIKE)
    try_create_match(db_session, user_a, user_b, event_id)

    _swipe(db_session, user_a, user_c, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_c, user_a, event_id, SwipeDirection.LIKE)
    try_create_match(db_session, user_a, user_c, event_id)

    assert len(list_matches_for_user(db_session, user_a)) == 2
    assert len(list_matches_for_user(db_session, user_b)) == 1
    assert len(list_matches_for_user(db_session, user_c)) == 1


def test_list_matches_for_user_respects_skip_and_limit(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    others = [_register(db_session, f"other{i}@example.com") for i in range(3)]
    event_id = _create_event(db_session, user_a)

    for other in others:
        _swipe(db_session, user_a, other, event_id, SwipeDirection.LIKE)
        _swipe(db_session, other, user_a, event_id, SwipeDirection.LIKE)
        try_create_match(db_session, user_a, other, event_id)

    assert len(list_matches_for_user(db_session, user_a, skip=0, limit=2)) == 2
    assert len(list_matches_for_user(db_session, user_a, skip=2, limit=2)) == 1


def test_list_matches_for_user_excludes_matches_with_blocked_users(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)

    _swipe(db_session, user_a, user_b, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_b, user_a, event_id, SwipeDirection.LIKE)
    try_create_match(db_session, user_a, user_b, event_id)

    block_user(db_session, blocker_id=user_a, blocked_id=user_b)

    assert list_matches_for_user(db_session, user_a) == []
    assert list_matches_for_user(db_session, user_b) == []


def test_list_matches_with_details_resolves_other_user(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)
    _swipe(db_session, user_a, user_b, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_b, user_a, event_id, SwipeDirection.LIKE)
    try_create_match(db_session, user_a, user_b, event_id)

    details = list_matches_with_details(db_session, user_a)

    assert len(details) == 1
    match, other_user, last_message = details[0]
    assert other_user.id == user_b
    assert last_message is None
    assert match.event_id == event_id


def test_list_matches_with_details_returns_most_recent_message(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)
    _swipe(db_session, user_a, user_b, event_id, SwipeDirection.LIKE)
    _swipe(db_session, user_b, user_a, event_id, SwipeDirection.LIKE)
    match = try_create_match(db_session, user_a, user_b, event_id)
    assert match is not None

    send_message(db_session, match.id, user_a, "İlk mesaj")
    send_message(db_session, match.id, user_b, "İkinci mesaj")

    details = list_matches_with_details(db_session, user_a)

    _, _, last_message = details[0]
    assert last_message is not None
    assert last_message.content == "İkinci mesaj"
    assert last_message.sender_id == user_b
