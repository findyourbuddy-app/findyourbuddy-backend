import logging
import smtplib
from functools import lru_cache
from typing import Protocol
from email.mime.text import MIMEText

from app.config import get_settings

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
        settings = get_settings()
        if not settings.smtp_username or not settings.smtp_password:
            # Fallback to logging if credentials are not configured in .env
            logger.warning("SMTP credentials not configured. Skipping SMTP email delivery.")
            return

        subject = "FindYourBuddy - Şifre Sıfırlama Talebi"
        body = (
            f"Merhaba,\n\n"
            f"Şifrenizi sıfırlamak için aşağıdaki kodu uygulamadaki şifre sıfırlama ekranına girin:\n\n"
            f"KOD: {reset_token}\n\n"
            f"Bu kod 15 dakika boyunca geçerlidir. Eğer bu talebi siz yapmadıysanız lütfen bu e-postayı dikkate almayın.\n\n"
            f"İyi günler,\n"
            f"FindYourBuddy Ekibi"
        )

        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = settings.smtp_sender
            msg["To"] = email

            # Connect to SMTP server (defaults to port 587 with starttls)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_username, settings.smtp_password)
                server.sendmail(settings.smtp_sender, [email], msg.as_string())
            logger.info("Password reset email sent successfully to %s", email)
        except Exception as e:
            logger.error("Failed to send password reset email to %s: %s", email, e)


@lru_cache
def get_password_reset_sender() -> PasswordResetSender:
    return SMTPPasswordResetSender()
