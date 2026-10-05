import uuid
from datetime import date, datetime
from decimal import Decimal

from app.models.enums import ExtractionSource, InvoiceStatus
from app.schemas.base import ORMModel


class DocumentCreate(ORMModel):
    sha256: str
    filename: str
    mime: str
    size: int
    storage_path: str
    page_count: int = 1
    uploaded_by: uuid.UUID | None = None
    uploaded_at: datetime


class DocumentRead(ORMModel):
    id: uuid.UUID
    sha256: str
    filename: str
    mime: str
    size: int
    page_count: int
    uploaded_at: datetime


class InvoiceLineRead(ORMModel):
    id: uuid.UUID
    line_no: int
    sku: str | None
    description: str
    qty: Decimal
    unit_price: Decimal
    amount: Decimal


class InvoiceRead(ORMModel):
    id: uuid.UUID
    document_id: uuid.UUID
    vendor_id: uuid.UUID | None
    invoice_no: str | None
    invoice_date: date | None
    due_date: date | None
    currency: str
    subtotal: Decimal | None
    tax: Decimal | None
    freight: Decimal | None
    discount: Decimal | None
    total: Decimal | None
    po_number_ref: str | None
    status: InvoiceStatus
    extraction_confidence: Decimal | None
    lines: list[InvoiceLineRead] = []


class InvoiceListItem(ORMModel):
    id: uuid.UUID
    invoice_no: str | None
    invoice_date: date | None
    due_date: date | None
    currency: str
    total: Decimal | None
    status: InvoiceStatus
    vendor_id: uuid.UUID | None
    vendor_name: str | None
    extraction_confidence: Decimal | None


class InvoiceListResponse(ORMModel):
    items: list[InvoiceListItem]
    total: int


class InvoiceFieldUpdate(ORMModel):
    invoice_no: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    freight: Decimal | None = None
    discount: Decimal | None = None
    total: Decimal | None = None
    po_number_ref: str | None = None


class UploadResultItem(ORMModel):
    filename: str
    status: str  # "queued" | "duplicate_exact" | "rejected"
    document_id: uuid.UUID | None = None
    invoice_id: uuid.UUID | None = None
    detail: str | None = None


class ExtractionRunRead(ORMModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    stage_path: ExtractionSource
    provider: str | None
    model: str | None
    tokens_in: int | None
    tokens_out: int | None
    latency_ms: int | None
    cache_hit: bool
    run_at: datetime
