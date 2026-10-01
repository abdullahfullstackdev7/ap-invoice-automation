import io
import uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast

from httpx import AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Invoice
from app.models.masterdata import Vendor
from app.models.procurement import POLine, PurchaseOrder
from app.services.embeddings import embed_text
from app.services.vendor_resolution import normalize_vendor_name
from app.workers.tasks import extract_invoice_fields, process_invoice, resolve_invoice_entities
from tests.conftest import TEST_PASSWORD, make_user


def _render_invoice() -> bytes:
    img = Image.new("RGB", (1100, 700), color="white")
    draw = ImageDraw.Draw(img)
    header = [
        "Acme Supplies Inc",
        "contact@acmesupplies.com",
        "",
        "Invoice No: INV-2026-0099",
        "Invoice Date: 2026-09-20",
        "PO Number: PO-000500",
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
    draw.text((500, y), "25.00", fill="black")
    draw.text((700, y), "75.00", fill="black")
    y += 60
    draw.text((30, y), "Subtotal: 75.00", fill="black")
    y += 35
    draw.text((30, y), "Tax: 7.50", fill="black")
    y += 35
    draw.text((30, y), "Total: 82.50", fill="black")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _seed_vendor_and_po(db_session: AsyncSession) -> tuple[Vendor, PurchaseOrder]:
    vendor = Vendor(
        code="V00099",
        name="Acme Supplies Inc",
        name_normalized=normalize_vendor_name("Acme Supplies Inc"),
        embedding=embed_text("Acme Supplies Inc"),
    )
    db_session.add(vendor)
    await db_session.flush()

    po = PurchaseOrder(
        po_number="PO-000500",
        vendor_id=vendor.id,
        currency="USD",
        status="open",
        po_date=date(2026, 9, 1),
        total=Decimal("75.00"),
    )
    db_session.add(po)
    await db_session.flush()

    db_session.add(
        POLine(
            po_id=po.id,
            line_no=1,
            description="Wireless Mouse Ergonomic Design",
            qty=Decimal("3"),
            unit_price=Decimal("25.00"),
            amount=Decimal("75.00"),
        )
    )
    await db_session.commit()
    await db_session.refresh(vendor)
    await db_session.refresh(po)
    return vendor, po


async def _login_clerk(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session, "clerk@example.com", UserRole.ap_clerk)
    response = await client.post(
        "/api/v1/auth/login", json={"email": "clerk@example.com", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def test_full_pipeline_resolves_vendor_po_and_lines(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    vendor, po = await _seed_vendor_and_po(db_session)
    await _login_clerk(client, db_session)

    csrf = client.cookies["csrf_token"]
    upload = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("invoice.png", _render_invoice(), "image/png"))],
    )
    document_id = upload.json()[0]["document_id"]
    invoice_id = upload.json()[0]["invoice_id"]

    await process_invoice.func(document_id=document_id)
    await extract_invoice_fields.func(invoice_id=invoice_id)
    await resolve_invoice_entities.func(invoice_id=invoice_id)

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)

    assert invoice.vendor_id == vendor.id
    assert invoice.extracted_json is not None
    resolution = cast(dict[str, Any], invoice.extracted_json["resolution"])
    assert resolution["vendor"]["vendor_id"] == str(vendor.id)
    assert resolution["po"]["po_id"] == str(po.id)
    assert resolution["po"]["method"] == "exact_number"
    assert len(resolution["line_matches"]) == 1
    assert resolution["line_matches"][0]["po_line_id"] is not None


async def test_pipeline_is_idempotent(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_vendor_and_po(db_session)
    await _login_clerk(client, db_session)

    csrf = client.cookies["csrf_token"]
    upload = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("invoice.png", _render_invoice(), "image/png"))],
    )
    document_id = upload.json()[0]["document_id"]
    invoice_id = upload.json()[0]["invoice_id"]

    await process_invoice.func(document_id=document_id)
    await extract_invoice_fields.func(invoice_id=invoice_id)
    await resolve_invoice_entities.func(invoice_id=invoice_id)
    await resolve_invoice_entities.func(invoice_id=invoice_id)  # re-run: must be a no-op

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)
    assert invoice.extracted_json is not None
    assert "resolution" in invoice.extracted_json


async def test_unresolvable_vendor_creates_exception(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # No vendor seeded at all: resolution must fail safely, not crash,
    # and leave a VENDOR_UNRESOLVED review task behind.
    await _login_clerk(client, db_session)

    csrf = client.cookies["csrf_token"]
    upload = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", ("invoice.png", _render_invoice(), "image/png"))],
    )
    document_id = upload.json()[0]["document_id"]
    invoice_id = upload.json()[0]["invoice_id"]

    await process_invoice.func(document_id=document_id)
    await extract_invoice_fields.func(invoice_id=invoice_id)
    await resolve_invoice_entities.func(invoice_id=invoice_id)

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)
    assert invoice.vendor_id is None

    from sqlalchemy import select

    result = await db_session.execute(
        select(ExceptionRecord).where(ExceptionRecord.invoice_id == invoice.id)
    )
    exceptions = list(result.scalars().all())
    assert len(exceptions) == 1
    assert exceptions[0].reason_code == "VENDOR_UNRESOLVED"
