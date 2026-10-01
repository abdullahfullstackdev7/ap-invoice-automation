"""Payment date selection, Plan.md section 8: "pay on due date, or earlier
when the early-pay discount is worth it (annualized return above a
configurable hurdle, default 10 percent)."

Annualized return of taking an early-payment discount, standard AP
formula:

    APR = [discount% / (100% - discount%)] * [365 / (net_days - discount_days)]

where net_days is the invoice's normal due date and discount_days is how
early payment must be made to earn the discount. If the discount is worth
less (annualized) than the hurdle rate, or there's no discount term at
all, pay on the normal due date instead.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

DAYS_PER_YEAR = Decimal("365")


@dataclass(frozen=True)
class PaymentScheduleDecision:
    scheduled_date: date
    early_pay_discount_taken: bool
    annualized_return_pct: Decimal | None


def _annualized_return_pct(
    discount_pct: Decimal, due_date: date, discount_date: date
) -> Decimal | None:
    days_earlier = (due_date - discount_date).days
    if days_earlier <= 0 or discount_pct <= 0 or discount_pct >= 100:
        return None
    rate = discount_pct / (Decimal("100") - discount_pct)
    return rate * (DAYS_PER_YEAR / Decimal(days_earlier)) * Decimal("100")


def decide_payment_schedule(
    *,
    invoice_date: date,
    due_date: date,
    discount_pct: Decimal | None,
    discount_days: int | None,
    hurdle_pct: Decimal,
) -> PaymentScheduleDecision:
    if discount_pct is None or discount_days is None or discount_pct <= 0:
        return PaymentScheduleDecision(due_date, False, None)

    discount_date = invoice_date + timedelta(days=discount_days)
    if discount_date >= due_date:
        return PaymentScheduleDecision(due_date, False, None)

    annualized = _annualized_return_pct(discount_pct, due_date, discount_date)
    if annualized is None or annualized < hurdle_pct:
        return PaymentScheduleDecision(due_date, False, annualized)

    return PaymentScheduleDecision(discount_date, True, annualized)
