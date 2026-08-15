from datetime import datetime

from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.message import Message
from app.models.user import User
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

    return UserDataExport(
        exported_at=datetime.utcnow(),
        profile=UserRead.model_validate(user),
        events_created=[EventRead.model_validate(event) for event in events_created],
        matches=matches,
        messages_sent=[MessageRead.model_validate(message) for message in messages_sent],
        notifications=[NotificationRead.model_validate(n) for n in notifications],
        bookmarks=bookmarks,
    )
