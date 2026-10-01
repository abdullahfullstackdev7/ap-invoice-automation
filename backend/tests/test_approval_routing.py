from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.policies import ApprovalPolicy
from app.services.approval_routing import determine_routing


async def test_clean_match_within_limit_is_auto_approved(db_session: AsyncSession) -> None:
    routing = await determine_routing(
        db_session,
        amount=Decimal("5000"),
        has_exceptions=False,
        exception_reason_codes=frozenset(),
    )
    assert routing.auto_approved is True
    assert routing.steps == []


async def test_clean_match_above_limit_falls_back_to_approver(db_session: AsyncSession) -> None:
    routing = await determine_routing(
        db_session,
        amount=Decimal("5000.01"),
        has_exceptions=False,
        exception_reason_codes=frozenset(),
    )
    assert routing.auto_approved is False
    assert routing.steps == [UserRole.approver]


async def test_small_exception_falls_back_to_ap_clerk(db_session: AsyncSession) -> None:
    routing = await determine_routing(
        db_session,
        amount=Decimal("2500"),
        has_exceptions=True,
        exception_reason_codes=frozenset({"PRICE_VARIANCE"}),
    )
    assert routing.steps == [UserRole.ap_clerk]


async def test_mid_exception_falls_back_to_approver(db_session: AsyncSession) -> None:
    routing = await determine_routing(
        db_session,
        amount=Decimal("25000"),
        has_exceptions=True,
        exception_reason_codes=frozenset({"PRICE_VARIANCE"}),
    )
    assert routing.steps == [UserRole.approver]


async def test_large_exception_falls_back_to_finance_manager(db_session: AsyncSession) -> None:
    routing = await determine_routing(
        db_session,
        amount=Decimal("25000.01"),
        has_exceptions=True,
        exception_reason_codes=frozenset({"PRICE_VARIANCE"}),
    )
    assert routing.steps == [UserRole.finance_manager]


async def test_duplicate_suspected_requires_approver_then_finance_manager(
    db_session: AsyncSession,
) -> None:
    routing = await determine_routing(
        db_session,
        amount=Decimal("100"),
        has_exceptions=True,
        exception_reason_codes=frozenset({"DUPLICATE_SUSPECTED"}),
    )
    assert routing.auto_approved is False
    assert routing.steps == [UserRole.approver, UserRole.finance_manager]


async def test_duplicate_suspected_overrides_a_small_amount_tier(db_session: AsyncSession) -> None:
    routing = await determine_routing(
        db_session,
        amount=Decimal("100"),
        has_exceptions=True,
        exception_reason_codes=frozenset({"PRICE_VARIANCE", "DUPLICATE_SUSPECTED"}),
    )
    assert routing.steps == [UserRole.approver, UserRole.finance_manager]


async def test_db_policy_row_overrides_the_hardcoded_default(db_session: AsyncSession) -> None:
    db_session.add(
        ApprovalPolicy(
            min_amount=Decimal("0"),
            max_amount=Decimal("2500"),
            reason_code=None,
            required_role=UserRole.finance_manager,
            steps=[],
        )
    )
    await db_session.commit()

    routing = await determine_routing(
        db_session,
        amount=Decimal("1000"),
        has_exceptions=True,
        exception_reason_codes=frozenset({"PRICE_VARIANCE"}),
    )
    assert routing.steps == [UserRole.finance_manager]
