from unittest.mock import patch

import httpx
from sqlalchemy.orm import Session

from app.core.notifications import ExpoPushNotificationSender, LoggingNotificationSender, get_notification_sender
from app.models.device_token import DeviceToken


def test_send_posts_to_expo_for_each_registered_token(db_session: Session) -> None:
    db_session.add(DeviceToken(user_id=1, token="ExponentPushToken[a]"))
    db_session.add(DeviceToken(user_id=1, token="ExponentPushToken[b]"))
    db_session.commit()
    sender = ExpoPushNotificationSender(db_session)

    with patch("app.core.notifications.httpx.post") as mock_post:
        sender.send(user_id=1, title="New match!", body="You matched.")

    assert mock_post.call_count == 1
    _, kwargs = mock_post.call_args
    sent_tokens = {message["to"] for message in kwargs["json"]}
    assert sent_tokens == {"ExponentPushToken[a]", "ExponentPushToken[b]"}


def test_send_does_nothing_when_user_has_no_device_tokens(db_session: Session) -> None:
    sender = ExpoPushNotificationSender(db_session)

    with patch("app.core.notifications.httpx.post") as mock_post:
        sender.send(user_id=1, title="New match!", body="You matched.")

    mock_post.assert_not_called()


def test_send_swallows_network_errors(db_session: Session) -> None:
    db_session.add(DeviceToken(user_id=1, token="ExponentPushToken[a]"))
    db_session.commit()
    sender = ExpoPushNotificationSender(db_session)

    with patch("app.core.notifications.httpx.post", side_effect=httpx.ConnectError("boom")):
        sender.send(user_id=1, title="New match!", body="You matched.")


def test_get_notification_sender_defaults_to_logging(db_session: Session, monkeypatch) -> None:
    from app.config import get_settings

    monkeypatch.delenv("PUSH_PROVIDER", raising=False)
    get_settings.cache_clear()

    sender = get_notification_sender(db_session)

    assert isinstance(sender, LoggingNotificationSender)
    get_settings.cache_clear()


def test_get_notification_sender_returns_expo_sender_when_configured(
    db_session: Session, monkeypatch
) -> None:
    from app.config import get_settings

    monkeypatch.setenv("PUSH_PROVIDER", "expo")
    get_settings.cache_clear()

    sender = get_notification_sender(db_session)

    assert isinstance(sender, ExpoPushNotificationSender)
    monkeypatch.delenv("PUSH_PROVIDER", raising=False)
    get_settings.cache_clear()
