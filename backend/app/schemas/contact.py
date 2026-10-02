from pydantic import EmailStr, Field

from app.schemas.base import ORMModel


class ContactSubmissionCreate(ORMModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    company: str | None = Field(default=None, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
