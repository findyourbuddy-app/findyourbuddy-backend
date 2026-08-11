from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    user_a_id: int
    user_b_id: int
    score: float
    created_at: datetime
