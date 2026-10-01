from decimal import Decimal

from app.matching.context import ExceptionDraft, MatchContext
from app.models.enums import ExceptionSeverity


def check_totals_and_tax(ctx: MatchContext) -> list[ExceptionDraft]:
    """Recompute totals from matched lines (tolerance 0.02) and check tax
    rate consistency against vendor history. Plan.md section 7, item 5.
    """
    drafts: list[ExceptionDraft] = []
    invoice = ctx.invoice

    line_sum = sum((line.amount for line in ctx.invoice_lines), Decimal("0"))
    if invoice.subtotal is not None:
        diff = abs(line_sum - invoice.subtotal)
        if diff > ctx.policy.total_abs:
            drafts.append(
                ExceptionDraft(
                    reason_code="TOTAL_MISMATCH",
                    severity=ExceptionSeverity.medium,
                    details={
                        "check": "sum_lines_vs_subtotal",
                        "line_sum": str(line_sum),
                        "subtotal": str(invoice.subtotal),
                        "diff": str(diff),
                    },
                )
            )

    if invoice.subtotal is not None and invoice.total is not None:
        tax = invoice.tax or Decimal("0")
        discount = invoice.discount or Decimal("0")
        computed_total = invoice.subtotal + tax - discount
        diff = abs(computed_total - invoice.total)
        if diff > ctx.policy.total_abs:
            drafts.append(
                ExceptionDraft(
                    reason_code="TOTAL_MISMATCH",
                    severity=ExceptionSeverity.medium,
                    details={
                        "check": "subtotal_plus_tax_minus_discount_vs_total",
                        "computed_total": str(computed_total),
                        "total": str(invoice.total),
                        "diff": str(diff),
                    },
                )
            )

    if invoice.subtotal and invoice.subtotal > 0 and invoice.tax is not None:
        tax_rate = invoice.tax / invoice.subtotal * 100
        history_rates = ctx.vendor_price_history.get("__tax_rates__")
        if history_rates:
            avg_rate = sum((rate for _, rate in history_rates), Decimal("0")) / len(history_rates)
            if abs(tax_rate - avg_rate) > ctx.policy.tax_abs * 100:
                drafts.append(
                    ExceptionDraft(
                        reason_code="TAX_INCONSISTENT",
                        severity=ExceptionSeverity.low,
                        details={
                            "tax_rate_pct": str(tax_rate.quantize(Decimal("0.01"))),
                            "vendor_avg_tax_rate_pct": str(avg_rate.quantize(Decimal("0.01"))),
                        },
                    )
                )

    return drafts
