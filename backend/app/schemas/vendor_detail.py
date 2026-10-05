import uuid
from datetime import date
from decimal import Decimal

from app.models.enums import InvoiceStatus, VendorRiskTier, VendorStatus
from app.schemas.base import ORMModel
from app.schemas.masterdata import VendorRead


class VendorListResponse(ORMModel):
    items: list[VendorRead]
    total: int


class VendorSummaryInvoice(ORMModel):
    id: uuid.UUID
    invoice_no: str | None
    invoice_date: date | None
    total: Decimal | None
    status: InvoiceStatus


class VendorPriceHistoryPoint(ORMModel):
    date: date
    description: str
    unit_price: Decimal


class VendorDetailRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    name_normalized: str
    tax_id: str | None
    address: str | None
    email: str | None
    payment_terms_days: int
    discount_pct: Decimal | None
    discount_days: int | None
    risk_tier: VendorRiskTier
    category: str | None
    status: VendorStatus
    invoices_count: int
    total_spend: Decimal
    exception_count: int
    exception_rate: float | None
    recent_invoices: list[VendorSummaryInvoice]
    price_history: list[VendorPriceHistoryPoint]
