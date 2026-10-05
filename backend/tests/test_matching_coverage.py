"""Branch coverage for the matching engine's less common paths (vendor and
category tolerance precedence, total and tax consistency, price-history
drift, and lines with no PO match). Plan.md section 13 sets a >= 95 percent
gate on the matching engine; these cover the branches the scenario tests
do not reach."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.matching.context import LineMapping
from app.matching.policy import DEFAULT_POLICY, get_tolerance_policy
from app.matching.rules.price import _pct_diff, check_price
from app.matching.rules.quantity import check_quantity
from app.matching.rules.totals_tax import check_totals_and_tax
from app.models.enums import TolerancePolicyScope
from app.models.policies import TolerancePolicy
from tests.test_matching_rules import _ctx, _invoice, _invoice_line, _po_line


async def test_policy_prefers_vendor_scope_over_category_and_global(
    db_session: AsyncSession,
) -> None:
    vendor_id = uuid.uuid4()
    db_session.add_all(
        [
            TolerancePolicy(scope=TolerancePolicyScope.global_scope, price_pct=Decimal("1")),
            TolerancePolicy(
                scope=TolerancePolicyScope.category, category="Office", price_pct=Decimal("2")
            ),
            TolerancePolicy(
                scope=TolerancePolicyScope.vendor, vendor_id=vendor_id, price_pct=Decimal("3")
            ),
        ]
    )
    await db_session.commit()

    policy = await get_tolerance_policy(db_session, vendor_id=vendor_id, category="Office")
    assert policy.price_pct == Decimal("3")


async def test_policy_falls_back_to_category_then_global(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            TolerancePolicy(scope=TolerancePolicyScope.global_scope, price_pct=Decimal("1")),
            TolerancePolicy(
                scope=TolerancePolicyScope.category, category="Travel", price_pct=Decimal("4")
            ),
        ]
    )
    await db_session.commit()

    by_category = await get_tolerance_policy(db_session, vendor_id=None, category="Travel")
    assert by_category.price_pct == Decimal("4")

    by_global = await get_tolerance_policy(db_session, vendor_id=None, category="Unknown")
    assert by_global.price_pct == Decimal("1")


async def test_policy_returns_default_when_nothing_configured(db_session: AsyncSession) -> None:
    policy = await get_tolerance_policy(db_session, vendor_id=None, category=None)
    assert policy is DEFAULT_POLICY


def test_total_mismatch_when_subtotal_plus_tax_disagrees_with_total() -> None:
    invoice = _invoice(
        subtotal=Decimal("100.00"), tax=Decimal("10.00"), discount=None, total=Decimal("150.00")
    )
    drafts = check_totals_and_tax(
        _ctx(invoice=invoice, invoice_lines=[_invoice_line(amount=Decimal("100.00"))])
    )
    assert [d.details["check"] for d in drafts] == ["subtotal_plus_tax_minus_discount_vs_total"]


def test_tax_rate_inconsistent_with_vendor_history_is_flagged() -> None:
    invoice = _invoice(subtotal=Decimal("100.00"), tax=Decimal("10.00"), total=Decimal("110.00"))
    ctx = _ctx(invoice=invoice, invoice_lines=[_invoice_line(amount=Decimal("100.00"))])
    ctx.vendor_price_history["__tax_rates__"] = [(date(2026, 1, 1), Decimal("20"))]
    drafts = check_totals_and_tax(ctx)
    assert [d.reason_code for d in drafts] == ["TAX_INCONSISTENT"]


def test_pct_diff_handles_zero_purchase_order_price() -> None:
    assert _pct_diff(Decimal("0"), Decimal("0")) == Decimal("0")
    assert _pct_diff(Decimal("5"), Decimal("0")) == Decimal("100")


def test_price_history_drift_above_threshold_is_flagged() -> None:
    line = _invoice_line(description="Widget", unit_price=Decimal("12.00"))
    po_line = _po_line(unit_price=Decimal("12.00"))
    ctx = _ctx(invoice_lines=[line], po_lines=[po_line])
    ctx.vendor_price_history["Widget"] = [(date(2026, 1, 1), Decimal("10.00"))]
    drafts = check_price(ctx)
    assert [d.details["source"] for d in drafts] == ["vendor_price_history"]


def test_lines_without_a_po_match_are_skipped_by_price_and_quantity() -> None:
    line = _invoice_line()
    ctx = _ctx(
        invoice_lines=[line],
        po_lines=[],
        line_mappings=[LineMapping(line.id, None, 0.0, "none")],
    )
    assert check_price(ctx) == []
    assert check_quantity(ctx) == []
