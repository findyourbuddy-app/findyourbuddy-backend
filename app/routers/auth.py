from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.password_reset import PasswordResetSender, get_password_reset_sender
from app.core.rate_limit import auth_rate_limit, limiter
from app.core.security import create_access_token
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    Token,
)
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import (
    EmailAlreadyRegisteredError,
    IncorrectCurrentPasswordError,
    InvalidCredentialsError,
    InvalidOrExpiredResetTokenError,
    authenticate_user,
    change_password,
    register_user,
    request_password_reset,
    reset_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(auth_rate_limit)
def register(request: Request, data: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    try:
        user = register_user(db, data)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from exc
    return user


@router.post("/login", response_model=Token)
@limiter.limit(auth_rate_limit)
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)) -> Token:
    try:
        user = authenticate_user(db, data.email, data.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        ) from exc
    return Token(access_token=create_access_token(subject=str(user.id)))


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(auth_rate_limit)
def request_reset(
    request: Request,
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
    reset_sender: PasswordResetSender = Depends(get_password_reset_sender),
) -> None:
    reset_token = request_password_reset(db, data.email)
    if reset_token is not None:
        reset_sender.send(data.email, reset_token)
    # Always responds 204 whether or not the email is registered, to avoid
    # leaking which emails have accounts.


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(auth_rate_limit)
def confirm_reset(request: Request, data: PasswordResetConfirm, db: Session = Depends(get_db)) -> None:
    try:
        reset_password(db, data.token, data.new_password)
    except InvalidOrExpiredResetTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token"
        ) from exc


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        change_password(db, current_user, data.current_password, data.new_password)
    except IncorrectCurrentPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
        ) from exc
