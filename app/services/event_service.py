from datetime import datetime

from sqlalchemy.orm import Session

from app.models.event import Event
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
    db: Session, category: str | None = None, upcoming_only: bool = True
) -> list[Event]:
    query = db.query(Event)
    if category is not None:
        query = query.filter(Event.category == category)
    if upcoming_only:
        query = query.filter(Event.starts_at >= datetime.utcnow())
    return query.order_by(Event.starts_at).all()
