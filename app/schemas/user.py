from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.schemas.user_photo import UserPhotoRead


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    photo_url: str | None = None
    trust_score: int = 0


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    accepted_terms: bool
    referral_code: str | None = None

    @field_validator("accepted_terms")
    @classmethod
    def _require_accepted_terms(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Terms of service and privacy policy must be accepted")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
    is_active: bool
    age: int | None = None
    bio: str | None = None
    interests: list[str] = []
    latitude: float | None = None
    longitude: float | None = None
    photo_url: str | None = None
    accepted_terms_at: datetime | None = None
    photos: list[UserPhotoRead] = []
    trust_score: int = 0
    referral_code: str
    bonus_swipe_credits: int = 0


class UserUpdate(BaseModel):
    display_name: str | None = None
    age: int | None = None
    bio: str | None = None
    interests: list[str] | None = None
    latitude: float | None = None
    longitude: float | None = None
