from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.report import ReportReason, ReportStatus


class BlockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    blocker_id: int
    blocked_id: int
    created_at: datetime


class ReportCreate(BaseModel):
    reported_user_id: int
    reason: ReportReason
    description: str | None = None


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reporter_id: int
    reported_user_id: int
    reason: ReportReason
    description: str | None
    status: ReportStatus
    created_at: datetime
