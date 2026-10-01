from datetime import date, timedelta
from decimal import Decimal

from app.extraction.types import ExtractedField, InvoiceExtract, LineItemExtract
from app.extraction.validator import validate
from app.models.enums import ExtractionSource


def _field[T](value: T, confidence: float = 0.95) -> ExtractedField[T]:
    return ExtractedField[T](value=value, confidence=confidence, source=ExtractionSource.rules)


def _clean_invoice() -> InvoiceExtract:
    return InvoiceExtract(
        invoice_no=_field("INV-001"),
        invoice_date=_field(date(2026, 9, 15)),
        due_date=_field(date(2026, 10, 15)),
        subtotal=_field(Decimal("175.00")),
        tax=_field(Decimal("17.50")),
        total=_field(Decimal("192.50")),
        lines=[
            LineItemExtract(
                line_no=1,
                description=_field("Widget A"),
                qty=_field(Decimal("3")),
                unit_price=_field(Decimal("25.00")),
                amount=_field(Decimal("75.00")),
            ),
            LineItemExtract(
                line_no=2,
                description=_field("Service B"),
                qty=_field(Decimal("1")),
                unit_price=_field(Decimal("100.00")),
                amount=_field(Decimal("100.00")),
            ),
        ],
    )


def test_clean_invoice_passes() -> None:
    result = validate(_clean_invoice())
    assert result.passed is True
    assert result.failing_fields == []
    assert result.needs_llm is False


def test_within_tolerance_drift_still_passes() -> None:
    invoice = _clean_invoice()
    invoice.total = _field(Decimal("192.51"))  # 0.01 off, within 0.02 tolerance

    result = validate(invoice)

    assert result.passed is True


def test_missing_required_field_fails() -> None:
    invoice = _clean_invoice()
    invoice.invoice_no = ExtractedField[str]()

    result = validate(invoice)

    assert result.passed is False
    assert "invoice_no" in result.failing_fields
    assert result.needs_llm is True


def test_line_arithmetic_mismatch_fails() -> None:
    invoice = _clean_invoice()
    invoice.lines[0].amount = _field(Decimal("999.99"))

    result = validate(invoice)

    assert result.passed is False
    assert any("lines[1]" in f for f in result.failing_fields)


def test_totals_mismatch_fails() -> None:
    invoice = _clean_invoice()
    invoice.total = _field(Decimal("500.00"))

    result = validate(invoice)

    assert result.passed is False
    assert "total" in result.failing_fields


def test_future_invoice_date_fails() -> None:
    invoice = _clean_invoice()
    invoice.invoice_date = _field(date.today() + timedelta(days=30))

    result = validate(invoice)

    assert result.passed is False
    assert "invoice_date" in result.failing_fields


def test_due_date_before_invoice_date_fails() -> None:
    invoice = _clean_invoice()
    assert invoice.invoice_date.value is not None
    invoice.due_date = _field(invoice.invoice_date.value - timedelta(days=5))

    result = validate(invoice)

    assert result.passed is False
    assert "due_date" in result.failing_fields


def test_low_confidence_field_flagged_for_llm_without_failing() -> None:
    invoice = _clean_invoice()
    invoice.po_reference = _field("PO-1", confidence=0.5)

    result = validate(invoice)

    assert result.passed is True
    assert "po_reference" in result.low_confidence_fields
    assert result.needs_llm is True


def test_missing_lines_fails() -> None:
    invoice = _clean_invoice()
    invoice.lines = []

    result = validate(invoice)

    assert result.passed is False
    assert "lines" in result.failing_fields
