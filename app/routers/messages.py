from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.notifications import NotificationSender, get_notification_sender
from app.database import get_db
from app.models.match import Match
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate, MessageRead
from app.services.message_service import (
    MatchNotFoundError,
    MessageBlockedError,
    NotMatchParticipantError,
    list_messages,
    send_message,
)
from app.services.notification_service import notify_new_message

router = APIRouter(prefix="/matches/{match_id}/messages", tags=["messages"])


@router.get("/", response_model=list[MessageRead])
def get_messages(
    match_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Message]:
    try:
        return list_messages(db, match_id, current_user.id)
    except MatchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found"
        ) from exc
    except NotMatchParticipantError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant in this match"
        ) from exc


@router.post("/", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
def post_message(
    match_id: int,
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    notification_sender: NotificationSender = Depends(get_notification_sender),
) -> Message:
    try:
        message = send_message(db, match_id, current_user.id, data.content)
    except MatchNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Match not found"
        ) from exc
    except NotMatchParticipantError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant in this match"
        ) from exc
    except MessageBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message contains blocked content",
        ) from exc

    match = db.get(Match, match_id)
    recipient_id = match.user_b_id if match.user_a_id == current_user.id else match.user_a_id
    notify_new_message(notification_sender, message, recipient_id)

    return message
