from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(_oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error

    user = db.get(User, int(user_id))
    if user is None:
        raise credentials_error

    return user


def get_current_staff_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Staff privileges required"
        )
    return current_user


def require_scraper_api_key(x_scraper_api_key: str | None = Header(default=None)) -> None:
    if x_scraper_api_key is None or x_scraper_api_key != get_settings().scraper_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid scraper API key"
        )
