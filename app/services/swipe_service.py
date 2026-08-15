from datetime import datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.geo import haversine_km
from app.models.swipe import Swipe, SwipeDirection
from app.models.user import User
from app.schemas.swipe import SwipeCreate
from app.services.safety_service import blocked_user_ids, is_blocked


class DailySwipeLimitExceededError(Exception):
    pass


class DuplicateSwipeError(Exception):
    pass


class BlockedUserError(Exception):
    pass


def _swipes_made_today(db: Session, swiper_id: int) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(Swipe)
        .filter(Swipe.swiper_id == swiper_id, Swipe.created_at >= today_start)
        .count()
    )


def _already_swiped(db: Session, swiper_id: int, target_id: int, event_id: int) -> bool:
    existing = (
        db.query(Swipe)
        .filter(
            Swipe.swiper_id == swiper_id,
            Swipe.target_id == target_id,
            Swipe.event_id == event_id,
        )
        .first()
    )
    return existing is not None


def record_swipe(db: Session, swiper_id: int, data: SwipeCreate) -> Swipe:
    daily_limit = get_settings().daily_swipe_limit
    if _swipes_made_today(db, swiper_id) >= daily_limit:
        raise DailySwipeLimitExceededError(swiper_id)

    if is_blocked(db, swiper_id, data.target_id):
        raise BlockedUserError(data.target_id)

    if _already_swiped(db, swiper_id, data.target_id, data.event_id):
        raise DuplicateSwipeError(data.target_id)

    swipe = Swipe(swiper_id=swiper_id, **data.model_dump())
    db.add(swipe)
    db.commit()
    db.refresh(swipe)
    return swipe


def list_swipe_candidates(
    db: Session,
    event_id: int,
    swiper_id: int,
    min_age: int | None = None,
    max_age: int | None = None,
    max_distance_km: float | None = None,
) -> list[User]:
    already_swiped_target_ids = db.query(Swipe.target_id).filter(
        Swipe.swiper_id == swiper_id, Swipe.event_id == event_id
    )
    excluded_ids = {swiper_id, *blocked_user_ids(db, swiper_id)}
    query = db.query(User).filter(
        User.id.notin_(already_swiped_target_ids),
        User.id.notin_(excluded_ids),
        User.is_active.is_(True),
    )
    if min_age is not None:
        query = query.filter(User.age.is_not(None), User.age >= min_age)
    if max_age is not None:
        query = query.filter(User.age.is_not(None), User.age <= max_age)

    candidates = query.all()

    if max_distance_km is not None:
        swiper = db.get(User, swiper_id)
        if swiper is not None and swiper.latitude is not None and swiper.longitude is not None:
            candidates = [
                user
                for user in candidates
                if user.latitude is not None
                and user.longitude is not None
                and haversine_km(swiper.latitude, swiper.longitude, user.latitude, user.longitude)
                <= max_distance_km
            ]

    return candidates


def list_incoming_likes(db: Session, event_id: int, user_id: int) -> list[User]:
    """Users who liked `user_id` for this event but haven't been reciprocated yet
    (a mutual like already creates a Match, so this is inherently pending-only)."""
    already_swiped_target_ids = db.query(Swipe.target_id).filter(
        Swipe.swiper_id == user_id, Swipe.event_id == event_id
    )
    excluded_ids = {user_id, *blocked_user_ids(db, user_id)}
    liker_ids = db.query(Swipe.swiper_id).filter(
        Swipe.target_id == user_id,
        Swipe.event_id == event_id,
        Swipe.direction == SwipeDirection.LIKE,
    )
    return (
        db.query(User)
        .filter(
            User.id.in_(liker_ids),
            User.id.notin_(already_swiped_target_ids),
            User.id.notin_(excluded_ids),
            User.is_active.is_(True),
        )
        .all()
    )
