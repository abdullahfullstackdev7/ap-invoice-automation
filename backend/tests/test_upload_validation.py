import io

import img2pdf
import pytest
from PIL import Image

from app.services.upload_validation import (
    UploadValidationError,
    compute_sha256,
    validate_upload,
)


def _png_bytes(size: tuple[int, int] = (100, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color="white").save(buf, format="PNG")
    return buf.getvalue()


def test_valid_png_accepted() -> None:
    mime_type, page_count = validate_upload(_png_bytes(), declared_filename="invoice.png")
    assert mime_type == "image/png"
    assert page_count == 1


def test_valid_pdf_accepted() -> None:
    pdf_bytes = img2pdf.convert(_png_bytes())
    mime_type, page_count = validate_upload(pdf_bytes, declared_filename="invoice.pdf")
    assert mime_type == "application/pdf"
    assert page_count == 1


def test_disallowed_mime_type_rejected() -> None:
    with pytest.raises(UploadValidationError):
        validate_upload(b"#!/bin/sh\necho hi\n", declared_filename="script.sh")


def test_oversized_file_rejected() -> None:
    oversized = b"\x00" * (16 * 1024 * 1024)
    with pytest.raises(UploadValidationError):
        validate_upload(oversized, declared_filename="big.png")


def test_malformed_pdf_rejected() -> None:
    with pytest.raises(UploadValidationError):
        validate_upload(b"%PDF-1.4\nnot actually a valid pdf", declared_filename="bad.pdf")


def test_pdf_exceeding_page_limit_rejected() -> None:
    pages = [_png_bytes() for _ in range(21)]
    pdf_bytes = img2pdf.convert(*pages)
    with pytest.raises(UploadValidationError):
        validate_upload(pdf_bytes, declared_filename="too_many_pages.pdf")


def test_sha256_is_deterministic() -> None:
    content = _png_bytes()
    assert compute_sha256(content) == compute_sha256(content)
    assert compute_sha256(content) != compute_sha256(_png_bytes((200, 200)))
