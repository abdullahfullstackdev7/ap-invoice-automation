import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import queries
from app.analytics.queries import AnalyticsFilters
from app.models.analytics import AnalyticsDaily
from app.models.enums import ExceptionSeverity, ExceptionStatus, InvoiceStatus, PaymentStatus
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Document, Invoice
from app.models.masterdata import Vendor
from app.models.payments import Payment


async def _vendor(db_session: AsyncSession, *, category: str = "Office") -> Vendor:
    vendor = Vendor(
        code=f"V{uuid.uuid4().hex[:8]}", name="Acme", name_normalized="acme", category=category
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


async def test_kpis_reconcile_with_analytics_daily(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    db_session.add(
        AnalyticsDaily(
            date=date(2026, 9, 10),
            vendor_id=vendor.id,
            category="Office",
            invoices_count=4,
            value=Decimal("400.00"),
            stp_count=3,
        )
    )
    await db_session.commit()

    filters = AnalyticsFilters(date(2026, 9, 10), date(2026, 9, 10))
    result = await queries.kpis(db_session, filters)

    assert result["total_invoices"]["current"] == 4  # type: ignore[index]
    assert result["total_value"]["current"] == Decimal("400.00")  # type: ignore[index]
    assert result["stp_rate"]["current"] == 75.0  # type: ignore[index]


async def test_volume_value_trend_buckets_by_week(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    db_session.add_all(
        [
            AnalyticsDaily(
                date=date(2026, 9, 14),  # Monday
                vendor_id=vendor.id,
                invoices_count=1,
                value=Decimal("10"),
            ),
            AnalyticsDaily(
                date=date(2026, 9, 16),  # same week
                vendor_id=vendor.id,
                invoices_count=2,
                value=Decimal("20"),
            ),
            AnalyticsDaily(
                date=date(2026, 9, 21),  # next week
                vendor_id=vendor.id,
                invoices_count=5,
                value=Decimal("50"),
            ),
        ]
    )
    await db_session.commit()

    filters = AnalyticsFilters(date(2026, 9, 14), date(2026, 9, 21))
    trend = await queries.volume_value_trend(db_session, filters, "week")

    assert len(trend) == 2
    assert trend[0]["period"] == date(2026, 9, 14)
    assert trend[0]["invoices_count"] == 3
    assert trend[0]["value"] == Decimal("30")
    assert trend[1]["invoices_count"] == 5


async def test_spend_by_vendor_ranks_and_paginates(db_session: AsyncSession) -> None:
    vendor_a = await _vendor(db_session)
    vendor_b = await _vendor(db_session)
    db_session.add_all(
        [
            AnalyticsDaily(
                date=date(2026, 9, 1),
                vendor_id=vendor_a.id,
                invoices_count=1,
                value=Decimal("1000"),
            ),
            AnalyticsDaily(
                date=date(2026, 9, 1),
                vendor_id=vendor_b.id,
                invoices_count=1,
                value=Decimal("5000"),
            ),
        ]
    )
    await db_session.commit()

    filters = AnalyticsFilters(date(2026, 9, 1), date(2026, 9, 1))
    rows, total = await queries.spend_by_vendor(db_session, filters, limit=1, offset=0)
    assert total == 2
    assert len(rows) == 1
    assert rows[0]["vendor_id"] == vendor_b.id  # higher spend first


async def test_exceptions_by_reason_counts_and_pct(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    uploaded_at = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)
    invoice = await _invoice(db_session, vendor, uploaded_at=uploaded_at, total=Decimal("10"))
    db_session.add_all(
        [
            ExceptionRecord(
                invoice_id=invoice.id,
                reason_code="PRICE_VARIANCE",
                severity=ExceptionSeverity.medium,
                status=ExceptionStatus.open,
                opened_at=uploaded_at,
            ),
            ExceptionRecord(
                invoice_id=invoice.id,
                reason_code="PRICE_VARIANCE",
                severity=ExceptionSeverity.medium,
                status=ExceptionStatus.open,
                opened_at=uploaded_at,
            ),
            ExceptionRecord(
                invoice_id=invoice.id,
                reason_code="QTY_NOT_RECEIVED",
                severity=ExceptionSeverity.high,
                status=ExceptionStatus.open,
                opened_at=uploaded_at,
            ),
        ]
    )
    await db_session.commit()

    filters = AnalyticsFilters(date(2026, 9, 10), date(2026, 9, 10))
    result = await queries.exceptions_by_reason(db_session, filters)

    by_code = {r["reason_code"]: r for r in result}
    assert by_code["PRICE_VARIANCE"]["count"] == 2
    assert by_code["PRICE_VARIANCE"]["pct"] == 66.67
    assert by_code["QTY_NOT_RECEIVED"]["count"] == 1


async def test_aging_buckets_by_days_outstanding(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    uploaded_at = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    as_of = date(2026, 9, 10)

    fresh = await _invoice(
        db_session, vendor, uploaded_at=uploaded_at, total=Decimal("100"), due_date=date(2026, 9, 1)
    )
    old = await _invoice(
        db_session, vendor, uploaded_at=uploaded_at, total=Decimal("200"), due_date=date(2026, 1, 1)
    )
    db_session.add_all(
        [
            Payment(
                invoice_id=fresh.id,
                amount=Decimal("100"),
                scheduled_date=date(2026, 9, 1),
                status=PaymentStatus.scheduled,
            ),
            Payment(
                invoice_id=old.id,
                amount=Decimal("200"),
                scheduled_date=date(2026, 1, 1),
                status=PaymentStatus.scheduled,
            ),
        ]
    )
    await db_session.commit()

    filters = AnalyticsFilters(as_of, as_of)
    buckets = await queries.aging(db_session, filters)
    by_bucket = {b["bucket"]: b for b in buckets}

    assert by_bucket["0_30"]["count"] == 1
    assert by_bucket["0_30"]["value"] == Decimal("100")
    assert by_bucket["90_plus"]["count"] == 1
    assert by_bucket["90_plus"]["value"] == Decimal("200")


async def test_cashflow_forecast_sums_by_week(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    uploaded_at = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
    today = date(2026, 9, 10)

    inv_a = await _invoice(db_session, vendor, uploaded_at=uploaded_at, total=Decimal("100"))
    inv_b = await _invoice(db_session, vendor, uploaded_at=uploaded_at, total=Decimal("50"))
    db_session.add_all(
        [
            Payment(
                invoice_id=inv_a.id,
                amount=Decimal("100"),
                scheduled_date=today + timedelta(days=2),
                status=PaymentStatus.scheduled,
            ),
            Payment(
                invoice_id=inv_b.id,
                amount=Decimal("50"),
                scheduled_date=today + timedelta(days=3),
                status=PaymentStatus.scheduled,
            ),
        ]
    )
    await db_session.commit()

    filters = AnalyticsFilters(today, today)
    forecast = await queries.cashflow_forecast(db_session, filters, horizon_days=90)
    assert len(forecast) == 1
    assert forecast[0]["amount"] == Decimal("150")


async def test_workflow_funnel_counts_by_current_status(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    uploaded_at = datetime(2026, 9, 12, 9, 0, tzinfo=UTC)
    await _invoice(
        db_session,
        vendor,
        uploaded_at=uploaded_at,
        total=Decimal("1"),
        status=InvoiceStatus.auto_approved,
    )
    await _invoice(
        db_session,
        vendor,
        uploaded_at=uploaded_at,
        total=Decimal("1"),
        status=InvoiceStatus.blocked,
    )
    await _invoice(
        db_session,
        vendor,
        uploaded_at=uploaded_at,
        total=Decimal("1"),
        status=InvoiceStatus.blocked,
    )
    await db_session.commit()

    filters = AnalyticsFilters(date(2026, 9, 12), date(2026, 9, 12))
    funnel = await queries.workflow_funnel(db_session, filters)
    by_status = {row["status"]: row["count"] for row in funnel}

    assert by_status["auto_approved"] == 1
    assert by_status["blocked"] == 2
    assert by_status["paid"] == 0


async def test_savings_breaks_down_duplicates_blocked(db_session: AsyncSession) -> None:
    vendor = await _vendor(db_session)
    uploaded_at = datetime(2026, 9, 13, 9, 0, tzinfo=UTC)
    invoice = await _invoice(
        db_session,
        vendor,
        uploaded_at=uploaded_at,
        total=Decimal("777"),
        status=InvoiceStatus.blocked,
    )
    db_session.add(
        ExceptionRecord(
            invoice_id=invoice.id,
            reason_code="DUPLICATE_EXACT",
            severity=ExceptionSeverity.high,
            status=ExceptionStatus.open,
            opened_at=uploaded_at,
        )
    )
    await db_session.commit()

    filters = AnalyticsFilters(date(2026, 9, 13), date(2026, 9, 13))
    result = await queries.savings(db_session, filters)

    assert result["duplicates_blocked"]["count"] == 1  # type: ignore[index]
    assert result["duplicates_blocked"]["value"] == Decimal("777")  # type: ignore[index]
