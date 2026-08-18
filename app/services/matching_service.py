import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.geo import haversine_km
from app.models.match import Match
from app.models.message import Message
from app.models.swipe import Swipe, SwipeDirection
from app.models.user import User
from app.services.safety_service import blocked_user_ids

logger = logging.getLogger(__name__)


def _ordered_pair(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    return (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)


_LIKE_DIRECTIONS = (SwipeDirection.LIKE, SwipeDirection.SUPER_LIKE)


def _mutual_like_exists(db: Session, user_a_id: int, user_b_id: int, event_id: int) -> bool:
    like_from_a = (
        db.query(Swipe)
        .filter(
            Swipe.swiper_id == user_a_id,
            Swipe.target_id == user_b_id,
            Swipe.event_id == event_id,
            Swipe.direction.in_(_LIKE_DIRECTIONS),
        )
        .first()
    )
    like_from_b = (
        db.query(Swipe)
        .filter(
            Swipe.swiper_id == user_b_id,
            Swipe.target_id == user_a_id,
            Swipe.event_id == event_id,
            Swipe.direction.in_(_LIKE_DIRECTIONS),
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
    user_a_interests = user_a.interests or []
    user_b_interests = user_b.interests or []
    shared_interests = set(user_a_interests) & set(user_b_interests)
    total_interests = set(user_a_interests) | set(user_b_interests)
    interest_jaccard = len(shared_interests) / len(total_interests) if total_interests else 0.0

    user_a_hobbies = user_a.hobbies or []
    user_b_hobbies = user_b.hobbies or []
    shared_hobbies = set(user_a_hobbies) & set(user_b_hobbies)
    total_hobbies = set(user_a_hobbies) | set(user_b_hobbies)
    hobby_jaccard = len(shared_hobbies) / len(total_hobbies) if total_hobbies else 0.0

    if total_interests and total_hobbies:
        return 0.5 * interest_jaccard + 0.5 * hobby_jaccard
    elif total_hobbies:
        return hobby_jaccard
    return interest_jaccard


_ZODIAC_ELEMENTS = {
    "Koç": "Ateş", "Aslan": "Ateş", "Yay": "Ateş",
    "Boğa": "Toprak", "Başak": "Toprak", "Oğlak": "Toprak",
    "İkizler": "Hava", "Terazi": "Hava", "Kova": "Hava",
    "Yengeç": "Su", "Akrep": "Su", "Balık": "Su",
}

_ELEMENT_SYNERGY = {
    ("Ateş", "Ateş"): 1.0, ("Ateş", "Hava"): 1.0, ("Ateş", "Toprak"): 0.5, ("Ateş", "Su"): 0.3,
    ("Toprak", "Toprak"): 1.0, ("Toprak", "Su"): 1.0, ("Toprak", "Hava"): 0.5, ("Toprak", "Ateş"): 0.5,
    ("Hava", "Hava"): 1.0, ("Hava", "Ateş"): 1.0, ("Hava", "Su"): 0.5, ("Hava", "Toprak"): 0.5,
    ("Su", "Su"): 1.0, ("Su", "Toprak"): 1.0, ("Su", "Ateş"): 0.3, ("Su", "Hava"): 0.5,
}


def _zodiac_score(user_a: User, user_b: User) -> float:
    z1 = user_a.zodiac_sign
    z2 = user_b.zodiac_sign
    if not z1 or not z2:
        return 0.0
    elem1 = _ZODIAC_ELEMENTS.get(z1)
    elem2 = _ZODIAC_ELEMENTS.get(z2)
    if not elem1 or not elem2:
        return 0.0
    return _ELEMENT_SYNERGY.get((elem1, elem2), 0.5)


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
    distance_km = haversine_km(
        user_a.latitude, user_a.longitude, user_b.latitude, user_b.longitude
    )
    return max(0.0, 1 - distance_km / max_distance_km)


def _calculate_score(db: Session, user_a_id: int, user_b_id: int) -> float:
    user_a = db.get(User, user_a_id)
    user_b = db.get(User, user_b_id)
    settings = get_settings()

    interest_part = settings.match_common_interest_weight * _interest_score(user_a, user_b)
    distance_part = settings.match_distance_weight * _distance_score(user_a, user_b)
    zodiac_part = 0.2 * _zodiac_score(user_a, user_b)

    return interest_part + distance_part + zodiac_part


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


def _other_user_id(match: Match, user_id: int) -> int:
    return match.user_b_id if match.user_a_id == user_id else match.user_a_id


def list_matches_for_user(
    db: Session, user_id: int, skip: int = 0, limit: int = 50
) -> list[Match]:
    blocked_ids = set(blocked_user_ids(db, user_id))
    matches = (
        db.query(Match)
        .filter(
            or_(Match.user_a_id == user_id, Match.user_b_id == user_id),
            Match.is_active.is_(True),
        )
        .order_by(Match.created_at.desc())
        .all()
    )
    visible = [match for match in matches if _other_user_id(match, user_id) not in blocked_ids]
    return visible[skip : skip + limit]


def _last_message(db: Session, match_id: int) -> Message | None:
    return (
        db.query(Message)
        .filter(Message.match_id == match_id)
        .order_by(Message.created_at.desc())
        .first()
    )


def list_matches_with_details(
    db: Session, user_id: int, skip: int = 0, limit: int = 50
) -> list[tuple[Match, User, Message | None]]:
    matches = list_matches_for_user(db, user_id, skip=skip, limit=limit)
    if not matches:
        return []

    other_ids = {_other_user_id(match, user_id) for match in matches}
    users_by_id = {
        user.id: user for user in db.query(User).filter(User.id.in_(other_ids)).all()
    }

    match_ids = [m.id for m in matches]
    last_messages_by_match_id: dict[int, Message] = {}
    if match_ids:
        # DISTINCT ON (via .distinct(column)) is Postgres-only and is
        # silently ignored on other dialects (e.g. SQLite in tests), which
        # would leave the *oldest* message per match rather than the
        # newest. Sorting ascending and letting later writes overwrite
        # earlier ones in the dict is portable across every backend.
        messages = (
            db.query(Message)
            .filter(Message.match_id.in_(match_ids))
            .order_by(Message.created_at.asc())
            .all()
        )
        for message in messages:
            last_messages_by_match_id[message.match_id] = message

    return [
        (match, users_by_id[_other_user_id(match, user_id)], last_messages_by_match_id.get(match.id))
        for match in matches
        if _other_user_id(match, user_id) in users_by_id
    ]
