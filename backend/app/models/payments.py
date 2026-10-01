import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin
from app.models.enums import PaymentBatchStatus, PaymentMethod, PaymentStatus


class PaymentBatch(UUIDPKMixin, Base):
    __tablename__ = "payment_batches"

    created_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    released_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    file_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[PaymentBatchStatus] = mapped_column(String(10), default=PaymentBatchStatus.draft)


class Payment(UUIDPKMixin, Base):
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoices.id"), index=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payment_batches.id")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[PaymentStatus] = mapped_column(String(10), default=PaymentStatus.scheduled)
    method: Mapped[PaymentMethod] = mapped_column(String(20), default=PaymentMethod.bank_file)
