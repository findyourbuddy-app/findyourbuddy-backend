from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from app.schemas import SafeEmail

from app.schemas.user_photo import UserPhotoRead


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    photo_url: str | None = None
    trust_score: int = 0
    university: str | None = None
    is_verified: bool = False


from app.core.sanitizer import sanitize_text, validate_content_safety


class UserCreate(BaseModel):
    email: SafeEmail
    password: str
    display_name: str
    accepted_terms: bool
    referral_code: str | None = None
    phone_number: str | None = None

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        from app.core.password_policy import validate_password_strength
        return validate_password_strength(v)

    @field_validator("accepted_terms")
    @classmethod
    def _require_accepted_terms(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Terms of service and privacy policy must be accepted")
        return value

    @field_validator("display_name")
    @classmethod
    def _sanitize_name(cls, v: str) -> str:
        cleaned = sanitize_text(v, max_length=50)
        is_safe, error_reason = validate_content_safety(cleaned)
        if not is_safe:
            raise ValueError(error_reason)
        return cleaned


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
    class_year: str | None = None
    zodiac_sign: str | None = None
    gender: str | None = None
    height: int | None = None
    political_views: str | None = None
    beliefs: str | None = None
    verification_status: str = "unverified"
    looking_for: str | None = None
    about_me_prompt: str | None = None
    voice_note_url: str | None = None
    bio: str | None = None
    interests: list[str] = []
    hobbies: list[str] = []
    languages_spoken: list[str] = []
    hidden_fields: list[str] = []
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
    event_credits_balance: int = 0
    phone_number: str | None = None
    phone_verified: bool = False
    is_verified: bool = False
    event_title: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = None
    date_of_birth: date | None = None
    occupation: str | None = None
    university: str | None = None
    class_year: str | None = None
    zodiac_sign: str | None = None
    gender: str | None = None
    height: int | None = None
    political_views: str | None = None
    beliefs: str | None = None
    looking_for: str | None = None
    about_me_prompt: str | None = None
    voice_note_url: str | None = None
    bio: str | None = None
    interests: list[str] | None = None
    hobbies: list[str] | None = None
    languages_spoken: list[str] | None = None
    hidden_fields: list[str] | None = None
    latitude: float | None = None
    longitude: float | None = None

    @field_validator("hobbies")
    @classmethod
    def _validate_hobbies_limit(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) > 4:
            raise ValueError("En fazla 4 hobi seçebilirsiniz.")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def _validate_minimum_age(cls, value: date | None) -> date | None:
        if value is None:
            return value
        today = date.today()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 18:
            raise ValueError("Uygulamayı kullanmak için 18 yaşında veya daha büyük olmalısınız.")
        return value

    @field_validator("latitude")
    @classmethod
    def _validate_latitude(cls, v: float | None) -> float | None:
        if v is not None and not (-90.0 <= v <= 90.0):
            raise ValueError("Enlem -90 ile 90 arasında olmalıdır.")
        return v

    @field_validator("longitude")
    @classmethod
    def _validate_longitude(cls, v: float | None) -> float | None:
        if v is not None and not (-180.0 <= v <= 180.0):
            raise ValueError("Boylam -180 ile 180 arasında olmalıdır.")
        return v

    @field_validator("display_name", "occupation", "university", "about_me_prompt", "bio")
    @classmethod
    def _sanitize_user_strings(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = sanitize_text(v, max_length=500)
        is_safe, error_reason = validate_content_safety(cleaned)
        if not is_safe:
            raise ValueError(error_reason)
        return cleaned


class AIRecommendation(BaseModel):
    user: UserRead
    match_score: float
