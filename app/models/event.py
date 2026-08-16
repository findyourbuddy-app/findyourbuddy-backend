from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_events_source_external_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    category: Mapped[str] = mapped_column(String(50), index=True)
    location_name: Mapped[str] = mapped_column(String(200))
    latitude: Mapped[float] = mapped_column()
    longitude: Mapped[float] = mapped_column()
    starts_at: Mapped[datetime] = mapped_column(index=True)
    creator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), default=None)
    source: Mapped[str | None] = mapped_column(String(50), default=None)
    external_id: Mapped[str | None] = mapped_column(String(255), default=None)
    source_url: Mapped[str | None] = mapped_column(String(500), default=None)
    image_url: Mapped[str | None] = mapped_column(String(500), default=None)
    is_group_event: Mapped[bool] = mapped_column(default=False, server_default="false")
    max_attendees: Mapped[int | None] = mapped_column(default=None)
    is_paid: Mapped[bool] = mapped_column(default=False, server_default="false")
    ticket_price: Mapped[float | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
