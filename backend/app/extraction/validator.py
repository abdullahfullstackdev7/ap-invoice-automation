from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.extraction.types import InvoiceExtract

ARITHMETIC_TOLERANCE = Decimal("0.02")
CONFIDENCE_THRESHOLD = 0.8
REQUIRED_FIELDS = ("invoice_no", "invoice_date", "total")


@dataclass
class ValidationResult:
    passed: bool
    failing_fields: list[str] = field(default_factory=list)
    low_confidence_fields: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def needs_llm(self) -> bool:
        return bool(self.failing_fields or self.low_confidence_fields)


def _check_line_arithmetic(extract: InvoiceExtract, errors: list[str], failing: list[str]) -> None:
    for line in extract.lines:
        qty, price, amount = line.qty.value, line.unit_price.value, line.amount.value
        if qty is None or price is None or amount is None:
            continue
        computed = qty * price
        if abs(computed - amount) > ARITHMETIC_TOLERANCE:
            errors.append(
                f"line {line.line_no}: qty * unit_price ({computed}) != amount ({amount})"
            )
            failing.append(f"lines[{line.line_no}]")


def _check_totals_arithmetic(
    extract: InvoiceExtract, errors: list[str], failing: list[str]
) -> None:
    line_amounts = [line.amount.value for line in extract.lines if line.amount.value is not None]
    if line_amounts and extract.subtotal.value is not None:
        line_sum = sum(line_amounts, Decimal("0"))
        if abs(line_sum - extract.subtotal.value) > ARITHMETIC_TOLERANCE:
            errors.append(f"sum(lines)={line_sum} != subtotal={extract.subtotal.value}")
            failing.append("subtotal")

    subtotal = extract.subtotal.value
    tax = extract.tax.value or Decimal("0")
    discount = extract.discount.value or Decimal("0")
    total = extract.total.value
    if subtotal is not None and total is not None:
        computed_total = subtotal + tax - discount
        if abs(computed_total - total) > ARITHMETIC_TOLERANCE:
            errors.append(f"subtotal + tax - discount ({computed_total}) != total ({total})")
            failing.append("total")


def _check_date_sanity(extract: InvoiceExtract, errors: list[str], failing: list[str]) -> None:
    today = datetime.now(UTC).date()
    invoice_date = extract.invoice_date.value
    due_date = extract.due_date.value

    if invoice_date is not None and invoice_date > today + timedelta(days=1):
        errors.append(f"invoice_date {invoice_date} is in the future")
        failing.append("invoice_date")

    if invoice_date is not None and due_date is not None and due_date < invoice_date:
        errors.append(f"due_date {due_date} is before invoice_date {invoice_date}")
        failing.append("due_date")


def _check_required_fields(extract: InvoiceExtract, failing: list[str]) -> None:
    for field_name in REQUIRED_FIELDS:
        extracted_field = getattr(extract, field_name)
        if not extracted_field.is_present:
            failing.append(field_name)
    if not extract.lines:
        failing.append("lines")


def _check_confidence(extract: InvoiceExtract, low_confidence: list[str]) -> None:
    for field_name in InvoiceExtract.HEADER_FIELDS:
        extracted_field = getattr(extract, field_name)
        if extracted_field.is_present and extracted_field.confidence < CONFIDENCE_THRESHOLD:
            low_confidence.append(field_name)


def validate(extract: InvoiceExtract) -> ValidationResult:
    errors: list[str] = []
    failing: list[str] = []
    low_confidence: list[str] = []

    _check_required_fields(extract, failing)
    _check_line_arithmetic(extract, errors, failing)
    _check_totals_arithmetic(extract, errors, failing)
    _check_date_sanity(extract, errors, failing)
    _check_confidence(extract, low_confidence)

    failing = sorted(set(failing))
    low_confidence = sorted(set(low_confidence) - set(failing))

    return ValidationResult(
        passed=not failing,
        failing_fields=failing,
        low_confidence_fields=low_confidence,
        errors=errors,
    )
