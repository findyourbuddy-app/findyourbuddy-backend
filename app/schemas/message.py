from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from app.core.sanitizer import sanitize_text, validate_content_safety


class MessageCreate(BaseModel):
    content: str
    message_type: str = "text"
    media_url: str | None = None
    # Not persisted -- forwarded to Firestore so the client can size the image
    # bubble immediately and match the delivered message to its local placeholder.
    media_width: int | None = None
    media_height: int | None = None
    client_temp_id: str | None = None

    @field_validator("content")
    @classmethod
    def _sanitize_content(cls, v: str) -> str:
        cleaned = sanitize_text(v, max_length=2000)
        is_safe, error_reason = validate_content_safety(cleaned)
        if not is_safe:
            raise ValueError(error_reason)
        return cleaned


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
