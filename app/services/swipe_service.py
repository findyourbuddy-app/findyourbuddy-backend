from datetime import datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.geo import haversine_km
from app.models.event_attendance import EventAttendance
from app.models.swipe import Swipe, SwipeDirection
from app.models.user import User
from app.schemas.swipe import SwipeCreate
from app.services.event_service import join_event
from app.services.safety_service import blocked_user_ids, is_blocked
from app.services.subscription_service import is_premium, premium_user_ids


class DailySwipeLimitExceededError(Exception):
    pass


class DailySuperLikeLimitExceededError(Exception):
    pass


class DuplicateSwipeError(Exception):
    pass


class BlockedUserError(Exception):
    pass


def _swipes_made_today(db: Session, swiper_id: int, direction: SwipeDirection | None = None) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    query = db.query(Swipe).filter(Swipe.swiper_id == swiper_id, Swipe.created_at >= today_start)
    if direction is not None:
        query = query.filter(Swipe.direction == direction)
    return query.count()


def _likes_made_today(db: Session, swiper_id: int) -> int:
    """Passes are free and unlimited; only LIKE/SUPER_LIKE count against the
    daily allowance (the super-like sub-quota is enforced separately)."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(Swipe)
        .filter(
            Swipe.swiper_id == swiper_id,
            Swipe.created_at >= today_start,
            Swipe.direction.in_([SwipeDirection.LIKE, SwipeDirection.SUPER_LIKE]),
        )
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


def get_swipe_quota(db: Session, swiper_id: int) -> dict:
    premium = is_premium(db, swiper_id)
    settings = get_settings()
    super_like_limit = settings.premium_daily_super_like_limit if premium else settings.daily_super_like_limit
    return {
        "is_premium": premium,
        "swipes_used_today": _likes_made_today(db, swiper_id),
        "swipe_limit": None if premium else settings.daily_swipe_limit,
        "super_likes_used_today": _swipes_made_today(db, swiper_id, SwipeDirection.SUPER_LIKE),
        "super_like_limit": super_like_limit,
    }


def record_swipe(db: Session, swiper_id: int, data: SwipeCreate) -> Swipe:
    premium = is_premium(db, swiper_id)
    settings = get_settings()

    if (
        data.direction != SwipeDirection.PASS
        and not premium
        and _likes_made_today(db, swiper_id) >= settings.daily_swipe_limit
    ):
        raise DailySwipeLimitExceededError(swiper_id)

    if data.direction == SwipeDirection.SUPER_LIKE:
        super_like_limit = (
            settings.premium_daily_super_like_limit if premium else settings.daily_super_like_limit
        )
        if _swipes_made_today(db, swiper_id, SwipeDirection.SUPER_LIKE) >= super_like_limit:
            raise DailySuperLikeLimitExceededError(swiper_id)

    if is_blocked(db, swiper_id, data.target_id):
        raise BlockedUserError(data.target_id)

    if _already_swiped(db, swiper_id, data.target_id, data.event_id):
        raise DuplicateSwipeError(data.target_id)

    join_event(db, data.event_id, swiper_id)

    swipe = Swipe(swiper_id=swiper_id, **data.model_dump())
    db.add(swipe)
    db.commit()
    db.refresh(swipe)
    
    # Gracefully remove target_id from the swiper's cached candidate list in Redis
    from app.services.cache_service import CacheService
    CacheService.remove_swiped_candidate(swiper_id, data.event_id, data.target_id)
    
    return swipe


def list_swipe_candidates(
    db: Session,
    event_id: int,
    swiper_id: int,
    min_age: int | None = None,
    max_age: int | None = None,
    max_distance_km: float | None = None,
) -> list[User]:
    swiper = db.get(User, swiper_id)
    if swiper is None:
        return []

    # Try to load candidate IDs from Redis cache first
    from app.services.cache_service import CacheService
    
    # We only cache the default view (when filters min_age/max_age/max_distance_km are empty)
    # to avoid caching multiple filter permutations.
    is_default_query = min_age is None and max_age is None and max_distance_km is None
    
    if is_default_query:
        cached_ids = CacheService.get_cached_candidates(swiper_id, event_id)
        if cached_ids is not None:
            # Fetch users in bulk
            users = db.query(User).filter(User.id.in_(cached_ids)).all()
            user_map = {user.id: user for user in users}
            # Return users in the exact order stored in Redis cache
            return [user_map[uid] for uid in cached_ids if uid in user_map]

    if not is_premium(db, swiper_id):
        min_age = max_age = max_distance_km = None

    already_swiped_target_ids = db.query(Swipe.target_id).filter(
        Swipe.swiper_id == swiper_id, Swipe.event_id == event_id
    )
    attending_user_ids = db.query(EventAttendance.user_id).filter(
        EventAttendance.event_id == event_id
    )
    excluded_ids = {swiper_id, *blocked_user_ids(db, swiper_id)}
    query = db.query(User).filter(
        User.id.in_(attending_user_ids),
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
        if swiper.latitude is not None and swiper.longitude is not None:
            candidates = [
                user
                for user in candidates
                if user.latitude is not None
                and user.longitude is not None
                and haversine_km(swiper.latitude, swiper.longitude, user.latitude, user.longitude)
                <= max_distance_km
            ]

    boosted_ids = premium_user_ids(db, [user.id for user in candidates])
    now = datetime.utcnow()
    
    # Sort candidates: Active Spotlight Boost users first, then Premium users, then sub-sorted by recommendation score (descending)
    from app.services.recommendation_service import RecommendationService
    
    candidates.sort(
        key=lambda user: (
            not (user.boosted_until is not None and user.boosted_until > now),  # Active Spotlight Boost users first
            user.id not in boosted_ids,  # Premium users next
            -RecommendationService.score_candidate(swiper, user)  # Recommendation score
        )
    )

    # Store in Redis cache if it's the default query
    if is_default_query:
        CacheService.set_cached_candidates(swiper_id, event_id, [u.id for u in candidates])

    return candidates


def list_incoming_likes(db: Session, user_id: int, event_id: int | None = None) -> list[dict]:
    """Users who liked `user_id` but haven't been reciprocated yet
    (a mutual like already creates a Match, so this is inherently pending-only)."""
    # 1. Fetch swipes that liked target user
    query = db.query(Swipe).filter(
        Swipe.target_id == user_id,
        Swipe.direction.in_([SwipeDirection.LIKE, SwipeDirection.SUPER_LIKE]),
    )
    if event_id is not None:
        query = query.filter(Swipe.event_id == event_id)
        
    swipes = query.all()
    
    # Exclude blocked users and user's own ID
    excluded_ids = {user_id, *blocked_user_ids(db, user_id)}
    
    res = []
    # Use cache to avoid redundant db queries for swiper details
    user_cache = {}
    
    for swipe in swipes:
        if swipe.swiper_id in excluded_ids:
            continue
            
        # Check if target user has already swiped back on this swiper for this event
        already_swiped = db.query(Swipe).filter(
            Swipe.swiper_id == user_id,
            Swipe.target_id == swipe.swiper_id,
            Swipe.event_id == swipe.event_id
        ).first()
        
        if already_swiped is not None:
            continue
            
        # Get swiper user details
        if swipe.swiper_id not in user_cache:
            user_cache[swipe.swiper_id] = db.get(User, swipe.swiper_id)
            
        swiper_user = user_cache[swipe.swiper_id]
        if swiper_user and swiper_user.is_active:
            res.append({
                "user": swiper_user,
                "event_id": swipe.event_id
            })
            
    return res
