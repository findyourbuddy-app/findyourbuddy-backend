from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.subscription_service import (
    get_subscription,
    grant_premium,
    is_premium,
    revoke_premium,
)


def _register(db_session: Session, email: str = "ada@example.com") -> int:
    return register_user(
        db_session,
        UserCreate(email=email, password="s3cret-pass", display_name=email, accepted_terms=True, phone_number=f"5{abs(hash(email)) % 10**9:09d}"),
    ).id


def test_is_premium_false_by_default(db_session: Session) -> None:
    user_id = _register(db_session)

    assert is_premium(db_session, user_id) is False


def test_grant_premium_activates_subscription(db_session: Session) -> None:
    user_id = _register(db_session)

    grant_premium(db_session, user_id)

    assert is_premium(db_session, user_id) is True


def test_grant_premium_respects_expiry(db_session: Session) -> None:
    user_id = _register(db_session)

    grant_premium(db_session, user_id, expires_at=datetime.utcnow() - timedelta(days=1))

    assert is_premium(db_session, user_id) is False


def test_grant_premium_with_no_expiry_never_expires(db_session: Session) -> None:
    user_id = _register(db_session)

    grant_premium(db_session, user_id, expires_at=None)

    assert is_premium(db_session, user_id) is True


def test_revoke_premium_deactivates_subscription(db_session: Session) -> None:
    user_id = _register(db_session)
    grant_premium(db_session, user_id)

    revoke_premium(db_session, user_id)

    assert is_premium(db_session, user_id) is False


def test_revoke_premium_on_user_without_subscription_is_a_noop(db_session: Session) -> None:
    user_id = _register(db_session)

    result = revoke_premium(db_session, user_id)

    assert result is None
    assert is_premium(db_session, user_id) is False


def test_grant_premium_twice_updates_same_row(db_session: Session) -> None:
    user_id = _register(db_session)

    grant_premium(db_session, user_id, expires_at=datetime.utcnow() + timedelta(days=1))
    grant_premium(db_session, user_id, expires_at=datetime.utcnow() + timedelta(days=30))

    subscription = get_subscription(db_session, user_id)
    assert subscription is not None
    assert db_session.query(Subscription).filter(Subscription.user_id == user_id).count() == 1
