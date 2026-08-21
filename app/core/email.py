import logging

logger = logging.getLogger(__name__)


def send_plain_email(to: str, subject: str, body: str) -> bool:
    """Stub email handler -- Firebase Auth handles authentication & password reset emails directly."""
    logger.info("Skipping plain email delivery to %s (handled via Firebase Auth)", to)
    return False


def send_html_email(to: str, subject: str, html_body: str) -> bool:
    """Stub email handler -- Firebase Auth handles authentication & password reset emails directly."""
    logger.info("Skipping HTML email delivery to %s (handled via Firebase Auth)", to)
    return False

