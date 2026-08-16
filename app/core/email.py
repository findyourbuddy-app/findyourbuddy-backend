import logging
import smtplib
from email.mime.text import MIMEText

from app.config import get_settings

logger = logging.getLogger(__name__)


def send_plain_email(to: str, subject: str, body: str) -> bool:
    """Sends a plain-text email via the configured SMTP account. Returns
    whether delivery succeeded so callers can log/fallback accordingly."""
    settings = get_settings()
    if not settings.smtp_username or not settings.smtp_password:
        logger.warning("SMTP credentials not configured. Skipping email delivery to %s.", to)
        return False

    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_sender
        msg["To"] = to

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(settings.smtp_sender, [to], msg.as_string())
        logger.info("Email sent successfully to %s", to)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        return False
