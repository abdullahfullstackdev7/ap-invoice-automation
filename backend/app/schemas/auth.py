from pydantic import EmailStr

from app.schemas.base import ORMModel


class LoginRequest(ORMModel):
    email: EmailStr
    password: str


class LoginResponse(ORMModel):
    status: str
    mfa_token: str | None = None


class MFAVerifyRequest(ORMModel):
    mfa_token: str
    code: str


class PasswordChangeRequest(ORMModel):
    current_password: str
    new_password: str
