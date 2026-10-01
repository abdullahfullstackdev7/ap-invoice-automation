import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin
from app.models.enums import MatchLineStatus, MatchOutcome


class MatchResult(UUIDPKMixin, Base):
    __tablename__ = "match_results"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoices.id"), index=True
    )
    po_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("purchase_orders.id")
    )
    outcome: Mapped[MatchOutcome] = mapped_column(String(20))
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    tolerance_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tolerance_policies.id")
    )
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    line_results: Mapped[list["MatchLineResult"]] = relationship(back_populates="match")


class MatchLineResult(UUIDPKMixin, Base):
    __tablename__ = "match_line_results"

    match_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("match_results.id"), index=True
    )
    invoice_line_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoice_lines.id")
    )
    po_line_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("po_lines.id")
    )
    qty_inv: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    qty_po: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    qty_recv: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    qty_prev_invoiced: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    price_inv: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    price_po: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    qty_var: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    price_var_pct: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    status: Mapped[MatchLineStatus] = mapped_column(String(10))

    match: Mapped[MatchResult] = relationship(back_populates="line_results")
