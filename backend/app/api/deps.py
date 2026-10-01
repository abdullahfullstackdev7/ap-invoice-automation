import uuid
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import NoReturn

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import ACCESS_COOKIE_NAME
from app.core.security import decode_token
from app.db.session import get_db_session
from app.models.base import Base
from app.models.enums import UserRole
from app.models.identity import User
from app.services.audit import AuditService


async def _deny(
    session: AsyncSession,
    request: Request,
    status_code: int,
    detail: str,
    actor_id: uuid.UUID | None,
) -> NoReturn:
    await AuditService(session).record(
        "access_denied",
        "http_request",
        actor_id=actor_id,
        after={"path": request.url.path, "method": request.method, "reason": detail},
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    raise HTTPException(status_code, detail)


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_db_session)
) -> User:
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        await _deny(session, request, status.HTTP_401_UNAUTHORIZED, "Not authenticated", None)

    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        await _deny(
            session, request, status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", None
        )

    if payload.get("type") != "access":
        await _deny(session, request, status.HTTP_401_UNAUTHORIZED, "Invalid token type", None)

    user = await session.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        await _deny(
            session, request, status.HTTP_401_UNAUTHORIZED, "User not found or inactive", None
        )

    return user


def require_role(*roles: UserRole) -> Callable[..., Awaitable[User]]:
    async def dependency(
        request: Request,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        if user.role not in roles:
            await _deny(session, request, status.HTTP_403_FORBIDDEN, "Insufficient role", user.id)
        return user

    return dependency


def require_limit(minimum_amount: Decimal) -> Callable[..., Awaitable[User]]:
    """Dependency factory: the current user must have an approval_limit that
    covers at least minimum_amount. Admins and roles without a limit concept
    (finance_manager) are expected to be gated separately via require_role.
    """

    async def dependency(
        request: Request,
        user: User = Depends(get_current_user),
        session: AsyncSession = Depends(get_db_session),
    ) -> User:
        if user.approval_limit is None or user.approval_limit < minimum_amount:
            await _deny(
                session, request, status.HTTP_403_FORBIDDEN, "Amount exceeds approval limit",
                user.id,
            )
        return user

    return dependency


async def get_object_or_404[ModelT: Base](
    session: AsyncSession, model: type[ModelT], object_id: uuid.UUID
) -> ModelT:
    instance = await session.get(model, object_id)
    if instance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__tablename__} not found")
    return instance


def forbid_same_actor(first_actor_id: uuid.UUID, second_actor_id: uuid.UUID, detail: str) -> None:
    """Segregation of duties: the same person may not perform both actions.

    Used, for example, to stop the invoice uploader from also approving it,
    or an approver from releasing the payment they approved.
    """
    if first_actor_id == second_actor_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail)
