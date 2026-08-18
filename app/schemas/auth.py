from pydantic import BaseModel
from app.schemas import SafeEmail


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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class FirebaseLoginRequest(BaseModel):
    id_token: str
