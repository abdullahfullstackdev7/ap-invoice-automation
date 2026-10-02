from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class ContactSubmission(UUIDPKMixin, Base):
    """Public marketing site's Contact form, Plan.md section 10: "form with
    validation, stored via API." Unauthenticated, rate-limited at the API
    layer (see app/api/contact.py); no actor to audit-log against."""

    __tablename__ = "contact_submissions"

    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    company: Mapped[str | None] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(String(4000))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
