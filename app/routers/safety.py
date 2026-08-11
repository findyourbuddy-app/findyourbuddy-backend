from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.block import Block
from app.models.report import Report
from app.models.user import User
from app.schemas.safety import BlockRead, ReportCreate, ReportRead
from app.services.safety_service import (
    AlreadyBlockedError,
    CannotBlockSelfError,
    CannotReportSelfError,
    block_user,
    create_report,
)

router = APIRouter(tags=["safety"])


@router.post(
    "/users/{user_id}/block", response_model=BlockRead, status_code=status.HTTP_201_CREATED
)
def block(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Block:
    try:
        return block_user(db, current_user.id, user_id)
    except CannotBlockSelfError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block yourself"
        ) from exc
    except AlreadyBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already blocked"
        ) from exc


@router.post("/reports", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
def report(
    data: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    try:
        return create_report(db, current_user.id, data)
    except CannotReportSelfError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot report yourself"
        ) from exc
