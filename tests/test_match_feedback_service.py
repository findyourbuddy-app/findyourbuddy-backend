from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.notifications import LoggingNotificationSender
from app.models.swipe import SwipeDirection
from app.models.user import User
from app.schemas.event import EventCreate
from app.schemas.swipe import SwipeCreate
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.event_service import create_event
from app.services.match_feedback_service import (
    EventNotFinishedError,
    NotAMatchParticipantError,
    needs_feedback,
    send_pending_feedback_notifications,
    submit_feedback,
)
from app.services.matching_service import try_create_match
from app.services.notification_service import list_notifications
from app.services.swipe_service import record_swipe


def _register(db_session: Session, email: str) -> int:
    return register_user(
        db_session,
        UserCreate(email=email, password="S3cret-pass", display_name=email, accepted_terms=True, phone_number=f"5{abs(hash(email)) % 10**9:09d}"),
    ).id


def _create_event(db_session: Session, creator_id: int, starts_at: datetime) -> int:
    return create_event(
        db_session,
        EventCreate(
            title="Trail run",
            category="sports",
            location_name="Central Park",
            latitude=40.0,
            longitude=-73.0,
            starts_at=starts_at,
        ),
        creator_id,
    ).id


def _make_match(db_session: Session, starts_at: datetime) -> tuple[int, int, int]:
    user_a = _register(db_session, "a@example.com")
    user_b = _register(db_session, "b@example.com")
    event_id = _create_event(db_session, user_a, starts_at)
    record_swipe(db_session, user_a, SwipeCreate(target_id=user_b, event_id=event_id, direction=SwipeDirection.LIKE))
    record_swipe(db_session, user_b, SwipeCreate(target_id=user_a, event_id=event_id, direction=SwipeDirection.LIKE))
    match = try_create_match(db_session, user_a, user_b, event_id)
    assert match is not None
    return match.id, user_a, user_b


def test_needs_feedback_false_when_event_upcoming(db_session: Session) -> None:
    match_id, user_a, _ = _make_match(db_session, datetime.now(timezone.utc) + timedelta(days=1))
    from app.models.match import Match

    match = db_session.get(Match, match_id)
    assert needs_feedback(db_session, match, user_a) is False


def test_needs_feedback_true_when_event_finished_and_unanswered(db_session: Session) -> None:
    match_id, user_a, _ = _make_match(db_session, datetime.now(timezone.utc) - timedelta(hours=1))
    from app.models.match import Match

    match = db_session.get(Match, match_id)
    assert needs_feedback(db_session, match, user_a) is True


def test_submit_feedback_raises_when_event_not_finished(db_session: Session) -> None:
    match_id, user_a, _ = _make_match(db_session, datetime.now(timezone.utc) + timedelta(days=1))

    with pytest.raises(EventNotFinishedError):
        submit_feedback(db_session, match_id, user_a, True)


def test_submit_feedback_raises_for_non_participant(db_session: Session) -> None:
    match_id, _, _ = _make_match(db_session, datetime.now(timezone.utc) - timedelta(hours=1))
    outsider_id = _register(db_session, "outsider@example.com")

    with pytest.raises(NotAMatchParticipantError):
        submit_feedback(db_session, match_id, outsider_id, True)


def test_submit_feedback_true_increments_rated_user_trust_score(db_session: Session) -> None:
    match_id, user_a, user_b = _make_match(db_session, datetime.now(timezone.utc) - timedelta(hours=1))

    submit_feedback(db_session, match_id, user_a, True)

    assert db_session.get(User, user_b).trust_score == 51


def test_submit_feedback_false_does_not_increment_trust_score(db_session: Session) -> None:
    match_id, user_a, user_b = _make_match(db_session, datetime.now(timezone.utc) - timedelta(hours=1))

    submit_feedback(db_session, match_id, user_a, False)

    assert db_session.get(User, user_b).trust_score == 50


def test_submit_feedback_marks_needs_feedback_false(db_session: Session) -> None:
    match_id, user_a, _ = _make_match(db_session, datetime.now(timezone.utc) - timedelta(hours=1))
    from app.models.match import Match

    submit_feedback(db_session, match_id, user_a, True)

    match = db_session.get(Match, match_id)
    assert needs_feedback(db_session, match, user_a) is False


def test_submit_feedback_twice_does_not_double_count_trust_score(db_session: Session) -> None:
    match_id, user_a, user_b = _make_match(db_session, datetime.now(timezone.utc) - timedelta(hours=1))

    submit_feedback(db_session, match_id, user_a, True)
    submit_feedback(db_session, match_id, user_a, True)

    assert db_session.get(User, user_b).trust_score == 51


def test_send_pending_feedback_notifications_notifies_both_participants_once(
    db_session: Session,
) -> None:
    match_id, user_a, user_b = _make_match(db_session, datetime.now(timezone.utc) - timedelta(hours=1))
    sender = LoggingNotificationSender()

    sent_first = send_pending_feedback_notifications(db_session, sender)
    sent_second = send_pending_feedback_notifications(db_session, sender)

    assert sent_first == 2
    assert sent_second == 0
    # user_a also created the match's event, so they additionally got an
    # event-approval notification on top of the feedback-request one.
    assert len(list_notifications(db_session, user_a)) == 2
    assert len(list_notifications(db_session, user_b)) == 1


def test_send_pending_feedback_notifications_skips_unfinished_events(db_session: Session) -> None:
    _make_match(db_session, datetime.now(timezone.utc) + timedelta(days=1))
    sender = LoggingNotificationSender()

    sent = send_pending_feedback_notifications(db_session, sender)

    assert sent == 0


def test_notification_clears_in_app_needs_feedback(db_session: Session) -> None:
    """Once the scheduler has notified a user, the in-app chat banner should
    not also show -- the notification is the fallback delivery channel, not
    an additional nag on top of it."""
    match_id, user_a, _ = _make_match(db_session, datetime.now(timezone.utc) - timedelta(hours=1))
    from app.models.match import Match

    send_pending_feedback_notifications(db_session, LoggingNotificationSender())

    match = db_session.get(Match, match_id)
    assert needs_feedback(db_session, match, user_a) is False
