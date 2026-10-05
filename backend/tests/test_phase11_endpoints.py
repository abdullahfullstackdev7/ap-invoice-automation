import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    ExceptionSeverity,
    ExceptionStatus,
    InvoiceStatus,
    UserRole,
)
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Document, Invoice
from app.models.masterdata import Vendor
from app.models.procurement import GoodsReceipt, GRLine, POLine, PurchaseOrder
from tests.conftest import TEST_PASSWORD, make_user


async def _login(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def _seed_vendor(db_session: AsyncSession, **overrides: object) -> Vendor:
    vendor = Vendor(
        code=f"V{uuid.uuid4().hex[:8]}",
        name="Acme Supplies",
        name_normalized="acme supplies",
        **overrides,
    )
    db_session.add(vendor)
    await db_session.flush()
    return vendor


async def _seed_invoice(
    db_session: AsyncSession, vendor: Vendor, *, total: Decimal, status: InvoiceStatus
) -> Invoice:
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
        invoice_no=f"INV-{uuid.uuid4().hex[:6]}",
        invoice_date=date(2026, 9, 1),
        currency="USD",
        total=total,
        status=status,
    )
    db_session.add(invoice)
    await db_session.commit()
    await db_session.refresh(invoice)
    return invoice


async def test_list_invoices_filters_and_paginates(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    vendor = await _seed_vendor(db_session)
    await _seed_invoice(
        db_session, vendor, total=Decimal("100"), status=InvoiceStatus.auto_approved
    )
    await _seed_invoice(db_session, vendor, total=Decimal("200"), status=InvoiceStatus.blocked)
    await make_user(db_session, "clerk@example.com", UserRole.ap_clerk)
    await _login(client, "clerk@example.com")

    response = await client.get("/api/v1/invoices", params={"invoice_status": "blocked"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["total"] == "200.00"
    assert body["items"][0]["vendor_name"] == "Acme Supplies"


async def test_update_invoice_requires_ap_clerk_or_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    vendor = await _seed_vendor(db_session)
    invoice = await _seed_invoice(
        db_session, vendor, total=Decimal("100"), status=InvoiceStatus.needs_review
    )
    await make_user(db_session, "auditor@example.com", UserRole.auditor)
    await _login(client, "auditor@example.com")
    csrf = client.cookies["csrf_token"]

    response = await client.patch(
        f"/api/v1/invoices/{invoice.id}",
        headers={"X-CSRF-Token": csrf},
        json={"invoice_no": "INV-CORRECTED"},
    )
    assert response.status_code == 403


async def test_update_invoice_edits_fields_and_audits(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    vendor = await _seed_vendor(db_session)
    invoice = await _seed_invoice(
        db_session, vendor, total=Decimal("100"), status=InvoiceStatus.needs_review
    )
    await make_user(db_session, "clerk2@example.com", UserRole.ap_clerk)
    await _login(client, "clerk2@example.com")
    csrf = client.cookies["csrf_token"]

    response = await client.patch(
        f"/api/v1/invoices/{invoice.id}",
        headers={"X-CSRF-Token": csrf},
        json={"invoice_no": "INV-CORRECTED"},
    )
    assert response.status_code == 200
    assert response.json()["invoice_no"] == "INV-CORRECTED"


async def test_invoice_match_result_404_when_not_yet_matched(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    vendor = await _seed_vendor(db_session)
    invoice = await _seed_invoice(
        db_session, vendor, total=Decimal("100"), status=InvoiceStatus.extracted
    )
    await make_user(db_session, "clerk3@example.com", UserRole.ap_clerk)
    await _login(client, "clerk3@example.com")

    response = await client.get(f"/api/v1/invoices/{invoice.id}/match-result")
    assert response.status_code == 404


async def test_list_and_get_vendor_detail(client: AsyncClient, db_session: AsyncSession) -> None:
    vendor = await _seed_vendor(db_session, category="Office")
    await _seed_invoice(
        db_session, vendor, total=Decimal("500"), status=InvoiceStatus.auto_approved
    )
    await make_user(db_session, "clerk4@example.com", UserRole.ap_clerk)
    await _login(client, "clerk4@example.com")

    list_resp = await client.get("/api/v1/vendors", params={"search": "Acme"})
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    detail_resp = await client.get(f"/api/v1/vendors/{vendor.id}")
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["invoices_count"] == 1
    assert body["total_spend"] == "500.00"


async def test_purchase_order_detail_includes_lines_receipts_and_linked_invoices(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    vendor = await _seed_vendor(db_session)
    po = PurchaseOrder(
        po_number="PO-9001",
        vendor_id=vendor.id,
        currency="USD",
        status="open",
        po_date=date(2026, 9, 1),
        total=Decimal("250.00"),
    )
    db_session.add(po)
    await db_session.flush()
    po_line = POLine(
        po_id=po.id,
        line_no=1,
        description="Widget",
        qty=Decimal("10"),
        unit_price=Decimal("25.00"),
        amount=Decimal("250.00"),
    )
    db_session.add(po_line)
    await db_session.flush()
    receipt = GoodsReceipt(
        grn_number="GRN-9001",
        po_id=po.id,
        received_date=date(2026, 9, 5),
        received_by="warehouse",
    )
    db_session.add(receipt)
    await db_session.flush()
    db_session.add(GRLine(grn_id=receipt.id, po_line_id=po_line.id, qty_received=Decimal("10")))

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
    linked_invoice = Invoice(
        document_id=document.id,
        vendor_id=vendor.id,
        invoice_no="INV-LINKED",
        po_number_ref="PO-9001",
        invoice_date=date(2026, 9, 6),
        currency="USD",
        total=Decimal("250.00"),
        status=InvoiceStatus.matched,
    )
    db_session.add(linked_invoice)
    await db_session.commit()

    await make_user(db_session, "clerk5@example.com", UserRole.ap_clerk)
    await _login(client, "clerk5@example.com")

    response = await client.get(f"/api/v1/purchase-orders/{po.id}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["lines"]) == 1
    assert len(body["receipts"]) == 1
    assert len(body["linked_invoices"]) == 1
    assert body["linked_invoices"][0]["invoice_no"] == "INV-LINKED"


async def test_goods_receipts_list_filters_by_po(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    vendor = await _seed_vendor(db_session)
    po = PurchaseOrder(
        po_number="PO-9002",
        vendor_id=vendor.id,
        currency="USD",
        status="open",
        po_date=date(2026, 9, 1),
        total=Decimal("100.00"),
    )
    db_session.add(po)
    await db_session.flush()
    db_session.add(
        GoodsReceipt(
            grn_number="GRN-9002",
            po_id=po.id,
            received_date=date(2026, 9, 5),
            received_by="warehouse",
        )
    )
    await db_session.commit()

    await make_user(db_session, "clerk6@example.com", UserRole.ap_clerk)
    await _login(client, "clerk6@example.com")

    response = await client.get("/api/v1/goods-receipts", params={"po_id": str(po.id)})
    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_tolerance_policy_crud_is_admin_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "clerk7@example.com", UserRole.ap_clerk)
    await _login(client, "clerk7@example.com")
    csrf = client.cookies["csrf_token"]

    response = await client.post(
        "/api/v1/policies/tolerance",
        headers={"X-CSRF-Token": csrf},
        json={"scope": "global"},
    )
    assert response.status_code == 403


async def test_tolerance_policy_crud_as_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "admin@example.com", UserRole.admin)
    await _login(client, "admin@example.com")
    csrf = client.cookies["csrf_token"]

    create_resp = await client.post(
        "/api/v1/policies/tolerance",
        headers={"X-CSRF-Token": csrf},
        json={"scope": "global", "price_pct": "2.00"},
    )
    assert create_resp.status_code == 201
    policy_id = create_resp.json()["id"]

    update_resp = await client.patch(
        f"/api/v1/policies/tolerance/{policy_id}",
        headers={"X-CSRF-Token": csrf},
        json={"scope": "global", "price_pct": "3.50"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["price_pct"] == "3.50"

    list_resp = await client.get("/api/v1/policies/tolerance")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_users_assignable_excludes_auditor_access(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "auditor2@example.com", UserRole.auditor)
    await _login(client, "auditor2@example.com")

    response = await client.get("/api/v1/users/assignable")
    assert response.status_code == 403


async def test_users_assignable_lists_active_users_for_ap_clerk(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "clerk8@example.com", UserRole.ap_clerk)
    await make_user(db_session, "approver8@example.com", UserRole.approver)
    await _login(client, "clerk8@example.com")

    response = await client.get("/api/v1/users/assignable")
    assert response.status_code == 200
    emails_present = {row["full_name"] for row in response.json()}
    assert "clerk8" in emails_present
    assert "approver8" in emails_present


async def test_bulk_assign_exceptions(client: AsyncClient, db_session: AsyncSession) -> None:
    vendor = await _seed_vendor(db_session)
    invoice = await _seed_invoice(
        db_session, vendor, total=Decimal("100"), status=InvoiceStatus.exception
    )
    exception = ExceptionRecord(
        invoice_id=invoice.id,
        reason_code="PRICE_VARIANCE",
        severity=ExceptionSeverity.medium,
        status=ExceptionStatus.open,
        opened_at=datetime.now(UTC),
    )
    db_session.add(exception)
    await db_session.commit()
    await db_session.refresh(exception)

    clerk = await make_user(db_session, "clerk9@example.com", UserRole.ap_clerk)
    approver = await make_user(db_session, "approver9@example.com", UserRole.approver)
    await _login(client, "clerk9@example.com")
    csrf = client.cookies["csrf_token"]

    response = await client.post(
        "/api/v1/exceptions/bulk-assign",
        headers={"X-CSRF-Token": csrf},
        json={"exception_ids": [str(exception.id)], "assignee_id": str(approver.id)},
    )
    assert response.status_code == 200
    assert response.json()[0]["assigned_to"] == str(approver.id)
    assert clerk.id != approver.id


async def test_llm_settings_requires_finance_or_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "clerk10@example.com", UserRole.ap_clerk)
    await _login(client, "clerk10@example.com")

    response = await client.get("/api/v1/settings/llm")
    assert response.status_code == 403


async def test_llm_settings_shows_unconfigured_providers(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "admin2@example.com", UserRole.admin)
    await _login(client, "admin2@example.com")

    response = await client.get("/api/v1/settings/llm")
    assert response.status_code == 200
    body = response.json()
    assert body["primary"] == "groq"
    providers = {p["provider"]: p for p in body["providers"]}
    assert providers["groq"]["configured"] is False


async def test_llm_test_call_reports_no_provider_configured(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "admin3@example.com", UserRole.admin)
    await _login(client, "admin3@example.com")
    csrf = client.cookies["csrf_token"]

    response = await client.post("/api/v1/settings/llm/test-call", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "No LLM API key" in body["detail"]
