from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.event import Event
from app.models.user import User
from app.schemas.event import EventCreate, EventRead
from app.services.event_service import create_event, get_event, list_events

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=list[EventRead])
def list_all_events(
    category: str | None = None,
    upcoming_only: bool = True,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[Event]:
    return list_events(db, category=category, upcoming_only=upcoming_only)


@router.get("/{event_id}", response_model=EventRead)
def read_event(
    event_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> Event:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.post("/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_new_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Event:
    return create_event(db, data, creator_id=current_user.id)
