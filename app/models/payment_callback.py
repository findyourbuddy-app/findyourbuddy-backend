from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PaymentCallback(Base):
    """Records each Iyzico checkout-form token once it's been acted on, so a
    retried/duplicated callback (browser refresh, network retry) can't grant
    the same premium extension or credit top-up twice."""

    __tablename__ = "payment_callbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(50))
    user_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
