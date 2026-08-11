from app.core.notifications import NotificationSender
from app.models.match import Match
from app.models.message import Message


def notify_match_created(sender: NotificationSender, match: Match) -> None:
    body = "You have a new match on FindYourBuddy."
    sender.send(match.user_a_id, "New match!", body)
    sender.send(match.user_b_id, "New match!", body)


def notify_new_message(sender: NotificationSender, message: Message, recipient_id: int) -> None:
    sender.send(recipient_id, "New message", "You have a new message.")
