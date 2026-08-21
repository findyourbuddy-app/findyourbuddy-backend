import secrets
import datetime
from typing import Tuple
from fastapi import logger

# Simple token generation for phone verification
def generate_verification_token(user_id: int) -> str:
    """Generate a token embedding the user ID and a random secret.
    The token format is `<user_id>:<random_string>`.
    """
    secret = secrets.token_urlsafe(16)
    return f"{user_id}:{secret}"

def parse_verification_token(token: str) -> Tuple[int, str] | None:
    """Parse the token and return (user_id, secret) if format is valid.
    Returns None if the token is malformed.
    """
    try:
        user_part, secret = token.split(":", 1)
        return int(user_part), secret
    except Exception as e:
        logger.error(f"Failed to parse verification token: {e}")
        return None

def is_token_expired(created_at: datetime.datetime, ttl_seconds: int = 3600) -> bool:
    """Check if the token is older than ttl_seconds (default 1 hour)."""
    return (datetime.datetime.now(datetime.timezone.utc) - created_at).total_seconds() > ttl_seconds
