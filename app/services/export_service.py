from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.block import Block
from app.models.event import Event
from app.models.message import Message
from app.models.report import Report
from app.models.subscription import Subscription
from app.models.swipe import Swipe
from app.models.user import User
from app.models.user_photo import UserPhoto
from app.schemas.bookmark import BookmarkRead
from app.schemas.event import EventRead
from app.schemas.export import UserDataExport
from app.schemas.match import MatchRead
from app.schemas.message import MessageRead
from app.schemas.notification import NotificationRead
from app.schemas.user import UserPublic, UserRead
from app.services.bookmark_service import list_bookmarks
from app.services.matching_service import list_matches_with_details
from app.services.notification_service import list_notifications

_EXPORT_ROW_LIMIT = 10_000


def export_user_data(db: Session, user: User) -> UserDataExport:
    events_created = db.query(Event).filter(Event.creator_id == user.id).all()
    messages_sent = db.query(Message).filter(Message.sender_id == user.id).all()

    matches = [
        MatchRead(
            id=match.id,
            event_id=match.event_id,
            user_a_id=match.user_a_id,
            user_b_id=match.user_b_id,
            score=match.score,
            created_at=match.created_at,
            other_user=UserPublic.model_validate(other_user),
            last_message=MessageRead.model_validate(last_message) if last_message else None,
        )
        for match, other_user, last_message in list_matches_with_details(
            db, user.id, skip=0, limit=_EXPORT_ROW_LIMIT
        )
    ]

    bookmarks = [
        BookmarkRead(id=bookmark.id, event=EventRead.model_validate(event), created_at=bookmark.created_at)
        for bookmark, event in list_bookmarks(db, user.id, skip=0, limit=_EXPORT_ROW_LIMIT)
    ]

    notifications = list_notifications(db, user.id, skip=0, limit=_EXPORT_ROW_LIMIT)

    swipes = db.query(Swipe).filter(Swipe.swiper_id == user.id).all()
    blocks = db.query(Block).filter(Block.blocker_id == user.id).all()
    reports = db.query(Report).filter(Report.reporter_id == user.id).all()
    photos = db.query(UserPhoto).filter(UserPhoto.user_id == user.id).all()
    subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()

    return UserDataExport(
        exported_at=datetime.now(timezone.utc),
        profile=UserRead.model_validate(user),
        events_created=[EventRead.model_validate(event) for event in events_created],
        matches=matches,
        messages_sent=[MessageRead.model_validate(message) for message in messages_sent],
        notifications=[NotificationRead.model_validate(n) for n in notifications],
        bookmarks=bookmarks,
        swipe_history=[
            {"target_id": s.target_id, "direction": s.direction, "event_id": s.event_id, "created_at": str(s.created_at)}
            for s in swipes
        ],
        blocks_and_reports=(
            [{"type": "block", "blocked_user_id": b.blocked_id, "created_at": str(b.created_at)} for b in blocks]
            + [{"type": "report", "reported_user_id": r.reported_user_id, "reason": r.reason, "created_at": str(r.created_at)} for r in reports]
        ),
        photos=[
            {"url": p.photo_url, "position": p.position, "created_at": str(p.created_at)}
            for p in photos
        ],
        subscription_history=(
            [{
                "is_active": subscription.is_active,
                "provider": subscription.provider,
                "started_at": str(subscription.started_at),
                "expires_at": str(subscription.expires_at),
                "created_at": str(subscription.created_at),
            }]
            if subscription else []
        ),
    )
