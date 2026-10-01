import io

import img2pdf
from PIL import Image

from app.ocr.preprocessing import extract_pdf_text_layer, pdf_has_text_layer, render_pdf_pages


def _minimal_text_pdf(text: str) -> bytes:
    """Hand-built single-page PDF with a real text layer (no external
    PDF-writing library in this project's dependencies).
    """
    content_stream = f"BT /F1 18 Tf 50 700 Td ({text}) Tj ET".encode()
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 4 0 R >> endobj",
        b"4 0 obj << /Length " + str(len(content_stream)).encode() + b" >> stream\n"
        + content_stream + b"\nendstream endobj",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
    ]

    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj + b"\n"
    xref_start = len(pdf)
    pdf += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += (
        b"trailer << /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_start).encode() + b"\n%%EOF"
    )
    return pdf


def _image_only_pdf() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), color="white").save(buf, format="PNG")
    return bytes(img2pdf.convert(buf.getvalue()))


def test_text_layer_pdf_is_detected() -> None:
    pdf_bytes = _minimal_text_pdf("ACME SUPPLIES INC Invoice INV-2026-0042 Total 192.50")
    assert pdf_has_text_layer(pdf_bytes) is True
    assert "ACME SUPPLIES INC" in extract_pdf_text_layer(pdf_bytes)[0]


def test_image_only_pdf_has_no_text_layer() -> None:
    assert pdf_has_text_layer(_image_only_pdf()) is False


def test_render_pdf_pages_produces_one_image_per_page() -> None:
    images = render_pdf_pages(_image_only_pdf())
    assert len(images) == 1
    assert images[0].ndim == 3  # BGR numpy array
