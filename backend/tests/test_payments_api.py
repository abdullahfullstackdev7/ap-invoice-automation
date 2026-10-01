import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InvoiceStatus, PaymentStatus, UserRole
from app.models.invoicing import Document, Invoice
from app.models.masterdata import Vendor
from app.models.payments import Payment
from tests.conftest import TEST_PASSWORD, make_user


async def _login(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def _seed_scheduled_payment(db_session: AsyncSession) -> Payment:
    vendor = Vendor(code=f"V{uuid.uuid4().hex[:8]}", name="Acme", name_normalized="acme")
    db_session.add(vendor)
    await db_session.flush()

    document = Document(
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        filename="f.png",
        mime="image/png",
        size=1,
        storage_path="x",
        uploaded_at=datetime.now(UTC),
    )
    db_session.add(document)
    await db_session.flush()

    invoice = Invoice(
        document_id=document.id,
        vendor_id=vendor.id,
        invoice_no="INV-1",
        invoice_date=date(2026, 9, 1),
        currency="USD",
        total=Decimal("500"),
        status=InvoiceStatus.auto_approved,
    )
    db_session.add(invoice)
    await db_session.flush()

    payment = Payment(
        invoice_id=invoice.id,
        amount=Decimal("500"),
        scheduled_date=date(2026, 10, 1),
        status=PaymentStatus.scheduled,
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)
    return payment


async def test_non_finance_cannot_create_batch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_scheduled_payment(db_session)
    await make_user(db_session, "clerk@example.com", UserRole.ap_clerk)
    await _login(client, "clerk@example.com")
    csrf = client.cookies["csrf_token"]

    response = await client.post("/api/v1/payments/batches", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 403


async def test_create_batch_with_no_eligible_payments_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "finance@example.com", UserRole.finance_manager)
    await _login(client, "finance@example.com")
    csrf = client.cookies["csrf_token"]

    response = await client.post("/api/v1/payments/batches", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 400


async def test_batch_creator_cannot_release_their_own_batch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_scheduled_payment(db_session)
    await make_user(db_session, "finance@example.com", UserRole.finance_manager)
    await _login(client, "finance@example.com")
    csrf = client.cookies["csrf_token"]

    create_resp = await client.post("/api/v1/payments/batches", headers={"X-CSRF-Token": csrf})
    assert create_resp.status_code == 201
    batch_id = create_resp.json()["id"]

    release_resp = await client.post(
        f"/api/v1/payments/batches/{batch_id}/release", headers={"X-CSRF-Token": csrf}
    )
    assert release_resp.status_code == 403


async def test_batch_file_download_contains_the_payment_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    payment = await _seed_scheduled_payment(db_session)
    await make_user(db_session, "finance@example.com", UserRole.finance_manager)
    await _login(client, "finance@example.com")
    csrf = client.cookies["csrf_token"]

    create_resp = await client.post("/api/v1/payments/batches", headers={"X-CSRF-Token": csrf})
    batch_id = create_resp.json()["id"]

    file_resp = await client.get(f"/api/v1/payments/batches/{batch_id}/file")
    assert file_resp.status_code == 200
    assert file_resp.headers["content-type"].startswith("text/csv")
    assert str(payment.id) in file_resp.text


async def test_second_finance_manager_can_release(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_scheduled_payment(db_session)
    await make_user(db_session, "finance_a@example.com", UserRole.finance_manager)
    await make_user(db_session, "finance_b@example.com", UserRole.finance_manager)

    await _login(client, "finance_a@example.com")
    csrf = client.cookies["csrf_token"]
    create_resp = await client.post("/api/v1/payments/batches", headers={"X-CSRF-Token": csrf})
    batch_id = create_resp.json()["id"]

    await _login(client, "finance_b@example.com")
    csrf = client.cookies["csrf_token"]
    release_resp = await client.post(
        f"/api/v1/payments/batches/{batch_id}/release", headers={"X-CSRF-Token": csrf}
    )
    assert release_resp.status_code == 200
    assert release_resp.json()["status"] == "released"
