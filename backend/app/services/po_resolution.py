import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.procurement import POLine, PurchaseOrder

CANDIDATE_WINDOW_DAYS = 120
CANDIDATE_SCORE_THRESHOLD = 0.6
TOTAL_WEIGHT = 0.7
LINES_WEIGHT = 0.3


@dataclass
class POResolutionResult:
    po_id: uuid.UUID | None
    method: str  # "exact_number" | "candidate_scoring" | "unresolved"
    score: float


def normalize_po_number(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _total_similarity(po_total: Decimal, invoice_total: Decimal) -> float:
    if po_total == 0 and invoice_total == 0:
        return 1.0
    denom = max(abs(po_total), abs(invoice_total), Decimal("1"))
    return float(max(Decimal("0"), 1 - abs(po_total - invoice_total) / denom))


def _lines_similarity(invoice_descriptions: list[str], po_descriptions: list[str]) -> float:
    if not invoice_descriptions or not po_descriptions:
        return 0.0
    scores = []
    for desc in invoice_descriptions:
        best = max(
            (fuzz.token_set_ratio(desc, po_desc) for po_desc in po_descriptions), default=0
        )
        scores.append(best / 100)
    return sum(scores) / len(scores)


async def _find_by_exact_number(
    session: AsyncSession, po_number_ref: str, vendor_id: uuid.UUID | None
) -> PurchaseOrder | None:
    normalized_ref = normalize_po_number(po_number_ref)
    stmt = select(PurchaseOrder)
    if vendor_id is not None:
        stmt = stmt.where(PurchaseOrder.vendor_id == vendor_id)
    result = await session.execute(stmt)
    for po in result.scalars().all():
        if normalize_po_number(po.po_number) == normalized_ref:
            return po
    return None


async def resolve_po(
    session: AsyncSession,
    *,
    po_number_ref: str | None,
    vendor_id: uuid.UUID | None,
    invoice_date: date | None,
    invoice_total: Decimal | None,
    invoice_line_descriptions: list[str] | None = None,
) -> POResolutionResult:
    """PO resolution per Plan.md section 6 / Phase 6: exact PO number
    first (normalized for case, spaces and prefixes), else score
    candidate open POs for the resolved vendor within 120 days by total
    and line-description similarity.
    """
    if po_number_ref:
        po = await _find_by_exact_number(session, po_number_ref, vendor_id)
        if po is not None:
            return POResolutionResult(po.id, "exact_number", 1.0)

    if vendor_id is None or invoice_date is None:
        return POResolutionResult(None, "unresolved", 0.0)

    window_start = invoice_date - timedelta(days=CANDIDATE_WINDOW_DAYS)
    result = await session.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.vendor_id == vendor_id,
            PurchaseOrder.po_date >= window_start,
            PurchaseOrder.po_date <= invoice_date,
        )
    )
    candidates = list(result.scalars().all())
    if not candidates:
        return POResolutionResult(None, "unresolved", 0.0)

    best_po: PurchaseOrder | None = None
    best_score = 0.0
    for po in candidates:
        total_score = _total_similarity(po.total, invoice_total or Decimal("0"))

        lines_score = 0.0
        if invoice_line_descriptions:
            lines_result = await session.execute(
                select(POLine.description).where(POLine.po_id == po.id)
            )
            po_descriptions = [row[0] for row in lines_result.all()]
            lines_score = _lines_similarity(invoice_line_descriptions, po_descriptions)

        score = TOTAL_WEIGHT * total_score + LINES_WEIGHT * lines_score
        if score > best_score:
            best_score = score
            best_po = po

    if best_po is not None and best_score >= CANDIDATE_SCORE_THRESHOLD:
        return POResolutionResult(best_po.id, "candidate_scoring", best_score)

    return POResolutionResult(None, "unresolved", best_score)
