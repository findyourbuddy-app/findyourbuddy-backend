from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.message import Message
from app.services.notification_service import (
    list_notifications,
    mark_notifications_as_read,
    notify_match_created,
    notify_new_message,
)
from tests.conftest import FakeNotificationSender


def test_notify_match_created_notifies_both_users(db_session: Session) -> None:
    sender = FakeNotificationSender()
    match = Match(id=1, event_id=1, user_a_id=10, user_b_id=20, score=0.5)

    notify_match_created(db_session, sender, match)

    notified_user_ids = {user_id for user_id, _, _ in sender.sent}
    assert notified_user_ids == {10, 20}


def test_notify_match_created_persists_notification_history(db_session: Session) -> None:
    sender = FakeNotificationSender()
    match = Match(id=1, event_id=1, user_a_id=10, user_b_id=20, score=0.5)

    notify_match_created(db_session, sender, match)

    assert [n.title for n in list_notifications(db_session, 10)] == ["New match!"]
    assert [n.title for n in list_notifications(db_session, 20)] == ["New match!"]


def test_notify_new_message_notifies_only_the_recipient(db_session: Session) -> None:
    sender = FakeNotificationSender()
    message = Message(id=1, match_id=1, sender_id=10, content="hi")

    notify_new_message(db_session, sender, message, recipient_id=20)

    assert sender.sent == [(20, "New message", "You have a new message.")]
    assert [n.title for n in list_notifications(db_session, 20)] == ["New message"]


def test_list_notifications_respects_skip_and_limit(db_session: Session) -> None:
    sender = FakeNotificationSender()
    for i in range(3):
        notify_new_message(
            db_session,
            sender,
            Message(id=i, match_id=1, sender_id=10, content="hi"),
            recipient_id=20,
        )

    assert len(list_notifications(db_session, 20, skip=0, limit=2)) == 2
    assert len(list_notifications(db_session, 20, skip=2, limit=2)) == 1


def test_mark_notifications_as_read_marks_only_that_users_unread_notifications(
    db_session: Session,
) -> None:
    sender = FakeNotificationSender()
    notify_new_message(
        db_session, sender, Message(id=1, match_id=1, sender_id=10, content="hi"), recipient_id=20
    )
    notify_new_message(
        db_session, sender, Message(id=2, match_id=1, sender_id=20, content="hi"), recipient_id=10
    )

    count = mark_notifications_as_read(db_session, 20)

    assert count == 1
    assert all(n.is_read for n in list_notifications(db_session, 20))
    assert all(not n.is_read for n in list_notifications(db_session, 10))
