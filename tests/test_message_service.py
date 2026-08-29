from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.match import Match
from app.models.swipe import SwipeDirection
from app.schemas.event import EventCreate
from app.schemas.swipe import SwipeCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.event_service import create_event
from app.services.matching_service import try_create_match
from app.services.message_service import (
    GroupChannelPostForbiddenError,
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
            starts_at=datetime.now(timezone.utc) + timedelta(days=1),
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


def _create_group_event(db_session: Session, creator_id: int) -> Event:
    event = Event(
        title="Study group",
        category="education",
        location_name="Library",
        latitude=40.0,
        longitude=-73.0,
        starts_at=datetime.now(timezone.utc) + timedelta(days=1),
        creator_id=creator_id,
        is_group_event=True,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


def _add_match(db_session: Session, event_id: int, user_a: int, user_b: int) -> Match:
    match = Match(event_id=event_id, user_a_id=user_a, user_b_id=user_b, score=1.0)
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)
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


def test_mark_messages_as_read_does_not_touch_sibling_matches_of_same_event(
    db_session: Session,
) -> None:
    organizer = _register(db_session, "org@example.com")
    friend_a = _register(db_session, "fa@example.com")
    friend_b = _register(db_session, "fb@example.com")
    event_id = _create_event(db_session, organizer)  # 1-on-1 event, not a group

    match_a = _add_match(db_session, event_id, organizer, friend_a)
    match_b = _add_match(db_session, event_id, organizer, friend_b)
    send_message(db_session, match_a.id, friend_a, "hi from A")
    send_message(db_session, match_b.id, friend_b, "hi from B")

    mark_messages_as_read(db_session, match_a.id, organizer)

    by_content = {
        m.content: m.is_read
        for m in list_messages(db_session, match_a.id, organizer)
        + list_messages(db_session, match_b.id, organizer)
    }
    assert by_content["hi from A"] is True
    assert by_content["hi from B"] is False


def test_list_messages_returns_most_recent_within_limit(db_session: Session) -> None:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a)
    match = _add_match(db_session, event_id, user_a, user_b)
    for i in range(5):
        send_message(db_session, match.id, user_a, f"msg {i}")

    recent = [m.content for m in list_messages(db_session, match.id, user_b, limit=2)]

    assert recent == ["msg 3", "msg 4"]


def test_group_channel_aggregates_messages_across_matches(db_session: Session) -> None:
    organizer = _register(db_session, "org@example.com")
    attendee_1 = _register(db_session, "a1@example.com")
    attendee_2 = _register(db_session, "a2@example.com")
    event = _create_group_event(db_session, organizer)
    match_1 = _add_match(db_session, event.id, organizer, attendee_1)
    match_2 = _add_match(db_session, event.id, organizer, attendee_2)

    send_message(db_session, match_1.id, organizer, "welcome all")

    seen_by_attendee_2 = [
        m.content for m in list_messages(db_session, match_2.id, attendee_2)
    ]
    assert seen_by_attendee_2 == ["welcome all"]


def test_only_group_organizer_can_post_in_channel(db_session: Session) -> None:
    organizer = _register(db_session, "org@example.com")
    attendee = _register(db_session, "att@example.com")
    event = _create_group_event(db_session, organizer)
    match = _add_match(db_session, event.id, organizer, attendee)

    send_message(db_session, match.id, organizer, "announcement")

    with pytest.raises(GroupChannelPostForbiddenError):
        send_message(db_session, match.id, attendee, "i should not be able to post")
