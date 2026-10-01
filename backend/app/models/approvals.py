import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin
from app.models.enums import ApprovalDecision


class Approval(UUIDPKMixin, Base):
    __tablename__ = "approvals"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoices.id"), index=True
    )
    step: Mapped[int] = mapped_column(Integer)
    approver_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    decision: Mapped[ApprovalDecision] = mapped_column(String(10))
    comment: Mapped[str | None] = mapped_column(String(1000))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
