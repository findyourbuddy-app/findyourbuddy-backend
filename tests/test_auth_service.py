from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.password_reset_token import PasswordResetToken
from app.schemas.user import UserCreate
from app.services.auth_service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    InvalidOrExpiredResetTokenError,
    authenticate_user,
    delete_expired_reset_tokens,
    register_user,
    request_password_reset,
    reset_password,
)


def _create_user(db_session: Session) -> None:
    register_user(
        db_session,
        UserCreate(
            email="ada@example.com",
            password="S3cret-pass",
            display_name="Ada",
            accepted_terms=True,
            phone_number="5000000001",
        ),
    )


def test_register_user_hashes_password(db_session: Session) -> None:
    user = register_user(
        db_session,
        UserCreate(
            email="ada@example.com",
            password="S3cret-pass",
            display_name="Ada",
            accepted_terms=True,
            phone_number="5000000001",
        ),
    )

    assert user.id is not None
    assert user.hashed_password != "S3cret-pass"


def test_register_user_rejects_duplicate_email(db_session: Session) -> None:
    _create_user(db_session)

    with pytest.raises(EmailAlreadyRegisteredError):
        register_user(
            db_session,
            UserCreate(
                email="ada@example.com",
                password="anOther-pass1",
                display_name="Ada2",
                accepted_terms=True,
                phone_number="5000000002",
            ),
        )


def test_authenticate_user_succeeds_with_correct_password(db_session: Session) -> None:
    _create_user(db_session)

    user = authenticate_user(db_session, "ada@example.com", "S3cret-pass")

    assert user.email == "ada@example.com"


def test_authenticate_user_fails_with_wrong_password(db_session: Session) -> None:
    _create_user(db_session)

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, "ada@example.com", "wrong-pass")


def test_authenticate_user_fails_for_unknown_email(db_session: Session) -> None:
    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, "nobody@example.com", "whatever")


def test_request_password_reset_returns_token_for_known_email(db_session: Session) -> None:
    _create_user(db_session)

    token = request_password_reset(db_session, "ada@example.com")

    assert token is not None


def test_request_password_reset_returns_none_for_unknown_email(db_session: Session) -> None:
    token = request_password_reset(db_session, "nobody@example.com")

    assert token is None


def test_reset_password_allows_login_with_new_password(db_session: Session) -> None:
    _create_user(db_session)
    token = request_password_reset(db_session, "ada@example.com")
    assert token is not None

    reset_password(db_session, token, "NewSecret1!")

    user = authenticate_user(db_session, "ada@example.com", "NewSecret1!")
    assert user.email == "ada@example.com"
    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, "ada@example.com", "S3cret-pass")


def test_reset_password_rejects_unknown_token(db_session: Session) -> None:
    with pytest.raises(InvalidOrExpiredResetTokenError):
        reset_password(db_session, "not-a-real-token", "NewSecret1!")


def test_reset_password_rejects_reused_token(db_session: Session) -> None:
    _create_user(db_session)
    token = request_password_reset(db_session, "ada@example.com")
    assert token is not None
    reset_password(db_session, token, "NewSecret1!")

    with pytest.raises(InvalidOrExpiredResetTokenError):
        reset_password(db_session, token, "anOther-pass1")


def test_delete_expired_reset_tokens_removes_used_and_expired_only(db_session: Session) -> None:
    _create_user(db_session)
    token = request_password_reset(db_session, "ada@example.com")
    assert token is not None
    reset_password(db_session, token, "NewSecret1!")  # marks it used

    fresh_token = request_password_reset(db_session, "ada@example.com")
    assert fresh_token is not None

    expired = db_session.query(PasswordResetToken).filter(
        PasswordResetToken.token == fresh_token
    ).first()
    expired.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    another_fresh_token = request_password_reset(db_session, "ada@example.com")
    assert another_fresh_token is not None

    deleted_count = delete_expired_reset_tokens(db_session)

    assert deleted_count == 2
    remaining_tokens = {t.token for t in db_session.query(PasswordResetToken).all()}
    assert remaining_tokens == {another_fresh_token}
