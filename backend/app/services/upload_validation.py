import hashlib

import magic
import pypdfium2 as pdfium

from app.core.settings import get_settings

ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_PDF_PAGES = 20


class UploadValidationError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def sniff_mime_type(content: bytes) -> str:
    return str(magic.from_buffer(content, mime=True))


def validate_size(content: bytes) -> None:
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise UploadValidationError(f"File exceeds the {settings.max_upload_mb} MB limit")


def validate_mime_type(content: bytes) -> str:
    mime_type = sniff_mime_type(content)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise UploadValidationError(f"Unsupported file type: {mime_type}")
    return mime_type


def validate_pdf_structure(content: bytes) -> int:
    """Returns the page count. Raises on encrypted, malformed or oversize PDFs."""
    try:
        doc = pdfium.PdfDocument(content)
    except pdfium.PdfiumError as exc:
        raise UploadValidationError("Malformed or unreadable PDF") from exc

    try:
        page_count = len(doc)
    finally:
        doc.close()

    if page_count == 0:
        raise UploadValidationError("PDF has no pages")
    if page_count > MAX_PDF_PAGES:
        raise UploadValidationError(f"PDF exceeds the {MAX_PDF_PAGES} page limit")

    return page_count


def validate_upload(content: bytes, *, declared_filename: str) -> tuple[str, int]:
    """Full validation pipeline. Returns (mime_type, page_count)."""
    validate_size(content)
    mime_type = validate_mime_type(content)

    page_count = validate_pdf_structure(content) if mime_type == "application/pdf" else 1

    return mime_type, page_count


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
