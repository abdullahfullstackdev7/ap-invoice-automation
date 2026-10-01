from app.matching.context import ExceptionDraft, MatchContext
from app.models.enums import ExceptionSeverity, POStatus


def check_header(ctx: MatchContext) -> list[ExceptionDraft]:
    """PO exists and open, vendor matches the PO's vendor, currency
    matches, invoice date is after the PO date. Plan.md section 7, item 2.
    """
    drafts: list[ExceptionDraft] = []

    if ctx.po is None:
        drafts.append(
            ExceptionDraft(
                reason_code="PO_NOT_FOUND",
                severity=ExceptionSeverity.high,
                details={"po_number_ref": ctx.invoice.po_number_ref},
            )
        )
        return drafts  # nothing else below is checkable without a PO

    if ctx.po.status == POStatus.closed:
        drafts.append(
            ExceptionDraft(
                reason_code="PO_CLOSED",
                severity=ExceptionSeverity.high,
                details={"po_id": str(ctx.po.id), "po_number": ctx.po.po_number},
            )
        )

    if ctx.invoice.vendor_id is not None and ctx.po.vendor_id != ctx.invoice.vendor_id:
        drafts.append(
            ExceptionDraft(
                reason_code="VENDOR_MISMATCH",
                severity=ExceptionSeverity.high,
                details={
                    "invoice_vendor_id": str(ctx.invoice.vendor_id),
                    "po_vendor_id": str(ctx.po.vendor_id),
                },
            )
        )

    if ctx.invoice.currency and ctx.po.currency and ctx.invoice.currency != ctx.po.currency:
        drafts.append(
            ExceptionDraft(
                reason_code="CURRENCY_MISMATCH",
                severity=ExceptionSeverity.medium,
                details={"invoice_currency": ctx.invoice.currency, "po_currency": ctx.po.currency},
            )
        )

    if (
        ctx.invoice.invoice_date is not None
        and ctx.po.po_date is not None
        and ctx.invoice.invoice_date < ctx.po.po_date
    ):
        drafts.append(
            ExceptionDraft(
                reason_code="INVOICE_DATE_BEFORE_PO",
                severity=ExceptionSeverity.low,
                details={
                    "invoice_date": ctx.invoice.invoice_date.isoformat(),
                    "po_date": ctx.po.po_date.isoformat(),
                },
            )
        )

    return drafts
