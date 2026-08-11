from app.models.match import Match
from app.models.message import Message
from app.services.notification_service import notify_match_created, notify_new_message
from tests.conftest import FakeNotificationSender


def test_notify_match_created_notifies_both_users() -> None:
    sender = FakeNotificationSender()
    match = Match(id=1, event_id=1, user_a_id=10, user_b_id=20, score=0.5)

    notify_match_created(sender, match)

    notified_user_ids = {user_id for user_id, _, _ in sender.sent}
    assert notified_user_ids == {10, 20}


def test_notify_new_message_notifies_only_the_recipient() -> None:
    sender = FakeNotificationSender()
    message = Message(id=1, match_id=1, sender_id=10, content="hi")

    notify_new_message(sender, message, recipient_id=20)

    assert sender.sent == [(20, "New message", "You have a new message.")]
