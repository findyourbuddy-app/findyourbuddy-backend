import logging
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidOrExpiredResetTokenError(Exception):
    pass


def register_user(db: Session, data: UserCreate) -> User:
    if db.query(User).filter(User.email == data.email).first() is not None:
        raise EmailAlreadyRegisteredError(data.email)

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        accepted_terms_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("user registered user_id=%s", user.id)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError(email)
    return user


def request_password_reset(db: Session, email: str) -> str | None:
    user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
    if user is None:
        return None

    reset_token = PasswordResetToken(user_id=user.id)
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)
    return reset_token.token


def reset_password(db: Session, token: str, new_password: str) -> None:
    reset_token = db.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()
    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.expires_at < datetime.utcnow()
    ):
        raise InvalidOrExpiredResetTokenError(token)

    user = db.get(User, reset_token.user_id)
    user.hashed_password = hash_password(new_password)
    reset_token.used_at = datetime.utcnow()
    db.commit()


def delete_expired_reset_tokens(db: Session) -> int:
    """Purges password reset tokens that are either used or past their
    expiry, so the table doesn't grow forever."""
    deleted_count = (
        db.query(PasswordResetToken)
        .filter(
            or_(
                PasswordResetToken.used_at.is_not(None),
                PasswordResetToken.expires_at < datetime.utcnow(),
            )
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted_count
