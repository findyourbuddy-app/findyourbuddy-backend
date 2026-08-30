import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User
from app.services.subscription_service import is_premium

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
_optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _authenticate_token(token: str, db: Session) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error

    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_error

    return user


def get_current_user(
    token: str = Depends(_oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    return _authenticate_token(token, db)


def get_current_staff_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Staff privileges required"
        )
    return current_user


def get_current_premium_user(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> User:
    if not is_premium(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Premium subscription required"
        )
    return current_user


def require_scraper_api_key(x_scraper_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().scraper_api_key
    if x_scraper_api_key is None or not secrets.compare_digest(x_scraper_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid scraper API key"
        )


def require_metrics_access(
    x_metrics_api_key: str | None = Header(default=None),
    token: str | None = Depends(_optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> None:
    """Allow a Prometheus scrape via the metrics API key (sent as the
    ``X-Metrics-Api-Key`` header or as a bearer token), or a staff JWT."""
    configured_key = get_settings().metrics_api_key
    if configured_key:
        presented_key = x_metrics_api_key or token
        if presented_key is not None and secrets.compare_digest(presented_key, configured_key):
            return

    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not _authenticate_token(token, db).is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Staff privileges required"
        )
