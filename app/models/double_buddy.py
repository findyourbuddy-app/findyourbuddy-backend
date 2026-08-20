from datetime import datetime
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DoubleBuddy(Base):
    __tablename__ = "double_buddies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_1_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_2_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="accepted")  # "pending", "accepted"
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
