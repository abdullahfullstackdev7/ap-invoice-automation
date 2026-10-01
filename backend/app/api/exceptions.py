import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_object_or_404, require_role
from app.core.csrf import require_csrf
from app.db.session import get_db_session
from app.models.enums import ExceptionStatus, UserRole
from app.models.exceptions import ExceptionRecord
from app.models.identity import User
from app.models.invoicing import Invoice
from app.schemas.exceptions import ExceptionActionRequest, ExceptionRead
from app.services.exception_actions import apply_exception_action
from app.workers.tasks import match_invoice

router = APIRouter(prefix="/exceptions", tags=["exceptions"])

can_act = require_role(
    UserRole.admin, UserRole.ap_clerk, UserRole.approver, UserRole.finance_manager
)


@router.get("", response_model=list[ExceptionRead])
async def list_exceptions(
    exception_status: ExceptionStatus | None = None,
    assigned_to: uuid.UUID | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ExceptionRecord]:
    query = select(ExceptionRecord)
    if exception_status is not None:
        query = query.where(ExceptionRecord.status == exception_status)
    if assigned_to is not None:
        query = query.where(ExceptionRecord.assigned_to == assigned_to)
    result = await session.execute(query.order_by(ExceptionRecord.sla_due_at.asc().nulls_last()))
    return list(result.scalars().all())


@router.get("/{exception_id}", response_model=ExceptionRead)
async def get_exception(
    exception_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExceptionRecord:
    return await get_object_or_404(session, ExceptionRecord, exception_id)


@router.post("/{exception_id}/action", response_model=ExceptionRead)
async def act_on_exception(
    exception_id: uuid.UUID,
    body: ExceptionActionRequest,
    actor: User = Depends(can_act),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> ExceptionRecord:
    exception = await get_object_or_404(session, ExceptionRecord, exception_id)
    invoice = await get_object_or_404(session, Invoice, exception.invoice_id)

    result = await apply_exception_action(
        session,
        exception=exception,
        invoice=invoice,
        actor=actor,
        action=body.action,
        comment=body.comment,
        assignee_id=body.assignee_id,
    )
    await session.commit()

    if result.re_match_requested:
        await match_invoice.defer_async(invoice_id=str(invoice.id))

    return exception
