from decimal import Decimal

from app.matching.context import ExceptionDraft, MatchContext
from app.models.enums import ExceptionSeverity


def check_quantity(ctx: MatchContext) -> list[ExceptionDraft]:
    """3-way quantity check, Plan.md section 7, item 3:
    qty_invoiced_now <= qty_received_total - qty_previously_invoiced,
    tolerance from policy, missing GRN -> QTY_NOT_RECEIVED.
    """
    drafts: list[ExceptionDraft] = []

    for invoice_line in ctx.invoice_lines:
        po_line = ctx.po_line_for(invoice_line.id)
        if po_line is None:
            continue  # unmatched lines are their own concern, not a quantity exception

        qty_received_total = ctx.qty_received_by_po_line.get(po_line.id, Decimal("0"))
        qty_previously_invoiced = po_line.qty_invoiced_cum
        qty_invoiced_now = invoice_line.qty

        if qty_received_total <= 0:
            drafts.append(
                ExceptionDraft(
                    reason_code="QTY_NOT_RECEIVED",
                    severity=ExceptionSeverity.high,
                    details={
                        "invoice_line_id": str(invoice_line.id),
                        "po_line_id": str(po_line.id),
                        "qty_invoiced": str(qty_invoiced_now),
                    },
                )
            )
            continue

        allowed = qty_received_total - qty_previously_invoiced
        tolerance_qty = allowed * (ctx.policy.qty_pct / Decimal("100"))

        if qty_invoiced_now > allowed + tolerance_qty:
            drafts.append(
                ExceptionDraft(
                    reason_code="QTY_OVER_RECEIVED",
                    severity=ExceptionSeverity.medium,
                    details={
                        "invoice_line_id": str(invoice_line.id),
                        "po_line_id": str(po_line.id),
                        "qty_invoiced": str(qty_invoiced_now),
                        "qty_received_total": str(qty_received_total),
                        "qty_previously_invoiced": str(qty_previously_invoiced),
                        "qty_allowed": str(allowed),
                    },
                )
            )

    return drafts
