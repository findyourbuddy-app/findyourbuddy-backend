from datetime import datetime

from pydantic import BaseModel, ConfigDict
from app.schemas.user import UserPublic


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
    is_checked_in: bool = False
    is_ticket_verified: bool = False


class EventCheckIn(BaseModel):
    latitude: float
    longitude: float


class EventTicketRead(BaseModel):
    ticket_image_url: str | None
    ticket_decoded_text: str | None
    is_ticket_verified: bool


class EventCreationQuota(BaseModel):
    is_premium: bool
    events_created_this_week: int
    weekly_limit: int | None
    credits_balance: int
