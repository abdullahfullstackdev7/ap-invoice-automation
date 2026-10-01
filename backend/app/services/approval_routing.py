"""Approval routing, Plan.md section 8's default matrix:

| Situation            | Amount     | Approver                      |
|-----------------------|-----------|--------------------------------|
| Clean match           | <= 5,000  | Auto                           |
| Clean match           | > 5,000   | approver                       |
| Exception             | <= 2,500  | ap_clerk with reason           |
| Exception             | <= 25,000 | approver                       |
| Exception             | > 25,000  | finance_manager                |
| Duplicate suspected   | any       | approver + finance_manager     |

Driven by the `approval_policies` table (vendor-agnostic here, unlike
tolerance_policies) so the matrix can be retuned without a deploy. Two
synthetic `reason_code` values disambiguate "situation" from a real
exception reason code, since the table has no separate situation column:
`CLEAN_MATCH_ABOVE_LIMIT` for a clean match over the auto-approve limit,
and `None` for the generic exception amount tiers. A real reason code
(e.g. `DUPLICATE_SUSPECTED`) always takes precedence when present, since
it can require a different (and longer) approval chain than the amount
alone would imply.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.models.enums import UserRole
from app.models.policies import ApprovalPolicy

CLEAN_MATCH_ABOVE_LIMIT = "CLEAN_MATCH_ABOVE_LIMIT"

DEFAULT_STEPS_BY_REASON: dict[str | None, list[UserRole]] = {
    "DUPLICATE_SUSPECTED": [UserRole.approver, UserRole.finance_manager],
}


@dataclass(frozen=True)
class RoutingDecision:
    auto_approved: bool
    steps: list[UserRole]


def _steps_from_policy(policy: ApprovalPolicy) -> list[UserRole]:
    if policy.steps:
        return [UserRole(step) for step in policy.steps]
    return [policy.required_role]


def _default_policy_steps(
    *, amount: Decimal, has_exceptions: bool, exception_reason_codes: frozenset[str]
) -> list[UserRole]:
    for reason_code in exception_reason_codes:
        if reason_code in DEFAULT_STEPS_BY_REASON:
            return list(DEFAULT_STEPS_BY_REASON[reason_code])

    if not has_exceptions:
        return [UserRole.approver]  # clean match above the auto-approve limit

    if amount <= Decimal("2500"):
        return [UserRole.ap_clerk]
    if amount <= Decimal("25000"):
        return [UserRole.approver]
    return [UserRole.finance_manager]


async def _policy_steps(
    session: AsyncSession,
    *,
    amount: Decimal,
    has_exceptions: bool,
    exception_reason_codes: frozenset[str],
) -> list[UserRole] | None:
    for reason_code in exception_reason_codes:
        result = await session.execute(
            select(ApprovalPolicy).where(
                ApprovalPolicy.reason_code == reason_code,
                ApprovalPolicy.min_amount <= amount,
                (ApprovalPolicy.max_amount.is_(None)) | (ApprovalPolicy.max_amount >= amount),
            )
        )
        policy = result.scalars().first()
        if policy is not None:
            return _steps_from_policy(policy)

    situation_reason_code = None if has_exceptions else CLEAN_MATCH_ABOVE_LIMIT
    result = await session.execute(
        select(ApprovalPolicy).where(
            ApprovalPolicy.reason_code == situation_reason_code,
            ApprovalPolicy.min_amount <= amount,
            (ApprovalPolicy.max_amount.is_(None)) | (ApprovalPolicy.max_amount >= amount),
        )
    )
    policy = result.scalars().first()
    if policy is not None:
        return _steps_from_policy(policy)
    return None


async def determine_routing(
    session: AsyncSession,
    *,
    amount: Decimal,
    has_exceptions: bool,
    exception_reason_codes: frozenset[str],
) -> RoutingDecision:
    settings = get_settings()

    if not has_exceptions and amount <= Decimal(str(settings.auto_approve_limit)):
        return RoutingDecision(auto_approved=True, steps=[])

    steps = await _policy_steps(
        session,
        amount=amount,
        has_exceptions=has_exceptions,
        exception_reason_codes=exception_reason_codes,
    )
    if steps is None:
        steps = _default_policy_steps(
            amount=amount,
            has_exceptions=has_exceptions,
            exception_reason_codes=exception_reason_codes,
        )
    return RoutingDecision(auto_approved=False, steps=steps)
