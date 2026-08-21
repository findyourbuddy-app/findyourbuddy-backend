import logging
import secrets
import string
from datetime import datetime, timezone

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

class PhoneNumberAlreadyRegisteredError(Exception):
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
    normalized_email = data.email.strip().lower()
    if db.query(User).filter(User.email == normalized_email).first() is not None:
        raise EmailAlreadyRegisteredError(normalized_email)
    
    phone = data.phone_number.strip() if data.phone_number and data.phone_number.strip() else None
    if phone:
        if db.query(User).filter(User.phone_number == phone).first() is not None:
            raise PhoneNumberAlreadyRegisteredError(phone)
    else:
        phone = f"unknown-{secrets.token_hex(6)}"

    inviter: User | None = None
    if data.referral_code:
        inviter = (
            db.query(User).filter(User.referral_code == data.referral_code.strip().upper()).first()
        )

    user = User(
        email=normalized_email,
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        accepted_terms_at=datetime.now(timezone.utc),
        referral_code=_generate_referral_code(db),
        referred_by_id=inviter.id if inviter is not None else None,
        bonus_swipe_credits=REFERRAL_BONUS_SWIPES if inviter is not None else 0,
        phone_number=phone,
        phone_verified=False,
        hobbies=[],
    )
    db.add(user)
    if inviter is not None:
        inviter.bonus_swipe_credits += REFERRAL_BONUS_SWIPES
    db.commit()
    db.refresh(user)
    logger.info("user registered user_id=%s referred_by=%s", user.id, user.referred_by_id)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    normalized_email = email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError(normalized_email)
    return user


def request_password_reset(db: Session, email: str) -> str | None:
    normalized_email = email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email, User.is_active.is_(True)).first()
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
                PasswordResetToken.expires_at < datetime.now(timezone.utc),
            )
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted_count


def authenticate_or_create_firebase_user(db: Session, decoded_token: dict) -> User:
    """Finds or provisions a User from a verified Firebase ID token."""
    firebase_uid = decoded_token.get("uid")
    if not firebase_uid:
        raise ValueError("Decoded Firebase token does not contain a valid uid")

    email = decoded_token.get("email")
    phone_number = decoded_token.get("phone_number")
    display_name = decoded_token.get("name") or (phone_number or "Buddy User")

    # 1. Search by firebase_uid
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if user:
        if not user.phone_verified and phone_number:
            user.phone_verified = True
            db.commit()
        return user

    # 2. Search by phone_number if available
    if phone_number:
        user = db.query(User).filter(User.phone_number == phone_number).first()
        if user:
            user.firebase_uid = firebase_uid
            user.phone_verified = True
            db.commit()
            return user

    # 3. Search by email if available
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.firebase_uid = firebase_uid
            if phone_number and not user.phone_verified:
                user.phone_verified = True
            db.commit()
            return user

    # 4. Provision new user if not found
    fallback_email = email or f"{firebase_uid}@firebase.findyourbuddy.app"
    fallback_phone = phone_number or f"firebase-{secrets.token_hex(8)}"

    new_user = User(
        email=fallback_email,
        phone_number=fallback_phone,
        hashed_password=hash_password(secrets.token_hex(32)),
        display_name=display_name,
        firebase_uid=firebase_uid,
        phone_verified=True if phone_number is not None else False,
        referral_code=_generate_referral_code(db),
        accepted_terms_at=datetime.now(timezone.utc),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
