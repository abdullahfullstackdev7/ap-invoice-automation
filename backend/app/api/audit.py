from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.session import get_db_session
from app.models.audit import AuditLog
from app.models.enums import UserRole
from app.models.identity import User
from app.schemas.audit import AuditLogRead
from app.services.audit import verify_chain

router = APIRouter(prefix="/audit", tags=["audit"])

admin_or_auditor = require_role(UserRole.admin, UserRole.auditor)


@router.get("", response_model=list[AuditLogRead])
async def list_audit_log(
    user: User = Depends(admin_or_auditor),
    session: AsyncSession = Depends(get_db_session),
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    result = await session.execute(
        select(AuditLog).order_by(AuditLog.ts.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/verify")
async def verify_audit_chain(
    user: User = Depends(admin_or_auditor),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    result = await verify_chain(session)
    return {
        "valid": result.valid,
        "entries_checked": result.checked,
        "broken_at_id": str(result.broken_at_id) if result.broken_at_id else None,
    }
