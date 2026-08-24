from datetime import datetime, timezone
from app.core.datetime_utils import utcnow

from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.geo import haversine_km
from app.models.event import Event
from app.models.event_attendance import EventAttendance
from app.models.swipe import Swipe, SwipeDirection
from app.models.user import User
from app.schemas.swipe import SwipeCreate
from app.services.cache_service import CacheService
from app.services.event_service import join_event
from app.services.recommendation_service import RecommendationService
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
    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    query = db.query(Swipe).filter(Swipe.swiper_id == swiper_id, Swipe.created_at >= today_start)
    if direction is not None:
        query = query.filter(Swipe.direction == direction)
    return query.count()


def _likes_made_today(db: Session, swiper_id: int) -> int:
    """Passes are free and unlimited; only LIKE/SUPER_LIKE count against the
    daily allowance (the super-like sub-quota is enforced separately)."""
    today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
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
    return db.query(
        exists().where(
            Swipe.swiper_id == swiper_id,
            Swipe.target_id == target_id,
            Swipe.event_id == event_id,
        )
    ).scalar()


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
    CacheService.remove_swiped_candidate(swiper_id, data.event_id, data.target_id)
    
    return swipe


def list_swipe_candidates(
    db: Session,
    event_id: int,
    swiper_id: int,
    min_age: int | None = None,
    max_age: int | None = None,
    max_distance_km: float | None = None,
    gender_preference: str | None = None,
    university: str | None = None,
    zodiac_sign: str | None = None,
    is_verified_only: bool | None = None,
    has_voice_note: bool | None = None,
    min_trust_score: int | None = None,
) -> list[User]:
    swiper = db.get(User, swiper_id)
    if swiper is None:
        return []

    is_default_query = (
        min_age is None
        and max_age is None
        and max_distance_km is None
        and gender_preference is None
        and university is None
        and zodiac_sign is None
        and not is_verified_only
        and not has_voice_note
        and min_trust_score is None
    )
    
    if is_default_query:
        cached_ids = CacheService.get_cached_candidates(swiper_id, event_id)
        if cached_ids is not None:
            users = db.query(User).filter(User.id.in_(cached_ids)).all()
            user_map = {user.id: user for user in users}
            return [user_map[uid] for uid in cached_ids if uid in user_map]

    if not is_premium(db, swiper_id):
        min_age = max_age = max_distance_km = gender_preference = university = zodiac_sign = min_trust_score = None
        is_verified_only = has_voice_note = False

    event = db.get(Event, event_id)
    is_group_or_system = event is not None and (event.is_group_event or event.creator_id is None)

    if not is_group_or_system and max_distance_km is None:
        max_distance_km = get_settings().match_max_distance_km

    already_swiped_target_ids = db.query(Swipe.target_id).filter(
        Swipe.swiper_id == swiper_id, Swipe.event_id == event_id
    )
    excluded_ids = {swiper_id, *blocked_user_ids(db, swiper_id)}

    query = db.query(User).filter(
        User.id.notin_(already_swiped_target_ids),
        User.id.notin_(excluded_ids),
        User.is_active.is_(True),
    )

    if is_group_or_system:
        attending_user_ids = db.query(EventAttendance.user_id).filter(
            EventAttendance.event_id == event_id, EventAttendance.status.in_(["approved", "pending"])
        )
        query = query.filter(User.id.in_(attending_user_ids))

    if min_age is not None:
        query = query.filter(User.age.is_not(None), User.age >= min_age)
    if max_age is not None:
        query = query.filter(User.age.is_not(None), User.age <= max_age)
    if gender_preference and gender_preference.lower() in ("female", "male", "other"):
        query = query.filter(User.gender == gender_preference)
    if university:
        query = query.filter(User.university.ilike(f"%{university.strip()}%"))
    if zodiac_sign and zodiac_sign != "Tümü":
        clean_zodiac = zodiac_sign.split()[0]
        query = query.filter(User.zodiac_sign == clean_zodiac)
    if is_verified_only:
        query = query.filter(User.is_verified.is_(True))
    if has_voice_note:
        query = query.filter(User.voice_note_url.is_not(None))
    if min_trust_score is not None and min_trust_score > 0:
        query = query.filter(User.trust_score >= min_trust_score)

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
    now = utcnow()

    # Sort candidates: Active Spotlight Boost users first, then Premium users, then sub-sorted by recommendation score (descending)
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


def get_upcoming_own_event_titles(db: Session, user_ids: list[int]) -> dict[int, str]:
    """For each user, the title of the soonest upcoming non-group event they
    created (if any) -- shown on their swipe card. 1:1 events don't scope
    candidates by attendance to the active event (see is_group_or_system
    above), so candidates aren't actually tied to it; surfacing what each
    person themselves is hosting is the only per-candidate event context
    that's meaningful here."""
    if not user_ids:
        return {}
    events = (
        db.query(Event)
        .filter(
            Event.creator_id.in_(user_ids),
            Event.is_group_event.is_(False),
            Event.starts_at >= utcnow(),
        )
        .order_by(Event.starts_at)
        .all()
    )
    titles: dict[int, str] = {}
    for event in events:
        if event.creator_id not in titles:
            titles[event.creator_id] = event.title
    return titles


def list_incoming_likes(
    db: Session,
    user_id: int,
    event_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    """Users who liked `user_id` but haven't been reciprocated yet
    (a mutual like already creates a Match, so this is inherently pending-only)."""
    query = db.query(Swipe).filter(
        Swipe.target_id == user_id,
        Swipe.direction.in_([SwipeDirection.LIKE, SwipeDirection.SUPER_LIKE]),
    )
    if event_id is not None:
        query = query.filter(Swipe.event_id == event_id)
    swipes = query.all()

    excluded_ids = {user_id, *blocked_user_ids(db, user_id)}
    already_swiped_pairs = {
        (target_id, ev_id)
        for target_id, ev_id in db.query(Swipe.target_id, Swipe.event_id)
        .filter(Swipe.swiper_id == user_id)
        .all()
    }

    candidate_swipes = [
        swipe
        for swipe in swipes
        if swipe.swiper_id not in excluded_ids
        and (swipe.swiper_id, swipe.event_id) not in already_swiped_pairs
    ]

    # Batch-fetch all relevant users in one query (no N+1)
    swiper_ids = {s.swiper_id for s in candidate_swipes}
    users_by_id = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(swiper_ids), User.is_active.is_(True)).all()
    }

    res = [
        {"user": users_by_id[swipe.swiper_id], "event_id": swipe.event_id}
        for swipe in candidate_swipes
        if swipe.swiper_id in users_by_id
    ]

    return res[skip : skip + limit]
