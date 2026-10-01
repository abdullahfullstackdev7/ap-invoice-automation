import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InvoiceStatus
from app.models.invoicing import Invoice
from app.ocr.types import OCRDocumentResult


def compute_ocr_text_hash(ocr_result: OCRDocumentResult) -> str:
    """SHA-256 of the normalized OCR text across all pages. Same input
    (a re-scanned or re-submitted copy of the same invoice) never reaches
    the rules extractor or an LLM twice, per Plan.md section 6, item 2.
    """
    normalized = "\n".join(
        " ".join(line.text.split()) for page in ocr_result.pages for line in page.lines
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def find_cached_extraction(
    session: AsyncSession, ocr_text_hash: str, exclude_invoice_id: uuid.UUID
) -> Invoice | None:
    result = await session.execute(
        select(Invoice).where(
            Invoice.dup_key == ocr_text_hash,
            Invoice.id != exclude_invoice_id,
            Invoice.status.in_(
                [InvoiceStatus.extracted, InvoiceStatus.matched, InvoiceStatus.auto_approved,
                 InvoiceStatus.approved, InvoiceStatus.paid]
            ),
        )
    )
    return result.scalars().first()
