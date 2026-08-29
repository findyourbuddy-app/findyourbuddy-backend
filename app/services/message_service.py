from sqlalchemy import update
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


class GroupChannelPostForbiddenError(Exception):
    """A non-organizer tried to post in a group-event announcement channel."""

    pass


def is_group_match(match: Match) -> bool:
    """A match belongs to a group-event announcement channel. Every match has a
    non-null event_id, so the group path must key off the event's flag, not the
    mere presence of event_id."""
    return bool(match.event and match.event.is_group_event)


def group_match_ids_for_event(db: Session, event_id: int) -> list[int]:
    """All match ids sharing a group event -- the announcement channel spans
    every organizer<->attendee match for that event."""
    return [row[0] for row in db.query(Match.id).filter(Match.event_id == event_id).all()]


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
    match = _get_match_for_participant(db, match_id, sender_id)

    if is_group_match(match) and match.event.creator_id != sender_id:
        raise GroupChannelPostForbiddenError(sender_id)

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


def _resolve_message_scope(db: Session, match_id: int, user_id: int):
    """Returns the SQLAlchemy filter selecting the messages a participant may
    see for this match -- a single match for 1-on-1 chats, every match of the
    event for a group announcement channel."""
    match = db.get(Match, match_id)
    if match is None:
        raise MatchNotFoundError(match_id)

    if is_group_match(match):
        if user_id not in (match.user_a_id, match.user_b_id):
            raise NotMatchParticipantError(user_id)
        other_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
        if is_blocked(db, user_id, other_id):
            raise BlockedParticipantError(user_id)
        return Message.match_id.in_(group_match_ids_for_event(db, match.event_id))

    _get_match_for_participant(db, match_id, user_id)
    return Message.match_id == match_id


def list_messages(
    db: Session,
    match_id: int,
    requester_id: int,
    skip: int = 0,
    limit: int = 50,
) -> list[Message]:
    scope = _resolve_message_scope(db, match_id, requester_id)
    # Page from the newest end so long conversations don't lose their recent
    # history to the row cap, then return chronological order for the client.
    # id is the tie-breaker so messages saved within the same instant keep a
    # stable order.
    rows = (
        db.query(Message)
        .filter(scope)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return list(reversed(rows))


def mark_messages_as_read(db: Session, match_id: int, reader_id: int) -> int:
    scope = _resolve_message_scope(db, match_id, reader_id)
    result = db.execute(
        update(Message)
        .where(
            scope,
            Message.sender_id != reader_id,
            Message.is_read.is_(False),
        )
        .values(is_read=True)
    )
    db.commit()
    return result.rowcount
