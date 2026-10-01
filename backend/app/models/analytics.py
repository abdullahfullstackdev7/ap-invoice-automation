import uuid
from datetime import date as date_
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class AnalyticsDaily(UUIDPKMixin, Base):
    __tablename__ = "analytics_daily"

    date: Mapped[date_] = mapped_column(Date, index=True)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id")
    )
    category: Mapped[str | None] = mapped_column(String(100))
    invoices_count: Mapped[int] = mapped_column(Integer, default=0)
    value: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    exceptions_by_type_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    stp_count: Mapped[int] = mapped_column(Integer, default=0)
    savings_prevented: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    discounts_captured: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    discounts_missed: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)

    __table_args__ = (
        UniqueConstraint("date", "vendor_id", "category", name="uq_analytics_daily_grain"),
    )
