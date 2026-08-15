from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EventCreate(BaseModel):
    title: str
    description: str | None = None
    category: str
    location_name: str
    latitude: float
    longitude: float
    starts_at: datetime


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
    source: str | None
    external_id: str | None
    source_url: str | None
    image_url: str | None
    created_at: datetime
