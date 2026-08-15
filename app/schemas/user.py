from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator
from app.schemas import SafeEmail

from app.schemas.user_photo import UserPhotoRead


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    photo_url: str | None = None
    trust_score: int = 0
    university: str | None = None


class UserCreate(BaseModel):
    email: SafeEmail
    password: str
    display_name: str
    accepted_terms: bool
    referral_code: str | None = None
    phone_number: str

    @field_validator("accepted_terms")
    @classmethod
    def _require_accepted_terms(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Terms of service and privacy policy must be accepted")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: SafeEmail
    display_name: str
    is_active: bool
    age: int | None = None
    date_of_birth: date | None = None
    occupation: str | None = None
    university: str | None = None
    zodiac_sign: str | None = None
    verification_status: str = "unverified"
    looking_for: str | None = None
    about_me_prompt: str | None = None
    voice_note_url: str | None = None
    bio: str | None = None
    interests: list[str] = []
    latitude: float | None = None
    longitude: float | None = None
    photo_url: str | None = None
    accepted_terms_at: datetime | None = None
    created_at: datetime
    photos: list[UserPhotoRead] = []
    trust_score: int = 0
    referral_code: str
    bonus_swipe_credits: int = 0
    boosted_until: datetime | None = None
    boosts_balance: int = 0
    extra_super_likes: int = 0
    phone_number: str
    phone_verified: bool = False


class UserUpdate(BaseModel):
    display_name: str | None = None
    date_of_birth: date | None = None
    occupation: str | None = None
    university: str | None = None
    zodiac_sign: str | None = None
    looking_for: str | None = None
    about_me_prompt: str | None = None
    voice_note_url: str | None = None
    bio: str | None = None
    interests: list[str] | None = None
    latitude: float | None = None
    longitude: float | None = None


class AIRecommendation(BaseModel):
    user: UserRead
    match_score: float
