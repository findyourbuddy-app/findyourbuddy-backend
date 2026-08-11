from datetime import datetime

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True)
    is_staff: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    age: Mapped[int | None] = mapped_column(default=None)
    bio: Mapped[str | None] = mapped_column(Text, default=None)
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    latitude: Mapped[float | None] = mapped_column(default=None)
    longitude: Mapped[float | None] = mapped_column(default=None)
    photo_url: Mapped[str | None] = mapped_column(default=None)
