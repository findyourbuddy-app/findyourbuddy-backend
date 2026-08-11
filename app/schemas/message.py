from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    content: str


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    sender_id: int
    content: str
    is_read: bool
    created_at: datetime
