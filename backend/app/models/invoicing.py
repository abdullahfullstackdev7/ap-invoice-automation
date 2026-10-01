import uuid
from datetime import date, datetime
from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin
from app.models.enums import ExtractionSource, InvoiceStatus
from app.models.masterdata import EMBEDDING_DIM


class Document(UUIDPKMixin, Base):
    __tablename__ = "documents"

    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(300))
    mime: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id")
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Invoice(UUIDPKMixin, Base):
    __tablename__ = "invoices"

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id"), index=True
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), index=True
    )
    invoice_no: Mapped[str | None] = mapped_column(String(100))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    tax: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    freight: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    discount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    po_number_ref: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[InvoiceStatus] = mapped_column(
        String(20), default=InvoiceStatus.uploaded, index=True
    )
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    dup_key: Mapped[str | None] = mapped_column(String(300), index=True)
    extracted_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)

    lines: Mapped[list["InvoiceLine"]] = relationship(back_populates="invoice")

    __table_args__ = (
        # Deliberately a plain index, not a UNIQUE constraint: Plan.md
        # section 7's duplicate-invoice handling (DUPLICATE_EXACT
        # exception, BLOCKED outcome) requires a duplicate invoice to be
        # persisted as its own row, visible in the UI and referencing the
        # original, not rejected by the database before the match engine
        # ever sees it. Exact (vendor_id, invoice_no) duplicates are a
        # real business event the app must capture, not an integrity
        # error; app.matching.duplicate enforces this logically instead.
        Index("ix_invoices_vendor_invoice_no", "vendor_id", "invoice_no"),
    )


class InvoiceLine(UUIDPKMixin, Base):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoices.id"), index=True
    )
    line_no: Mapped[int] = mapped_column(Integer)
    sku: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(500))
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    bbox_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    invoice: Mapped[Invoice] = relationship(back_populates="lines")

    __table_args__ = (
        Index(
            "ix_invoice_lines_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class ExtractionRun(UUIDPKMixin, Base):
    __tablename__ = "extraction_runs"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("invoices.id"), index=True
    )
    stage_path: Mapped[ExtractionSource] = mapped_column(String(20))
    provider: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(default=False)
    errors_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
