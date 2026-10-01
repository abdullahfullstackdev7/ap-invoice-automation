import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_object_or_404, require_role
from app.core.csrf import require_csrf
from app.core.security import (
    PasswordPolicyError,
    encrypt_field,
    generate_totp_secret,
    hash_password,
    totp_provisioning_uri,
    validate_password_policy,
)
from app.db.session import get_db_session
from app.models.enums import UserRole
from app.models.identity import User
from app.schemas.identity import UserCreate, UserRead, UserUpdate
from app.services.audit import AuditService

router = APIRouter(prefix="/users", tags=["users"])

admin_only = require_role(UserRole.admin)
admin_or_auditor = require_role(UserRole.admin, UserRole.auditor)


@router.get("", response_model=list[UserRead])
async def list_users(
    user: User = Depends(admin_or_auditor),
    session: AsyncSession = Depends(get_db_session),
) -> list[User]:
    result = await session.execute(select(User).order_by(User.email))
    return list(result.scalars().all())


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    body: UserCreate,
    actor: User = Depends(admin_only),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> User:
    try:
        validate_password_policy(body.password)
    except PasswordPolicyError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")

    new_user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        approval_limit=body.approval_limit,
        is_active=True,
    )
    session.add(new_user)
    await session.flush()

    await AuditService(session).record(
        "user_created", "user", actor_id=actor.id, entity_id=new_user.id,
        after={"email": new_user.email, "role": new_user.role},
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    return new_user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    request: Request,
    user_id: uuid.UUID,
    body: UserUpdate,
    actor: User = Depends(admin_only),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> User:
    target = await get_object_or_404(session, User, user_id)

    updates = body.model_dump(exclude_unset=True)
    before = {field: getattr(target, field) for field in updates}
    for field, value in updates.items():
        setattr(target, field, value)

    await session.flush()
    await AuditService(session).record(
        "user_updated", "user", actor_id=actor.id, entity_id=target.id,
        before=before, after=updates,
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    return target


@router.post("/{user_id}/mfa/enable")
async def enable_mfa(
    request: Request,
    user_id: uuid.UUID,
    actor: User = Depends(admin_only),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> dict[str, str]:
    target = await get_object_or_404(session, User, user_id)
    if target.role not in (UserRole.admin, UserRole.approver):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "MFA is only available for admin and approver roles"
        )

    secret = generate_totp_secret()
    target.mfa_secret_enc = encrypt_field(secret).decode("utf-8")
    await session.flush()

    await AuditService(session).record(
        "mfa_enabled", "user", actor_id=actor.id, entity_id=target.id,
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    return {"provisioning_uri": totp_provisioning_uri(secret, target.email)}
