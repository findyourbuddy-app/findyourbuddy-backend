from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeviceTokenCreate(BaseModel):
    token: str


class DeviceTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    token: str
    created_at: datetime
