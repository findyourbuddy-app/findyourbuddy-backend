import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.event import Event
from app.models.user import User
from app.schemas.event import EventCheckIn, EventCreate, EventRead
from app.schemas.user import UserRead, UserPublic
from app.services.event_service import (
    DailyEventCreationLimitExceededError,
    EventCheckInOutsideWindowError,
    EventCheckInTooFarError,
    check_in_to_event,
    count_attendees,
    count_attendees_bulk,
    create_event,
    get_event,
    is_attending,
    is_checked_in,
    is_ticket_verified,
    join_event,
    list_attending_events,
    list_events,
    submit_ticket,
)
from app.services.media_service import MediaStorage, get_media_storage
from app.services.media_validation import ImageTooLargeError, InvalidImageError, validate_image
from app.services.subscription_service import is_premium
from app.services.ticket_service import decode_qr_or_barcode

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=list[EventRead])
def list_all_events(
    category: str | None = None,
    upcoming_only: bool = True,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EventRead]:
    events = list_events(
        db, category=category, upcoming_only=upcoming_only, skip=skip, limit=limit
    )
    attendee_counts = count_attendees_bulk(db, [event.id for event in events])
    creator_ids = {e.creator_id for e in events if e.creator_id}
    creators = {u.id: u for u in db.query(User).filter(User.id.in_(creator_ids)).all()} if creator_ids else {}
    return [
        EventRead.model_validate(event).model_copy(
            update={
                "attendee_count": attendee_counts.get(event.id, 0),
                "is_attending": is_attending(db, event.id, current_user.id),
                "is_checked_in": is_checked_in(db, event.id, current_user.id),
                "is_ticket_verified": is_ticket_verified(db, event.id, current_user.id),
                "creator": UserPublic.model_validate(creators[event.creator_id]) if event.creator_id in creators else None,
            }
        )
        for event in events
    ]


@router.get("/me/attending", response_model=list[EventRead])
def read_my_attending_events(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EventRead]:
    events = list_attending_events(db, current_user.id)
    attendee_counts = count_attendees_bulk(db, [event.id for event in events])
    creator_ids = {e.creator_id for e in events if e.creator_id}
    creators = {u.id: u for u in db.query(User).filter(User.id.in_(creator_ids)).all()} if creator_ids else {}
    return [
        EventRead.model_validate(event).model_copy(
            update={
                "attendee_count": attendee_counts.get(event.id, 0),
                "is_attending": True,
                "is_checked_in": is_checked_in(db, event.id, current_user.id),
                "is_ticket_verified": is_ticket_verified(db, event.id, current_user.id),
                "creator": UserPublic.model_validate(creators[event.creator_id]) if event.creator_id in creators else None,
            }
        )
        for event in events
    ]


@router.get("/{event_id}", response_model=EventRead)
def read_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventRead:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    creator = db.get(User, event.creator_id) if event.creator_id else None
    return EventRead.model_validate(event).model_copy(
        update={
            "attendee_count": count_attendees(db, event_id),
            "is_attending": is_attending(db, event_id, current_user.id),
            "is_checked_in": is_checked_in(db, event_id, current_user.id),
            "is_ticket_verified": is_ticket_verified(db, event_id, current_user.id),
            "creator": UserPublic.model_validate(creator) if creator else None,
        }
    )


@router.post("/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_new_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Event:
    try:
        return create_event(
            db, data, creator_id=current_user.id, is_premium=is_premium(db, current_user.id)
        )
    except DailyEventCreationLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily event creation limit reached",
        ) from exc


from pydantic import BaseModel
class JoinRequestAction(BaseModel):
    approved: bool


@router.post("/{event_id}/attend", response_model=EventRead)
def attend_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventRead:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    attendance = join_event(db, event_id, current_user.id)
    
    if event.is_group_event and event.creator_id:
        from app.models.notification import Notification
        db.add(Notification(
            user_id=event.creator_id,
            title="Yeni Katılım İsteği!",
            body=f"{current_user.display_name}, '{event.title}' etkinliğine katılmak istiyor."
        ))
        db.commit()

    return EventRead.model_validate(event).model_copy(
        update={
            "attendee_count": count_attendees(db, event_id),
            "is_attending": attendance.status == "approved",
            "is_checked_in": attendance.checked_in_at is not None,
            "is_ticket_verified": attendance.ticket_verified_at is not None,
        }
    )


@router.post("/{event_id}/ticket", response_model=EventRead)
def upload_ticket(
    event_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    storage: MediaStorage = Depends(get_media_storage),
) -> EventRead:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    try:
        data = validate_image(file.file)
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image file"
        ) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Image too large"
        ) from exc

    decoded_text = decode_qr_or_barcode(data)
    image_url = storage.upload(io.BytesIO(data), file.filename or "ticket.jpg")
    attendance = submit_ticket(db, event_id, current_user.id, image_url, decoded_text)

    if decoded_text is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No QR/barcode could be read from this photo. Try a clearer photo of the ticket.",
        )

    return EventRead.model_validate(event).model_copy(
        update={
            "attendee_count": count_attendees(db, event_id),
            "is_attending": True,
            "is_checked_in": attendance.checked_in_at is not None,
            "is_ticket_verified": True,
        }
    )


@router.post("/{event_id}/check-in", response_model=EventRead)
def check_in(
    event_id: int,
    data: EventCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventRead:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    try:
        check_in_to_event(db, event_id, current_user.id, data.latitude, data.longitude)
    except EventCheckInOutsideWindowError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in is only available around the event's time",
        ) from exc
    except EventCheckInTooFarError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You're too far from the event location to check in",
        ) from exc
    return EventRead.model_validate(event).model_copy(
        update={
            "attendee_count": count_attendees(db, event_id),
            "is_attending": True,
            "is_checked_in": True,
        }
    )


@router.get("/{event_id}/join-requests", response_model=list[UserRead])
def get_join_requests(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event.creator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator can see join requests")
    
    from app.models.event_attendance import EventAttendance
    requests = (
        db.query(User)
        .join(EventAttendance, EventAttendance.user_id == User.id)
        .filter(EventAttendance.event_id == event_id, EventAttendance.status == "pending")
        .all()
    )
    return requests


@router.patch("/{event_id}/join-requests/{user_id}", response_model=EventRead)
def handle_join_request(
    event_id: int,
    user_id: int,
    data: JoinRequestAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventRead:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event.creator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator can manage join requests")
    
    from app.models.event_attendance import EventAttendance
    attendance = (
        db.query(EventAttendance)
        .filter(EventAttendance.event_id == event_id, EventAttendance.user_id == user_id)
        .first()
    )
    if attendance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance request not found")
    
    attendance.status = "approved" if data.approved else "rejected"
    
    from app.models.notification import Notification
    status_label = "onaylandı 🎉" if data.approved else "reddedildi"
    db.add(Notification(
        user_id=user_id,
        title="Grup Katılım Sonucu",
        body=f"'{event.title}' grubuna katılım isteğin {status_label}."
    ))
    db.commit()

    return EventRead.model_validate(event).model_copy(
        update={
            "attendee_count": count_attendees(db, event_id),
            "is_attending": is_attending(db, event_id, current_user.id),
        }
    )


@router.get("/{event_id}/attendees", response_model=list[UserRead])
def get_event_attendees(
    event_id: int,
    db: Session = Depends(get_db),
) -> list[User]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    from app.models.event_attendance import EventAttendance
    attendees = (
        db.query(User)
        .join(EventAttendance, EventAttendance.user_id == User.id)
        .filter(EventAttendance.event_id == event_id, EventAttendance.status == "approved")
        .all()
    )
    return attendees
