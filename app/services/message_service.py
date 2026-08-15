from sqlalchemy.orm import Session

from app.models.match import Match
from app.models.message import Message
from app.services.moderation_service import contains_banned_words
from app.services.safety_service import is_blocked


class MatchNotFoundError(Exception):
    pass


class NotMatchParticipantError(Exception):
    pass


class BlockedParticipantError(Exception):
    pass


class MessageBlockedError(Exception):
    pass


def _get_match_for_participant(db: Session, match_id: int, user_id: int) -> Match:
    match = db.get(Match, match_id)
    if match is None:
        raise MatchNotFoundError(match_id)
    if user_id not in (match.user_a_id, match.user_b_id):
        raise NotMatchParticipantError(user_id)

    other_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
    if is_blocked(db, user_id, other_id):
        raise BlockedParticipantError(user_id)
    return match


def send_message(
    db: Session,
    match_id: int,
    sender_id: int,
    content: str,
    message_type: str = "text",
    media_url: str | None = None,
) -> Message:
    _get_match_for_participant(db, match_id, sender_id)

    if contains_banned_words(content):
        raise MessageBlockedError(content)

    message = Message(
        match_id=match_id,
        sender_id=sender_id,
        content=content,
        message_type=message_type,
        media_url=media_url,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def list_messages(db: Session, match_id: int, requester_id: int) -> list[Message]:
    _get_match_for_participant(db, match_id, requester_id)
    return (
        db.query(Message)
        .filter(Message.match_id == match_id)
        .order_by(Message.created_at)
        .all()
    )


def mark_messages_as_read(db: Session, match_id: int, reader_id: int) -> int:
    _get_match_for_participant(db, match_id, reader_id)
    unread_messages = (
        db.query(Message)
        .filter(
            Message.match_id == match_id,
            Message.sender_id != reader_id,
            Message.is_read.is_(False),
        )
        .all()
    )
    for message in unread_messages:
        message.is_read = True
    db.commit()
    return len(unread_messages)
