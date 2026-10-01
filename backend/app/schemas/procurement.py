import uuid
from datetime import date
from decimal import Decimal

from app.models.enums import POStatus
from app.schemas.base import ORMModel


class POLineRead(ORMModel):
    id: uuid.UUID
    line_no: int
    item_id: uuid.UUID | None
    description: str
    qty: Decimal
    unit_price: Decimal
    amount: Decimal
    qty_invoiced_cum: Decimal


class PurchaseOrderCreate(ORMModel):
    po_number: str
    vendor_id: uuid.UUID
    currency: str = "USD"
    po_date: date
    total: Decimal


class PurchaseOrderRead(ORMModel):
    id: uuid.UUID
    po_number: str
    vendor_id: uuid.UUID
    currency: str
    status: POStatus
    po_date: date
    total: Decimal
    lines: list[POLineRead] = []


class GRLineRead(ORMModel):
    id: uuid.UUID
    po_line_id: uuid.UUID
    qty_received: Decimal


class GoodsReceiptCreate(ORMModel):
    grn_number: str
    po_id: uuid.UUID
    received_date: date
    received_by: str


class GoodsReceiptRead(ORMModel):
    id: uuid.UUID
    grn_number: str
    po_id: uuid.UUID
    received_date: date
    received_by: str
    lines: list[GRLineRead] = []
