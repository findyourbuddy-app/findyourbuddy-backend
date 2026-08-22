from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expires_at, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, token_version: int = 0) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
    payload = {"sub": subject, "exp": expires_at, "type": "refresh", "ver": token_version}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_refresh_token_with_version(token: str) -> tuple[str, int] | None:
    """Returns (user_id, token_version) or None if invalid."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("type", "access") != "refresh":
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    return sub, int(payload.get("ver", 0))


def decode_access_token(token: str) -> str | None:
    return _decode_token_of_type(token, "access")


def decode_refresh_token(token: str) -> str | None:
    return _decode_token_of_type(token, "refresh")


def _decode_token_of_type(token: str, expected_type: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    # Tokens issued before this "type" claim existed have none -- treat
    # those as access tokens so already-logged-in sessions don't break.
    if payload.get("type", "access") != expected_type:
        return None
    return payload.get("sub")
