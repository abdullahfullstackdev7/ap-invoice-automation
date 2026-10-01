from decimal import Decimal

from app.matching.context import ExceptionDraft, MatchContext
from app.models.enums import ExceptionSeverity

WARNING_PCT = Decimal("5")
HISTORY_DRIFT_PCT = Decimal("10")


def _pct_diff(price_inv: Decimal, price_po: Decimal) -> Decimal:
    if price_po == 0:
        return Decimal("0") if price_inv == 0 else Decimal("100")
    return abs(price_inv - price_po) / price_po * 100


def check_price(ctx: MatchContext) -> list[ExceptionDraft]:
    """abs(price_inv - price_po) / price_po against policy, Plan.md
    section 7, item 4: pass within max(price_pct%, price_abs), warning up
    to 5%, exception above 5%. Also flags vendor 6-month price-history
    drift above 10% even when the PO itself matches.
    """
    drafts: list[ExceptionDraft] = []

    for invoice_line in ctx.invoice_lines:
        po_line = ctx.po_line_for(invoice_line.id)
        if po_line is None:
            continue

        price_inv = invoice_line.unit_price
        price_po = po_line.unit_price
        abs_diff = abs(price_inv - price_po)
        pct_diff = _pct_diff(price_inv, price_po)

        within_tolerance = abs_diff <= ctx.policy.price_abs or pct_diff <= ctx.policy.price_pct
        if not within_tolerance:
            severity = (
                ExceptionSeverity.low if pct_diff <= WARNING_PCT else ExceptionSeverity.medium
            )
            drafts.append(
                ExceptionDraft(
                    reason_code="PRICE_VARIANCE",
                    severity=severity,
                    details={
                        "invoice_line_id": str(invoice_line.id),
                        "po_line_id": str(po_line.id),
                        "price_inv": str(price_inv),
                        "price_po": str(price_po),
                        "variance_pct": str(pct_diff.quantize(Decimal("0.01"))),
                    },
                )
            )

        history = ctx.vendor_price_history.get(invoice_line.description)
        if history:
            recent_prices = [price for _, price in history]
            avg_price = sum(recent_prices, Decimal("0")) / len(recent_prices)
            history_drift = _pct_diff(price_inv, avg_price)
            if history_drift > HISTORY_DRIFT_PCT:
                drafts.append(
                    ExceptionDraft(
                        reason_code="PRICE_VARIANCE",
                        severity=ExceptionSeverity.low,
                        details={
                            "invoice_line_id": str(invoice_line.id),
                            "price_inv": str(price_inv),
                            "vendor_avg_price_6mo": str(avg_price.quantize(Decimal("0.01"))),
                            "history_drift_pct": str(history_drift.quantize(Decimal("0.01"))),
                            "source": "vendor_price_history",
                        },
                    )
                )

    return drafts
