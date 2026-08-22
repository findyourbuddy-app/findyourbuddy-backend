from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EventAttendance(Base):
    __tablename__ = "event_attendances"
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_attendances_event_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="approved", server_default="approved")
    checked_in_at: Mapped[datetime | None] = mapped_column(default=None)
    no_show_penalized_at: Mapped[datetime | None] = mapped_column(default=None)
    ticket_image_url: Mapped[str | None] = mapped_column(String(500), default=None)
    ticket_decoded_text: Mapped[str | None] = mapped_column(String(500), default=None)
    ticket_verified_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
