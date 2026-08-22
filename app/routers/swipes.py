from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_premium_user, get_current_user
from app.core.notifications import NotificationSender, get_notification_sender
from app.database import get_db
from app.models.swipe import SwipeDirection
from app.models.user import User
from app.schemas.swipe import LikerRead, SwipeCreate, SwipeQuota, SwipeRead
from app.schemas.user import UserPublic, UserRead
from app.services.matching_service import try_create_match
from app.services.notification_service import notify_match_created, notify_new_like
from app.services.swipe_service import (
    BlockedUserError,
    DailySuperLikeLimitExceededError,
    DailySwipeLimitExceededError,
    DuplicateSwipeError,
    get_swipe_quota,
    list_incoming_likes,
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
) -> SwipeRead:
    try:
        swipe = record_swipe(db, current_user.id, data)
    except DailySwipeLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily swipe limit reached",
        ) from exc
    except DailySuperLikeLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily super like limit reached",
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

    match_id: int | None = None
    matched_user: UserPublic | None = None
    if swipe.direction in (SwipeDirection.LIKE, SwipeDirection.SUPER_LIKE):
        match = try_create_match(db, current_user.id, data.target_id, data.event_id)
        if match is not None:
            notify_match_created(db, notification_sender, match)
            match_id = match.id
            matched_user = UserPublic.model_validate(db.get(User, data.target_id))
        else:
            notify_new_like(db, data.target_id)

    return SwipeRead.model_validate(swipe).model_copy(
        update={"match_id": match_id, "matched_user": matched_user}
    )


@router.get("/quota", response_model=SwipeQuota)
def get_quota(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return get_swipe_quota(db, current_user.id)


@router.get("/candidates", response_model=list[UserRead])
def get_swipe_candidates(
    event_id: int,
    min_age: int | None = None,
    max_age: int | None = None,
    max_distance_km: float | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[User]:
    return list_swipe_candidates(
        db,
        event_id=event_id,
        swiper_id=current_user.id,
        min_age=min_age,
        max_age=max_age,
        max_distance_km=max_distance_km,
    )


@router.get("/likes-received", response_model=list[LikerRead])
def get_incoming_likes(
    event_id: int | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return list_incoming_likes(db, event_id=event_id, user_id=current_user.id, skip=skip, limit=limit)
