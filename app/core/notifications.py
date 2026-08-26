import logging
from typing import Protocol

import httpx
from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.device_token import DeviceToken

logger = logging.getLogger(__name__)


class NotificationSender(Protocol):
    def send(self, user_id: int, title: str, body: str) -> None:
        """Sends a push notification to a user."""
        ...


class LoggingNotificationSender:
    def send(self, user_id: int, title: str, body: str) -> None:
        logger.info("notification user_id=%s title=%r body=%r", user_id, title, body)

    def send_bulk(self, user_ids: list[int], title: str, body: str) -> None:
        for user_id in user_ids:
            self.send(user_id, title, body)


class ExpoPushNotificationSender:
    """Sends push notifications via Expo's push HTTP API to every device
    token registered for the user. Requires the frontend to have registered
    at least one token via POST /users/me/device-tokens."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def send(self, user_id: int, title: str, body: str) -> None:
        tokens = [
            device_token.token
            for device_token in self._db.query(DeviceToken)
            .filter(DeviceToken.user_id == user_id)
            .all()
        ]
        if not tokens:
            return

        messages = [{"to": token, "title": title, "body": body} for token in tokens]
        try:
            httpx.post(get_settings().expo_push_api_url, json=messages, timeout=10.0)
        except httpx.HTTPError:
            logger.warning("failed to send push notification user_id=%s", user_id)

    def send_bulk(self, user_ids: list[int], title: str, body: str) -> None:
        """Fetches all device tokens for the given users in one query and
        sends a single batched request to the Expo push API."""
        if not user_ids:
            return
        tokens = [
            dt.token
            for dt in self._db.query(DeviceToken)
            .filter(DeviceToken.user_id.in_(user_ids))
            .all()
        ]
        if not tokens:
            return
        messages = [{"to": token, "title": title, "body": body} for token in tokens]
        try:
            httpx.post(get_settings().expo_push_api_url, json=messages, timeout=10.0)
        except httpx.HTTPError:
            logger.warning("failed to send bulk push notification user_ids=%s", user_ids)


def get_notification_sender(db: Session = Depends(get_db)) -> NotificationSender:
    if get_settings().push_provider == "expo":
        return ExpoPushNotificationSender(db)
    return LoggingNotificationSender()
