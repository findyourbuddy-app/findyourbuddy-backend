import pytest
from sqlalchemy.orm import Session

from app.schemas.user import UserCreate
from app.services.admin_service import UserNotFoundError, list_users, set_user_active_status
from app.services.auth_service import register_user


def _register(db_session: Session, email: str) -> int:
    return register_user(
        db_session,
        UserCreate(email=email, password="s3cret-pass", display_name=email, accepted_terms=True),
    ).id


def test_list_users_returns_all_users(db_session: Session) -> None:
    a = _register(db_session, "a@example.com")
    b = _register(db_session, "b@example.com")

    result = {user.id for user in list_users(db_session)}

    assert result == {a, b}


def test_list_users_respects_skip_and_limit(db_session: Session) -> None:
    for i in range(3):
        _register(db_session, f"user{i}@example.com")

    result = list_users(db_session, skip=1, limit=1)

    assert len(result) == 1


def test_set_user_active_status_deactivates_user(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")

    updated = set_user_active_status(db_session, user_id, False)

    assert updated.is_active is False


def test_set_user_active_status_raises_for_unknown_user(db_session: Session) -> None:
    with pytest.raises(UserNotFoundError):
        set_user_active_status(db_session, 999, False)
