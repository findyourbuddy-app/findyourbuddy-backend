from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MatchFeedback(Base):
    """One rater's answer to 'did you actually meet up?' for a match, collected
    after the event has passed. met_in_person is null when the rater dismissed
    the prompt without answering -- still recorded so we stop nagging them."""

    __tablename__ = "match_feedback"
    __table_args__ = (UniqueConstraint("match_id", "rater_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    rater_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rated_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    met_in_person: Mapped[bool | None] = mapped_column(default=None)
    notified_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
