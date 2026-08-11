import logging
from functools import lru_cache
from typing import Protocol

logger = logging.getLogger(__name__)


class NotificationSender(Protocol):
    def send(self, user_id: int, title: str, body: str) -> None:
        """Sends a push notification to a user."""
        ...


class LoggingNotificationSender:
    def send(self, user_id: int, title: str, body: str) -> None:
        logger.info("notification user_id=%s title=%r body=%r", user_id, title, body)


@lru_cache
def get_notification_sender() -> NotificationSender:
    return LoggingNotificationSender()
