from datetime import datetime

from pydantic import BaseModel


class SubscriptionStatus(BaseModel):
    is_premium: bool
    expires_at: datetime | None = None


class GrantPremiumRequest(BaseModel):
    expires_at: datetime | None = None
