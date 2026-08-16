from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment_callback import PaymentCallback


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
