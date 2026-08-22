import pytest
from sqlalchemy.orm import Session

from app.schemas.user import UserCreate
from app.services.auth_service import register_user
from app.services.user_photo_service import (
    MAX_PHOTOS,
    PhotoNotFoundError,
    TooManyPhotosError,
    add_photo,
    list_photos,
    remove_photo,
)


def _register(db_session: Session, email: str) -> int:
    return register_user(
        db_session,
        UserCreate(email=email, password="S3cret-pass", display_name=email, accepted_terms=True, phone_number=f"5{abs(hash(email)) % 10**9:09d}"),
    ).id


def test_add_photo(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")

    photo = add_photo(db_session, user_id, "https://example.com/1.jpg")

    assert photo.user_id == user_id
    assert photo.photo_url == "https://example.com/1.jpg"
    assert photo.position == 0


def test_add_photo_increments_position(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    add_photo(db_session, user_id, "https://example.com/1.jpg")

    second = add_photo(db_session, user_id, "https://example.com/2.jpg")

    assert second.position == 1


def test_add_photo_raises_when_limit_reached(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    for i in range(MAX_PHOTOS):
        add_photo(db_session, user_id, f"https://example.com/{i}.jpg")

    with pytest.raises(TooManyPhotosError):
        add_photo(db_session, user_id, "https://example.com/overflow.jpg")


def test_list_photos_returns_only_my_photos_ordered(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    other_id = _register(db_session, "other@example.com")
    add_photo(db_session, user_id, "https://example.com/1.jpg")
    add_photo(db_session, user_id, "https://example.com/2.jpg")
    add_photo(db_session, other_id, "https://example.com/other.jpg")

    photos = list_photos(db_session, user_id)

    assert [p.photo_url for p in photos] == [
        "https://example.com/1.jpg",
        "https://example.com/2.jpg",
    ]


def test_remove_photo(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    photo = add_photo(db_session, user_id, "https://example.com/1.jpg")

    remove_photo(db_session, user_id, photo.id)

    assert list_photos(db_session, user_id) == []


def test_remove_photo_raises_for_unknown_photo(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")

    with pytest.raises(PhotoNotFoundError):
        remove_photo(db_session, user_id, 999)


def test_remove_photo_raises_when_not_owner(db_session: Session) -> None:
    user_id = _register(db_session, "user@example.com")
    other_id = _register(db_session, "other@example.com")
    photo = add_photo(db_session, user_id, "https://example.com/1.jpg")

    with pytest.raises(PhotoNotFoundError):
        remove_photo(db_session, other_id, photo.id)
