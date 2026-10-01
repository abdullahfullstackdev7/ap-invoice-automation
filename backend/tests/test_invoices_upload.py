import io
import uuid

import pytest
from httpx import AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InvoiceStatus, UserRole
from app.models.invoicing import Document, Invoice
from app.workers.tasks import process_invoice
from tests.conftest import TEST_PASSWORD, make_user


def _png_bytes(seed: int = 0) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(seed % 255, 0, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


def _invoice_png_bytes() -> bytes:
    """An image with real, OCR-readable text. A blank color square (as
    _png_bytes produces) has no words for RapidOCR to find, which drives
    mean confidence to 0 and triggers the Tesseract fallback - not
    installed in this dev environment (see README known constraints).
    """
    img = Image.new("RGB", (400, 150), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "ACME SUPPLIES INC", fill="black")
    draw.text((10, 40), "Invoice No: INV-0001", fill="black")
    draw.text((10, 70), "Total: 100.00", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _login_as(client: AsyncClient, db_session: AsyncSession, role: UserRole) -> None:
    email = f"{role.value}@example.com"
    await make_user(db_session, email, role)
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


UPLOAD_ALLOWED_ROLES = {UserRole.admin, UserRole.ap_clerk}


ALL_ROLES = [
    UserRole.admin,
    UserRole.ap_clerk,
    UserRole.approver,
    UserRole.finance_manager,
    UserRole.auditor,
]


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_upload_role_matrix(
    client: AsyncClient, db_session: AsyncSession, role: UserRole
) -> None:
    await _login_as(client, db_session, role)
    csrf = client.cookies["csrf_token"]

    response = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("invoice.png", _png_bytes(1), "image/png"))],
    )

    if role in UPLOAD_ALLOWED_ROLES:
        assert response.status_code == 200
        assert response.json()[0]["status"] == "queued"
    else:
        assert response.status_code == 403


async def test_upload_creates_document_and_invoice(
    client: AsyncClient, db_session: AsyncSession, deferred_jobs: list[dict[str, object]]
) -> None:
    await _login_as(client, db_session, UserRole.ap_clerk)
    csrf = client.cookies["csrf_token"]

    response = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("invoice.png", _png_bytes(2), "image/png"))],
    )

    assert response.status_code == 200
    item = response.json()[0]
    assert item["status"] == "queued"

    document = await db_session.get(Document, uuid.UUID(item["document_id"]))
    assert document is not None
    assert document.filename == "invoice.png"

    invoice = await db_session.get(Invoice, uuid.UUID(item["invoice_id"]))
    assert invoice is not None
    assert invoice.status == InvoiceStatus.uploaded
    assert invoice.document_id == document.id

    assert deferred_jobs == [{"task": "process_invoice", "document_id": str(document.id)}]


async def test_duplicate_upload_is_flagged_without_reprocessing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, UserRole.ap_clerk)
    csrf = client.cookies["csrf_token"]
    content = _png_bytes(3)

    first = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("invoice.png", content, "image/png"))],
    )
    assert first.json()[0]["status"] == "queued"

    second = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("invoice_resubmitted.png", content, "image/png"))],
    )
    assert second.json()[0]["status"] == "duplicate_exact"
    assert second.json()[0]["document_id"] is None

    result = await db_session.execute(select(Document))
    assert len(list(result.scalars().all())) == 1


async def test_upload_rejects_disallowed_file_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, UserRole.ap_clerk)
    csrf = client.cookies["csrf_token"]

    response = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("script.sh", b"#!/bin/sh\necho hi\n", "application/x-sh"))],
    )

    assert response.status_code == 200
    assert response.json()[0]["status"] == "rejected"


async def test_upload_without_csrf_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, UserRole.ap_clerk)

    response = await client.post(
        "/api/v1/invoices/upload",
        files=[("files", ("invoice.png", _png_bytes(4), "image/png"))],
    )

    assert response.status_code == 403


async def test_get_invoice_document_roundtrip(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, UserRole.ap_clerk)
    csrf = client.cookies["csrf_token"]
    content = _png_bytes(5)

    upload = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("invoice.png", content, "image/png"))],
    )
    invoice_id = upload.json()[0]["invoice_id"]

    response = await client.get(f"/api/v1/invoices/{invoice_id}/document")

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "image/png"


async def test_get_unknown_invoice_returns_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, UserRole.auditor)

    response = await client.get(f"/api/v1/invoices/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_process_invoice_transitions_status_and_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, UserRole.ap_clerk)
    csrf = client.cookies["csrf_token"]

    upload = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("invoice.png", _invoice_png_bytes(), "image/png"))],
    )
    document_id = upload.json()[0]["document_id"]
    invoice_id = upload.json()[0]["invoice_id"]

    await process_invoice.func(document_id=document_id)

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.ocr_done
    assert invoice.extraction_confidence is not None
    assert invoice.extracted_json is not None

    # Re-running the task (simulating a retry or duplicate enqueue) must
    # not fail or redo work once the invoice already advanced past
    # "uploaded".
    await process_invoice.func(document_id=document_id)
    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.ocr_done
