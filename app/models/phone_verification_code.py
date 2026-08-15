import secrets
from datetime import datetime, timedelta

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

CODE_TTL_MINUTES = 15


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _default_expiry() -> datetime:
    return datetime.utcnow() + timedelta(minutes=CODE_TTL_MINUTES)


class PhoneVerificationCode(Base):
    __tablename__ = "phone_verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(6), default=_generate_code)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(default=_default_expiry)
    consumed_at: Mapped[datetime | None] = mapped_column(default=None)
