from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.notifications import NotificationSender, get_notification_sender
from app.database import get_db
from app.models.swipe import Swipe, SwipeDirection
from app.models.user import User
from app.schemas.swipe import SwipeCreate, SwipeRead
from app.schemas.user import UserRead
from app.services.matching_service import try_create_match
from app.services.notification_service import notify_match_created
from app.services.swipe_service import (
    BlockedUserError,
    DailySwipeLimitExceededError,
    DuplicateSwipeError,
    list_swipe_candidates,
    record_swipe,
)

router = APIRouter(prefix="/swipes", tags=["swipes"])


@router.post("/", response_model=SwipeRead, status_code=status.HTTP_201_CREATED)
def create_swipe(
    data: SwipeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    notification_sender: NotificationSender = Depends(get_notification_sender),
) -> Swipe:
    try:
        swipe = record_swipe(db, current_user.id, data)
    except DailySwipeLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily swipe limit reached",
        ) from exc
    except DuplicateSwipeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already swiped on this user for this event",
        ) from exc
    except BlockedUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot swipe on a blocked user",
        ) from exc

    if swipe.direction == SwipeDirection.LIKE:
        match = try_create_match(db, current_user.id, data.target_id, data.event_id)
        if match is not None:
            notify_match_created(notification_sender, match)

    return swipe


@router.get("/candidates", response_model=list[UserRead])
def get_swipe_candidates(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[User]:
    return list_swipe_candidates(db, event_id=event_id, swiper_id=current_user.id)
