"""Nightly (and post-batch) analytics_daily refresh, Plan.md section 9.

Recomputes the (date, vendor_id, category) grain from the raw tables for
a date range and upserts it (delete + reinsert, so a re-run is safe).
analytics_daily exists purely as a fast-path cache for the KPI, trend and
spend-by-* endpoints; everything else in app/analytics/queries.py reads
the raw tables directly since their grain doesn't fit a daily rollup.
"""

import uuid
from collections import defaultdict
from datetime import date as date_
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsDaily
from app.models.enums import ExceptionStatus, InvoiceStatus
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Document, Invoice, InvoiceLine
from app.models.masterdata import Vendor
from app.models.payments import Payment

PREVENTED_REASON_CODES = frozenset({"PRICE_VARIANCE", "QTY_OVER_RECEIVED", "TOTAL_MISMATCH"})


async def _prevented_value(session: AsyncSession, exceptions: list[ExceptionRecord]) -> Decimal:
    """Dollar value of overpayment a resolved exception prevented, read back
    from the numeric evidence each matching rule already stores in
    details_json (see app/matching/rules/*.py)."""
    total = Decimal("0")
    for exc in exceptions:
        details = exc.details_json or {}
        if exc.reason_code == "PRICE_VARIANCE" and {"price_inv", "price_po"} <= details.keys():
            line_id = details.get("invoice_line_id")
            if not isinstance(line_id, str):
                continue
            line = await session.get(InvoiceLine, uuid.UUID(line_id))
            if line is not None:
                price_diff = Decimal(str(details["price_inv"])) - Decimal(str(details["price_po"]))
                total += abs(price_diff) * line.qty
        elif (
            exc.reason_code == "QTY_OVER_RECEIVED"
            and {
                "qty_allowed",
                "qty_invoiced",
            }
            <= details.keys()
        ):
            line_id = details.get("invoice_line_id")
            if not isinstance(line_id, str):
                continue
            line = await session.get(InvoiceLine, uuid.UUID(line_id))
            if line is not None:
                qty_invoiced = Decimal(str(details["qty_invoiced"]))
                qty_allowed = Decimal(str(details["qty_allowed"]))
                over_qty = qty_invoiced - qty_allowed
                if over_qty > 0:
                    total += over_qty * line.unit_price
        elif exc.reason_code == "TOTAL_MISMATCH" and "diff" in details:
            total += Decimal(str(details["diff"]))
    return total


async def refresh_analytics_daily(session: AsyncSession, date_from: date_, date_to: date_) -> int:
    rows_result = await session.execute(
        select(Invoice, Document, Vendor)
        .join(Document, Invoice.document_id == Document.id)
        .outerjoin(Vendor, Invoice.vendor_id == Vendor.id)
    )
    rows = rows_result.all()

    groups: dict[tuple[date_, uuid.UUID | None, str | None], list[Invoice]] = defaultdict(list)
    vendor_by_id: dict[uuid.UUID, Vendor] = {}
    for invoice, document, vendor in rows:
        d = document.uploaded_at.date()
        if d < date_from or d > date_to:
            continue
        category = vendor.category if vendor is not None else None
        groups[(d, invoice.vendor_id, category)].append(invoice)
        if vendor is not None:
            vendor_by_id[vendor.id] = vendor

    await session.execute(
        delete(AnalyticsDaily).where(
            AnalyticsDaily.date >= date_from, AnalyticsDaily.date <= date_to
        )
    )

    for (d, vendor_id, category), invoices in groups.items():
        invoice_ids = [inv.id for inv in invoices]
        value = sum((inv.total or Decimal("0") for inv in invoices), Decimal("0"))
        stp_count = sum(1 for inv in invoices if inv.status == InvoiceStatus.auto_approved)

        exc_result = await session.execute(
            select(ExceptionRecord).where(ExceptionRecord.invoice_id.in_(invoice_ids))
        )
        exceptions_today = [e for e in exc_result.scalars().all() if e.opened_at.date() == d]
        exceptions_by_type: dict[str, int] = defaultdict(int)
        for exc in exceptions_today:
            exceptions_by_type[exc.reason_code] += 1

        prevented = [
            e
            for e in exceptions_today
            if e.status == ExceptionStatus.resolved and e.reason_code in PREVENTED_REASON_CODES
        ]
        savings_prevented = await _prevented_value(session, prevented)

        discounts_captured = Decimal("0")
        discounts_missed = Decimal("0")
        group_vendor = vendor_by_id.get(vendor_id) if vendor_id else None
        if group_vendor is not None and group_vendor.discount_pct:
            pay_result = await session.execute(
                select(Payment, Invoice)
                .join(Invoice, Payment.invoice_id == Invoice.id)
                .where(Payment.invoice_id.in_(invoice_ids))
            )
            for payment, inv in pay_result.all():
                if inv.due_date is None or inv.total is None:
                    continue
                discount_value = group_vendor.discount_pct / Decimal("100") * inv.total
                if payment.scheduled_date < inv.due_date:
                    discounts_captured += discount_value
                else:
                    discounts_missed += discount_value

        session.add(
            AnalyticsDaily(
                date=d,
                vendor_id=vendor_id,
                category=category,
                invoices_count=len(invoices),
                value=value,
                exceptions_by_type_json=dict(exceptions_by_type) or None,
                stp_count=stp_count,
                savings_prevented=savings_prevented,
                discounts_captured=discounts_captured,
                discounts_missed=discounts_missed,
            )
        )

    await session.commit()
    return len(groups)
