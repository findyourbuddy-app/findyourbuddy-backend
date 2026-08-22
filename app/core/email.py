import logging
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_plain_email(to: str, subject: str, body: str) -> bool:
    from app.config import get_settings
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_username:
        logger.warning("SMTP not configured; skipping email to %s", to)
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from_email or settings.smtp_username
        msg["To"] = to
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(msg["From"], [to], msg.as_string())
        logger.info("Email sent to %s", to)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def send_html_email(to: str, subject: str, body_html: str) -> bool:
    from app.config import get_settings
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_username:
        logger.warning("SMTP not configured; skipping email to %s", to)
        return False
    try:
        msg = MIMEText(body_html, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from_email or settings.smtp_username
        msg["To"] = to
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(msg["From"], [to], msg.as_string())
        logger.info("HTML Email sent to %s", to)
        return True
    except Exception:
        logger.exception("Failed to send HTML email to %s", to)
        return False
