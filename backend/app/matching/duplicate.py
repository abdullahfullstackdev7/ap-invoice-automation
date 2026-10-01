import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

import numpy as np
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.extraction.parsing import normalize_invoice_number
from app.matching.context import ExceptionDraft
from app.models.enums import ExceptionSeverity
from app.models.invoicing import Invoice, InvoiceLine
from app.services.embeddings import embed_texts

NEAR_DUP_AMOUNT_PCT = Decimal("0.005")
NEAR_DUP_DATE_WINDOW_DAYS = 7
NEAR_DUP_INVOICE_NO_SIMILARITY = 0.85
NEAR_DUP_LINE_EMBEDDING_SIMILARITY = 0.85


@dataclass(frozen=True)
class DuplicateCheckResult:
    is_exact: bool
    draft: ExceptionDraft | None


async def _exact_duplicate(session: AsyncSession, invoice: Invoice) -> Invoice | None:
    """(vendor_id, normalized invoice_no) exact match against another
    invoice. The identical-file case is already caught at upload time
    (Phase 4's SHA-256 dedup, before any processing cost is spent); this
    catches the same invoice number resubmitted as a different file.
    """
    if invoice.vendor_id is None or not invoice.invoice_no:
        return None

    normalized = normalize_invoice_number(invoice.invoice_no)
    result = await session.execute(
        select(Invoice).where(
            Invoice.vendor_id == invoice.vendor_id,
            Invoice.invoice_no.is_not(None),
            Invoice.id != invoice.id,
        )
    )
    for other in result.scalars().all():
        if other.invoice_no and normalize_invoice_number(other.invoice_no) == normalized:
            return other
    return None


async def _near_duplicate_candidates(session: AsyncSession, invoice: Invoice) -> list[Invoice]:
    if invoice.vendor_id is None or invoice.invoice_date is None or invoice.total is None:
        return []

    window_start = invoice.invoice_date - timedelta(days=NEAR_DUP_DATE_WINDOW_DAYS)
    window_end = invoice.invoice_date + timedelta(days=NEAR_DUP_DATE_WINDOW_DAYS)
    amount_tolerance = abs(invoice.total) * NEAR_DUP_AMOUNT_PCT

    result = await session.execute(
        select(Invoice).where(
            Invoice.vendor_id == invoice.vendor_id,
            Invoice.id != invoice.id,
            Invoice.invoice_date.is_not(None),
            Invoice.invoice_date >= window_start,
            Invoice.invoice_date <= window_end,
            Invoice.total.is_not(None),
            Invoice.total >= invoice.total - amount_tolerance,
            Invoice.total <= invoice.total + amount_tolerance,
        )
    )
    return list(result.scalars().all())


async def _line_embedding_similarity(
    session: AsyncSession, invoice_lines: list[InvoiceLine], other_invoice_id: uuid.UUID
) -> float:
    if not invoice_lines:
        return 0.0

    result = await session.execute(
        select(InvoiceLine).where(InvoiceLine.invoice_id == other_invoice_id)
    )
    other_lines = list(result.scalars().all())
    if not other_lines:
        return 0.0

    own_texts = [line.description for line in invoice_lines]
    other_texts = [line.description for line in other_lines]
    own_embeddings = embed_texts(own_texts)
    other_embeddings = embed_texts(other_texts)

    best_per_line = []
    for own_vec in own_embeddings:
        sims = [float(np.dot(own_vec, other_vec)) for other_vec in other_embeddings]
        best_per_line.append(max(sims, default=0.0))
    return sum(best_per_line) / len(best_per_line)


async def check_duplicate(
    session: AsyncSession, invoice: Invoice, invoice_lines: list[InvoiceLine]
) -> DuplicateCheckResult:
    exact_match = await _exact_duplicate(session, invoice)
    if exact_match is not None:
        return DuplicateCheckResult(
            is_exact=True,
            draft=ExceptionDraft(
                reason_code="DUPLICATE_EXACT",
                severity=ExceptionSeverity.high,
                details={"duplicate_of_invoice_id": str(exact_match.id)},
            ),
        )

    for candidate in await _near_duplicate_candidates(session, invoice):
        if not (invoice.invoice_no and candidate.invoice_no):
            continue
        name_similarity = (
            fuzz.ratio(
                normalize_invoice_number(invoice.invoice_no),
                normalize_invoice_number(candidate.invoice_no),
            )
            / 100
        )
        if name_similarity < NEAR_DUP_INVOICE_NO_SIMILARITY:
            continue

        line_similarity = await _line_embedding_similarity(session, invoice_lines, candidate.id)
        if line_similarity < NEAR_DUP_LINE_EMBEDDING_SIMILARITY:
            continue

        return DuplicateCheckResult(
            is_exact=False,
            draft=ExceptionDraft(
                reason_code="DUPLICATE_SUSPECTED",
                severity=ExceptionSeverity.high,
                details={
                    "candidate_invoice_id": str(candidate.id),
                    "invoice_no_similarity": name_similarity,
                    "line_similarity": line_similarity,
                },
            ),
        )

    return DuplicateCheckResult(is_exact=False, draft=None)
