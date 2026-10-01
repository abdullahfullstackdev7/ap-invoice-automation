import io
import uuid
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import InvoiceStatus, PaymentBatchStatus, PaymentStatus, UserRole
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Invoice
from app.models.masterdata import Vendor
from app.models.payments import Payment, PaymentBatch
from app.models.procurement import GoodsReceipt, GRLine, POLine, PurchaseOrder
from app.services.embeddings import embed_text
from app.services.vendor_resolution import normalize_vendor_name
from app.workers.tasks import (
    extract_invoice_fields,
    match_invoice,
    process_invoice,
    resolve_invoice_entities,
    route_invoice,
    schedule_payment,
    settle_payment_batch,
)
from tests.conftest import TEST_PASSWORD, make_user


def _render_invoice(
    *, invoice_no: str, invoice_date: str, po_number: str, price: str, amount: str
) -> bytes:
    img = Image.new("RGB", (1100, 700), color="white")
    draw = ImageDraw.Draw(img)
    header = [
        "Acme Supplies Inc",
        "contact@acmesupplies.com",
        "",
        f"Invoice No: {invoice_no}",
        f"Invoice Date: {invoice_date}",
        f"PO Number: {po_number}",
        "",
    ]
    y = 20
    for line in header:
        draw.text((30, y), line, fill="black")
        y += 35

    draw.text((30, y), "Description", fill="black")
    draw.text((500, y), "Price", fill="black")
    draw.text((700, y), "Amount", fill="black")
    y += 40
    draw.text((30, y), "Wireless Mouse Ergonomic", fill="black")
    draw.text((500, y), price, fill="black")
    draw.text((700, y), amount, fill="black")
    y += 60
    draw.text((30, y), f"Subtotal: {amount}", fill="black")
    y += 35
    draw.text((30, y), "Tax: 0.00", fill="black")
    y += 35
    draw.text((30, y), f"Total: {amount}", fill="black")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _seed_vendor_and_po(
    db_session: AsyncSession,
    *,
    po_number: str,
    qty: Decimal,
    unit_price: Decimal,
    discount_pct: Decimal | None = None,
    discount_days: int | None = None,
) -> tuple[Vendor, PurchaseOrder, POLine]:
    vendor = Vendor(
        code=f"V{uuid.uuid4().hex[:8]}",
        name="Acme Supplies Inc",
        name_normalized=normalize_vendor_name("Acme Supplies Inc"),
        embedding=embed_text("Acme Supplies Inc"),
        discount_pct=discount_pct,
        discount_days=discount_days,
    )
    db_session.add(vendor)
    await db_session.flush()

    po = PurchaseOrder(
        po_number=po_number,
        vendor_id=vendor.id,
        currency="USD",
        status="open",
        po_date=date(2026, 9, 1),
        total=qty * unit_price,
    )
    db_session.add(po)
    await db_session.flush()

    po_line = POLine(
        po_id=po.id,
        line_no=1,
        description="Wireless Mouse Ergonomic Design",
        qty=qty,
        unit_price=unit_price,
        amount=qty * unit_price,
    )
    db_session.add(po_line)
    await db_session.commit()
    await db_session.refresh(vendor)
    await db_session.refresh(po)
    await db_session.refresh(po_line)
    return vendor, po, po_line


async def _receive_goods(
    db_session: AsyncSession, po: PurchaseOrder, po_line: POLine, qty: Decimal
) -> None:
    receipt = GoodsReceipt(
        grn_number=f"GRN-{uuid.uuid4().hex[:8]}",
        po_id=po.id,
        received_date=date(2026, 9, 10),
        received_by="warehouse",
    )
    db_session.add(receipt)
    await db_session.flush()
    db_session.add(GRLine(grn_id=receipt.id, po_line_id=po_line.id, qty_received=qty))
    await db_session.commit()


async def _login(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def _run_pipeline_through_routing(client: AsyncClient, image_bytes: bytes) -> str:
    csrf = client.cookies["csrf_token"]
    upload = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("invoice.png", image_bytes, "image/png"))],
    )
    document_id = upload.json()[0]["document_id"]
    invoice_id: str = upload.json()[0]["invoice_id"]

    await process_invoice.func(document_id=document_id)
    await extract_invoice_fields.func(invoice_id=invoice_id)
    await resolve_invoice_entities.func(invoice_id=invoice_id)
    await match_invoice.func(invoice_id=invoice_id)
    await route_invoice.func(invoice_id=invoice_id)
    return invoice_id


async def _audit_actions_for(session: AsyncSession, entity_id: uuid.UUID) -> set[str]:
    result = await session.execute(select(AuditLog.action).where(AuditLog.entity_id == entity_id))
    return {row[0] for row in result.all()}


async def test_clean_invoice_within_limit_is_paid_end_to_end(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Acceptance scenario, Plan.md section 8: clean invoice paid."""
    _, po, po_line = await _seed_vendor_and_po(
        db_session, po_number="PO-000700", qty=Decimal("3"), unit_price=Decimal("25.00")
    )
    await _receive_goods(db_session, po, po_line, Decimal("3"))
    await make_user(db_session, "clerk700@example.com", UserRole.ap_clerk)
    finance_a = await make_user(db_session, "finance700a@example.com", UserRole.finance_manager)
    finance_b = await make_user(db_session, "finance700b@example.com", UserRole.finance_manager)

    await _login(client, "clerk700@example.com")
    invoice_id = await _run_pipeline_through_routing(
        client,
        _render_invoice(
            invoice_no="INV-2026-0700",
            invoice_date="2026-09-20",
            po_number="PO-000700",
            price="25.00",
            amount="75.00",
        ),
    )

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.auto_approved

    await schedule_payment.func(invoice_id=invoice_id)
    payment = (
        await db_session.execute(select(Payment).where(Payment.invoice_id == invoice.id))
    ).scalar_one()
    assert payment.status == PaymentStatus.scheduled

    await _login(client, "finance700a@example.com")
    csrf = client.cookies["csrf_token"]
    create_resp = await client.post("/api/v1/payments/batches", headers={"X-CSRF-Token": csrf})
    assert create_resp.status_code == 201
    batch_id = create_resp.json()["id"]

    await _login(client, "finance700b@example.com")
    csrf = client.cookies["csrf_token"]
    release_resp = await client.post(
        f"/api/v1/payments/batches/{batch_id}/release", headers={"X-CSRF-Token": csrf}
    )
    assert release_resp.status_code == 200

    await settle_payment_batch.func(batch_id=batch_id)

    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.paid  # type: ignore[comparison-overlap]

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.settled

    batch = await db_session.get(PaymentBatch, uuid.UUID(batch_id))
    assert batch is not None
    assert batch.status == PaymentBatchStatus.settled
    assert batch.created_by == finance_a.id
    assert batch.released_by == finance_b.id

    audit_actions = await _audit_actions_for(db_session, invoice.id)
    assert "invoice_matched" in audit_actions
    assert "invoice_auto_approved" in audit_actions


async def test_price_drift_is_routed_to_approver_and_approved(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Acceptance scenario: price drift routed to approver. Amount in the
    2,500-25,000 exception tier, so the matrix requires the approver role.
    """
    _, po, po_line = await _seed_vendor_and_po(
        db_session, po_number="PO-000701", qty=Decimal("300"), unit_price=Decimal("25.00")
    )
    await _receive_goods(db_session, po, po_line, Decimal("300"))
    await make_user(db_session, "clerk701@example.com", UserRole.ap_clerk)
    await make_user(
        db_session,
        "approver701@example.com",
        UserRole.approver,
        approval_limit=Decimal("25000"),
    )

    await _login(client, "clerk701@example.com")
    invoice_id = await _run_pipeline_through_routing(
        client,
        _render_invoice(
            invoice_no="INV-2026-0701",
            invoice_date="2026-09-20",
            po_number="PO-000701",
            price="30.00",
            amount="9000.00",  # >5% above the PO's 25.00 price
        ),
    )

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.exception

    exception = (
        await db_session.execute(
            select(ExceptionRecord).where(
                ExceptionRecord.invoice_id == invoice.id,
                ExceptionRecord.reason_code == "PRICE_VARIANCE",
            )
        )
    ).scalar_one()

    await _login(client, "approver701@example.com")
    csrf = client.cookies["csrf_token"]
    decision_resp = await client.post(
        f"/api/v1/invoices/{invoice_id}/approvals/decision",
        headers={"X-CSRF-Token": csrf},
        json={"decision": "approved", "comment": "price variance acceptable this time"},
    )
    assert decision_resp.status_code == 200
    assert decision_resp.json()["decision"] == "approved"

    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.approved  # type: ignore[comparison-overlap]

    audit_actions = await _audit_actions_for(db_session, invoice.id)
    assert "invoice_approved" in audit_actions
    assert exception.id is not None  # sanity: the exception row exists


async def test_duplicate_invoice_is_blocked(client: AsyncClient, db_session: AsyncSession) -> None:
    """Acceptance scenario: duplicate blocked. No approval routing, no
    payment, and the invoice stays in the blocked status for a human to
    resolve through the exceptions queue.
    """
    _, po, po_line = await _seed_vendor_and_po(
        db_session, po_number="PO-000702", qty=Decimal("3"), unit_price=Decimal("25.00")
    )
    await _receive_goods(db_session, po, po_line, Decimal("3"))
    await make_user(db_session, "clerk702@example.com", UserRole.ap_clerk)

    await _login(client, "clerk702@example.com")
    first_invoice_id = await _run_pipeline_through_routing(
        client,
        _render_invoice(
            invoice_no="INV-2026-0702",
            invoice_date="2026-09-20",
            po_number="PO-000702",
            price="25.00",
            amount="75.00",
        ),
    )
    first_invoice = await db_session.get(Invoice, uuid.UUID(first_invoice_id))
    assert first_invoice is not None
    await db_session.refresh(first_invoice)
    assert first_invoice.status == InvoiceStatus.auto_approved

    # A second invoice, same vendor and invoice number, different document
    # bytes (so the exact-document-hash dedup in /upload doesn't catch it
    # before OCR), same as Phase 7's DUPLICATE_EXACT case.
    csrf = client.cookies["csrf_token"]
    upload = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[
            (
                "files",
                (
                    "invoice2.png",
                    _render_invoice(
                        invoice_no="INV-2026-0702",
                        invoice_date="2026-09-21",
                        po_number="PO-000702",
                        price="25.00",
                        amount="75.01",
                    ),
                    "image/png",
                ),
            )
        ],
    )
    document_id = upload.json()[0]["document_id"]
    dup_invoice_id = upload.json()[0]["invoice_id"]

    await process_invoice.func(document_id=document_id)
    await extract_invoice_fields.func(invoice_id=dup_invoice_id)
    await resolve_invoice_entities.func(invoice_id=dup_invoice_id)
    await match_invoice.func(invoice_id=dup_invoice_id)

    dup_invoice = await db_session.get(Invoice, uuid.UUID(dup_invoice_id))
    assert dup_invoice is not None
    await db_session.refresh(dup_invoice)
    assert dup_invoice.status == InvoiceStatus.blocked

    payments = (
        (await db_session.execute(select(Payment).where(Payment.invoice_id == dup_invoice.id)))
        .scalars()
        .all()
    )
    assert payments == []

    audit_actions = await _audit_actions_for(db_session, dup_invoice.id)
    assert "invoice_matched" in audit_actions
    assert "invoice_auto_approved" not in audit_actions


async def test_uploader_cannot_approve_own_invoice_sod_violation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Acceptance scenario: SoD violation rejected. The same ap_clerk both
    uploaded the invoice and tries to decide its approval (an exception
    <= 2,500 requires exactly the ap_clerk role, so the role/limit checks
    alone would let this through); SoD must block it anyway, per Plan.md
    section 7's uploader-cannot-approve rule.
    """
    _, po, po_line = await _seed_vendor_and_po(
        db_session, po_number="PO-000703", qty=Decimal("60"), unit_price=Decimal("25.00")
    )
    await _receive_goods(db_session, po, po_line, Decimal("60"))
    await make_user(
        db_session,
        "clerk703@example.com",
        UserRole.ap_clerk,
        approval_limit=Decimal("2500"),
    )

    await _login(client, "clerk703@example.com")
    invoice_id = await _run_pipeline_through_routing(
        client,
        _render_invoice(
            invoice_no="INV-2026-0703",
            invoice_date="2026-09-20",
            po_number="PO-000703",
            price="35.00",
            amount="2100.00",
        ),
    )

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.exception

    csrf = client.cookies["csrf_token"]
    decision_resp = await client.post(
        f"/api/v1/invoices/{invoice_id}/approvals/decision",
        headers={"X-CSRF-Token": csrf},
        json={"decision": "approved", "comment": "self-approving"},
    )
    assert decision_resp.status_code == 403

    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.exception  # unchanged

    audit_actions = await _audit_actions_for(db_session, invoice.id)
    assert "invoice_approved" not in audit_actions
