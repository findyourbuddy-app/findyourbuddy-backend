from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.swipe import SwipeDirection
from app.schemas.event import EventCreate
from app.schemas.swipe import SwipeCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.event_service import create_event
from app.services.matching_service import try_create_match
from app.services.message_service import (
    MatchNotFoundError,
    MessageBlockedError,
    NotMatchParticipantError,
    list_messages,
    mark_messages_as_read,
    send_message,
)
from app.services.swipe_service import record_swipe


def _register(db_session: Session, email: str) -> int:
    return register_user(
        db_session,
        UserCreate(email=email, password="S3cret-pass", display_name=email, accepted_terms=True, phone_number=f"5{abs(hash(email)) % 10**9:09d}"),
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


def _create_match(db_session: Session, user_a: int, user_b: int, event_id: int) -> Match:
    record_swipe(
        db_session, user_a, SwipeCreate(target_id=user_b, event_id=event_id, direction=SwipeDirection.LIKE)
    )
    record_swipe(
        db_session, user_b, SwipeCreate(target_id=user_a, event_id=event_id, direction=SwipeDirection.LIKE)
    )
    match = try_create_match(db_session, user_a, user_b, event_id)
    assert match is not None
    return match


def test_matched_user_can_send_and_read_messages(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)
    match = _create_match(db_session, user_a, user_b, event_id)

    send_message(db_session, match.id, user_a, "hey there")
    messages = list_messages(db_session, match.id, user_b)

    assert [message.content for message in messages] == ["hey there"]


def test_non_participant_cannot_send_message(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    outsider = _register(db_session, "outsider@example.com")
    event_id = _create_event(db_session, user_a)
    match = _create_match(db_session, user_a, user_b, event_id)

    with pytest.raises(NotMatchParticipantError):
        send_message(db_session, match.id, outsider, "hi")


def test_non_participant_cannot_read_messages(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    outsider = _register(db_session, "outsider@example.com")
    event_id = _create_event(db_session, user_a)
    match = _create_match(db_session, user_a, user_b, event_id)
    send_message(db_session, match.id, user_a, "hey there")

    with pytest.raises(NotMatchParticipantError):
        list_messages(db_session, match.id, outsider)


def test_send_message_raises_for_unknown_match(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")

    with pytest.raises(MatchNotFoundError):
        send_message(db_session, 999, user_a, "hi")


def test_send_message_blocks_banned_content(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)
    match = _create_match(db_session, user_a, user_b, event_id)

    with pytest.raises(MessageBlockedError):
        send_message(db_session, match.id, user_a, "this is a scam")


def test_mark_messages_as_read_only_affects_received_unread_messages(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)
    match = _create_match(db_session, user_a, user_b, event_id)

    send_message(db_session, match.id, user_a, "hey there")
    send_message(db_session, match.id, user_a, "second message")
    send_message(db_session, match.id, user_b, "reply")

    count = mark_messages_as_read(db_session, match.id, user_b)

    assert count == 2
    messages = {message.content: message.is_read for message in list_messages(db_session, match.id, user_b)}
    assert messages["hey there"] is True
    assert messages["second message"] is True
    assert messages["reply"] is False


def test_mark_messages_as_read_is_idempotent(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)
    match = _create_match(db_session, user_a, user_b, event_id)
    send_message(db_session, match.id, user_a, "hey there")

    mark_messages_as_read(db_session, match.id, user_b)
    second_count = mark_messages_as_read(db_session, match.id, user_b)

    assert second_count == 0
