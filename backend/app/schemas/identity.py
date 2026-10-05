import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import EmailStr

from app.models.enums import UserRole
from app.schemas.base import ORMModel


class UserCreate(ORMModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole
    approval_limit: Decimal | None = None


class UserUpdate(ORMModel):
    full_name: str | None = None
    role: UserRole | None = None
    approval_limit: Decimal | None = None
    is_active: bool | None = None


class UserRead(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    approval_limit: Decimal | None
    is_active: bool
    last_login_at: datetime | None


class AssignableUserRead(ORMModel):
    """A slim, non-admin-gated user listing for exception reassignment and
    similar pickers - no email, limit or login history, just enough to
    label a dropdown option."""

    id: uuid.UUID
    full_name: str
    role: UserRole
