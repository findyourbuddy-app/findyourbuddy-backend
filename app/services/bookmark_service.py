from datetime import datetime, timezone
from app.core.datetime_utils import utcnow

from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.models.bookmark import Bookmark
from app.models.event import Event


class EventNotFoundError(Exception):
    pass


class AlreadyBookmarkedError(Exception):
    pass


class BookmarkNotFoundError(Exception):
    pass


def create_bookmark(db: Session, user_id: int, event_id: int) -> Bookmark:
    if db.get(Event, event_id) is None:
        raise EventNotFoundError(event_id)

    if db.query(exists().where(Bookmark.user_id == user_id, Bookmark.event_id == event_id)).scalar():
        raise AlreadyBookmarkedError(event_id)

    bookmark = Bookmark(user_id=user_id, event_id=event_id)
    db.add(bookmark)
    db.commit()
    db.refresh(bookmark)
    return bookmark


def remove_bookmark(db: Session, user_id: int, event_id: int) -> None:
    bookmark = (
        db.query(Bookmark)
        .filter(Bookmark.user_id == user_id, Bookmark.event_id == event_id)
        .first()
    )
    if bookmark is None:
        raise BookmarkNotFoundError(event_id)

    db.delete(bookmark)
    db.commit()


def list_bookmarks(
    db: Session, user_id: int, skip: int = 0, limit: int = 50
) -> list[tuple[Bookmark, Event]]:
    bookmarks = (
        db.query(Bookmark)
        .filter(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    if not bookmarks:
        return []
    events_by_id = {
        event.id: event
        for event in db.query(Event).filter(Event.id.in_([b.event_id for b in bookmarks])).all()
    }
    return [(b, events_by_id[b.event_id]) for b in bookmarks if b.event_id in events_by_id]


def delete_past_event_bookmarks(db: Session) -> int:
    """Saving an event to "remind me to go" stops making sense once it's
    already happened -- unlike attendance history, there's no reason to
    keep these around, so they're purged outright."""
    expired_event_ids = db.query(Event.id).filter(Event.starts_at < utcnow())
    deleted_count = (
        db.query(Bookmark)
        .filter(Bookmark.event_id.in_(expired_event_ids))
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted_count
