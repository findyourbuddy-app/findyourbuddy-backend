from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    content: str
    message_type: str = "text"
    media_url: str | None = None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    sender_id: int
    content: str
    message_type: str
    media_url: str | None = None
    is_read: bool
    created_at: datetime


class MessagesMarkedRead(BaseModel):
    count: int
