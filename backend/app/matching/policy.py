import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TolerancePolicyScope
from app.models.policies import TolerancePolicy

DEFAULT_POLICY = TolerancePolicy(
    scope=TolerancePolicyScope.global_scope,
    vendor_id=None,
    category=None,
    qty_pct=Decimal("0"),
    price_pct=Decimal("1"),
    price_abs=Decimal("1"),
    total_abs=Decimal("0.02"),
    tax_abs=Decimal("0.02"),
)


async def get_tolerance_policy(
    session: AsyncSession, *, vendor_id: uuid.UUID | None, category: str | None
) -> TolerancePolicy:
    """Vendor > category > global precedence, per Plan.md section 7,
    "Design points". Falls back to an in-memory policy matching the
    Plan.md section 5 defaults when nothing has been configured yet.
    """
    if vendor_id is not None:
        result = await session.execute(
            select(TolerancePolicy).where(
                TolerancePolicy.scope == TolerancePolicyScope.vendor,
                TolerancePolicy.vendor_id == vendor_id,
            )
        )
        policy = result.scalar_one_or_none()
        if policy is not None:
            return policy

    if category is not None:
        result = await session.execute(
            select(TolerancePolicy).where(
                TolerancePolicy.scope == TolerancePolicyScope.category,
                TolerancePolicy.category == category,
            )
        )
        policy = result.scalar_one_or_none()
        if policy is not None:
            return policy

    result = await session.execute(
        select(TolerancePolicy).where(TolerancePolicy.scope == TolerancePolicyScope.global_scope)
    )
    policy = result.scalar_one_or_none()
    return policy if policy is not None else DEFAULT_POLICY
