from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, ConfigDict, field_validator
from app.schemas.user import UserPublic
from app.core.sanitizer import sanitize_text, validate_content_safety


class EventCreate(BaseModel):
    title: str
    description: str | None = None
    category: str
    location_name: str
    latitude: float
    longitude: float
    starts_at: datetime
    is_group_event: bool = False
    max_attendees: int | None = None
    is_paid: bool = False
    ticket_price: float | None = None
    image_url: str | None = None

    @field_validator("title", "description", "location_name", "category", "image_url")
    @classmethod
    def _sanitize_event_strings(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = sanitize_text(v, max_length=1000)
        is_safe, error_reason = validate_content_safety(cleaned)
        if not is_safe:
            raise ValueError(error_reason)
        return cleaned



class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    category: str
    location_name: str
    latitude: float
    longitude: float
    starts_at: datetime
    creator_id: int | None
    creator: UserPublic | None = None
    source: str | None
    external_id: str | None
    source_url: str | None
    image_url: str | None
    is_group_event: bool
    max_attendees: int | None = None
    is_paid: bool = False
    ticket_price: float | None = None
    created_at: datetime
    attendee_count: int = 0
    is_attending: bool = False
    is_pending: bool = False
    is_checked_in: bool = False


class EventPublicSummary(BaseModel):
    """Minimal, privacy-safe event summary shown on another user's profile
    card (e.g. while swiping) -- deliberately excludes attendee lists
    and other detail only relevant to actual attendees."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    starts_at: datetime
    location_name: str


class EventCheckIn(BaseModel):
    latitude: float
    longitude: float



class EventCreationQuota(BaseModel):
    is_premium: bool
    events_created_this_week: int
    weekly_limit: int | None
    credits_balance: int


class EventRatingCreate(BaseModel):
    rating: int
    comment: str | None = None


class EventRatingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    user_id: int
    rating: int
    comment: str | None
    created_at: datetime

