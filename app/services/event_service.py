from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.bookmark import Bookmark
from app.models.event import Event
from app.models.match import Match
from app.models.swipe import Swipe
from app.schemas.event import EventCreate


def create_event(db: Session, data: EventCreate, creator_id: int) -> Event:
    event = Event(**data.model_dump(), creator_id=creator_id)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_event(db: Session, event_id: int) -> Event | None:
    return db.get(Event, event_id)


def list_events(
    db: Session,
    category: str | None = None,
    upcoming_only: bool = True,
    skip: int = 0,
    limit: int = 50,
) -> list[Event]:
    query = db.query(Event)
    if category is not None:
        query = query.filter(Event.category == category)
    if upcoming_only:
        query = query.filter(Event.starts_at >= datetime.utcnow())
    return query.order_by(Event.starts_at).offset(skip).limit(limit).all()


def delete_expired_events(db: Session, retention_days: int) -> int:
    """Permanently deletes events whose starts_at is older than the retention
    window, along with their swipes/bookmarks. Events that produced at least
    one Match are left untouched so existing conversations are never lost."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    matched_event_ids = db.query(Match.event_id).distinct()
    expired_events = (
        db.query(Event)
        .filter(Event.starts_at < cutoff, Event.id.notin_(matched_event_ids))
        .all()
    )

    deleted_count = 0
    for event in expired_events:
        db.query(Swipe).filter(Swipe.event_id == event.id).delete()
        db.query(Bookmark).filter(Bookmark.event_id == event.id).delete()
        db.delete(event)
        deleted_count += 1

    db.commit()
    return deleted_count
