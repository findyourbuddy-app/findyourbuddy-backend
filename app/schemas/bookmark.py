from datetime import datetime

from pydantic import BaseModel

from app.schemas.event import EventRead


class BookmarkRead(BaseModel):
    id: int
    event: EventRead
    created_at: datetime
