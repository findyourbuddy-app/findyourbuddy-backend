from sqlalchemy.orm import Session

from app.models.user_photo import UserPhoto

MAX_PHOTOS = 6


class TooManyPhotosError(Exception):
    pass


class PhotoNotFoundError(Exception):
    pass


def list_photos(db: Session, user_id: int) -> list[UserPhoto]:
    return (
        db.query(UserPhoto)
        .filter(UserPhoto.user_id == user_id)
        .order_by(UserPhoto.position)
        .all()
    )


def add_photo(db: Session, user_id: int, photo_url: str) -> UserPhoto:
    existing_count = db.query(UserPhoto).filter(UserPhoto.user_id == user_id).count()
    if existing_count >= MAX_PHOTOS:
        raise TooManyPhotosError(user_id)

    photo = UserPhoto(user_id=user_id, photo_url=photo_url, position=existing_count)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


def remove_photo(db: Session, user_id: int, photo_id: int) -> None:
    photo = (
        db.query(UserPhoto)
        .filter(UserPhoto.id == photo_id, UserPhoto.user_id == user_id)
        .first()
    )
    if photo is None:
        raise PhotoNotFoundError(photo_id)

    db.delete(photo)
    db.commit()
