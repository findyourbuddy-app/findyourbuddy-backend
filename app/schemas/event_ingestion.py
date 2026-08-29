from datetime import datetime, timezone

from pydantic import BaseModel, field_validator


class EventIngestPayload(BaseModel):
    external_id: str
    source: str
    title: str
    description: str | None = None
    category: str
    location_name: str
    latitude: float
    longitude: float
    starts_at: datetime
    source_url: str | None = None
    image_url: str | None = None

    @field_validator("starts_at")
    @classmethod
    def _starts_at_to_naive_utc(cls, v: datetime) -> datetime:
        # DB column is timezone-naive and the codebase reads naive datetimes as
        # UTC. Normalize an offset-aware value so an event's date/time doesn't
        # shift (or roll to the next day) when the app parses it back.
        if v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v
    is_paid: bool = False


class EventIngestBatch(BaseModel):
    events: list[EventIngestPayload]


class EventIngestResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str]


class KnownExternalIds(BaseModel):
    external_ids: list[str]
