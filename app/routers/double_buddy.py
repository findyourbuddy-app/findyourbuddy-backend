from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.notifications import NotificationSender, get_notification_sender
from app.database import get_db
from app.models.double_buddy import DoubleBuddy
from app.models.user import User
from app.services.notification_service import notify_double_buddy

router = APIRouter(prefix="/double-buddy", tags=["double-buddy"])


class InviteRequest(BaseModel):
    partner_id: int


class RespondRequest(BaseModel):
    accept: bool


class DoubleBuddyRead(BaseModel):
    id: int
    user_1_id: int
    user_2_id: int
    status: str
    partner_name: str
    partner_photo: str | None
    # True when this row is a pending invite awaiting the current user's answer.
    is_incoming: bool


def _pairs_for(db: Session, user_id: int):
    return db.query(DoubleBuddy).filter(
        or_(DoubleBuddy.user_1_id == user_id, DoubleBuddy.user_2_id == user_id)
    )


def _to_read(db: Session, pair: DoubleBuddy, current_user_id: int) -> DoubleBuddyRead:
    partner_id = pair.user_2_id if pair.user_1_id == current_user_id else pair.user_1_id
    partner = db.get(User, partner_id)
    return DoubleBuddyRead(
        id=pair.id,
        user_1_id=pair.user_1_id,
        user_2_id=pair.user_2_id,
        status=pair.status,
        partner_name=partner.display_name if partner else "Kanka",
        partner_photo=partner.photo_url if partner else None,
        is_incoming=pair.status == "pending" and pair.user_2_id == current_user_id,
    )


@router.get("/me", response_model=DoubleBuddyRead | None)
def get_my_double_buddy(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pairs = _pairs_for(db, current_user.id).all()
    if not pairs:
        return None

    # An accepted pair wins; then an invite waiting on us; then one we sent.
    def rank(pair: DoubleBuddy) -> int:
        if pair.status == "accepted":
            return 0
        if pair.user_2_id == current_user.id:
            return 1
        return 2

    return _to_read(db, min(pairs, key=rank), current_user.id)


@router.post("/invite", response_model=DoubleBuddyRead, status_code=status.HTTP_201_CREATED)
def invite_double_buddy(
    data: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    sender: NotificationSender = Depends(get_notification_sender),
):
    if data.partner_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot pair with yourself"
        )

    partner = db.get(User, data.partner_id)
    if not partner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner user not found")

    if _pairs_for(db, current_user.id).filter(DoubleBuddy.status == "accepted").first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="You already have a Double Buddy"
        )
    if _pairs_for(db, partner.id).filter(DoubleBuddy.status == "accepted").first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This user already has a Double Buddy"
        )

    # Re-inviting replaces the current user's own outstanding invite.
    _pairs_for(db, current_user.id).filter(DoubleBuddy.status == "pending").delete(
        synchronize_session=False
    )

    new_pair = DoubleBuddy(user_1_id=current_user.id, user_2_id=partner.id, status="pending")
    db.add(new_pair)
    db.commit()
    db.refresh(new_pair)

    notify_double_buddy(db, sender, partner.id, "invite", new_pair.id, current_user.display_name)

    return _to_read(db, new_pair, current_user.id)


@router.post("/{pair_id}/respond", response_model=DoubleBuddyRead | None)
def respond_to_invite(
    pair_id: int,
    data: RespondRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    sender: NotificationSender = Depends(get_notification_sender),
):
    pair = db.get(DoubleBuddy, pair_id)
    if pair is None or pair.status != "pending" or pair.user_2_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    inviter_id = pair.user_1_id

    if not data.accept:
        db.delete(pair)
        db.commit()
        notify_double_buddy(db, sender, inviter_id, "rejected", pair_id, current_user.display_name)
        return None

    # Accepting clears every other pending invite either side is involved in.
    _pairs_for(db, current_user.id).filter(
        DoubleBuddy.status == "pending", DoubleBuddy.id != pair.id
    ).delete(synchronize_session=False)
    _pairs_for(db, inviter_id).filter(
        DoubleBuddy.status == "pending", DoubleBuddy.id != pair.id
    ).delete(synchronize_session=False)

    pair.status = "accepted"
    db.commit()
    db.refresh(pair)

    notify_double_buddy(db, sender, inviter_id, "accepted", pair.id, current_user.display_name)

    return _to_read(db, pair, current_user.id)


@router.delete("/disband", status_code=status.HTTP_204_NO_CONTENT)
def disband_double_buddy(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _pairs_for(db, current_user.id).delete(synchronize_session=False)
    db.commit()
    return None
