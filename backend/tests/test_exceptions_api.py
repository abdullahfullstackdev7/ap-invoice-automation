import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ExceptionSeverity, ExceptionStatus, InvoiceStatus, UserRole
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Document, Invoice
from app.models.masterdata import Vendor
from tests.conftest import TEST_PASSWORD, make_user

ALL_ROLES = [
    UserRole.admin,
    UserRole.ap_clerk,
    UserRole.approver,
    UserRole.finance_manager,
    UserRole.auditor,
]


async def _login_as(client: AsyncClient, db_session: AsyncSession, role: UserRole) -> None:
    email = f"{role.value}@example.com"
    await make_user(db_session, email, role, approval_limit=Decimal("2500"))
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def _seed_exception(db_session: AsyncSession) -> ExceptionRecord:
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
        total=Decimal("1000"),
        status=InvoiceStatus.exception,
    )
    db_session.add(invoice)
    await db_session.flush()

    exception = ExceptionRecord(
        invoice_id=invoice.id,
        reason_code="PRICE_VARIANCE",
        severity=ExceptionSeverity.medium,
        status=ExceptionStatus.open,
    )
    db_session.add(exception)
    await db_session.commit()
    await db_session.refresh(exception)
    return exception


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_act_on_exception_role_matrix(
    client: AsyncClient, db_session: AsyncSession, role: UserRole
) -> None:
    exception = await _seed_exception(db_session)
    await _login_as(client, db_session, role)
    csrf = client.cookies["csrf_token"]

    response = await client.post(
        f"/api/v1/exceptions/{exception.id}/action",
        headers={"X-CSRF-Token": csrf},
        json={"action": "hold", "comment": "checking"},
    )

    if role == UserRole.auditor:
        assert response.status_code == 403
    else:
        assert response.status_code == 200
        assert response.json()["status"] == "in_review"


async def test_list_exceptions_filters_by_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    exception = await _seed_exception(db_session)
    await _login_as(client, db_session, UserRole.ap_clerk)

    open_resp = await client.get("/api/v1/exceptions", params={"exception_status": "open"})
    assert open_resp.status_code == 200
    assert any(row["id"] == str(exception.id) for row in open_resp.json())

    resolved_resp = await client.get("/api/v1/exceptions", params={"exception_status": "resolved"})
    assert resolved_resp.status_code == 200
    assert resolved_resp.json() == []


async def test_unknown_action_is_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    exception = await _seed_exception(db_session)
    await _login_as(client, db_session, UserRole.ap_clerk)
    csrf = client.cookies["csrf_token"]

    response = await client.post(
        f"/api/v1/exceptions/{exception.id}/action",
        headers={"X-CSRF-Token": csrf},
        json={"action": "not_a_real_action"},
    )
    assert response.status_code == 422
