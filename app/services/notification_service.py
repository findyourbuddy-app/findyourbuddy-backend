from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.notifications import NotificationSender
from app.models.match import Match
from app.models.message import Message
from app.models.notification import Notification


def notify_new_like(db: Session, target_user_id: int) -> None:
    db.add(Notification(
        user_id=target_user_id,
        title="Yeni Beğeni!",
        body="Biri seni kanka olarak beğendi.",
        notification_type="like",
    ))
    db.commit()


def notify_match_created(db: Session, sender: NotificationSender, match: Match) -> None:
    body = "FindYourBuddy'de yeni bir kanka eşleşmen var!"
    title = "Yeni Eşleşme! 🎉"
    for user_id in (match.user_a_id, match.user_b_id):
        other_id = match.user_b_id if user_id == match.user_a_id else match.user_a_id
        sender.send(user_id, title, body)
        db.add(Notification(
            user_id=user_id,
            match_id=match.id,
            notification_type="match",
            data={"match_id": match.id, "other_user_id": other_id},
            title=title,
            body=body,
        ))
    db.commit()


def notify_new_message(db: Session, sender: NotificationSender, message: Message, recipient_id: int) -> None:
    title = "Yeni Mesaj 💬"
    body = "Sana yeni bir mesaj geldi."
    sender.send(recipient_id, title, body)
    db.add(Notification(
        user_id=recipient_id,
        match_id=message.match_id,
        notification_type="message",
        data={"match_id": message.match_id, "sender_id": message.sender_id},
        title=title,
        body=body,
    ))
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
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return result.rowcount


def notify_photo_verification_result(
    db: Session, sender: NotificationSender, user_id: int, verified: bool, reason: str | None = None
) -> None:
    if verified:
        title = "Profil Doğrulandı! 🔵"
        body = "Tebrikler! Canlı selfie doğrulamanız onaylandı ve Mavi Tik 🔵 rozetiniz aktif edildi."
    else:
        title = "Profil Doğrulaması Başarısız ⚠️"
        body = f"Selfie doğrulamanız onaylanamadı: {reason or 'Profil fotoğrafıyla uyuşmadı.'}"

    sender.send(user_id, title, body)
    db.add(Notification(
        user_id=user_id,
        notification_type="verification",
        title=title,
        body=body,
    ))
    db.commit()


def notify_event_approved(
    db: Session, sender: NotificationSender, user_id: int, event_title: str, event_id: int | None = None
) -> None:
    title = "Etkinliğin Onaylandı! 🚀"
    body = f"Oluşturduğun '{event_title}' etkinliği onaylandı ve yayına alındı."
    sender.send(user_id, title, body)
    db.add(Notification(
        user_id=user_id,
        event_id=event_id,
        notification_type="event",
        data={"event_id": event_id} if event_id else None,
        title=title,
        body=body,
    ))
    db.commit()
