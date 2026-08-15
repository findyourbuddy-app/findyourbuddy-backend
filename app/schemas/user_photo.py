from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserPhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    photo_url: str
    position: int
    created_at: datetime
