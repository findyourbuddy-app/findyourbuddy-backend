from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.notifications import NotificationSender
from app.models.match import Match
from app.models.message import Message
from app.models.notification import Notification
from app.models.user import User


def _display_name(db: Session, user_id: int) -> str | None:
    user = db.get(User, user_id)
    return user.display_name if user is not None else None


def notify_double_buddy(
    db: Session,
    sender: NotificationSender,
    recipient_id: int,
    kind: str,
    double_buddy_id: int,
    other_name: str,
) -> None:
    """kind: "invite" | "accepted" | "rejected"."""
    copy = {
        "invite": (
            "Double Buddy Daveti 👯",
            f"{other_name} seni Double Buddy ekibine davet etti. Kabul ediyor musun?",
        ),
        "accepted": (
            "Double Buddy Kuruldu 🎉",
            f"{other_name} Double Buddy davetini kabul etti. Artık ikili moddasınız!",
        ),
        "rejected": (
            "Double Buddy Daveti",
            f"{other_name} şu an Double Buddy olmak istemiyor.",
        ),
    }
    title, body = copy[kind]
    data = {"double_buddy_id": double_buddy_id, "notification_type": f"double_buddy_{kind}"}
    sender.send(recipient_id, title, body, data=data)
    db.add(Notification(
        user_id=recipient_id,
        title=title,
        body=body,
        notification_type=f"double_buddy_{kind}",
        data={"double_buddy_id": double_buddy_id},
    ))
    db.commit()


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
            data={
                "match_id": match.id,
                "other_user_id": other_id,
                "other_user_name": _display_name(db, other_id),
            },
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
        data={
            "match_id": message.match_id,
            "sender_id": message.sender_id,
            "other_user_id": message.sender_id,
            "other_user_name": _display_name(db, message.sender_id),
        },
        title=title,
        body=body,
    ))
    db.commit()


def notify_new_message_bulk(
    db: Session, sender: NotificationSender, message: Message, recipient_ids: set[int]
) -> None:
    """Notifies multiple recipients with one push batch and one DB commit."""
    if not recipient_ids:
        return
    title = "Yeni Mesaj 💬"
    body = "Sana yeni bir mesaj geldi."
    if hasattr(sender, "send_bulk"):
        sender.send_bulk(list(recipient_ids), title, body)
    else:
        for rid in recipient_ids:
            sender.send(rid, title, body)
    sender_name = _display_name(db, message.sender_id)
    for rid in recipient_ids:
        db.add(Notification(
            user_id=rid,
            match_id=message.match_id,
            notification_type="message",
            data={
                "match_id": message.match_id,
                "sender_id": message.sender_id,
                "other_user_id": message.sender_id,
                "other_user_name": sender_name,
            },
            title=title,
            body=body,
        ))
    db.commit()


def list_notifications(
    db: Session, user_id: int, skip: int = 0, limit: int = 50
) -> list[Notification]:
    try:
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    except Exception as e:
        db.rollback()
        return []


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
