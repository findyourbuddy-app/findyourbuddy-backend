import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

RESET_TOKEN_TTL_MINUTES = 30


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _default_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, default=_generate_token)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(default=_default_expiry)
    used_at: Mapped[datetime | None] = mapped_column(default=None)
