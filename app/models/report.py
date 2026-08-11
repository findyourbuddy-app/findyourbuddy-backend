import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReportReason(str, enum.Enum):
    HARASSMENT = "harassment"
    SPAM = "spam"
    FAKE_PROFILE = "fake_profile"
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reported_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[ReportReason] = mapped_column(Enum(ReportReason))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus), default=ReportStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
