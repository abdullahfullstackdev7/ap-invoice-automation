"""Seed demo users: admin, clerk, approver, finance manager, auditor.

Demo credentials are fixed and documented in README.md so the sample
deployment's login page can show them (DEMO_MODE=true). Override any of
them via SEED_<ROLE>_PASSWORD env vars for a non-demo deployment; doing so
is mandatory before exposing this outside a local sandbox.
"""

import asyncio
import os
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.enums import UserRole
from app.models.identity import User
from app.models.policies import ApprovalPolicy
from app.services.approval_routing import CLEAN_MATCH_ABOVE_LIMIT

DEMO_PASSWORD_DEFAULT = "ChangeMe123Demo!"


@dataclass(frozen=True)
class SeedUser:
    email: str
    full_name: str
    role: UserRole
    approval_limit: Decimal | None
    password_env: str


SEED_USERS = [
    SeedUser(
        "admin@veridianpayables.demo", "Demo Admin", UserRole.admin, None, "SEED_ADMIN_PASSWORD"
    ),
    SeedUser(
        "clerk@veridianpayables.demo",
        "Demo AP Clerk",
        UserRole.ap_clerk,
        Decimal("2500"),
        "SEED_CLERK_PASSWORD",
    ),
    SeedUser(
        "approver@veridianpayables.demo",
        "Demo Approver",
        UserRole.approver,
        Decimal("25000"),
        "SEED_APPROVER_PASSWORD",
    ),
    SeedUser(
        "manager@veridianpayables.demo",
        "Demo Finance Manager",
        UserRole.finance_manager,
        None,
        "SEED_MANAGER_PASSWORD",
    ),
    SeedUser(
        "auditor@veridianpayables.demo",
        "Demo Auditor",
        UserRole.auditor,
        None,
        "SEED_AUDITOR_PASSWORD",
    ),
]


@dataclass(frozen=True)
class SeedApprovalPolicy:
    min_amount: Decimal
    max_amount: Decimal | None
    reason_code: str | None
    required_role: UserRole
    steps: list[str]


# Plan.md section 8's default approval matrix. The <=5,000 clean-match
# "Auto" row needs no policy row: route_invoice checks AUTO_APPROVE_LIMIT
# directly. CLEAN_MATCH_ABOVE_LIMIT is a synthetic reason_code (not a real
# exception reason) that disambiguates "clean match, over the limit" from
# the generic exception amount tiers below it; see
# app/services/approval_routing.py.
SEED_APPROVAL_POLICIES = [
    SeedApprovalPolicy(Decimal("0"), None, CLEAN_MATCH_ABOVE_LIMIT, UserRole.approver, []),
    SeedApprovalPolicy(Decimal("0"), Decimal("2500"), None, UserRole.ap_clerk, []),
    SeedApprovalPolicy(Decimal("2500.01"), Decimal("25000"), None, UserRole.approver, []),
    SeedApprovalPolicy(Decimal("25000.01"), None, None, UserRole.finance_manager, []),
    SeedApprovalPolicy(
        Decimal("0"),
        None,
        "DUPLICATE_SUSPECTED",
        UserRole.approver,
        ["approver", "finance_manager"],
    ),
]


async def seed() -> None:
    async with async_session_factory() as session:
        for spec in SEED_USERS:
            existing = await session.execute(select(User).where(User.email == spec.email))
            if existing.scalar_one_or_none() is not None:
                print(f"Skipping {spec.email}: already exists")
                continue

            password = os.environ.get(spec.password_env, DEMO_PASSWORD_DEFAULT)
            user = User(
                email=spec.email,
                password_hash=hash_password(password),
                full_name=spec.full_name,
                role=spec.role,
                approval_limit=spec.approval_limit,
                is_active=True,
            )
            session.add(user)
            print(f"Created {spec.email} ({spec.role.value})")

        existing_policies = await session.execute(select(ApprovalPolicy))
        if existing_policies.scalars().first() is None:
            for policy_spec in SEED_APPROVAL_POLICIES:
                session.add(
                    ApprovalPolicy(
                        min_amount=policy_spec.min_amount,
                        max_amount=policy_spec.max_amount,
                        reason_code=policy_spec.reason_code,
                        required_role=policy_spec.required_role,
                        steps=policy_spec.steps,
                    )
                )
            print(f"Created {len(SEED_APPROVAL_POLICIES)} approval policies")
        else:
            print("Skipping approval policies: already seeded")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
