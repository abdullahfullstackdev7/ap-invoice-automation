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

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
