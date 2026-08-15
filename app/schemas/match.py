from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.message import MessageRead
from app.schemas.user import UserPublic


class MatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    user_a_id: int
    user_b_id: int
    score: float
    created_at: datetime
    other_user: UserPublic
    last_message: MessageRead | None = None
    needs_feedback: bool = False
