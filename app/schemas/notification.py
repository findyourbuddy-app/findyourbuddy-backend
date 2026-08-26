from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    is_read: bool
    event_id: int | None = None
    match_id: int | None = None
    notification_type: str | None = None
    data: dict | None = None
    created_at: datetime


class NotificationsMarkedRead(BaseModel):
    count: int
