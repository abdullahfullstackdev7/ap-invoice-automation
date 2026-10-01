import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.matching.context import LineMapping, MatchContext
from app.matching.duplicate import check_duplicate
from app.matching.engine import MatchDecision, run_match
from app.matching.policy import get_tolerance_policy
from app.matching.rules.terms import early_pay_discount_eligible
from app.models.invoicing import Invoice, InvoiceLine
from app.models.masterdata import Vendor
from app.models.procurement import GRLine, POLine, PurchaseOrder

PRICE_HISTORY_WINDOW_DAYS = 180


@dataclass
class MatchRunResult:
    decision: MatchDecision
    po: PurchaseOrder | None
    line_mappings: list[LineMapping]
    discount_info: dict[str, object] | None


async def _qty_received_by_po_line(
    session: AsyncSession, po_line_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Decimal]:
    if not po_line_ids:
        return {}
    result = await session.execute(
        select(GRLine.po_line_id, func.sum(GRLine.qty_received))
        .where(GRLine.po_line_id.in_(po_line_ids))
        .group_by(GRLine.po_line_id)
    )
    return {row[0]: row[1] for row in result.all()}


async def _vendor_price_history(
    session: AsyncSession, vendor_id: uuid.UUID | None, as_of: date | None
) -> dict[str, list[tuple[date, Decimal]]]:
    """Best-effort vendor price history from prior matched invoices over
    the last ~6 months (Plan.md section 7, item 4), keyed by line
    description. Empty (not an error) when there is no prior history yet,
    which is the common case for a freshly seeded demo.
    """
    history: dict[str, list[tuple[date, Decimal]]] = {}
    if vendor_id is None or as_of is None:
        return history

    window_start = as_of - timedelta(days=PRICE_HISTORY_WINDOW_DAYS)
    result = await session.execute(
        select(InvoiceLine.description, InvoiceLine.unit_price, Invoice.invoice_date)
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .where(
            Invoice.vendor_id == vendor_id,
            Invoice.invoice_date.is_not(None),
            Invoice.invoice_date >= window_start,
            Invoice.invoice_date < as_of,
        )
    )
    for description, unit_price, invoice_date in result.all():
        if invoice_date is None:
            continue
        history.setdefault(description, []).append((invoice_date, unit_price))

    tax_result = await session.execute(
        select(Invoice.tax, Invoice.subtotal, Invoice.invoice_date).where(
            Invoice.vendor_id == vendor_id,
            Invoice.invoice_date.is_not(None),
            Invoice.invoice_date >= window_start,
            Invoice.invoice_date < as_of,
            Invoice.subtotal.is_not(None),
            Invoice.subtotal > 0,
            Invoice.tax.is_not(None),
        )
    )
    tax_rates: list[tuple[date, Decimal]] = [
        (invoice_date, (tax / subtotal * 100))
        for tax, subtotal, invoice_date in tax_result.all()
        if invoice_date is not None and tax is not None and subtotal is not None
    ]
    if tax_rates:
        history["__tax_rates__"] = tax_rates

    return history


def _line_mappings_from_resolution(extracted_json: dict[str, Any] | None) -> list[LineMapping]:
    if not extracted_json:
        return []
    resolution = extracted_json.get("resolution")
    if not resolution:
        return []
    mappings = []
    for entry in resolution.get("line_matches", []):
        mappings.append(
            LineMapping(
                invoice_line_id=uuid.UUID(entry["invoice_line_id"]),
                po_line_id=uuid.UUID(entry["po_line_id"]) if entry.get("po_line_id") else None,
                score=entry["score"],
                method=entry["method"],
            )
        )
    return mappings


async def run_match_for_invoice(session: AsyncSession, invoice: Invoice) -> MatchRunResult:
    """Assembles a MatchContext from the database and runs the full rule
    set. Safe to call repeatedly (idempotent re-match, Plan.md section 7,
    "Design points": a late-arriving PO or GRN should be re-matchable).
    """
    settings = get_settings()

    lines_result = await session.execute(
        select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id)
    )
    invoice_lines = list(lines_result.scalars().all())

    vendor = await session.get(Vendor, invoice.vendor_id) if invoice.vendor_id else None

    extracted_json = cast(dict[str, Any] | None, invoice.extracted_json)
    resolution = (extracted_json or {}).get("resolution") or {}
    po_id_raw = (resolution.get("po") or {}).get("po_id")
    po = await session.get(PurchaseOrder, uuid.UUID(po_id_raw)) if po_id_raw else None

    po_lines: list[POLine] = []
    if po is not None:
        po_lines_result = await session.execute(select(POLine).where(POLine.po_id == po.id))
        po_lines = list(po_lines_result.scalars().all())
    po_lines_by_id = {line.id: line for line in po_lines}

    qty_received = await _qty_received_by_po_line(session, list(po_lines_by_id.keys()))
    line_mappings = _line_mappings_from_resolution(extracted_json)

    policy = await get_tolerance_policy(
        session, vendor_id=invoice.vendor_id, category=vendor.category if vendor else None
    )
    vendor_price_history = await _vendor_price_history(
        session, invoice.vendor_id, invoice.invoice_date
    )

    ctx = MatchContext(
        invoice=invoice,
        invoice_lines=invoice_lines,
        vendor=vendor,
        po=po,
        po_lines=po_lines,
        po_lines_by_id=po_lines_by_id,
        qty_received_by_po_line=qty_received,
        line_mappings=line_mappings,
        policy=policy,
        auto_approve_limit=Decimal(settings.auto_approve_limit),
        vendor_price_history=vendor_price_history,
    )

    duplicate_result = await check_duplicate(session, invoice, invoice_lines)
    decision = run_match(
        ctx, is_exact_duplicate=duplicate_result.is_exact, duplicate_draft=duplicate_result.draft
    )
    discount_info = early_pay_discount_eligible(ctx)

    return MatchRunResult(
        decision=decision, po=po, line_mappings=line_mappings, discount_info=discount_info
    )
