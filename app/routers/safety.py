from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_staff_user, get_current_user
from app.database import get_db
from app.models.block import Block
from app.models.report import Report, ReportStatus
from app.models.user import User
from app.schemas.safety import BlockedUserRead, BlockRead, ReportCreate, ReportRead, ReportStatusUpdate
from app.schemas.user import UserPublic
from app.services.safety_service import (
    AlreadyBlockedError,
    BlockNotFoundError,
    CannotBlockSelfError,
    CannotReportSelfError,
    ReportNotFoundError,
    block_user,
    create_report,
    list_my_blocks,
    list_reports,
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


@router.get("/users/me/blocks", response_model=list[BlockedUserRead])
def list_my_blocked_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BlockedUserRead]:
    return [
        BlockedUserRead(
            id=block.id, blocked_user=UserPublic.model_validate(user), created_at=block.created_at
        )
        for block, user in list_my_blocks(db, current_user.id)
    ]


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


@router.get("/reports", response_model=list[ReportRead])
def list_all_reports(
    status: ReportStatus | None = None,
    reported_user_id: int | None = None,
    _staff_user: User = Depends(get_current_staff_user),
    db: Session = Depends(get_db),
) -> list[Report]:
    return list_reports(db, status=status, reported_user_id=reported_user_id)


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


from app.models.emergency_contact import EmergencyContact
from app.schemas.emergency_contact import EmergencyContactCreate, EmergencyContactRead, PanicAlertTrigger


@router.post("/emergency-contacts", response_model=EmergencyContactRead, status_code=status.HTTP_201_CREATED)
def add_emergency_contact(
    data: EmergencyContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmergencyContact:
    contact = EmergencyContact(
        user_id=current_user.id,
        contact_name=data.contact_name,
        phone_number=data.phone_number,
        relationship=data.relationship,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("/emergency-contacts", response_model=list[EmergencyContactRead])
def get_emergency_contacts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EmergencyContact]:
    return db.query(EmergencyContact).filter(EmergencyContact.user_id == current_user.id).all()


@router.post("/panic", status_code=status.HTTP_200_OK)
def trigger_panic_sos_alert(
    data: PanicAlertTrigger,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    contacts = db.query(EmergencyContact).filter(EmergencyContact.user_id == current_user.id).all()
    
    from app.core.sms import get_sms_sender
    sms_sender = get_sms_sender()
    
    loc_str = f"Konum: {data.location_name}" if data.location_name else ""
    if data.latitude and data.longitude:
        loc_str += f" (https://maps.google.com/?q={data.latitude},{data.longitude})"
        
    sos_msg = f"⚠️ ACİL DURUM UYARISI! {current_user.display_name} yardım çağrısı gönderdi! {loc_str}"
    
    for c in contacts:
        sms_sender.send(current_user, sos_msg)
        
    return {
        "status": "alert_sent",
        "contacts_notified": len(contacts),
        "message": f"Acil durum uyarısı {len(contacts)} kayıtlı yakınınıza ve güvenlik merkezimize iletildi."
    }
