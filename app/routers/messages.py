import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.firebase import get_firestore_client
from app.core.notifications import NotificationSender, get_notification_sender
from app.core.rate_limit import limiter, messages_rate_limit
from app.database import get_db
from app.models.match import Match
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageRead, MessagesMarkedRead
from app.services.message_service import (
    BlockedParticipantError,
    MatchNotFoundError,
    MessageBlockedError,
    NotMatchParticipantError,
    list_messages,
    mark_messages_as_read,
    send_message,
)
from app.services.notification_service import notify_new_message

router = APIRouter(prefix="/matches/{match_id}/messages", tags=["messages"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[MessageRead])
def get_messages(
    match_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Message]:
    try:
        return list_messages(db, match_id, current_user.id, skip=skip, limit=limit)
    except MatchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found"
        ) from exc
    except NotMatchParticipantError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant in this match"
        ) from exc
    except BlockedParticipantError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access messages with a blocked user"
        ) from exc


@router.post("/", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(messages_rate_limit)
def post_message(
    request: Request,
    match_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    notification_sender: NotificationSender = Depends(get_notification_sender),
) -> Message:
    try:
        message = send_message(
            db,
            match_id,
            current_user.id,
            data.content,
            data.message_type,
            data.media_url,
        )
    except MatchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found"
        ) from exc
    except NotMatchParticipantError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant in this match"
        ) from exc
    except BlockedParticipantError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access messages with a blocked user"
        ) from exc
    except MessageBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message contains blocked content",
        ) from exc

    match = db.get(Match, match_id)
    recipient_id = match.user_b_id if match.user_a_id == current_user.id else match.user_a_id
    notify_new_message(db, notification_sender, message, recipient_id)
    _relay_to_firestore(match_id, message)

    return message


def _relay_to_firestore(match_id: int, message: Message) -> None:
    """Writes the already-moderated, already-rate-limited message into
    Firestore for real-time delivery. Best-effort: a Firestore outage
    shouldn't fail the send, since the message is already durably saved
    in Postgres and push-notified."""
    db_client = get_firestore_client()
    if db_client is None:
        return
    try:
        db_client.collection("matches").document(str(match_id)).collection("messages").add({
            "sender_id": message.sender_id,
            "content": message.content,
            "message_type": message.message_type,
            "media_url": message.media_url,
            "created_at": message.created_at,
            "is_read": False,
        })
    except Exception:
        logger.warning("Failed to relay message %s to Firestore", message.id, exc_info=True)


@router.patch("/read", response_model=MessagesMarkedRead)
def mark_read(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessagesMarkedRead:
    try:
        count = mark_messages_as_read(db, match_id, current_user.id)
    except MatchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found"
        ) from exc
    except NotMatchParticipantError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant in this match"
        ) from exc
    return MessagesMarkedRead(count=count)


@router.get("/icebreakers")
def get_icebreakers(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    match = db.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    if current_user.id not in (match.user_a_id, match.user_b_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant in this match")

    other_user_id = match.user_b_id if match.user_a_id == current_user.id else match.user_a_id
    other_user = db.get(User, other_user_id)
    if not other_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")

    from app.services.llm_matching_service import generate_llm_icebreakers
    return generate_llm_icebreakers(current_user, other_user)

