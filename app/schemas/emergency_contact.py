from datetime import datetime
from pydantic import BaseModel, Field


class EmergencyContactCreate(BaseModel):
    contact_name: str = Field(..., max_length=100)
    phone_number: str = Field(..., max_length=30)
    relationship: str | None = Field(default=None, max_length=50)


class EmergencyContactRead(BaseModel):
    id: int
    contact_name: str
    phone_number: str
    relationship: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PanicAlertTrigger(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    location_name: str | None = None
    message: str | None = None
