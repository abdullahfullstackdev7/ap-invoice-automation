import io

from PIL import Image, ImageDraw

from app.ocr.service import process_document

MEAN_CONFIDENCE_TARGET = 0.85  # Plan.md section 8, Phase 4 acceptance


def _synthetic_invoice_png() -> bytes:
    img = Image.new("RGB", (800, 400), color="white")
    draw = ImageDraw.Draw(img)
    lines = [
        "ACME SUPPLIES INC",
        "Invoice No: INV-2026-0042",
        "Invoice Date: 2026-09-15",
        "Total: 192.50",
    ]
    y = 30
    for line in lines:
        draw.text((30, y), line, fill="black")
        y += 35
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_process_document_runs_ocr_on_clean_image_above_confidence_target() -> None:
    result = process_document(_synthetic_invoice_png(), "image/png")

    assert result.source == "rapidocr"
    assert len(result.pages) == 1
    assert result.mean_confidence > MEAN_CONFIDENCE_TARGET
    joined = " ".join(line.text for line in result.pages[0].lines)
    assert "INV-2026-0042" in joined
    assert "192.50" in joined


def test_process_document_words_carry_page_and_bbox() -> None:
    result = process_document(_synthetic_invoice_png(), "image/png")

    for word in result.pages[0].words:
        assert word.page == 1
        assert word.bbox.x1 > word.bbox.x0
        assert word.bbox.y1 > word.bbox.y0
        assert 0.0 <= word.conf <= 1.0
