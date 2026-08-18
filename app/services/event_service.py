from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.geo import haversine_km
from app.models.bookmark import Bookmark
from app.models.event import Event
from app.models.event_attendance import EventAttendance
from app.models.match import Match
from app.models.swipe import Swipe
from app.models.user import User
from app.schemas.event import EventCreate

CHECK_IN_RADIUS_KM = 1.0
CHECK_IN_TRUST_SCORE_BONUS = 1


class WeeklyEventCreationLimitExceededError(Exception):
    pass


class EventCheckInTooFarError(Exception):
    pass


class EventCheckInOutsideWindowError(Exception):
    pass


def count_events_created_this_week(db: Session, creator_id: int) -> int:
    week_start = datetime.utcnow() - timedelta(days=7)
    return (
        db.query(Event)
        .filter(Event.creator_id == creator_id, Event.created_at >= week_start)
        .count()
    )


from app.services.llm_moderation_service import moderate_new_event


def create_event(db: Session, data: EventCreate, creator_id: int, is_premium: bool = False) -> Event:
    if not is_premium:
        settings = get_settings()
        if count_events_created_this_week(db, creator_id) >= settings.weekly_event_creation_limit:
            creator = db.get(User, creator_id)
            if creator is None or creator.event_credits_balance <= 0:
                raise WeeklyEventCreationLimitExceededError(creator_id)
            creator.event_credits_balance -= 1

    event = Event(**data.model_dump(), creator_id=creator_id)
    db.add(event)
    db.commit()
    db.refresh(event)
    return moderate_new_event(db, event)


def grant_event_credits(db: Session, user_id: int, amount: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    user.event_credits_balance += amount
    db.commit()
    db.refresh(user)
    return user


def get_event(db: Session, event_id: int) -> Event | None:
    return db.get(Event, event_id)


def list_events(
    db: Session,
    category: str | None = None,
    upcoming_only: bool = True,
    skip: int = 0,
    limit: int = 50,
) -> list[Event]:
    query = db.query(Event).filter(Event.is_approved.isnot(False))
    if category is not None:
        query = query.filter(Event.category == category)
    if upcoming_only:
        query = query.filter(Event.starts_at >= datetime.utcnow())
    return query.order_by(Event.starts_at).offset(skip).limit(limit).all()


def join_event(db: Session, event_id: int, user_id: int) -> EventAttendance:
    existing = (
        db.query(EventAttendance)
        .filter(EventAttendance.event_id == event_id, EventAttendance.user_id == user_id)
        .first()
    )
    if existing is not None:
        return existing
    event = db.get(Event, event_id)
    status = "pending" if (event and event.is_group_event) else "approved"
    attendance = EventAttendance(event_id=event_id, user_id=user_id, status=status)
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    return attendance


def check_in_to_event(
    db: Session, event_id: int, user_id: int, latitude: float, longitude: float
) -> EventAttendance:
    """Confirms physical attendance: the user must be within CHECK_IN_RADIUS_KM
    of the event's coordinates, and it must be within the event's time window
    (opens 1h before start, stays open for 8h after -- covers late arrivals)."""
    event = db.get(Event, event_id)
    if event is None:
        raise ValueError(f"Event {event_id} not found")

    now = datetime.utcnow()
    window_start = event.starts_at - timedelta(hours=1)
    window_end = event.starts_at + timedelta(hours=8)
    if not (window_start <= now <= window_end):
        raise EventCheckInOutsideWindowError(event_id)

    distance_km = haversine_km(latitude, longitude, event.latitude, event.longitude)
    if distance_km > CHECK_IN_RADIUS_KM:
        raise EventCheckInTooFarError(event_id)

    attendance = join_event(db, event_id, user_id)
    if attendance.checked_in_at is None:
        attendance.checked_in_at = now
        user = db.get(User, user_id)
        if user is not None:
            user.trust_score += CHECK_IN_TRUST_SCORE_BONUS
        db.commit()
        db.refresh(attendance)
    return attendance


def is_ticket_verified(db: Session, event_id: int, user_id: int) -> bool:
    attendance = (
        db.query(EventAttendance)
        .filter(EventAttendance.event_id == event_id, EventAttendance.user_id == user_id)
        .first()
    )
    return attendance is not None and attendance.ticket_verified_at is not None


def is_checked_in(db: Session, event_id: int, user_id: int) -> bool:
    attendance = (
        db.query(EventAttendance)
        .filter(EventAttendance.event_id == event_id, EventAttendance.user_id == user_id)
        .first()
    )
    return attendance is not None and attendance.checked_in_at is not None


def list_attending_events(db: Session, user_id: int, upcoming_only: bool = True) -> list[Event]:
    query = (
        db.query(Event)
        .join(EventAttendance, EventAttendance.event_id == Event.id)
        .filter(EventAttendance.user_id == user_id, EventAttendance.status == "approved")
    )
    if upcoming_only:
        query = query.filter(Event.starts_at >= datetime.utcnow())
    return query.order_by(Event.starts_at).all()


def is_attending(db: Session, event_id: int, user_id: int) -> bool:
    return (
        db.query(EventAttendance)
        .filter(
            EventAttendance.event_id == event_id,
            EventAttendance.user_id == user_id,
            EventAttendance.status == "approved",
        )
        .first()
        is not None
    )


def count_attendees(db: Session, event_id: int) -> int:
    return (
        db.query(EventAttendance)
        .filter(
            EventAttendance.event_id == event_id,
            EventAttendance.status == "approved",
        )
        .count()
    )


def count_attendees_bulk(db: Session, event_ids: list[int]) -> dict[int, int]:
    if not event_ids:
        return {}
    rows = (
        db.query(EventAttendance.event_id, func.count(EventAttendance.id))
        .filter(
            EventAttendance.event_id.in_(event_ids),
            EventAttendance.status == "approved",
        )
        .group_by(EventAttendance.event_id)
        .all()
    )
    return {event_id: count for event_id, count in rows}


def delete_expired_events(db: Session, retention_days: int) -> int:
    """Permanently deletes events whose starts_at is older than the retention
    window, along with their swipes/bookmarks. Events that produced at least
    one Match are left untouched so existing conversations are never lost."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    matched_event_ids = (
        db.query(Match.event_id)
        .filter(Match.event_id.isnot(None))
        .distinct()
    )
    expired_events = (
        db.query(Event)
        .filter(Event.starts_at < cutoff, Event.id.notin_(matched_event_ids))
        .all()
    )

    deleted_count = 0
    for event in expired_events:
        db.query(Swipe).filter(Swipe.event_id == event.id).delete()
        db.query(Bookmark).filter(Bookmark.event_id == event.id).delete()
        db.query(EventAttendance).filter(EventAttendance.event_id == event.id).delete()
        db.delete(event)
        deleted_count += 1

    db.commit()
    return deleted_count
