from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment_callback import PaymentCallback
from app.models.user import User


def apply_purchase(user: User, item_type: str, quantity: int) -> None:
    if item_type == "boost":
        user.boosts_balance += quantity
    elif item_type == "super_likes":
        user.extra_super_likes += quantity
    elif item_type == "swipes":
        user.bonus_swipe_credits += quantity * 50


def claim_payment_callback(db: Session, token: str, purpose: str, user_id: int) -> bool:
    """Records this Iyzico checkout token as processed. Returns True the
    first time a token is claimed (caller should grant the purchase), False
    if it's already been claimed before (a duplicate/retried callback --
    caller should skip granting again but can still show a success page)."""
    db.add(PaymentCallback(token=token, purpose=purpose, user_id=user_id))
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
