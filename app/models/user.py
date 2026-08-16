from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user_photo import UserPhoto


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_staff: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    accepted_terms_at: Mapped[datetime | None] = mapped_column(default=None)

    age: Mapped[int | None] = mapped_column(default=None)
    date_of_birth: Mapped[date | None] = mapped_column(default=None)
    occupation: Mapped[str | None] = mapped_column(String(100), default=None)
    university: Mapped[str | None] = mapped_column(String(150), default=None)
    zodiac_sign: Mapped[str | None] = mapped_column(String(50), default=None)
    gender: Mapped[str | None] = mapped_column(String(30), default=None)
    verification_status: Mapped[str] = mapped_column(String(50), default="unverified")
    looking_for: Mapped[str | None] = mapped_column(String(100), default=None)
    about_me_prompt: Mapped[str | None] = mapped_column(Text, default=None)
    voice_note_url: Mapped[str | None] = mapped_column(default=None)
    bio: Mapped[str | None] = mapped_column(Text, default=None)
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    hobbies: Mapped[list[str]] = mapped_column(JSON, default=list)
    latitude: Mapped[float | None] = mapped_column(default=None)
    longitude: Mapped[float | None] = mapped_column(default=None)
    photo_url: Mapped[str | None] = mapped_column(default=None)
    trust_score: Mapped[int] = mapped_column(default=0)

    referral_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    bonus_swipe_credits: Mapped[int] = mapped_column(default=0)
    boosted_until: Mapped[datetime | None] = mapped_column(default=None)
    boosts_balance: Mapped[int] = mapped_column(default=0)
    extra_super_likes: Mapped[int] = mapped_column(default=0)
    event_credits_balance: Mapped[int] = mapped_column(default=0, server_default="0")
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    photos: Mapped[list["UserPhoto"]] = relationship(
        "UserPhoto", order_by="UserPhoto.position", lazy="selectin"
    )
