import io
import uuid
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InvoiceStatus, MatchOutcome, UserRole
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Invoice
from app.models.masterdata import Vendor
from app.models.matching import MatchLineResult, MatchResult
from app.models.procurement import GoodsReceipt, GRLine, POLine, PurchaseOrder
from app.services.embeddings import embed_text
from app.services.vendor_resolution import normalize_vendor_name
from app.workers.tasks import (
    extract_invoice_fields,
    match_invoice,
    process_invoice,
    resolve_invoice_entities,
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
    db_session: AsyncSession, *, po_number: str, qty: Decimal, unit_price: Decimal
) -> tuple[Vendor, PurchaseOrder, POLine]:
    vendor = Vendor(
        code=f"V{uuid.uuid4().hex[:8]}",
        name="Acme Supplies Inc",
        name_normalized=normalize_vendor_name("Acme Supplies Inc"),
        embedding=embed_text("Acme Supplies Inc"),
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


async def _login_clerk(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session, "clerk@example.com", UserRole.ap_clerk)
    response = await client.post(
        "/api/v1/auth/login", json={"email": "clerk@example.com", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def _run_pipeline_to_match(client: AsyncClient, image_bytes: bytes) -> str:
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
    return invoice_id


async def test_clean_invoice_is_auto_approved(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, po, po_line = await _seed_vendor_and_po(
        db_session, po_number="PO-000600", qty=Decimal("3"), unit_price=Decimal("25.00")
    )
    await _receive_goods(db_session, po, po_line, Decimal("3"))
    await _login_clerk(client, db_session)

    invoice_id = await _run_pipeline_to_match(
        client,
        _render_invoice(
            invoice_no="INV-2026-0600",
            invoice_date="2026-09-20",
            po_number="PO-000600",
            price="25.00",
            amount="75.00",
        ),
    )

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.matched

    match_result = (
        await db_session.execute(select(MatchResult).where(MatchResult.invoice_id == invoice.id))
    ).scalar_one()
    assert match_result.outcome == MatchOutcome.auto_approved
    assert match_result.po_id == po.id

    line_results = (
        (
            await db_session.execute(
                select(MatchLineResult).where(MatchLineResult.match_id == match_result.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(line_results) == 1
    assert line_results[0].po_line_id == po_line.id

    exceptions = (
        (
            await db_session.execute(
                select(ExceptionRecord).where(ExceptionRecord.invoice_id == invoice.id)
            )
        )
        .scalars()
        .all()
    )
    assert exceptions == []


async def test_price_variance_above_tolerance_creates_exception(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, po, po_line = await _seed_vendor_and_po(
        db_session, po_number="PO-000601", qty=Decimal("3"), unit_price=Decimal("25.00")
    )
    await _receive_goods(db_session, po, po_line, Decimal("3"))
    await _login_clerk(client, db_session)

    invoice_id = await _run_pipeline_to_match(
        client,
        _render_invoice(
            invoice_no="INV-2026-0601",
            invoice_date="2026-09-20",
            po_number="PO-000601",
            price="30.00",
            amount="90.00",
        ),
    )

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.exception

    match_result = (
        await db_session.execute(select(MatchResult).where(MatchResult.invoice_id == invoice.id))
    ).scalar_one()
    assert match_result.outcome == MatchOutcome.exception

    exceptions = (
        (
            await db_session.execute(
                select(ExceptionRecord).where(ExceptionRecord.invoice_id == invoice.id)
            )
        )
        .scalars()
        .all()
    )
    reason_codes = {e.reason_code for e in exceptions}
    assert "PRICE_VARIANCE" in reason_codes


async def test_missing_goods_receipt_blocks_quantity_and_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # No GRN seeded at all: QTY_NOT_RECEIVED must fire, and re-running
    # match_invoice (the re-match job, Plan.md section 7) must not
    # duplicate the open exception.
    await _seed_vendor_and_po(
        db_session, po_number="PO-000602", qty=Decimal("3"), unit_price=Decimal("25.00")
    )
    await _login_clerk(client, db_session)

    invoice_id = await _run_pipeline_to_match(
        client,
        _render_invoice(
            invoice_no="INV-2026-0602",
            invoice_date="2026-09-20",
            po_number="PO-000602",
            price="25.00",
            amount="75.00",
        ),
    )

    await match_invoice.func(invoice_id=invoice_id)  # re-match: must be idempotent

    invoice = await db_session.get(Invoice, uuid.UUID(invoice_id))
    assert invoice is not None
    await db_session.refresh(invoice)

    exceptions = (
        (
            await db_session.execute(
                select(ExceptionRecord).where(
                    ExceptionRecord.invoice_id == invoice.id,
                    ExceptionRecord.reason_code == "QTY_NOT_RECEIVED",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(exceptions) == 1  # not duplicated by the re-run

    match_results = (
        (await db_session.execute(select(MatchResult).where(MatchResult.invoice_id == invoice.id)))
        .scalars()
        .all()
    )
    assert len(match_results) == 2  # one MatchResult row per run, exceptions dedup separately
