import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.user_photo import UserPhoto
from app.schemas.device_token import DeviceTokenCreate, DeviceTokenRead
from app.schemas.export import UserDataExport
from app.schemas.user import UserRead, UserUpdate
from app.schemas.user_photo import UserPhotoRead
from app.services.device_token_service import register_device_token, unregister_device_token
from app.services.export_service import export_user_data
from app.services.media_service import MediaStorage, get_media_storage
from app.services.media_validation import ImageTooLargeError, InvalidImageError, validate_image
from app.services.user_photo_service import (
    PhotoNotFoundError,
    TooManyPhotosError,
    add_photo,
    list_photos,
    remove_photo,
)
from app.services.user_service import delete_account, update_profile

router = APIRouter(prefix="/users", tags=["users"])


def _upload_validated_photo(file: UploadFile, storage: MediaStorage) -> str:
    try:
        data = validate_image(file.file)
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image file"
        ) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large"
        ) from exc

    return storage.upload(io.BytesIO(data), file.filename or "photo")


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


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_current_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    delete_account(db, current_user)


@router.get("/me/export", response_model=UserDataExport)
def export_current_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserDataExport:
    return export_user_data(db, current_user)


@router.post(
    "/me/device-tokens", response_model=DeviceTokenRead, status_code=status.HTTP_201_CREATED
)
def register_current_user_device_token(
    data: DeviceTokenCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceTokenRead:
    return register_device_token(db, current_user.id, data.token)


@router.delete("/me/device-tokens/{token}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_current_user_device_token(
    token: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    unregister_device_token(db, current_user.id, token)


@router.post("/me/photo", response_model=UserRead)
def upload_profile_photo(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> User:
    current_user.photo_url = _upload_validated_photo(file, storage)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/photos", response_model=list[UserPhotoRead])
def list_my_photos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UserPhoto]:
    return list_photos(db, current_user.id)


@router.post("/me/photos", response_model=UserPhotoRead, status_code=status.HTTP_201_CREATED)
def upload_my_photo(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> UserPhoto:
    photo_url = _upload_validated_photo(file, storage)
    try:
        return add_photo(db, current_user.id, photo_url)
    except TooManyPhotosError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Photo limit reached"
        ) from exc


@router.delete("/me/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_photo(
    photo_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        remove_photo(db, current_user.id, photo_id)
    except PhotoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found") from exc
