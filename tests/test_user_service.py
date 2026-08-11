from sqlalchemy.orm import Session

from app.schemas.user import UserCreate, UserUpdate
from app.services.auth_service import register_user
from app.services.user_service import update_profile


def test_update_profile_applies_only_provided_fields(db_session: Session) -> None:
    user = register_user(
        db_session,
        UserCreate(email="ada@example.com", password="s3cret-pass", display_name="Ada"),
    )

    updated = update_profile(
        db_session, user, UserUpdate(age=28, interests=["hiking", "chess"])
    )

    assert updated.age == 28
    assert updated.interests == ["hiking", "chess"]
    assert updated.display_name == "Ada"


def test_update_profile_ignores_unset_fields(db_session: Session) -> None:
    user = register_user(
        db_session,
        UserCreate(email="ada@example.com", password="s3cret-pass", display_name="Ada"),
    )
    update_profile(db_session, user, UserUpdate(bio="Loves trails"))

    update_profile(db_session, user, UserUpdate(age=30))

    assert user.bio == "Loves trails"
    assert user.age == 30
