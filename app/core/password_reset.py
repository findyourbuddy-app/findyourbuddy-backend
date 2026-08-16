import logging
from functools import lru_cache
from typing import Protocol

from app.core.email import send_plain_email

logger = logging.getLogger(__name__)


class PasswordResetSender(Protocol):
    def send(self, email: str, reset_token: str) -> None:
        """Delivers a password reset token to the user (email, SMS, etc.)."""
        ...


class LoggingPasswordResetSender:
    def send(self, email: str, reset_token: str) -> None:
        logger.info("password reset requested email=%s token=%s", email, reset_token)


class SMTPPasswordResetSender:
    def send(self, email: str, reset_token: str) -> None:
        logger.info("password reset requested email=%s token=%s", email, reset_token)
        subject = "FindYourBuddy - Şifre Sıfırlama Talebi"
        body = (
            f"Merhaba,\n\n"
            f"Şifrenizi sıfırlamak için aşağıdaki kodu uygulamadaki şifre sıfırlama ekranına girin:\n\n"
            f"KOD: {reset_token}\n\n"
            f"Bu kod 15 dakika boyunca geçerlidir. Eğer bu talebi siz yapmadıysanız lütfen bu e-postayı dikkate almayın.\n\n"
            f"İyi günler,\n"
            f"FindYourBuddy Ekibi"
        )
        send_plain_email(email, subject, body)


@lru_cache
def get_password_reset_sender() -> PasswordResetSender:
    return SMTPPasswordResetSender()
