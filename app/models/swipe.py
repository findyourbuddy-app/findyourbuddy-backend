import enum
from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SwipeDirection(str, enum.Enum):
    LIKE = "like"
    PASS = "pass"
    SUPER_LIKE = "super_like"


class Swipe(Base):
    __tablename__ = "swipes"
    __table_args__ = (UniqueConstraint("swiper_id", "target_id", "event_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    swiper_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    direction: Mapped[SwipeDirection] = mapped_column(Enum(SwipeDirection))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), index=True)
