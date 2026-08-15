import logging
import secrets
import string
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)

REFERRAL_BONUS_SWIPES = 5
_REFERRAL_CODE_ALPHABET = string.ascii_uppercase + string.digits


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidOrExpiredResetTokenError(Exception):
    pass


class IncorrectCurrentPasswordError(Exception):
    pass


def _generate_referral_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(_REFERRAL_CODE_ALPHABET) for _ in range(7))
        if db.query(User).filter(User.referral_code == code).first() is None:
            return code


def register_user(db: Session, data: UserCreate) -> User:
    if db.query(User).filter(User.email == data.email).first() is not None:
        raise EmailAlreadyRegisteredError(data.email)

    inviter: User | None = None
    if data.referral_code:
        inviter = (
            db.query(User).filter(User.referral_code == data.referral_code.strip().upper()).first()
        )

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        accepted_terms_at=datetime.utcnow(),
        referral_code=_generate_referral_code(db),
        referred_by_id=inviter.id if inviter is not None else None,
        bonus_swipe_credits=REFERRAL_BONUS_SWIPES if inviter is not None else 0,
    )
    db.add(user)
    if inviter is not None:
        inviter.bonus_swipe_credits += REFERRAL_BONUS_SWIPES
    db.commit()
    db.refresh(user)
    logger.info("user registered user_id=%s referred_by=%s", user.id, user.referred_by_id)
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


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.hashed_password):
        raise IncorrectCurrentPasswordError(user.id)
    user.hashed_password = hash_password(new_password)
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
