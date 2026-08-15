from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_staff_user
from app.database import get_db
from app.models.user import User
from app.schemas.admin import UserActiveStatusUpdate
from app.schemas.user import UserRead
from app.services.admin_service import UserNotFoundError, list_users, set_user_active_status

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserRead])
def list_all_users(
    skip: int = 0,
    limit: int = 50,
    _staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
) -> list[User]:
    return list_users(db, skip=skip, limit=limit)


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user_active_status(
    user_id: int,
    data: UserActiveStatusUpdate,
    _staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
) -> User:
    try:
        return set_user_active_status(db, user_id, data.is_active)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
