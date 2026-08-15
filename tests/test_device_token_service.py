from sqlalchemy.orm import Session

from app.models.device_token import DeviceToken
from app.services.device_token_service import register_device_token, unregister_device_token


def test_register_device_token_creates_new_token(db_session: Session) -> None:
    device_token = register_device_token(db_session, user_id=1, token="ExponentPushToken[abc]")

    assert device_token.user_id == 1
    assert device_token.token == "ExponentPushToken[abc]"


def test_register_device_token_reassigns_existing_token_to_new_user(db_session: Session) -> None:
    register_device_token(db_session, user_id=1, token="ExponentPushToken[abc]")

    reassigned = register_device_token(db_session, user_id=2, token="ExponentPushToken[abc]")

    assert reassigned.user_id == 2
    assert db_session.query(DeviceToken).count() == 1


def test_unregister_device_token_removes_it(db_session: Session) -> None:
    register_device_token(db_session, user_id=1, token="ExponentPushToken[abc]")

    unregister_device_token(db_session, user_id=1, token="ExponentPushToken[abc]")

    assert db_session.query(DeviceToken).count() == 0


def test_unregister_device_token_ignores_other_users_tokens(db_session: Session) -> None:
    register_device_token(db_session, user_id=1, token="ExponentPushToken[abc]")

    unregister_device_token(db_session, user_id=2, token="ExponentPushToken[abc]")

    assert db_session.query(DeviceToken).count() == 1
