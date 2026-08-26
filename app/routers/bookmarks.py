from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.event import Event
from app.models.user import User
from app.schemas.bookmark import BookmarkRead
from app.schemas.event import EventRead
from app.services.bookmark_service import (
    AlreadyBookmarkedError,
    BookmarkNotFoundError,
    EventNotFoundError,
    create_bookmark,
    list_bookmarks,
    remove_bookmark,
)

router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


@router.get("", response_model=list[BookmarkRead])
@router.get("/", response_model=list[BookmarkRead])
def list_my_bookmarks(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BookmarkRead]:
    return [
        BookmarkRead(id=bookmark.id, event=EventRead.model_validate(event), created_at=bookmark.created_at)
        for bookmark, event in list_bookmarks(db, current_user.id, skip=skip, limit=limit)
    ]


@router.post("/{event_id}", response_model=BookmarkRead, status_code=status.HTTP_201_CREATED)
def create_my_bookmark(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookmarkRead:
    try:
        bookmark = create_bookmark(db, current_user.id, event_id)
    except EventNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found") from exc
    except AlreadyBookmarkedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Event already bookmarked"
        ) from exc

    event = db.get(Event, event_id)
    return BookmarkRead(
        id=bookmark.id, event=EventRead.model_validate(event), created_at=bookmark.created_at
    )


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_bookmark(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        remove_bookmark(db, current_user.id, event_id)
    except BookmarkNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found") from exc
