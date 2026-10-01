import uuid
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from app.matching.context import LineMapping, MatchContext
from app.matching.policy import DEFAULT_POLICY
from app.matching.rules.price import _pct_diff, check_price
from app.matching.rules.quantity import check_quantity
from app.matching.rules.totals_tax import check_totals_and_tax
from app.models.invoicing import Invoice, InvoiceLine
from app.models.procurement import POLine

money = st.decimals(
    min_value=Decimal("0.01"), max_value=Decimal("100000"), places=2, allow_nan=False,
    allow_infinity=False,
)
small_qty = st.integers(min_value=1, max_value=1000).map(Decimal)


def _invoice_line(qty: Decimal, unit_price: Decimal) -> InvoiceLine:
    return InvoiceLine(
        id=uuid.uuid4(), invoice_id=uuid.uuid4(), line_no=1, description="x",
        qty=qty, unit_price=unit_price, amount=qty * unit_price,
    )


def _po_line(qty: Decimal, unit_price: Decimal, qty_invoiced_cum: Decimal = Decimal("0")) -> POLine:
    return POLine(
        id=uuid.uuid4(), po_id=uuid.uuid4(), line_no=1, item_id=None, description="x",
        qty=qty, unit_price=unit_price, amount=qty * unit_price,
        qty_invoiced_cum=qty_invoiced_cum,
    )


def _ctx(
    invoice: Invoice, lines: list[InvoiceLine], po_lines: list[POLine], **kwargs: object
) -> MatchContext:
    mappings = [
        LineMapping(line.id, po_line.id, 1.0, "sku")
        for line, po_line in zip(lines, po_lines, strict=False)
    ]
    return MatchContext(
        invoice=invoice,
        invoice_lines=lines,
        vendor=None,
        po=None,
        po_lines=po_lines,
        po_lines_by_id={pl.id: pl for pl in po_lines},
        line_mappings=mappings,
        policy=DEFAULT_POLICY,
        auto_approve_limit=Decimal("5000"),
        **kwargs,  # type: ignore[arg-type]
    )


# --- Decimal arithmetic invariants ---


@given(price_inv=money, price_po=money)
def test_pct_diff_always_returns_decimal_never_float(price_inv: Decimal, price_po: Decimal) -> None:
    result = _pct_diff(price_inv, price_po)
    assert isinstance(result, Decimal)
    assert result >= 0


@given(price=money)
def test_pct_diff_identical_prices_is_always_zero(price: Decimal) -> None:
    assert _pct_diff(price, price) == Decimal("0")


# --- no false positive within tolerance (price) ---


@given(price_po=money, drift_fraction=st.decimals(min_value="-0.009", max_value="0.009", places=4))
@settings(max_examples=50)
def test_price_within_one_percent_never_flagged(price_po: Decimal, drift_fraction: Decimal) -> None:
    price_inv = (price_po * (1 + drift_fraction)).quantize(Decimal("0.01"))
    inv_line = _invoice_line(Decimal("1"), price_inv)
    po_line = _po_line(Decimal("1"), price_po)
    ctx = _ctx(
        Invoice(id=uuid.uuid4(), document_id=uuid.uuid4(), currency="USD"),
        [inv_line],
        [po_line],
        qty_received_by_po_line={},
    )
    drafts = check_price(ctx)
    assert drafts == [], f"false positive: price_po={price_po}, price_inv={price_inv}"


@given(price_po=st.decimals(min_value="10", max_value="100000", places=2))
@settings(max_examples=50)
def test_price_within_one_dollar_absolute_never_flagged(price_po: Decimal) -> None:
    """The $1 absolute floor must hold even when 1% would be stricter."""
    price_inv = price_po + Decimal("0.50")
    inv_line = _invoice_line(Decimal("1"), price_inv)
    po_line = _po_line(Decimal("1"), price_po)
    ctx = _ctx(
        Invoice(id=uuid.uuid4(), document_id=uuid.uuid4(), currency="USD"),
        [inv_line],
        [po_line],
        qty_received_by_po_line={},
    )
    drafts = check_price(ctx)
    assert drafts == []


# --- no false positive within tolerance (quantity) ---


@given(qty_received=small_qty, qty_prev=st.integers(min_value=0, max_value=1000).map(Decimal))
@settings(max_examples=50)
def test_quantity_exactly_at_allowed_boundary_never_flagged(
    qty_received: Decimal, qty_prev: Decimal
) -> None:
    if qty_prev > qty_received:
        qty_prev = qty_received  # keep the scenario physically sensible
    allowed = qty_received - qty_prev
    if allowed <= 0:
        return  # QTY_NOT_RECEIVED / nothing left is a different, already-tested case
    inv_line = _invoice_line(allowed, Decimal("10.00"))
    po_line = _po_line(qty_received, Decimal("10.00"), qty_invoiced_cum=qty_prev)
    ctx = _ctx(
        Invoice(id=uuid.uuid4(), document_id=uuid.uuid4(), currency="USD"),
        [inv_line],
        [po_line],
        qty_received_by_po_line={po_line.id: qty_received},
    )
    drafts = check_quantity(ctx)
    assert drafts == [], f"false positive at exact boundary: allowed={allowed}"


# --- no false positive within tolerance (totals) ---


@given(subtotal=money, drift=st.decimals(min_value="-0.02", max_value="0.02", places=2))
@settings(max_examples=50)
def test_totals_within_002_tolerance_never_flagged(subtotal: Decimal, drift: Decimal) -> None:
    line = _invoice_line(Decimal("1"), subtotal)
    invoice = Invoice(
        id=uuid.uuid4(), document_id=uuid.uuid4(), currency="USD",
        subtotal=subtotal + drift, tax=Decimal("0"), discount=None,
        total=subtotal + drift,
    )
    ctx = _ctx(invoice, [line], [], qty_received_by_po_line={})
    drafts = check_totals_and_tax(ctx)
    assert drafts == [], f"false positive: subtotal={subtotal}, drift={drift}"
