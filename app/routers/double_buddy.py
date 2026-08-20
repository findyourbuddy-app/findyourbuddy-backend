from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.double_buddy import DoubleBuddy
from app.models.user import User

router = APIRouter(prefix="/double-buddy", tags=["double-buddy"])


class InviteRequest(BaseModel):
    partner_id: int


class DoubleBuddyRead(BaseModel):
    id: int
    user_1_id: int
    user_2_id: int
    status: str
    partner_name: str
    partner_photo: str | None


@router.get("/me", response_model=DoubleBuddyRead | None)
def get_my_double_buddy(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pair = (
        db.query(DoubleBuddy)
        .filter(
            (DoubleBuddy.user_1_id == current_user.id) | (DoubleBuddy.user_2_id == current_user.id)
        )
        .first()
    )
    if not pair:
        return None

    partner_id = pair.user_2_id if pair.user_1_id == current_user.id else pair.user_1_id
    partner = db.get(User, partner_id)

    return DoubleBuddyRead(
        id=pair.id,
        user_1_id=pair.user_1_id,
        user_2_id=pair.user_2_id,
        status=pair.status,
        partner_name=partner.display_name if partner else "Kanka",
        partner_photo=partner.photo_url if partner else None,
    )


@router.post("/invite", response_model=DoubleBuddyRead, status_code=status.HTTP_201_CREATED)
def invite_double_buddy(
    data: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.partner_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot pair with yourself"
        )

    partner = db.get(User, data.partner_id)
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner user not found")

    # Remove existing pairs
    db.query(DoubleBuddy).filter(
        (DoubleBuddy.user_1_id == current_user.id) | (DoubleBuddy.user_2_id == current_user.id)
    ).delete()

    new_pair = DoubleBuddy(
        user_1_id=current_user.id,
        user_2_id=partner.id,
        status="accepted",
    )
    db.add(new_pair)
    db.commit()
    db.refresh(new_pair)

    return DoubleBuddyRead(
        id=new_pair.id,
        user_1_id=new_pair.user_1_id,
        user_2_id=new_pair.user_2_id,
        status=new_pair.status,
        partner_name=partner.display_name,
        partner_photo=partner.photo_url,
    )


@router.delete("/disband", status_code=status.HTTP_204_NO_CONTENT)
def disband_double_buddy(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(DoubleBuddy).filter(
        (DoubleBuddy.user_1_id == current_user.id) | (DoubleBuddy.user_2_id == current_user.id)
    ).delete()
    db.commit()
    return None
