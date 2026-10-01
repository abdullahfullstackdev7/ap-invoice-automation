from datetime import date
from decimal import Decimal

from app.services.payment_scheduling import decide_payment_schedule

HURDLE = Decimal("10.0")


def test_no_discount_terms_pays_on_due_date() -> None:
    decision = decide_payment_schedule(
        invoice_date=date(2026, 9, 1),
        due_date=date(2026, 10, 1),
        discount_pct=None,
        discount_days=None,
        hurdle_pct=HURDLE,
    )
    assert decision.scheduled_date == date(2026, 10, 1)
    assert decision.early_pay_discount_taken is False


def test_rich_discount_clears_hurdle_and_is_taken() -> None:
    # 2/10 net 30: APR = (2/98) * (365/20) * 100 ~= 37.2%, well above 10%.
    decision = decide_payment_schedule(
        invoice_date=date(2026, 9, 1),
        due_date=date(2026, 10, 1),
        discount_pct=Decimal("2"),
        discount_days=10,
        hurdle_pct=HURDLE,
    )
    assert decision.early_pay_discount_taken is True
    assert decision.scheduled_date == date(2026, 9, 11)
    assert decision.annualized_return_pct is not None
    assert decision.annualized_return_pct > HURDLE


def test_thin_discount_below_hurdle_is_not_taken() -> None:
    # 0.1/10 net 30: tiny discount, annualized return is well under 10%.
    decision = decide_payment_schedule(
        invoice_date=date(2026, 9, 1),
        due_date=date(2026, 10, 1),
        discount_pct=Decimal("0.1"),
        discount_days=10,
        hurdle_pct=HURDLE,
    )
    assert decision.early_pay_discount_taken is False
    assert decision.scheduled_date == date(2026, 10, 1)


def test_discount_date_on_or_after_due_date_is_ignored() -> None:
    decision = decide_payment_schedule(
        invoice_date=date(2026, 9, 1),
        due_date=date(2026, 9, 5),
        discount_pct=Decimal("2"),
        discount_days=10,
        hurdle_pct=HURDLE,
    )
    assert decision.early_pay_discount_taken is False
    assert decision.scheduled_date == date(2026, 9, 5)


def test_zero_discount_pct_is_ignored() -> None:
    decision = decide_payment_schedule(
        invoice_date=date(2026, 9, 1),
        due_date=date(2026, 10, 1),
        discount_pct=Decimal("0"),
        discount_days=10,
        hurdle_pct=HURDLE,
    )
    assert decision.early_pay_discount_taken is False
