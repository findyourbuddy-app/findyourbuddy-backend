from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Subscription(Base):
    """Tracks a user's premium entitlement. One row per user. `provider`
    identifies how the subscription was activated ("manual" for now, until
    a real payment processor like RevenueCat is wired up -- at that point
    a webhook handler would call the same subscription_service functions
    with provider="revenuecat" instead of a staff admin action)."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=False)
    provider: Mapped[str] = mapped_column(String(50), default="manual")
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
