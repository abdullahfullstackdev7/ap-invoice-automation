from datetime import date
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel

from app.models.enums import ExtractionSource
from app.ocr.types import BoundingBox


class ExtractedField[T](BaseModel):
    value: T | None = None
    confidence: float = 0.0
    source: ExtractionSource = ExtractionSource.rules
    bbox: BoundingBox | None = None

    @property
    def is_present(self) -> bool:
        return self.value is not None


class LineItemExtract(BaseModel):
    line_no: int
    description: ExtractedField[str]
    qty: ExtractedField[Decimal]
    unit_price: ExtractedField[Decimal]
    amount: ExtractedField[Decimal]


class InvoiceExtract(BaseModel):
    invoice_no: ExtractedField[str] = ExtractedField[str]()
    invoice_date: ExtractedField[date] = ExtractedField[date]()
    due_date: ExtractedField[date] = ExtractedField[date]()
    po_reference: ExtractedField[str] = ExtractedField[str]()
    vendor_name: ExtractedField[str] = ExtractedField[str]()
    vendor_email: ExtractedField[str] = ExtractedField[str]()
    vendor_tax_id: ExtractedField[str] = ExtractedField[str]()
    currency: ExtractedField[str] = ExtractedField[str]()
    subtotal: ExtractedField[Decimal] = ExtractedField[Decimal]()
    tax: ExtractedField[Decimal] = ExtractedField[Decimal]()
    discount: ExtractedField[Decimal] = ExtractedField[Decimal]()
    total: ExtractedField[Decimal] = ExtractedField[Decimal]()
    lines: list[LineItemExtract] = []

    HEADER_FIELDS: ClassVar[tuple[str, ...]] = (
        "invoice_no",
        "invoice_date",
        "due_date",
        "po_reference",
        "vendor_name",
        "vendor_email",
        "vendor_tax_id",
        "currency",
        "subtotal",
        "tax",
        "discount",
        "total",
    )
