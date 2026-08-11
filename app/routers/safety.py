from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_staff_user, get_current_user
from app.database import get_db
from app.models.block import Block
from app.models.report import Report
from app.models.user import User
from app.schemas.safety import BlockRead, ReportCreate, ReportRead, ReportStatusUpdate
from app.services.safety_service import (
    AlreadyBlockedError,
    BlockNotFoundError,
    CannotBlockSelfError,
    CannotReportSelfError,
    ReportNotFoundError,
    block_user,
    create_report,
    unblock_user,
    update_report_status,
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


@router.delete("/users/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT)
def unblock(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        unblock_user(db, current_user.id, user_id)
    except BlockNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Block not found"
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


@router.patch("/reports/{report_id}", response_model=ReportRead)
def update_report(
    report_id: int,
    data: ReportStatusUpdate,
    _staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
) -> Report:
    try:
        return update_report_status(db, report_id, data.status)
    except ReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        ) from exc
