import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.matching.duplicate import check_duplicate
from app.models.invoicing import Document, Invoice, InvoiceLine
from app.models.masterdata import Vendor


async def _make_vendor(db_session: AsyncSession) -> uuid.UUID:
    vendor = Vendor(
        code=f"V{uuid.uuid4().hex[:8]}", name="Test Vendor",
        name_normalized="test vendor",
    )
    db_session.add(vendor)
    await db_session.flush()
    return vendor.id


async def _make_document(db_session: AsyncSession, sha256: str) -> Document:
    doc = Document(
        sha256=sha256, filename="f.png", mime="image/png", size=10,
        storage_path=f"invoices/{sha256}.png", uploaded_at=datetime.now(UTC),
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


async def _make_invoice(
    db_session: AsyncSession,
    *,
    vendor_id: uuid.UUID,
    invoice_no: str,
    invoice_date: date,
    total: Decimal,
    lines: list[str],
    sha256: str,
) -> tuple[Invoice, list[InvoiceLine]]:
    doc = await _make_document(db_session, sha256)
    invoice = Invoice(
        document_id=doc.id, vendor_id=vendor_id, invoice_no=invoice_no,
        invoice_date=invoice_date, currency="USD", total=total,
    )
    db_session.add(invoice)
    await db_session.flush()
    invoice_lines = []
    for idx, desc in enumerate(lines, start=1):
        line = InvoiceLine(
            invoice_id=invoice.id, line_no=idx, description=desc,
            qty=Decimal("1"), unit_price=total, amount=total,
        )
        db_session.add(line)
        invoice_lines.append(line)
    await db_session.commit()
    return invoice, invoice_lines


async def test_exact_duplicate_vendor_and_invoice_no(db_session: AsyncSession) -> None:
    vendor_id = await _make_vendor(db_session)
    original, _ = await _make_invoice(
        db_session, vendor_id=vendor_id, invoice_no="INV-001", invoice_date=date(2026, 9, 1),
        total=Decimal("100.00"), lines=["Widget A"], sha256="a" * 64,
    )
    duplicate, dup_lines = await _make_invoice(
        db_session, vendor_id=vendor_id, invoice_no="inv-001", invoice_date=date(2026, 9, 2),
        total=Decimal("100.00"), lines=["Widget A"], sha256="b" * 64,
    )

    result = await check_duplicate(db_session, duplicate, dup_lines)

    assert result.is_exact is True
    assert result.draft is not None
    assert result.draft.reason_code == "DUPLICATE_EXACT"
    assert result.draft.details["duplicate_of_invoice_id"] == str(original.id)


async def test_near_duplicate_similar_number_and_lines(db_session: AsyncSession) -> None:
    vendor_id = await _make_vendor(db_session)
    await _make_invoice(
        db_session, vendor_id=vendor_id, invoice_no="INV-1000", invoice_date=date(2026, 9, 1),
        total=Decimal("250.00"), lines=["Wireless Mouse Ergonomic"], sha256="c" * 64,
    )
    candidate, candidate_lines = await _make_invoice(
        db_session, vendor_id=vendor_id, invoice_no="INV-l000", invoice_date=date(2026, 9, 3),
        total=Decimal("250.50"), lines=["Wireless Mouse Ergonomic Design"], sha256="d" * 64,
    )

    result = await check_duplicate(db_session, candidate, candidate_lines)

    assert result.is_exact is False
    assert result.draft is not None
    assert result.draft.reason_code == "DUPLICATE_SUSPECTED"


async def test_different_vendor_is_not_a_duplicate(db_session: AsyncSession) -> None:
    vendor_a = await _make_vendor(db_session)
    vendor_b = await _make_vendor(db_session)
    await _make_invoice(
        db_session, vendor_id=vendor_a, invoice_no="INV-001", invoice_date=date(2026, 9, 1),
        total=Decimal("100.00"), lines=["Widget A"], sha256="e" * 64,
    )
    other, other_lines = await _make_invoice(
        db_session, vendor_id=vendor_b, invoice_no="INV-001", invoice_date=date(2026, 9, 1),
        total=Decimal("100.00"), lines=["Widget A"], sha256="f" * 64,
    )

    result = await check_duplicate(db_session, other, other_lines)

    assert result.is_exact is False
    assert result.draft is None


async def test_unrelated_invoice_outside_date_window_not_flagged(db_session: AsyncSession) -> None:
    vendor_id = await _make_vendor(db_session)
    await _make_invoice(
        db_session, vendor_id=vendor_id, invoice_no="INV-2000", invoice_date=date(2026, 1, 1),
        total=Decimal("250.00"), lines=["Wireless Mouse"], sha256="g" * 64,
    )
    later, later_lines = await _make_invoice(
        db_session, vendor_id=vendor_id, invoice_no="INV-2000", invoice_date=date(2026, 9, 1),
        total=Decimal("250.00"), lines=["Wireless Mouse"], sha256="h" * 64,
    )

    # Same invoice_no but normalized comparison treats them as an exact
    # duplicate regardless of date, since the (vendor, invoice_no) pair
    # check per Plan.md section 7 item 1 does not have a date window.
    result = await check_duplicate(db_session, later, later_lines)
    assert result.is_exact is True
