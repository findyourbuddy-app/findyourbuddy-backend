from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(default=False)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), default=None, nullable=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), default=None, nullable=True)
    notification_type: Mapped[str | None] = mapped_column(String(50), default=None, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), index=True)

