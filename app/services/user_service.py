import secrets

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.models.user_photo import UserPhoto
from app.schemas.user import UserUpdate


def update_profile(db: Session, user: User, data: UserUpdate) -> User:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


def delete_account(db: Session, user: User) -> None:
    """Soft-deletes the account: deactivates login, scrubs personal data,
    and frees up the email for reuse. Matches/messages/events the user was
    part of are left intact for the other side's history."""
    user.is_active = False
    user.email = f"deleted-user-{user.id}-{secrets.token_hex(4)}@findyourbuddy.invalid"
    user.hashed_password = hash_password(secrets.token_urlsafe(32))
    user.display_name = "Silinmiş Kullanıcı"
    user.bio = None
    user.interests = []
    user.latitude = None
    user.longitude = None
    user.photo_url = None
    db.query(UserPhoto).filter(UserPhoto.user_id == user.id).delete()
    db.commit()
