import uuid
from datetime import date
from decimal import Decimal

from app.matching.context import LineMapping, MatchContext
from app.matching.policy import DEFAULT_POLICY
from app.matching.rules.header import check_header
from app.matching.rules.price import check_price
from app.matching.rules.quantity import check_quantity
from app.matching.rules.terms import check_terms, early_pay_discount_eligible
from app.matching.rules.totals_tax import check_totals_and_tax
from app.models.enums import POStatus
from app.models.invoicing import Invoice, InvoiceLine
from app.models.masterdata import Vendor
from app.models.policies import TolerancePolicy
from app.models.procurement import POLine, PurchaseOrder


def _vendor(**overrides: object) -> Vendor:
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(), code="V1", name="Acme", name_normalized="acme",
        payment_terms_days=30, discount_pct=None, discount_days=None,
    )
    defaults.update(overrides)
    return Vendor(**defaults)


def _po(**overrides: object) -> PurchaseOrder:
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(), po_number="PO-1", vendor_id=uuid.uuid4(), currency="USD",
        status=POStatus.open, po_date=date(2026, 9, 1), total=Decimal("100.00"),
    )
    defaults.update(overrides)
    return PurchaseOrder(**defaults)


def _po_line(**overrides: object) -> POLine:
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(), po_id=uuid.uuid4(), line_no=1, item_id=None,
        description="Widget", qty=Decimal("10"), unit_price=Decimal("10.00"),
        amount=Decimal("100.00"), qty_invoiced_cum=Decimal("0"),
    )
    defaults.update(overrides)
    return POLine(**defaults)


def _invoice_line(**overrides: object) -> InvoiceLine:
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(), invoice_id=uuid.uuid4(), line_no=1, sku=None,
        description="Widget", qty=Decimal("10"), unit_price=Decimal("10.00"),
        amount=Decimal("100.00"),
    )
    defaults.update(overrides)
    return InvoiceLine(**defaults)


def _invoice(**overrides: object) -> Invoice:
    defaults: dict[str, object] = dict(
        id=uuid.uuid4(), document_id=uuid.uuid4(), vendor_id=uuid.uuid4(),
        invoice_no="INV-1", invoice_date=date(2026, 9, 15), due_date=date(2026, 10, 15),
        currency="USD", subtotal=Decimal("100.00"), tax=Decimal("10.00"),
        discount=None, total=Decimal("110.00"), po_number_ref="PO-1",
    )
    defaults.update(overrides)
    return Invoice(**defaults)


def _ctx(
    *,
    invoice: Invoice | None = None,
    invoice_lines: list[InvoiceLine] | None = None,
    vendor: Vendor | None = None,
    po: PurchaseOrder | None = None,
    po_lines: list[POLine] | None = None,
    qty_received: dict[uuid.UUID, Decimal] | None = None,
    line_mappings: list[LineMapping] | None = None,
    policy: TolerancePolicy = DEFAULT_POLICY,
) -> MatchContext:
    invoice = invoice or _invoice()
    invoice_lines = invoice_lines if invoice_lines is not None else [_invoice_line()]
    po_lines = po_lines or []
    if line_mappings is None and po_lines and invoice_lines:
        line_mappings = [
            LineMapping(invoice_lines[0].id, po_lines[0].id, 1.0, "sku")
        ]
    return MatchContext(
        invoice=invoice,
        invoice_lines=invoice_lines,
        vendor=vendor,
        po=po,
        po_lines=po_lines,
        po_lines_by_id={line.id: line for line in po_lines},
        qty_received_by_po_line=qty_received or {},
        line_mappings=line_mappings or [],
        policy=policy,
        auto_approve_limit=Decimal("5000"),
    )


# --- header ---


def test_header_missing_po() -> None:
    ctx = _ctx(po=None)
    drafts = check_header(ctx)
    assert [d.reason_code for d in drafts] == ["PO_NOT_FOUND"]


def test_header_closed_po() -> None:
    po = _po(status=POStatus.closed)
    ctx = _ctx(po=po)
    drafts = check_header(ctx)
    assert "PO_CLOSED" in [d.reason_code for d in drafts]


def test_header_vendor_mismatch() -> None:
    invoice = _invoice(vendor_id=uuid.uuid4())
    po = _po(vendor_id=uuid.uuid4())
    ctx = _ctx(invoice=invoice, po=po)
    drafts = check_header(ctx)
    assert "VENDOR_MISMATCH" in [d.reason_code for d in drafts]


def test_header_currency_mismatch() -> None:
    invoice = _invoice(currency="EUR")
    po = _po(currency="USD", vendor_id=invoice.vendor_id)
    ctx = _ctx(invoice=invoice, po=po)
    drafts = check_header(ctx)
    assert "CURRENCY_MISMATCH" in [d.reason_code for d in drafts]


def test_header_invoice_before_po_date() -> None:
    invoice = _invoice(invoice_date=date(2026, 8, 1))
    po = _po(vendor_id=invoice.vendor_id, po_date=date(2026, 9, 1))
    ctx = _ctx(invoice=invoice, po=po)
    drafts = check_header(ctx)
    assert "INVOICE_DATE_BEFORE_PO" in [d.reason_code for d in drafts]


def test_header_clean_match_no_exceptions() -> None:
    invoice = _invoice()
    po = _po(vendor_id=invoice.vendor_id, currency=invoice.currency, po_date=date(2026, 9, 1))
    ctx = _ctx(invoice=invoice, po=po)
    assert check_header(ctx) == []


# --- quantity ---


def test_quantity_missing_grn() -> None:
    po_line = _po_line()
    inv_line = _invoice_line()
    ctx = _ctx(invoice_lines=[inv_line], po=_po(), po_lines=[po_line], qty_received={})
    drafts = check_quantity(ctx)
    assert [d.reason_code for d in drafts] == ["QTY_NOT_RECEIVED"]


def test_quantity_within_received_amount_passes() -> None:
    po_line = _po_line(qty=Decimal("10"))
    inv_line = _invoice_line(qty=Decimal("10"))
    ctx = _ctx(
        invoice_lines=[inv_line], po=_po(), po_lines=[po_line],
        qty_received={po_line.id: Decimal("10")},
    )
    assert check_quantity(ctx) == []


def test_quantity_over_received_flags_exception() -> None:
    po_line = _po_line(qty=Decimal("10"))
    inv_line = _invoice_line(qty=Decimal("15"))
    ctx = _ctx(
        invoice_lines=[inv_line], po=_po(), po_lines=[po_line],
        qty_received={po_line.id: Decimal("10")},
    )
    drafts = check_quantity(ctx)
    assert [d.reason_code for d in drafts] == ["QTY_OVER_RECEIVED"]


def test_quantity_accounts_for_previously_invoiced() -> None:
    po_line = _po_line(qty=Decimal("10"), qty_invoiced_cum=Decimal("8"))
    inv_line = _invoice_line(qty=Decimal("2"))
    ctx = _ctx(
        invoice_lines=[inv_line], po=_po(), po_lines=[po_line],
        qty_received={po_line.id: Decimal("10")},
    )
    # 10 received - 8 previously invoiced = 2 remaining, exactly matches.
    assert check_quantity(ctx) == []


# --- price ---


def test_price_within_tolerance_passes() -> None:
    po_line = _po_line(unit_price=Decimal("10.00"))
    inv_line = _invoice_line(unit_price=Decimal("10.05"))  # within $1 abs tolerance
    ctx = _ctx(invoice_lines=[inv_line], po=_po(), po_lines=[po_line])
    assert check_price(ctx) == []


def test_price_warning_tier() -> None:
    po_line = _po_line(unit_price=Decimal("100.00"))
    inv_line = _invoice_line(unit_price=Decimal("103.00"))  # 3% over, >1% and >$1
    ctx = _ctx(invoice_lines=[inv_line], po=_po(), po_lines=[po_line])
    drafts = check_price(ctx)
    assert len(drafts) == 1
    assert drafts[0].reason_code == "PRICE_VARIANCE"


def test_price_exception_tier_above_5_percent() -> None:
    po_line = _po_line(unit_price=Decimal("100.00"))
    inv_line = _invoice_line(unit_price=Decimal("110.00"))  # 10% over
    ctx = _ctx(invoice_lines=[inv_line], po=_po(), po_lines=[po_line])
    drafts = check_price(ctx)
    assert len(drafts) == 1
    assert drafts[0].reason_code == "PRICE_VARIANCE"


# --- totals/tax ---


def test_totals_clean_match_passes() -> None:
    inv_line = _invoice_line(amount=Decimal("100.00"))
    invoice = _invoice(subtotal=Decimal("100.00"), tax=Decimal("10.00"), total=Decimal("110.00"))
    ctx = _ctx(invoice=invoice, invoice_lines=[inv_line])
    assert check_totals_and_tax(ctx) == []


def test_totals_mismatch_sum_lines_vs_subtotal() -> None:
    inv_line = _invoice_line(amount=Decimal("50.00"))
    invoice = _invoice(subtotal=Decimal("100.00"))
    ctx = _ctx(invoice=invoice, invoice_lines=[inv_line])
    drafts = check_totals_and_tax(ctx)
    assert any(d.reason_code == "TOTAL_MISMATCH" for d in drafts)


def test_totals_within_tolerance_002_passes() -> None:
    inv_line = _invoice_line(amount=Decimal("100.00"))
    invoice = _invoice(subtotal=Decimal("100.01"), tax=Decimal("10.00"), total=Decimal("110.01"))
    ctx = _ctx(invoice=invoice, invoice_lines=[inv_line])
    assert check_totals_and_tax(ctx) == []


# --- terms ---


def test_terms_due_date_matches_vendor_terms_passes() -> None:
    vendor = _vendor(payment_terms_days=30)
    invoice = _invoice(invoice_date=date(2026, 9, 1), due_date=date(2026, 10, 1))
    ctx = _ctx(invoice=invoice, vendor=vendor)
    assert check_terms(ctx) == []


def test_terms_due_date_mismatch_flags_low_severity() -> None:
    vendor = _vendor(payment_terms_days=30)
    invoice = _invoice(invoice_date=date(2026, 9, 1), due_date=date(2026, 12, 1))
    ctx = _ctx(invoice=invoice, vendor=vendor)
    drafts = check_terms(ctx)
    assert [d.reason_code for d in drafts] == ["DUE_DATE_MISMATCH"]


def test_early_pay_discount_eligible_computed() -> None:
    vendor = _vendor(discount_pct=Decimal("2"), discount_days=10)
    invoice = _invoice(invoice_date=date(2026, 9, 1), total=Decimal("1000.00"))
    ctx = _ctx(invoice=invoice, vendor=vendor)
    info = early_pay_discount_eligible(ctx)
    assert info is not None
    assert info["estimated_savings"] == "20.00"


def test_early_pay_discount_none_when_vendor_has_no_terms() -> None:
    vendor = _vendor(discount_pct=None, discount_days=None)
    ctx = _ctx(vendor=vendor)
    assert early_pay_discount_eligible(ctx) is None
