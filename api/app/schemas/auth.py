from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordResponse(BaseModel):
    message: str
    # populated only outside production, so a self-hosted operator can copy it
    reset_token: str | None = None


class MessageResponse(BaseModel):
    message: str


class UserOut(BaseModel):
    id: int
    email: str
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True


class AdminCreateUser(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.EDITOR


class AdminUpdateUser(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
