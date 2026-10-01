import io
from decimal import Decimal

from PIL import Image, ImageDraw

from app.extraction.rules_extractor import run_rules_extraction
from app.ocr.service import process_document


def _render_invoice() -> bytes:
    img = Image.new("RGB", (1100, 700), color="white")
    draw = ImageDraw.Draw(img)
    header = [
        "ACME SUPPLIES INC",
        "contact@acmesupplies.com",
        "TAX-786579303",
        "",
        "Invoice No: INV-2026-0042",
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
    draw.text((350, y), "3", fill="black")
    draw.text((500, y), "25.00", fill="black")
    draw.text((700, y), "75.00", fill="black")
    y += 40
    draw.text((30, y), "Service B", fill="black")
    draw.text((350, y), "1", fill="black")
    draw.text((500, y), "100.00", fill="black")
    draw.text((700, y), "100.00", fill="black")
    y += 60
    draw.text((30, y), "Subtotal: 175.00", fill="black")
    y += 35
    draw.text((30, y), "Tax: 17.50", fill="black")
    y += 35
    draw.text((30, y), "Total: 192.50", fill="black")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_rules_extraction_header_fields() -> None:
    ocr_result = process_document(_render_invoice(), "image/png")
    extract = run_rules_extraction(ocr_result)

    assert extract.invoice_no.value == "INV-2026-0042"
    assert extract.invoice_no.confidence > 0.8
    assert extract.invoice_date.value is not None
    assert extract.invoice_date.value.isoformat() == "2026-09-15"
    assert extract.due_date.value is not None
    assert extract.due_date.value.isoformat() == "2026-10-15"
    assert extract.po_reference.value == "PO-000123"


def test_rules_extraction_vendor_block() -> None:
    ocr_result = process_document(_render_invoice(), "image/png")
    extract = run_rules_extraction(ocr_result)

    assert extract.vendor_name.value == "ACME SUPPLIES INC"
    assert extract.vendor_email.value == "contact@acmesupplies.com"
    assert extract.vendor_tax_id.value == "TAX-786579303"


def test_rules_extraction_totals() -> None:
    ocr_result = process_document(_render_invoice(), "image/png")
    extract = run_rules_extraction(ocr_result)

    assert extract.subtotal.value == Decimal("175.00")
    assert extract.tax.value == Decimal("17.50")
    assert extract.total.value == Decimal("192.50")


def test_rules_extraction_line_items_columns() -> None:
    ocr_result = process_document(_render_invoice(), "image/png")
    extract = run_rules_extraction(ocr_result)

    assert len(extract.lines) == 2
    assert extract.lines[0].description.value == "Widget A"
    assert extract.lines[0].unit_price.value == Decimal("25.00")
    assert extract.lines[0].amount.value == Decimal("75.00")
    assert extract.lines[1].description.value == "Service B"
    assert extract.lines[1].unit_price.value == Decimal("100.00")
    assert extract.lines[1].amount.value == Decimal("100.00")
