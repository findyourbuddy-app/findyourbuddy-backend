import json
import logging
from datetime import datetime, timedelta, timezone
from html import escape
from app.core.datetime_utils import utcnow

import iyzipay
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, responses, status
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.deps import get_current_user
from app.core.rate_limit import event_writes_rate_limit, limiter
from app.database import get_db
from app.models.event import Event
from app.models.event_attendance import EventAttendance
from app.models.event_rating import EventRating
from app.models.match import Match
from app.models.notification import Notification
from app.models.user import User
from app.schemas.event import EventCheckIn, EventCreate, EventCreationQuota, EventPublicSummary, EventRatingCreate, EventRead
from app.schemas.user import UserRead, UserPublic
from app.services.event_service import (
    EventCheckInOutsideWindowError,
    EventCheckInTooFarError,
    WeeklyEventCreationLimitExceededError,
    check_in_to_event,
    count_attendees,
    count_attendees_bulk,
    count_events_created_this_week,
    create_event,
    get_event,
    grant_event_credits,
    is_attending,
    is_pending,
    is_checked_in,
    is_ticket_verified,
    join_event,
    list_attending_events,
    list_events,
)
from app.services.media_service import MediaStorage, get_media_storage
from app.services.media_validation import ImageTooLargeError, InvalidImageError, validate_image
from app.services.payment_service import claim_payment_callback
from app.services.subscription_service import is_premium

logger = logging.getLogger(__name__)

EVENT_CREDITS_PER_PURCHASE = 3
EVENT_CREDITS_PRICE_TRY = "49.00"

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventRead])
@router.get("/", response_model=list[EventRead])
def list_all_events(
    category: str | None = None,
    upcoming_only: bool = True,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    origin: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EventRead]:
    if origin not in (None, "system", "user"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="origin must be 'system' or 'user'")
    events = list_events(
        db, category=category, upcoming_only=upcoming_only, skip=skip, limit=limit, origin=origin
    )
    event_ids = [e.id for e in events]
    attendee_counts = count_attendees_bulk(db, event_ids)
    creator_ids = {e.creator_id for e in events if e.creator_id}
    creators = {u.id: u for u in db.query(User).filter(User.id.in_(creator_ids)).all()} if creator_ids else {}

    user_attendances = (
        {
            att.event_id: att
            for att in db.query(EventAttendance)
            .filter(
                EventAttendance.event_id.in_(event_ids),
                EventAttendance.user_id == current_user.id,
            )
            .all()
        }
        if event_ids
        else {}
    )

    res = [
        EventRead.model_validate(event).model_copy(
            update={
                "attendee_count": attendee_counts.get(event.id, 0),
                "is_attending": (
                    user_attendances.get(event.id) is not None
                    and user_attendances[event.id].status == "approved"
                ),
                "is_pending": (
                    user_attendances.get(event.id) is not None
                    and user_attendances[event.id].status == "pending"
                ),
                "is_checked_in": (
                    user_attendances.get(event.id) is not None
                    and user_attendances[event.id].checked_in_at is not None
                ),
                "is_ticket_verified": (
                    user_attendances.get(event.id) is not None
                    and user_attendances[event.id].ticket_verified_at is not None
                ),
                "creator": UserPublic.model_validate(creators[event.creator_id]) if event.creator_id in creators else None,
            }
        )
        for event in events
    ]

    res.sort(key=lambda e: not (e.is_attending or e.is_pending or e.creator_id == current_user.id))
    return res


@router.get("/me/attending", response_model=list[EventRead])
def read_my_attending_events(
    upcoming_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EventRead]:
    events = list_attending_events(db, current_user.id, upcoming_only=upcoming_only)
    event_ids = [e.id for e in events]
    attendee_counts = count_attendees_bulk(db, event_ids)
    creator_ids = {e.creator_id for e in events if e.creator_id}
    creators = {u.id: u for u in db.query(User).filter(User.id.in_(creator_ids)).all()} if creator_ids else {}

    user_attendances = (
        {
            att.event_id: att
            for att in db.query(EventAttendance)
            .filter(
                EventAttendance.event_id.in_(event_ids),
                EventAttendance.user_id == current_user.id,
            )
            .all()
        }
        if event_ids
        else {}
    )

    return [
        EventRead.model_validate(event).model_copy(
            update={
                "attendee_count": attendee_counts.get(event.id, 0),
                "is_attending": True,
                "is_checked_in": (
                    user_attendances.get(event.id) is not None
                    and user_attendances[event.id].checked_in_at is not None
                ),
                "is_ticket_verified": (
                    user_attendances.get(event.id) is not None
                    and user_attendances[event.id].ticket_verified_at is not None
                ),
                "creator": UserPublic.model_validate(creators[event.creator_id]) if event.creator_id in creators else None,
            }
        )
        for event in events
    ]


@router.get("/me/created", response_model=list[EventRead])
def read_my_created_events(
    upcoming_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EventRead]:
    query = db.query(Event).filter(Event.creator_id == current_user.id)
    if upcoming_only:
        six_hours_ago = utcnow() - timedelta(hours=6)
        query = query.filter(Event.starts_at >= six_hours_ago)
    events = query.order_by(Event.starts_at.desc()).all()
    if not events:
        return []

    event_ids = [e.id for e in events]
    attendee_counts = count_attendees_bulk(db, event_ids)

    return [
        EventRead.model_validate(event).model_copy(
            update={
                "attendee_count": attendee_counts.get(event.id, 0),
                "is_attending": True,
                "creator": UserPublic.model_validate(current_user),
            }
        )
        for event in events
    ]


@router.get("/user/{user_id}/upcoming", response_model=list[EventPublicSummary])
def read_user_upcoming_events(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Event]:
    """Public, minimal summary of another user's upcoming events -- shown
    under their card while swiping/viewing their profile, so buddies can see
    what they're actually into rather than just their bio."""
    return list_attending_events(db, user_id, upcoming_only=True)[:5]


@router.get("/me/creation-quota", response_model=EventCreationQuota)
def get_creation_quota(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventCreationQuota:
    premium = is_premium(db, current_user.id)
    return EventCreationQuota(
        is_premium=premium,
        events_created_this_week=count_events_created_this_week(db, current_user.id),
        weekly_limit=None if premium else get_settings().weekly_event_creation_limit,
        credits_balance=current_user.event_credits_balance,
    )


@router.post("/credits/checkout-session")
def create_credits_checkout_session(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Creates a hosted Iyzico checkout form session for buying extra weekly
    event-creation credits, mirroring subscriptions.create_checkout_session."""
    settings = get_settings()
    options = {
        "api_key": settings.iyzico_api_key,
        "secret_key": settings.iyzico_secret_key,
        "base_url": settings.iyzico_base_url,
    }

    now = utcnow()
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "0.0.0.0").split(",")[0].strip()
    gsm = current_user.phone_number or "+905300000000"

    request_data = {
        "locale": "tr",
        "conversationId": f"credits_{current_user.id}_{int(now.timestamp())}",
        "price": EVENT_CREDITS_PRICE_TRY,
        "paidPrice": EVENT_CREDITS_PRICE_TRY,
        "currency": "TRY",
        "basketId": f"basket_{current_user.id}",
        "paymentGroup": "PRODUCT",
        "callbackUrl": settings.public_base_url + "/events/credits/callback",
        "buyer": {
            "id": str(current_user.id),
            "name": current_user.display_name or "Buddy",
            "surname": "User",
            "gsmNumber": gsm,
            "email": current_user.email,
            "identityNumber": settings.iyzico_buyer_identity_number,
            "lastLoginDate": now.strftime("%Y-%m-%d %H:%M:%S"),
            "registrationDate": now.strftime("%Y-%m-%d %H:%M:%S"),
            "registrationAddress": "Turkey",
            "ip": client_ip,
            "city": "Istanbul",
            "country": "Turkey",
            "zipCode": "34700",
        },
        "shippingAddress": {
            "contactName": current_user.display_name or "Buddy User",
            "city": "Istanbul",
            "country": "Turkey",
            "address": "Turkey",
            "zipCode": "34700",
        },
        "billingAddress": {
            "contactName": current_user.display_name or "Buddy User",
            "city": "Istanbul",
            "country": "Turkey",
            "address": "Turkey",
            "zipCode": "34700",
        },
        "basketItems": [
            {
                "id": "event_credits",
                "name": f"{EVENT_CREDITS_PER_PURCHASE} Ekstra Etkinlik Oluşturma Hakkı",
                "category1": "EventCredits",
                "itemType": "VIRTUAL",
                "price": EVENT_CREDITS_PRICE_TRY,
            }
        ],
    }

    try:
        raw_response = iyzipay.CheckoutFormInitialize().create(request_data, options)
        response = json.loads(raw_response.read().decode("utf-8"))
        if response.get("status") == "success":
            return {"checkout_url": response.get("paymentPageUrl")}
        raise HTTPException(
            status_code=400, detail=response.get("errorMessage") or "Ödeme başlatılamadı."
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/credits/callback")
async def event_credits_callback(
    token: str = Form(...),
    db: Session = Depends(get_db),
):
    """Processes Iyzico payment redirection callback to verify and grant
    event-creation credits, mirroring subscriptions.iyzico_callback."""
    settings = get_settings()
    options = {
        "api_key": settings.iyzico_api_key,
        "secret_key": settings.iyzico_secret_key,
        "base_url": settings.iyzico_base_url,
    }

    try:
        raw_response = iyzipay.CheckoutForm().retrieve({"token": token}, options)
        checkout_form = json.loads(raw_response.read().decode("utf-8"))
        checkout_status = checkout_form.get("status")
        payment_status = checkout_form.get("paymentStatus")

        if checkout_status == "success" and payment_status == "SUCCESS":
            paid_price = str(checkout_form.get("paidPrice") or checkout_form.get("price") or "")
            if paid_price and float(paid_price) < float(EVENT_CREDITS_PRICE_TRY):
                logger.warning(f"Price mismatch in credits callback: expected {EVENT_CREDITS_PRICE_TRY}, got {paid_price}")
                return responses.HTMLResponse(content="<html><body><h1>Ödeme Tutarı Geçersiz</h1></body></html>", status_code=400)

            conv_id = checkout_form.get("conversationId")
            if conv_id and conv_id.startswith("credits_"):
                user_id = int(conv_id.split("_")[1])
                if claim_payment_callback(db, token, "event_credits", user_id):
                    grant_event_credits(db, user_id, EVENT_CREDITS_PER_PURCHASE)
                return responses.HTMLResponse(content=f"""
                    <html>
                        <head>
                            <meta charset="utf-8">
                            <title>Ödeme Başarılı</title>
                        </head>
                        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; text-align: center; padding-top: 100px; background: #121214; color: #ffffff;">
                            <div style="max-width: 400px; margin: 0 auto; background: #1a1a1e; padding: 40px; border-radius: 16px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);">
                                <div style="font-size: 64px; margin-bottom: 20px;">🎉</div>
                                <h1 style="color: #4CAF50; font-size: 24px; margin-bottom: 10px;">Hakların Tanımlandı!</h1>
                                <p style="color: #c9c9cf; font-size: 14px; line-height: 1.5; margin-bottom: 30px;">{EVENT_CREDITS_PER_PURCHASE} adet ekstra etkinlik oluşturma hakkın hesabına tanımlandı.</p>
                                <p style="color: #8c8c96; font-size: 12px;">Bu ekran 5 saniye içinde kapanacaktır.</p>
                            </div>
                            <script>setTimeout(function() {{ window.close(); }}, 5000);</script>
                        </body>
                    </html>
                """)

        error_msg = escape(checkout_form.get("errorMessage") or "Ödeme tamamlanamadı.")
        return responses.HTMLResponse(content=f"""
            <html>
                <head>
                    <meta charset="utf-8">
                    <title>Ödeme Başarısız</title>
                </head>
                <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; text-align: center; padding-top: 100px; background: #121214; color: #ffffff;">
                    <div style="max-width: 400px; margin: 0 auto; background: #1a1a1e; padding: 40px; border-radius: 16px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);">
                        <div style="font-size: 64px; margin-bottom: 20px;">❌</div>
                        <h1 style="color: #F44336; font-size: 24px; margin-bottom: 10px;">Ödeme Başarısız</h1>
                        <p style="color: #c9c9cf; font-size: 14px; line-height: 1.5; margin-bottom: 30px;">{error_msg}</p>
                        <p style="color: #8c8c96; font-size: 12px;">Lütfen tekrar deneyin. Bu ekran 5 saniye içinde kapanacaktır.</p>
                    </div>
                    <script>setTimeout(function() {{ window.close(); }}, 5000);</script>
                </body>
            </html>
        """)
    except Exception as exc:
        logger.error(f"Iyzico event-credits callback verification error: {exc}")
        return responses.HTMLResponse(content=f"""
            <html>
                <body style="font-family: sans-serif; text-align: center; padding-top: 100px; background: #121212; color: #fff;">
                    <h1 style="color: #F44336;">❌ Bir Hata Oluştu</h1>
                    <p>{escape(str(exc))}</p>
                </body>
            </html>
        """)


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
            "is_pending": is_pending(db, event_id, current_user.id),
            "is_checked_in": is_checked_in(db, event_id, current_user.id),
            "is_ticket_verified": is_ticket_verified(db, event_id, current_user.id),
            "creator": UserPublic.model_validate(creator) if creator else None,
        }
    )


@router.post("", response_model=EventRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=EventRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(event_writes_rate_limit)
def create_new_event(
    request: Request,
    data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Event:
    cutoff = utcnow() - timedelta(minutes=5)
    starts_at_naive = data.starts_at.replace(tzinfo=None) if data.starts_at.tzinfo else data.starts_at
    if starts_at_naive < cutoff:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Etkinlik başlangıç zamanı geçmişte olamaz.",
        )
    try:
        return create_event(
            db, data, creator_id=current_user.id, is_premium=is_premium(db, current_user.id)
        )
    except WeeklyEventCreationLimitExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Weekly event creation limit reached",
        ) from exc


class JoinRequestAction(BaseModel):
    approved: bool


@router.post("/{event_id}/attend", response_model=EventRead)
@limiter.limit(event_writes_rate_limit)
def attend_event(
    request: Request,
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventRead:
    event = get_event(db, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    attendance = join_event(db, event_id, current_user.id)
    
    if event.creator_id and event.creator_id != current_user.id:
        db.add(Notification(
            user_id=event.creator_id,
            title="Yeni Katılım İsteği!",
            body=f"{current_user.display_name}, '{event.title}' etkinliğine katılmak istiyor.",
            event_id=event.id,
            notification_type="event_request",
            data={"event_id": event.id},
        ))
        db.commit()

    return EventRead.model_validate(event).model_copy(
        update={
            "attendee_count": count_attendees(db, event_id),
            "is_attending": attendance.status == "approved",
            "is_pending": attendance.status == "pending",
            "is_checked_in": attendance.checked_in_at is not None,
            "is_ticket_verified": attendance.ticket_verified_at is not None,
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
    
    attendance = (
        db.query(EventAttendance)
        .filter(EventAttendance.event_id == event_id, EventAttendance.user_id == user_id)
        .first()
    )
    if attendance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance request not found")

    if data.approved:
        attendance.status = "approved"
        existing_match = db.query(Match).filter(
            Match.event_id == event_id,
            or_(
                and_(Match.user_a_id == current_user.id, Match.user_b_id == user_id),
                and_(Match.user_a_id == user_id, Match.user_b_id == current_user.id),
            )
        ).first()
        if not existing_match:
            db.add(Match(
                event_id=event_id,
                user_a_id=current_user.id,
                user_b_id=user_id,
                score=1.0,
                is_active=True,
            ))
    else:
        attendance.status = "rejected"

    status_label = "onaylandı" if data.approved else "reddedildi"
    db.add(Notification(
        user_id=user_id,
        title="Grup Katılım Sonucu",
        body=f"'{event.title}' grubuna katılım isteğin {status_label}.",
        event_id=event.id,
    ))
    db.commit()

    return EventRead.model_validate(event).model_copy(
        update={
            "attendee_count": count_attendees(db, event_id),
            "is_attending": is_attending(db, event_id, current_user.id),
            "is_pending": is_pending(db, event_id, current_user.id),
        }
    )


@router.post("/{event_id}/join-requests/approve-all", response_model=EventRead)
def approve_all_join_requests(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EventRead:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    if event.creator_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator can manage join requests")

    pending_attendances = (
        db.query(EventAttendance)
        .filter(EventAttendance.event_id == event_id, EventAttendance.status == "pending")
        .all()
    )

    for attendance in pending_attendances:
        attendance.status = "approved"
        existing_match = db.query(Match).filter(
            Match.event_id == event_id,
            or_(
                and_(Match.user_a_id == current_user.id, Match.user_b_id == attendance.user_id),
                and_(Match.user_a_id == attendance.user_id, Match.user_b_id == current_user.id),
            )
        ).first()
        if not existing_match:
            db.add(Match(
                event_id=event_id,
                user_a_id=current_user.id,
                user_b_id=attendance.user_id,
                score=1.0,
                is_active=True,
            ))
        db.add(Notification(
            user_id=attendance.user_id,
            title="Grup Katılım Sonucu",
            body=f"'{event.title}' grubuna katılım isteğin onaylandı.",
            event_id=event.id,
        ))

    db.commit()

    return EventRead.model_validate(event).model_copy(
        update={
            "attendee_count": count_attendees(db, event_id),
            "is_attending": is_attending(db, event_id, current_user.id),
            "is_pending": is_pending(db, event_id, current_user.id),
        }
    )


@router.get("/{event_id}/attendees", response_model=list[UserRead])
def get_event_attendees(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    attendees = (
        db.query(User)
        .join(EventAttendance, EventAttendance.user_id == User.id)
        .filter(EventAttendance.event_id == event_id, EventAttendance.status == "approved")
        .all()
    )
    return attendees


@router.post("/{event_id}/impressions", status_code=status.HTTP_204_NO_CONTENT)
def record_event_impression(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Records an impression when an event card is rendered/viewed by a user."""
    return None


@router.post("/impressions", status_code=status.HTTP_204_NO_CONTENT)
def record_bulk_event_impressions(
    event_ids: list[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Records impressions in bulk when a list of event cards is rendered."""
    return None


@router.post("/{event_id}/rate")
def rate_event(
    event_id: int,
    payload: EventRatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rating must be between 1 and 5 stars")

    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if event.creator_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot rate your own event")

    existing = db.query(EventRating).filter(
        EventRating.event_id == event_id,
        EventRating.user_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already rated this event")

    rating_record = EventRating(
        event_id=event_id,
        user_id=current_user.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(rating_record)

    # Impact Host / Creator Trust Score if event was created by a user
    creator_trust_score = None
    if event.creator_id:
        creator = db.get(User, event.creator_id)
        if creator:
            if payload.rating >= 4:
                boost = 3 if payload.rating == 5 else 2
                creator.trust_score += boost
            elif payload.rating <= 2:
                penalty = 4 if payload.rating == 1 else 2
                creator.trust_score -= penalty
            creator_trust_score = creator.trust_score

    db.commit()
    return {
        "status": "ok",
        "message": "Event and host rated successfully",
        "creator_trust_score": creator_trust_score
    }
