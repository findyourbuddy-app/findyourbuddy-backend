import secrets
from datetime import date, datetime, timedelta, timezone
from app.core.datetime_utils import utcnow

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import hash_password
from app.models.user import User
from app.models.user_photo import UserPhoto
from app.schemas.user import UserUpdate


def _age_from_birth_date(birth_date: date, today: date | None = None) -> int:
    today = today or date.today()
    had_birthday_this_year = (today.month, today.day) >= (birth_date.month, birth_date.day)
    return today.year - birth_date.year - (0 if had_birthday_this_year else 1)


def update_profile(db: Session, user: User, data: UserUpdate) -> User:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    if data.date_of_birth is not None:
        user.age = _age_from_birth_date(data.date_of_birth)

    db.commit()
    db.refresh(user)
    return user


def update_trust_suspensions(db: Session) -> int:
    """Tracks how long each active user's trust_score has stayed below the
    suspension threshold, and suspends (is_active=False) accounts that have
    stayed low for trust_score_suspension_grace_days straight -- a single bad
    night shouldn't nuke an account, only a sustained pattern should."""
    settings = get_settings()
    threshold = settings.trust_score_suspension_threshold
    grace = timedelta(days=settings.trust_score_suspension_grace_days)
    now = utcnow()
    cutoff = now - grace

    # Mark the start of the low-trust window for users newly below threshold
    db.execute(
        update(User)
        .where(User.is_active.is_(True), User.trust_score < threshold, User.trust_score_low_since.is_(None))
        .values(trust_score_low_since=now)
    )

    # Suspend users that have been low for longer than the grace period
    result = db.execute(
        update(User)
        .where(User.is_active.is_(True), User.trust_score < threshold, User.trust_score_low_since <= cutoff)
        .values(is_active=False)
    )
    suspended: int = result.rowcount

    # Clear the low-since marker for users that recovered
    db.execute(
        update(User)
        .where(User.is_active.is_(True), User.trust_score >= threshold, User.trust_score_low_since.is_not(None))
        .values(trust_score_low_since=None)
    )

    db.commit()
    return suspended


from app.services.media_service import get_media_storage


def delete_account(db: Session, user: User) -> None:
    """Soft-deletes the account: deactivates login, scrubs personal data,
    and frees up the email for reuse. Matches/messages/events the user was
    part of are left intact for the other side's history."""
    media_storage = get_media_storage()

    # Delete main profile photo and voice note from storage if present
    if user.photo_url:
        media_storage.delete(user.photo_url)
        user.photo_url = None
    if user.voice_note_url:
        media_storage.delete(user.voice_note_url)
        user.voice_note_url = None

    # Delete additional user photos from storage and DB
    user_photos = db.query(UserPhoto).filter(UserPhoto.user_id == user.id).all()
    for photo in user_photos:
        if photo.photo_url:
            media_storage.delete(photo.photo_url)
    db.query(UserPhoto).filter(UserPhoto.user_id == user.id).delete()

    user.is_active = False
    user.token_version += 1
    user.email = f"deleted-user-{user.id}-{secrets.token_hex(4)}@findyourbuddy.invalid"
    user.phone_number = f"del-{secrets.token_hex(8)}"
    user.hashed_password = hash_password(secrets.token_urlsafe(32))
    user.display_name = "Silinmiş Kullanıcı"
    user.bio = None
    user.university = None
    user.zodiac_sign = None
    user.looking_for = None
    user.about_me_prompt = None
    user.occupation = None
    user.gender = None
    user.height = None
    user.political_views = None
    user.beliefs = None
    user.verification_status = "unverified"
    user.interests = []
    user.hobbies = []
    user.languages_spoken = []
    user.hidden_fields = []
    user.latitude = None
    user.longitude = None
    db.commit()
