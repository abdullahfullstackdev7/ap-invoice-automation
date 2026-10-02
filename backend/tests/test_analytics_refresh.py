import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.refresh import refresh_analytics_daily
from app.models.analytics import AnalyticsDaily
from app.models.enums import ExceptionSeverity, ExceptionStatus, InvoiceStatus
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Document, Invoice, InvoiceLine
from app.models.masterdata import Vendor
from app.models.payments import Payment


async def _vendor(
    db_session: AsyncSession,
    *,
    discount_pct: Decimal | None = None,
    discount_days: int | None = None,
) -> Vendor:
    vendor = Vendor(
        code=f"V{uuid.uuid4().hex[:8]}",
        name="Acme",
        name_normalized="acme",
        category="Office",
        discount_pct=discount_pct,
        discount_days=discount_days,
    )
    db_session.add(vendor)
    await db_session.flush()
    return vendor


async def _invoice(
    db_session: AsyncSession,
    vendor: Vendor,
    *,
    uploaded_at: datetime,
    total: Decimal,
    status: InvoiceStatus = InvoiceStatus.auto_approved,
    due_date: date | None = None,
) -> Invoice:
    document = Document(
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        filename="f.png",
        mime="image/png",
        size=1,
        storage_path="x",
        uploaded_at=uploaded_at,
    )
    db_session.add(document)
    await db_session.flush()

    invoice = Invoice(
        document_id=document.id,
        vendor_id=vendor.id,
        invoice_no=f"INV-{uuid.uuid4().hex[:6]}",
        invoice_date=uploaded_at.date(),
        due_date=due_date,
        currency="USD",
        total=total,
        status=status,
    )
    db_session.add(invoice)
    await db_session.flush()
    return invoice


async def test_refresh_reconciles_invoice_count_and_value(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    d = date(2026, 9, 15)
    uploaded_at = datetime(2026, 9, 15, 10, 0, tzinfo=UTC)

    await _invoice(db_session, vendor, uploaded_at=uploaded_at, total=Decimal("100.00"))
    await _invoice(db_session, vendor, uploaded_at=uploaded_at, total=Decimal("250.00"))
    await db_session.commit()

    groups = await refresh_analytics_daily(db_session, d, d)
    assert groups == 1

    row = (
        await db_session.execute(
            select(AnalyticsDaily).where(
                AnalyticsDaily.date == d, AnalyticsDaily.vendor_id == vendor.id
            )
        )
    ).scalar_one()
    assert row.invoices_count == 2
    assert row.value == Decimal("350.00")
    assert row.category == "Office"


async def test_refresh_counts_stp_only_for_auto_approved(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    d = date(2026, 9, 16)
    uploaded_at = datetime(2026, 9, 16, 9, 0, tzinfo=UTC)

    await _invoice(
        db_session,
        vendor,
        uploaded_at=uploaded_at,
        total=Decimal("100"),
        status=InvoiceStatus.auto_approved,
    )
    await _invoice(
        db_session,
        vendor,
        uploaded_at=uploaded_at,
        total=Decimal("100"),
        status=InvoiceStatus.exception,
    )
    await db_session.commit()

    await refresh_analytics_daily(db_session, d, d)

    row = (
        await db_session.execute(
            select(AnalyticsDaily).where(
                AnalyticsDaily.date == d, AnalyticsDaily.vendor_id == vendor.id
            )
        )
    ).scalar_one()
    assert row.invoices_count == 2
    assert row.stp_count == 1


async def test_refresh_computes_price_variance_savings_prevented(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    d = date(2026, 9, 17)
    uploaded_at = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)

    invoice = await _invoice(db_session, vendor, uploaded_at=uploaded_at, total=Decimal("120"))
    line = InvoiceLine(
        invoice_id=invoice.id,
        line_no=1,
        description="Widget",
        qty=Decimal("4"),
        unit_price=Decimal("30.00"),
        amount=Decimal("120.00"),
    )
    db_session.add(line)
    await db_session.flush()

    exception = ExceptionRecord(
        invoice_id=invoice.id,
        reason_code="PRICE_VARIANCE",
        severity=ExceptionSeverity.medium,
        status=ExceptionStatus.resolved,
        opened_at=uploaded_at,
        details_json={
            "invoice_line_id": str(line.id),
            "price_inv": "30.00",
            "price_po": "25.00",
            "variance_pct": "20.00",
        },
    )
    db_session.add(exception)
    await db_session.commit()

    await refresh_analytics_daily(db_session, d, d)

    row = (
        await db_session.execute(
            select(AnalyticsDaily).where(
                AnalyticsDaily.date == d, AnalyticsDaily.vendor_id == vendor.id
            )
        )
    ).scalar_one()
    # (30.00 - 25.00) * qty 4 = 20.00 prevented overpayment
    assert row.savings_prevented == Decimal("20.00")
    assert row.exceptions_by_type_json == {"PRICE_VARIANCE": 1}


async def test_refresh_computes_discounts_captured_and_missed(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session, discount_pct=Decimal("2"), discount_days=10)
    d = date(2026, 9, 18)
    uploaded_at = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)

    captured_invoice = await _invoice(
        db_session,
        vendor,
        uploaded_at=uploaded_at,
        total=Decimal("1000"),
        due_date=date(2026, 10, 18),
    )
    missed_invoice = await _invoice(
        db_session,
        vendor,
        uploaded_at=uploaded_at,
        total=Decimal("500"),
        due_date=date(2026, 10, 18),
    )
    db_session.add(
        Payment(
            invoice_id=captured_invoice.id,
            amount=Decimal("1000"),
            scheduled_date=date(2026, 9, 28),  # before due_date: discount taken
        )
    )
    db_session.add(
        Payment(
            invoice_id=missed_invoice.id,
            amount=Decimal("500"),
            scheduled_date=date(2026, 10, 18),  # on due_date: discount missed
        )
    )
    await db_session.commit()

    await refresh_analytics_daily(db_session, d, d)

    row = (
        await db_session.execute(
            select(AnalyticsDaily).where(
                AnalyticsDaily.date == d, AnalyticsDaily.vendor_id == vendor.id
            )
        )
    ).scalar_one()
    assert row.discounts_captured == Decimal("20.00")  # 2% of 1000
    assert row.discounts_missed == Decimal("10.00")  # 2% of 500


async def test_refresh_is_idempotent_and_re_runnable(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    d = date(2026, 9, 19)
    uploaded_at = datetime(2026, 9, 19, 9, 0, tzinfo=UTC)
    await _invoice(db_session, vendor, uploaded_at=uploaded_at, total=Decimal("50"))
    await db_session.commit()

    await refresh_analytics_daily(db_session, d, d)
    await refresh_analytics_daily(db_session, d, d)

    rows = (
        (
            await db_session.execute(
                select(AnalyticsDaily).where(
                    AnalyticsDaily.date == d, AnalyticsDaily.vendor_id == vendor.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].invoices_count == 1


async def test_refresh_ignores_invoices_outside_the_date_range(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    outside = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    await _invoice(db_session, vendor, uploaded_at=outside, total=Decimal("999"))
    await db_session.commit()

    groups = await refresh_analytics_daily(db_session, date(2026, 9, 1), date(2026, 9, 30))
    assert groups == 0
