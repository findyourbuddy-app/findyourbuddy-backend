import logging
import math

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.match import Match
from app.models.swipe import Swipe, SwipeDirection
from app.models.user import User

logger = logging.getLogger(__name__)

_EARTH_RADIUS_KM = 6371.0


def _ordered_pair(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    return (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)


def _mutual_like_exists(db: Session, user_a_id: int, user_b_id: int, event_id: int) -> bool:
    like_from_a = (
        db.query(Swipe)
        .filter(
            Swipe.swiper_id == user_a_id,
            Swipe.target_id == user_b_id,
            Swipe.event_id == event_id,
            Swipe.direction == SwipeDirection.LIKE,
        )
        .first()
    )
    like_from_b = (
        db.query(Swipe)
        .filter(
            Swipe.swiper_id == user_b_id,
            Swipe.target_id == user_a_id,
            Swipe.event_id == event_id,
            Swipe.direction == SwipeDirection.LIKE,
        )
        .first()
    )
    return like_from_a is not None and like_from_b is not None


def _existing_match(db: Session, user_a_id: int, user_b_id: int, event_id: int) -> Match | None:
    return (
        db.query(Match)
        .filter(
            Match.event_id == event_id,
            Match.user_a_id == user_a_id,
            Match.user_b_id == user_b_id,
        )
        .first()
    )


def _interest_score(user_a: User, user_b: User) -> float:
    shared = set(user_a.interests) & set(user_b.interests)
    total = set(user_a.interests) | set(user_b.interests)
    return len(shared) / len(total) if total else 0.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _distance_score(user_a: User, user_b: User) -> float:
    has_coordinates = None not in (
        user_a.latitude,
        user_a.longitude,
        user_b.latitude,
        user_b.longitude,
    )
    if not has_coordinates:
        return 0.0

    max_distance_km = get_settings().match_max_distance_km
    distance_km = _haversine_km(
        user_a.latitude, user_a.longitude, user_b.latitude, user_b.longitude
    )
    return max(0.0, 1 - distance_km / max_distance_km)


def _calculate_score(db: Session, user_a_id: int, user_b_id: int) -> float:
    user_a = db.get(User, user_a_id)
    user_b = db.get(User, user_b_id)
    settings = get_settings()

    return (
        settings.match_common_interest_weight * _interest_score(user_a, user_b)
        + settings.match_distance_weight * _distance_score(user_a, user_b)
    )


def try_create_match(db: Session, swiper_id: int, target_id: int, event_id: int) -> Match | None:
    if not _mutual_like_exists(db, swiper_id, target_id, event_id):
        return None

    user_a_id, user_b_id = _ordered_pair(swiper_id, target_id)
    if _existing_match(db, user_a_id, user_b_id, event_id) is not None:
        return None

    match = Match(
        event_id=event_id,
        user_a_id=user_a_id,
        user_b_id=user_b_id,
        score=_calculate_score(db, user_a_id, user_b_id),
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    logger.info("match created match_id=%s event_id=%s", match.id, event_id)
    return match


def list_matches_for_user(db: Session, user_id: int) -> list[Match]:
    return (
        db.query(Match)
        .filter(or_(Match.user_a_id == user_id, Match.user_b_id == user_id))
        .order_by(Match.created_at.desc())
        .all()
    )
