import logging
from functools import lru_cache
from typing import Protocol

logger = logging.getLogger(__name__)


class PasswordResetSender(Protocol):
    def send(self, email: str, reset_token: str) -> None:
        """Delivers a password reset token to the user (email, SMS, etc.)."""
        ...


class LoggingPasswordResetSender:
    def send(self, email: str, reset_token: str) -> None:
        logger.info("password reset requested email=%s token=%s", email, reset_token)


@lru_cache
def get_password_reset_sender() -> PasswordResetSender:
    return LoggingPasswordResetSender()
