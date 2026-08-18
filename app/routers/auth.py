from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.password_reset import PasswordResetSender, get_password_reset_sender
from app.core.rate_limit import auth_rate_limit, limiter
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token
from app.core.sms import LoggingSmsSender, SmsSender, get_sms_sender
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    PhoneVerificationConfirm,
    RefreshRequest,
    Token,
)
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import (
    EmailAlreadyRegisteredError,
    IncorrectCurrentPasswordError,
    InvalidCredentialsError,
    InvalidOrExpiredPhoneCodeError,
    InvalidOrExpiredResetTokenError,
    PhoneAlreadyVerifiedError,
    PhoneNumberAlreadyRegisteredError,
    authenticate_user,
    change_password,
    create_phone_verification_code,
    register_user,
    request_password_reset,
    reset_password,
    verify_phone_code,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@router.post("/register/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(auth_rate_limit)
def register(
    request: Request,
    data: UserCreate,
    db: Session = Depends(get_db),
    sms_sender: SmsSender = Depends(get_sms_sender),
) -> UserRead:
    try:
        user = register_user(db, data)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from exc
    except PhoneNumberAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered"
        ) from exc
    if isinstance(sms_sender, LoggingSmsSender):
        user.phone_verified = True
        db.commit()
        db.refresh(user)
    else:
        code = create_phone_verification_code(db, user)
        sms_sender.send(user, code)
    return user


@router.post("/phone/verify", status_code=status.HTTP_204_NO_CONTENT)
@router.post("/phone/verify/", status_code=status.HTTP_204_NO_CONTENT)
def verify_phone(
    data: PhoneVerificationConfirm,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        verify_phone_code(db, current_user, data.code)
    except InvalidOrExpiredPhoneCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code"
        ) from exc
    except PhoneAlreadyVerifiedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Phone already verified"
        ) from exc


@router.post("/phone/resend", status_code=status.HTTP_204_NO_CONTENT)
@router.post("/phone/resend/", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(auth_rate_limit)
def resend_phone_code(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    sms_sender: SmsSender = Depends(get_sms_sender),
) -> None:
    if current_user.phone_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone already verified")
    code = create_phone_verification_code(db, current_user)
    sms_sender.send(current_user, code)


@router.post("/login", response_model=Token)
@router.post("/login/", response_model=Token)
@limiter.limit(auth_rate_limit)
def login(request: Request, data: LoginRequest, db: Session = Depends(get_db)) -> Token:
    try:
        user = authenticate_user(db, data.email, data.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        ) from exc
    return Token(
        access_token=create_access_token(subject=str(user.id)),
        refresh_token=create_refresh_token(subject=str(user.id)),
    )


@router.post("/refresh", response_model=Token)
@router.post("/refresh/", response_model=Token)
@limiter.limit(auth_rate_limit)
def refresh(request: Request, data: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
    )
    user_id = decode_refresh_token(data.refresh_token)
    if user_id is None:
        raise credentials_error
    user = db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise credentials_error
    return Token(
        access_token=create_access_token(subject=str(user.id)),
        refresh_token=create_refresh_token(subject=str(user.id)),
    )


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT)
@router.post("/password-reset/request/", status_code=status.HTTP_204_NO_CONTENT)
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


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
@router.post("/password-reset/confirm/", status_code=status.HTTP_204_NO_CONTENT)
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
