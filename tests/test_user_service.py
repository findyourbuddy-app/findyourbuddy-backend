from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.schemas.user import UserCreate, UserUpdate
from app.services.auth_service import InvalidCredentialsError, authenticate_user, register_user
from app.services.user_service import delete_account, update_profile


def _birth_date_for_age(age: int) -> date:
    today = date.today()
    return today.replace(year=today.year - age)


def test_update_profile_applies_only_provided_fields(db_session: Session) -> None:
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

    updated = update_profile(
        db_session,
        user,
        UserUpdate(date_of_birth=_birth_date_for_age(28), interests=["hiking", "chess"]),
    )

    assert updated.age == 28
    assert updated.interests == ["hiking", "chess"]
    assert updated.display_name == "Ada"


def test_update_profile_ignores_unset_fields(db_session: Session) -> None:
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
    update_profile(db_session, user, UserUpdate(bio="Loves trails"))

    update_profile(db_session, user, UserUpdate(date_of_birth=_birth_date_for_age(30)))

    assert user.bio == "Loves trails"
    assert user.age == 30


def test_delete_account_deactivates_and_scrubs_pii(db_session: Session) -> None:
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
    user.occupation = "Engineer"
    user.gender = "female"
    user.height = 170
    user.political_views = "Centrist"
    user.beliefs = "Agnostic"
    user.voice_note_url = "http://localhost:8000/media/voice.mp3"
    user.languages_spoken = ["TR", "EN"]
    user.hidden_fields = ["age"]
    user.photo_url = "http://localhost:8000/media/profile.jpg"
    update_profile(db_session, user, UserUpdate(bio="Loves trails", interests=["hiking"]))

    delete_account(db_session, user)

    assert user.is_active is False
    assert user.email != "ada@example.com"
    assert user.bio is None
    assert user.interests == []
    assert user.photo_url is None
    assert user.voice_note_url is None
    assert user.occupation is None
    assert user.gender is None
    assert user.height is None
    assert user.political_views is None
    assert user.beliefs is None
    assert user.languages_spoken == []
    assert user.hidden_fields == []


def test_delete_account_prevents_future_login(db_session: Session) -> None:
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

    delete_account(db_session, user)

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, "ada@example.com", "S3cret-pass")


def test_delete_account_frees_email_for_reuse(db_session: Session) -> None:
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
    delete_account(db_session, user)

    new_user = register_user(
        db_session,
        UserCreate(
            email="ada@example.com",
            password="anOther-pass1",
            display_name="Ada2",
            accepted_terms=True,
            phone_number="5000000002",
        ),
    )

    assert new_user.id != user.id
