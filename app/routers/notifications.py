from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead, NotificationsMarkedRead
from app.services.notification_service import list_notifications, mark_notifications_as_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=list[NotificationRead])
def list_my_notifications(
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    return list_notifications(db, current_user.id, skip=skip, limit=limit)


@router.patch("/read", response_model=NotificationsMarkedRead)
def mark_my_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationsMarkedRead:
    count = mark_notifications_as_read(db, current_user.id)
    return NotificationsMarkedRead(count=count)
