import re

from pydantic import BaseModel, field_validator

from app.schemas import SafeEmail

_MIN_PASSWORD_LENGTH = 8
_PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$")


def _validate_password_strength(value: str) -> str:
    if len(value) < _MIN_PASSWORD_LENGTH:
        raise ValueError(f"Şifre en az {_MIN_PASSWORD_LENGTH} karakter olmalıdır.")
    if not _PASSWORD_PATTERN.match(value):
        raise ValueError("Şifre en az bir büyük harf, bir küçük harf ve bir rakam içermelidir.")
    return value


class LoginRequest(BaseModel):
    email: SafeEmail
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: SafeEmail


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class FirebaseLoginRequest(BaseModel):
    id_token: str
