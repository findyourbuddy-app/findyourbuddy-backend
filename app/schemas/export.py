from datetime import datetime

from pydantic import BaseModel

from app.schemas.bookmark import BookmarkRead
from app.schemas.event import EventRead
from app.schemas.match import MatchRead
from app.schemas.message import MessageRead
from app.schemas.notification import NotificationRead
from app.schemas.user import UserRead


class UserDataExport(BaseModel):
    exported_at: datetime
    profile: UserRead
    events_created: list[EventRead]
    matches: list[MatchRead]
    messages_sent: list[MessageRead]
    notifications: list[NotificationRead]
    bookmarks: list[BookmarkRead]
    swipe_history: list[dict] = []
    blocks_and_reports: list[dict] = []
    photos: list[dict] = []
    subscription_history: list[dict] = []
