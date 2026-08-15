import logging
from functools import lru_cache
from typing import Protocol

from app.config import get_settings

logger = logging.getLogger(__name__)


class SmsSender(Protocol):
    def send(self, phone_number: str, code: str) -> None:
        """Delivers a phone verification code to the given number."""
        ...


class LoggingSmsSender:
    def send(self, phone_number: str, code: str) -> None:
        logger.info("phone verification code phone=%s code=%s", phone_number, code)


@lru_cache
def get_sms_sender() -> SmsSender:
    # No real SMS provider is wired up yet (Netgsm/Twilio/etc. need an account
    # and API keys). Swap this once one is chosen; logging keeps the codebase
    # provider-agnostic in the meantime, mirroring push_provider in config.py.
    if get_settings().sms_provider == "logging":
        return LoggingSmsSender()
    return LoggingSmsSender()
