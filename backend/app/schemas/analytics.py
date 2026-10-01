import uuid
from datetime import date
from decimal import Decimal

from app.schemas.base import ORMModel


class AnalyticsDailyRead(ORMModel):
    id: uuid.UUID
    date: date
    vendor_id: uuid.UUID | None
    category: str | None
    invoices_count: int
    value: Decimal
    stp_count: int
    savings_prevented: Decimal
    discounts_captured: Decimal
    discounts_missed: Decimal
