from datetime import timedelta
from decimal import Decimal

from app.matching.context import ExceptionDraft, MatchContext
from app.models.enums import ExceptionSeverity

DUE_DATE_TOLERANCE_DAYS = 2


def check_terms(ctx: MatchContext) -> list[ExceptionDraft]:
    """Due date vs vendor payment terms. Plan.md section 7, item 6. Early
    pay discount eligibility is computed separately by
    early_pay_discount_eligible() for Phase 8/9 to use, since it is an
    opportunity to flag, not an exception.
    """
    drafts: list[ExceptionDraft] = []
    invoice = ctx.invoice

    if invoice.invoice_date is None or invoice.due_date is None or ctx.vendor is None:
        return drafts

    expected_due = invoice.invoice_date + timedelta(days=ctx.vendor.payment_terms_days)
    drift_days = abs((invoice.due_date - expected_due).days)

    if drift_days > DUE_DATE_TOLERANCE_DAYS:
        drafts.append(
            ExceptionDraft(
                reason_code="DUE_DATE_MISMATCH",
                severity=ExceptionSeverity.low,
                details={
                    "due_date": invoice.due_date.isoformat(),
                    "expected_due_date": expected_due.isoformat(),
                    "vendor_terms_days": ctx.vendor.payment_terms_days,
                    "drift_days": drift_days,
                },
            )
        )

    return drafts


def early_pay_discount_eligible(ctx: MatchContext) -> dict[str, object] | None:
    vendor = ctx.vendor
    invoice = ctx.invoice
    if (
        vendor is None
        or vendor.discount_pct is None
        or vendor.discount_days is None
        or invoice.invoice_date is None
        or invoice.total is None
    ):
        return None

    discount_by = invoice.invoice_date + timedelta(days=vendor.discount_days)
    savings = (invoice.total * vendor.discount_pct / Decimal("100")).quantize(Decimal("0.01"))
    return {
        "eligible_if_paid_by": discount_by.isoformat(),
        "discount_pct": str(vendor.discount_pct),
        "estimated_savings": str(savings),
    }
