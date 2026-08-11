from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate
from app.services.media_service import MediaStorage, get_media_storage
from app.services.user_service import update_profile

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_current_user(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return update_profile(db, current_user, data)


@router.post("/me/photo", response_model=UserRead)
def upload_profile_photo(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> User:
    current_user.photo_url = storage.upload(file.file, file.filename or "photo")
    db.commit()
    db.refresh(current_user)
    return current_user
