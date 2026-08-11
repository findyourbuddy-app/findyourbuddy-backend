import pytest
from sqlalchemy.orm import Session

from app.schemas.user import UserCreate
from app.services.auth_service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    authenticate_user,
    register_user,
)


def _create_user(db_session: Session) -> None:
    register_user(
        db_session,
        UserCreate(email="ada@example.com", password="s3cret-pass", display_name="Ada"),
    )


def test_register_user_hashes_password(db_session: Session) -> None:
    user = register_user(
        db_session,
        UserCreate(email="ada@example.com", password="s3cret-pass", display_name="Ada"),
    )

    assert user.id is not None
    assert user.hashed_password != "s3cret-pass"


def test_register_user_rejects_duplicate_email(db_session: Session) -> None:
    _create_user(db_session)

    with pytest.raises(EmailAlreadyRegisteredError):
        register_user(
            db_session,
            UserCreate(email="ada@example.com", password="another-pass", display_name="Ada2"),
        )


def test_authenticate_user_succeeds_with_correct_password(db_session: Session) -> None:
    _create_user(db_session)

    user = authenticate_user(db_session, "ada@example.com", "s3cret-pass")

    assert user.email == "ada@example.com"


def test_authenticate_user_fails_with_wrong_password(db_session: Session) -> None:
    _create_user(db_session)

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, "ada@example.com", "wrong-pass")


def test_authenticate_user_fails_for_unknown_email(db_session: Session) -> None:
    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, "nobody@example.com", "whatever")
