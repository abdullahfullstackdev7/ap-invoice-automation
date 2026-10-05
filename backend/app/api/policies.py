import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_object_or_404, require_role
from app.core.csrf import require_csrf
from app.db.session import get_db_session
from app.models.enums import UserRole
from app.models.identity import User
from app.models.policies import ApprovalPolicy, TolerancePolicy
from app.schemas.policies import (
    ApprovalPolicyCreate,
    ApprovalPolicyRead,
    TolerancePolicyCreate,
    TolerancePolicyRead,
)
from app.services.audit import AuditService

router = APIRouter(prefix="/policies", tags=["policies"])

can_view = require_role(
    UserRole.admin, UserRole.finance_manager, UserRole.auditor, UserRole.approver
)
can_manage = require_role(UserRole.admin)


@router.get("/tolerance", response_model=list[TolerancePolicyRead])
async def list_tolerance_policies(
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> list[TolerancePolicy]:
    result = await session.execute(select(TolerancePolicy))
    return list(result.scalars().all())


@router.post("/tolerance", response_model=TolerancePolicyRead, status_code=201)
async def create_tolerance_policy(
    body: TolerancePolicyCreate,
    actor: User = Depends(can_manage),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> TolerancePolicy:
    policy = TolerancePolicy(**body.model_dump())
    session.add(policy)
    await session.flush()
    await AuditService(session).record(
        "tolerance_policy_created", "tolerance_policy", actor_id=actor.id, entity_id=policy.id,
        after=body.model_dump(mode="json"),
    )
    await session.commit()
    return policy


@router.patch("/tolerance/{policy_id}", response_model=TolerancePolicyRead)
async def update_tolerance_policy(
    policy_id: uuid.UUID,
    body: TolerancePolicyCreate,
    actor: User = Depends(can_manage),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> TolerancePolicy:
    policy = await get_object_or_404(session, TolerancePolicy, policy_id)
    before = {k: getattr(policy, k) for k in body.model_dump()}
    for key, value in body.model_dump().items():
        setattr(policy, key, value)
    await session.flush()
    await AuditService(session).record(
        "tolerance_policy_updated", "tolerance_policy", actor_id=actor.id, entity_id=policy.id,
        before=before, after=body.model_dump(mode="json"),
    )
    await session.commit()
    return policy


@router.get("/approval", response_model=list[ApprovalPolicyRead])
async def list_approval_policies(
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> list[ApprovalPolicy]:
    result = await session.execute(select(ApprovalPolicy).order_by(ApprovalPolicy.min_amount))
    return list(result.scalars().all())


@router.post("/approval", response_model=ApprovalPolicyRead, status_code=201)
async def create_approval_policy(
    body: ApprovalPolicyCreate,
    actor: User = Depends(can_manage),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> ApprovalPolicy:
    policy = ApprovalPolicy(**body.model_dump())
    session.add(policy)
    await session.flush()
    await AuditService(session).record(
        "approval_policy_created", "approval_policy", actor_id=actor.id, entity_id=policy.id,
        after=body.model_dump(mode="json"),
    )
    await session.commit()
    return policy


@router.patch("/approval/{policy_id}", response_model=ApprovalPolicyRead)
async def update_approval_policy(
    policy_id: uuid.UUID,
    body: ApprovalPolicyCreate,
    actor: User = Depends(can_manage),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> ApprovalPolicy:
    policy = await get_object_or_404(session, ApprovalPolicy, policy_id)
    before = {k: getattr(policy, k) for k in body.model_dump()}
    for key, value in body.model_dump().items():
        setattr(policy, key, value)
    await session.flush()
    await AuditService(session).record(
        "approval_policy_updated", "approval_policy", actor_id=actor.id, entity_id=policy.id,
        before=before, after=body.model_dump(mode="json"),
    )
    await session.commit()
    return policy
