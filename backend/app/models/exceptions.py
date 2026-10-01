import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin
from app.models.enums import ExceptionSeverity, ExceptionStatus


class ExceptionRecord(UUIDPKMixin, Base):
    __tablename__ = "exceptions"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoices.id"), index=True
    )
    reason_code: Mapped[str] = mapped_column(String(50))
    severity: Mapped[ExceptionSeverity] = mapped_column(String(10))
    details_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    status: Mapped[ExceptionStatus] = mapped_column(
        String(15), default=ExceptionStatus.open, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    resolution: Mapped[str | None] = mapped_column(String(1000))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
