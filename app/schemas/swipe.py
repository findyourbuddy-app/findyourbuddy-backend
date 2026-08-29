from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.swipe import SwipeDirection
from app.schemas.user import UserPublic, UserRead


class SwipeCreate(BaseModel):
    target_id: int
    event_id: int | None = None
    direction: SwipeDirection


class SwipeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    swiper_id: int
    target_id: int
    event_id: int | None = None
    direction: SwipeDirection
    created_at: datetime
    match_id: int | None = None
    matched_user: UserPublic | None = None


class SwipeQuota(BaseModel):
    is_premium: bool
    swipes_used_today: int
    swipe_limit: int | None
    super_likes_used_today: int
    super_like_limit: int


class LikerRead(BaseModel):
    user: UserRead
    event_id: int | None = None
