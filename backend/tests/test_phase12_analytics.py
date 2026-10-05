import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsDaily
from app.models.enums import ExceptionSeverity, ExceptionStatus, InvoiceStatus, UserRole
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Document, Invoice
from app.models.masterdata import Vendor
from tests.conftest import TEST_PASSWORD, make_user


async def _login(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def _exception_with_times(
    db_session: AsyncSession,
    *,
    opened_at: datetime,
    due: datetime,
    resolved_at: datetime | None,
) -> None:
    vendor = Vendor(code=f"V{uuid.uuid4().hex[:8]}", name="Acme", name_normalized="acme")
    db_session.add(vendor)
    await db_session.flush()
    document = Document(
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        filename="f.png",
        mime="image/png",
        size=1,
        storage_path="x",
        uploaded_at=opened_at,
    )
    db_session.add(document)
    await db_session.flush()
    invoice = Invoice(
        document_id=document.id,
        vendor_id=vendor.id,
        invoice_no="INV-1",
        invoice_date=opened_at.date(),
        currency="USD",
        total=Decimal("10"),
        status=InvoiceStatus.exception,
    )
    db_session.add(invoice)
    await db_session.flush()
    db_session.add(
        ExceptionRecord(
            invoice_id=invoice.id,
            reason_code="PRICE_VARIANCE",
            severity=ExceptionSeverity.medium,
            status=ExceptionStatus.resolved if resolved_at else ExceptionStatus.open,
            opened_at=opened_at,
            sla_due_at=due,
            resolved_at=resolved_at,
        )
    )
    await db_session.commit()


async def test_sla_compliance_counts_met_and_overdue(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    now = datetime.now(UTC)
    opened = now - timedelta(hours=1)
    # met: resolved before its due time
    await _exception_with_times(
        db_session, opened_at=opened, due=now + timedelta(hours=2), resolved_at=now
    )
    # missed: resolved after its due time
    await _exception_with_times(
        db_session, opened_at=opened, due=now - timedelta(minutes=1), resolved_at=now
    )
    # overdue and still open
    await _exception_with_times(
        db_session, opened_at=opened, due=now - timedelta(hours=1), resolved_at=None
    )
    await make_user(db_session, "fm@example.com", UserRole.finance_manager)
    await _login(client, "fm@example.com")

    today = date.today()
    response = await client.get(
        "/api/v1/analytics/sla-compliance",
        params={"date_from": (today - timedelta(days=2)).isoformat(), "date_to": today.isoformat()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["resolved_count"] == 2
    assert body["sla_met_count"] == 1
    assert body["sla_compliance_pct"] == 50.0
    assert body["overdue_open_count"] == 1


async def test_exception_heatmap_time_buckets_by_weekday_and_hour(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    opened = datetime(2026, 9, 14, 9, 30, tzinfo=UTC)  # a Monday
    await _exception_with_times(
        db_session, opened_at=opened, due=opened + timedelta(hours=4), resolved_at=None
    )
    await make_user(db_session, "fm2@example.com", UserRole.finance_manager)
    await _login(client, "fm2@example.com")

    response = await client.get(
        "/api/v1/analytics/exception-heatmap-time",
        params={"date_from": "2026-09-14", "date_to": "2026-09-14"},
    )
    assert response.status_code == 200
    assert response.json() == [{"weekday": 0, "hour": 9, "count": 1}]


async def test_savings_trend_returns_monthly_buckets(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            AnalyticsDaily(
                date=date(2026, 8, 3),
                invoices_count=1,
                value=Decimal("100"),
                savings_prevented=Decimal("5"),
                discounts_captured=Decimal("2"),
                discounts_missed=Decimal("0"),
            ),
            AnalyticsDaily(
                date=date(2026, 8, 20),
                invoices_count=1,
                value=Decimal("50"),
                savings_prevented=Decimal("1"),
                discounts_captured=Decimal("0"),
                discounts_missed=Decimal("1"),
            ),
        ]
    )
    await db_session.commit()
    await make_user(db_session, "fm3@example.com", UserRole.finance_manager)
    await _login(client, "fm3@example.com")

    response = await client.get(
        "/api/v1/analytics/savings-trend",
        params={"date_from": "2026-08-01", "date_to": "2026-08-31", "granularity": "month"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["savings_prevented"] == "6.00"
    assert body[0]["invoice_value"] == "150.00"
