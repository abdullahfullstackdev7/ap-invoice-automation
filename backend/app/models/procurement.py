import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin
from app.models.enums import POStatus


class PurchaseOrder(UUIDPKMixin, Base):
    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(String(30), unique=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), index=True
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[POStatus] = mapped_column(String(10), default=POStatus.open)
    po_date: Mapped[date] = mapped_column(Date)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    lines: Mapped[list["POLine"]] = relationship(back_populates="po")
    receipts: Mapped[list["GoodsReceipt"]] = relationship(back_populates="po")


class POLine(UUIDPKMixin, Base):
    __tablename__ = "po_lines"

    po_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("purchase_orders.id"), index=True
    )
    line_no: Mapped[int] = mapped_column(Integer)
    item_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("items.id"))
    description: Mapped[str] = mapped_column(String(500))
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    qty_invoiced_cum: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)

    po: Mapped[PurchaseOrder] = relationship(back_populates="lines")


class GoodsReceipt(UUIDPKMixin, Base):
    __tablename__ = "goods_receipts"

    grn_number: Mapped[str] = mapped_column(String(30), unique=True)
    po_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("purchase_orders.id"), index=True
    )
    received_date: Mapped[date] = mapped_column(Date)
    received_by: Mapped[str] = mapped_column(String(200))

    po: Mapped[PurchaseOrder] = relationship(back_populates="receipts")
    lines: Mapped[list["GRLine"]] = relationship(back_populates="receipt")


class GRLine(UUIDPKMixin, Base):
    __tablename__ = "gr_lines"

    grn_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("goods_receipts.id"), index=True
    )
    po_line_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("po_lines.id"), index=True
    )
    qty_received: Mapped[Decimal] = mapped_column(Numeric(14, 3))

    receipt: Mapped[GoodsReceipt] = relationship(back_populates="lines")
