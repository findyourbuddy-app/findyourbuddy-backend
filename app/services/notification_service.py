from sqlalchemy.orm import Session

from app.core.notifications import NotificationSender
from app.models.match import Match
from app.models.message import Message
from app.models.notification import Notification


def notify_match_created(db: Session, sender: NotificationSender, match: Match) -> None:
    body = "FindYourBuddy'de yeni bir kanka eşleşmen var!"
    title = "Yeni Eşleşme! 🎉"
    for user_id in (match.user_a_id, match.user_b_id):
        sender.send(user_id, title, body)
        db.add(Notification(user_id=user_id, title=title, body=body))
    db.commit()


def notify_new_message(db: Session, sender: NotificationSender, message: Message, recipient_id: int) -> None:
    title = "Yeni Mesaj 💬"
    body = "Sana yeni bir mesaj geldi."
    sender.send(recipient_id, title, body)
    db.add(Notification(user_id=recipient_id, title=title, body=body))
    db.commit()


def list_notifications(
    db: Session, user_id: int, skip: int = 0, limit: int = 50
) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def mark_notifications_as_read(db: Session, user_id: int) -> int:
    unread = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
        .all()
    )
    for notification in unread:
        notification.is_read = True
    db.commit()
    return len(unread)
