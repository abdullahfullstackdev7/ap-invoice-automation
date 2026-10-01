import io
import uuid
from decimal import Decimal

from httpx import AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InvoiceStatus, UserRole
from app.models.invoicing import Invoice, InvoiceLine
from app.workers.tasks import extract_invoice_fields, process_invoice
from tests.conftest import TEST_PASSWORD, make_user


def _render_clean_invoice(invoice_no: str = "INV-2026-0042") -> bytes:
    img = Image.new("RGB", (1100, 700), color="white")
    draw = ImageDraw.Draw(img)
    header = [
        "ACME SUPPLIES INC",
        "contact@acmesupplies.com",
        "TAX-786579303",
        "",
        f"Invoice No: {invoice_no}",
        "Invoice Date: 2026-09-15",
        "Due Date: 2026-10-15",
        "PO Number: PO-000123",
        "",
    ]
    y = 20
    for line in header:
        draw.text((30, y), line, fill="black")
        y += 35

    draw.text((30, y), "Description", fill="black")
    draw.text((350, y), "Qty", fill="black")
    draw.text((500, y), "Price", fill="black")
    draw.text((700, y), "Amount", fill="black")
    y += 40
    draw.text((30, y), "Widget A", fill="black")
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


async def _upload_and_run_ocr(
    client: AsyncClient, filename: str, content: bytes
) -> tuple[str, str]:
    csrf = client.cookies["csrf_token"]
    response = await client.post(
        "/api/v1/invoices/upload",
        headers={"X-CSRF-Token": csrf},
        files=[("files", (filename, content, "image/png"))],
    )
    item = response.json()[0]
    await process_invoice.func(document_id=item["document_id"])
    return item["document_id"], item["invoice_id"]


async def _login_clerk(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session, "clerk@example.com", UserRole.ap_clerk)
    response = await client.post(
        "/api/v1/auth/login", json={"email": "clerk@example.com", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def test_extraction_populates_header_and_lines(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_clerk(client, db_session)
    _, invoice_id = await _upload_and_run_ocr(client, "invoice.png", _render_clean_invoice())

    await extract_invoice_fields.func(invoice_id=invoice_id)

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)

    assert invoice.status == InvoiceStatus.extracted
    assert invoice.invoice_no == "INV-2026-0042"
    assert invoice.invoice_date is not None and invoice.invoice_date.isoformat() == "2026-09-15"
    assert invoice.subtotal == Decimal("75.00")
    assert invoice.tax == Decimal("7.50")
    assert invoice.total == Decimal("82.50")
    assert invoice.dup_key is not None

    lines_result = await db_session.execute(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
    )
    lines = list(lines_result.scalars().all())
    assert len(lines) == 1
    assert lines[0].description == "Widget A"
    assert lines[0].amount == Decimal("75.00")


async def test_extraction_is_idempotent(client: AsyncClient, db_session: AsyncSession) -> None:
    await _login_clerk(client, db_session)
    _, invoice_id = await _upload_and_run_ocr(client, "invoice.png", _render_clean_invoice())

    await extract_invoice_fields.func(invoice_id=invoice_id)
    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)
    first_status = invoice.status

    # Re-running once already past ocr_done must be a no-op, not a
    # duplicate set of invoice_lines.
    await extract_invoice_fields.func(invoice_id=invoice_id)
    await db_session.refresh(invoice)
    assert invoice.status == first_status

    lines_result = await db_session.execute(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
    )
    assert len(list(lines_result.scalars().all())) == 1


async def test_extraction_cache_hit_on_identical_ocr_text(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_clerk(client, db_session)
    content = _render_clean_invoice()

    _, first_invoice_id = await _upload_and_run_ocr(client, "invoice_a.png", content)
    await extract_invoice_fields.func(invoice_id=first_invoice_id)

    # A visually-identical but byte-different re-scan (different filename
    # forces a different sha256, bypassing the exact-duplicate check from
    # Phase 4) should hit the OCR-text cache instead of re-running rules
    # extraction or an LLM call.
    import io as io_module

    from PIL import Image as PILImage

    img = PILImage.open(io_module.BytesIO(content))
    buf = io_module.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    slightly_different_bytes = buf.getvalue() + b"\x00"

    _, second_invoice_id = await _upload_and_run_ocr(
        client, "invoice_b.png", slightly_different_bytes
    )
    await extract_invoice_fields.func(invoice_id=second_invoice_id)

    second_invoice = await db_session.get(Invoice, uuid.UUID(second_invoice_id))
    assert second_invoice is not None
    await db_session.refresh(second_invoice)

    assert second_invoice.status == InvoiceStatus.extracted
    assert second_invoice.extracted_json is not None
    assert second_invoice.extracted_json.get("cache_hit_from") == first_invoice_id
    assert second_invoice.invoice_no == "INV-2026-0042"


async def test_extraction_without_llm_keys_marks_needs_review_on_bad_scan(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_clerk(client, db_session)
    # Readable but irrelevant text: no recognizable header fields and no
    # line-item table, so validation fails. This must still have real text
    # (not a blank image) so RapidOCR finds words and returns a normal
    # confidence score - a blank page drives confidence to 0 and triggers
    # the Tesseract fallback, which is not installed in this dev sandbox
    # (see README known constraints) and is unrelated to what this test
    # checks (validation -> needs_review with no LLM keys configured).
    img = Image.new("RGB", (400, 150), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "This page has no invoice fields on it", fill="black")
    draw.text((10, 40), "just some unrelated printed text", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    _, invoice_id = await _upload_and_run_ocr(client, "irrelevant.png", buf.getvalue())
    await extract_invoice_fields.func(invoice_id=invoice_id)

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.needs_review
