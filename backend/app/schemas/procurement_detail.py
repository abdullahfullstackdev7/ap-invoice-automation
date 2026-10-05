import uuid
from datetime import date
from decimal import Decimal

from app.models.enums import InvoiceStatus, POStatus
from app.schemas.base import ORMModel
from app.schemas.procurement import GoodsReceiptRead, POLineRead, PurchaseOrderRead


class PurchaseOrderListResponse(ORMModel):
    items: list[PurchaseOrderRead]
    total: int


class GoodsReceiptListResponse(ORMModel):
    items: list[GoodsReceiptRead]
    total: int


class LinkedInvoiceSummary(ORMModel):
    id: uuid.UUID
    invoice_no: str | None
    total: Decimal | None
    status: InvoiceStatus


class PurchaseOrderDetailRead(ORMModel):
    id: uuid.UUID
    po_number: str
    vendor_id: uuid.UUID
    currency: str
    status: POStatus
    po_date: date
    total: Decimal
    lines: list[POLineRead]
    receipts: list[GoodsReceiptRead]
    linked_invoices: list[LinkedInvoiceSummary]
