from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.subscription import Subscription


def get_subscription(db: Session, user_id: int) -> Subscription | None:
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()


def is_premium(db: Session, user_id: int) -> bool:
    subscription = get_subscription(db, user_id)
    if subscription is None or not subscription.is_active:
        return False
    if subscription.expires_at is not None and subscription.expires_at < datetime.now(timezone.utc):
        return False
    return True


def premium_user_ids(db: Session, user_ids: list[int]) -> set[int]:
    if not user_ids:
        return set()
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Subscription.user_id)
        .filter(
            Subscription.user_id.in_(user_ids),
            Subscription.is_active.is_(True),
            (Subscription.expires_at.is_(None)) | (Subscription.expires_at >= now),
        )
        .all()
    )
    return {row[0] for row in rows}


def grant_premium(
    db: Session, user_id: int, expires_at: datetime | None = None, provider: str = "manual"
) -> Subscription:
    subscription = get_subscription(db, user_id)
    now = datetime.now(timezone.utc)
    if subscription is None:
        subscription = Subscription(user_id=user_id)
        db.add(subscription)
        subscription.started_at = now
    else:
        # Extend from current expiry if still active, otherwise start fresh
        if (
            subscription.is_active
            and subscription.expires_at is not None
            and expires_at is not None
            and subscription.expires_at > now
        ):
            from datetime import timedelta
            remaining = subscription.expires_at - now
            expires_at = expires_at + remaining
        else:
            subscription.started_at = now

    subscription.is_active = True
    subscription.provider = provider
    subscription.expires_at = expires_at
    db.commit()
    db.refresh(subscription)
    return subscription


def revoke_premium(db: Session, user_id: int) -> Subscription | None:
    subscription = get_subscription(db, user_id)
    if subscription is None:
        return None

    subscription.is_active = False
    db.commit()
    db.refresh(subscription)
    return subscription
