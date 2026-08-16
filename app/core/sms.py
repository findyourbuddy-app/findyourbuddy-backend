import logging
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import get_settings
from app.models.user import User

logger = logging.getLogger(__name__)


class SmsSender(Protocol):
    def send(self, user: User, code: str) -> None:
        """Delivers a phone verification code to the user."""
        ...


class LoggingSmsSender:
    def send(self, user: User, code: str) -> None:
        logger.info("phone verification code phone=%s code=%s", user.phone_number, code)


class NetgsmSmsSender:
    """Sends the code as a real SMS via Netgsm's REST gateway. Requires a
    paid Netgsm account (NETGSM_USERNAME/NETGSM_PASSWORD/NETGSM_HEADER in
    .env) -- until that's set up, get_sms_sender() falls back to logging."""

    def send(self, user: User, code: str) -> None:
        settings = get_settings()
        message = f"FindYourBuddy dogrulama kodun: {code}"
        try:
            response = httpx.get(
                "https://api.netgsm.com.tr/sms/send/get",
                params={
                    "usercode": settings.netgsm_username,
                    "password": settings.netgsm_password,
                    "gsmno": user.phone_number,
                    "message": message,
                    "msgheader": settings.netgsm_header,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            logger.info("netgsm sms sent phone=%s response=%s", user.phone_number, response.text.strip())
        except Exception as exc:
            logger.error("Failed to send SMS via Netgsm to %s: %s", user.phone_number, exc)


@lru_cache
def get_sms_sender() -> SmsSender:
    settings = get_settings()
    if settings.sms_provider == "netgsm" and settings.netgsm_username and settings.netgsm_password:
        return NetgsmSmsSender()
    return LoggingSmsSender()
