import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.masterdata import Vendor
from app.models.procurement import POLine, PurchaseOrder
from app.services.po_resolution import normalize_po_number, resolve_po


async def _seed_vendor(db_session: AsyncSession) -> Vendor:
    vendor = Vendor(
        code="V00001", name="Acme Supplies Inc", name_normalized="acme supplies inc"
    )
    db_session.add(vendor)
    await db_session.commit()
    await db_session.refresh(vendor)
    return vendor


async def _seed_po(
    db_session: AsyncSession,
    vendor: Vendor,
    *,
    po_number: str,
    po_date: date,
    total: Decimal,
    lines: list[tuple[str, Decimal, Decimal]] | None = None,
) -> PurchaseOrder:
    po = PurchaseOrder(
        po_number=po_number, vendor_id=vendor.id, currency="USD", status="open",
        po_date=po_date, total=total,
    )
    db_session.add(po)
    await db_session.flush()
    for line_no, (description, qty, unit_price) in enumerate(lines or [], start=1):
        db_session.add(
            POLine(
                po_id=po.id, line_no=line_no, description=description, qty=qty,
                unit_price=unit_price, amount=qty * unit_price,
            )
        )
    await db_session.commit()
    await db_session.refresh(po)
    return po


def test_normalize_po_number() -> None:
    assert normalize_po_number("po-000123") == "PO000123"
    assert normalize_po_number("PO 000123") == "PO000123"
    assert normalize_po_number("  po#000123 ") == "PO000123"


async def test_exact_po_number_match(db_session: AsyncSession) -> None:
    vendor = await _seed_vendor(db_session)
    po = await _seed_po(
        db_session, vendor, po_number="PO-000123", po_date=date(2026, 9, 1),
        total=Decimal("100.00"),
    )

    result = await resolve_po(
        db_session,
        po_number_ref="po 000123",
        vendor_id=vendor.id,
        invoice_date=date(2026, 9, 15),
        invoice_total=Decimal("100.00"),
    )

    assert result.po_id == po.id
    assert result.method == "exact_number"
    assert result.score == 1.0


async def test_no_po_reference_falls_back_to_candidate_scoring(
    db_session: AsyncSession,
) -> None:
    vendor = await _seed_vendor(db_session)
    po = await _seed_po(
        db_session, vendor, po_number="PO-000200", po_date=date(2026, 9, 1),
        total=Decimal("250.00"),
        lines=[("Widget A", Decimal("3"), Decimal("25.00"))],
    )
    # A decoy PO for the same vendor with a very different total.
    await _seed_po(
        db_session, vendor, po_number="PO-000201", po_date=date(2026, 9, 2),
        total=Decimal("9999.00"),
    )

    result = await resolve_po(
        db_session,
        po_number_ref=None,
        vendor_id=vendor.id,
        invoice_date=date(2026, 9, 20),
        invoice_total=Decimal("250.00"),
        invoice_line_descriptions=["Widget A"],
    )

    assert result.po_id == po.id
    assert result.method == "candidate_scoring"
    assert result.score > 0.6


async def test_candidate_outside_window_is_excluded(db_session: AsyncSession) -> None:
    vendor = await _seed_vendor(db_session)
    await _seed_po(
        db_session, vendor, po_number="PO-OLD", po_date=date(2025, 1, 1),
        total=Decimal("250.00"),
    )

    result = await resolve_po(
        db_session,
        po_number_ref=None,
        vendor_id=vendor.id,
        invoice_date=date(2026, 9, 20),
        invoice_total=Decimal("250.00"),
    )

    assert result.po_id is None
    assert result.method == "unresolved"


async def test_unknown_vendor_is_unresolved(db_session: AsyncSession) -> None:
    result = await resolve_po(
        db_session,
        po_number_ref=None,
        vendor_id=uuid.uuid4(),
        invoice_date=date(2026, 9, 20),
        invoice_total=Decimal("250.00"),
    )

    assert result.po_id is None
    assert result.method == "unresolved"
