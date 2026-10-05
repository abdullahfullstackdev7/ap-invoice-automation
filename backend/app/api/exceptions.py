import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_object_or_404, require_role
from app.core.csrf import require_csrf
from app.db.session import get_db_session
from app.models.enums import ExceptionSeverity, ExceptionStatus, UserRole
from app.models.exceptions import ExceptionRecord
from app.models.identity import User
from app.models.invoicing import Invoice
from app.models.masterdata import Vendor
from app.schemas.exceptions import (
    BulkAssignRequest,
    ExceptionActionRequest,
    ExceptionListItem,
    ExceptionListResponse,
    ExceptionRead,
)
from app.services.audit import AuditService
from app.services.exception_actions import apply_exception_action
from app.workers.tasks import match_invoice

router = APIRouter(prefix="/exceptions", tags=["exceptions"])

can_act = require_role(
    UserRole.admin, UserRole.ap_clerk, UserRole.approver, UserRole.finance_manager
)


@router.get("", response_model=ExceptionListResponse)
async def list_exceptions(
    exception_status: ExceptionStatus | None = None,
    reason_code: str | None = None,
    severity: ExceptionSeverity | None = None,
    vendor_id: uuid.UUID | None = None,
    assigned_to: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ExceptionListResponse:
    query = (
        select(ExceptionRecord, Invoice, Vendor.name)
        .join(Invoice, ExceptionRecord.invoice_id == Invoice.id)
        .outerjoin(Vendor, Invoice.vendor_id == Vendor.id)
    )
    if exception_status is not None:
        query = query.where(ExceptionRecord.status == exception_status)
    if reason_code is not None:
        query = query.where(ExceptionRecord.reason_code == reason_code)
    if severity is not None:
        query = query.where(ExceptionRecord.severity == severity)
    if vendor_id is not None:
        query = query.where(Invoice.vendor_id == vendor_id)
    if assigned_to is not None:
        query = query.where(ExceptionRecord.assigned_to == assigned_to)

    all_rows = (await session.execute(query)).all()
    total = len(all_rows)
    query = (
        query.order_by(ExceptionRecord.sla_due_at.asc().nulls_last()).limit(limit).offset(offset)
    )
    result = await session.execute(query)

    items = [
        ExceptionListItem(
            **ExceptionRead.model_validate(exc).model_dump(),
            invoice_no=invoice.invoice_no,
            invoice_total=invoice.total,
            invoice_date=invoice.invoice_date,
            vendor_name=vendor_name,
            invoice_status=invoice.status,
        )
        for exc, invoice, vendor_name in result.all()
    ]
    return ExceptionListResponse(items=items, total=total)


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


@router.post("/bulk-assign", response_model=list[ExceptionRead])
async def bulk_assign_exceptions(
    body: BulkAssignRequest,
    actor: User = Depends(can_act),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> list[ExceptionRecord]:
    result = await session.execute(
        select(ExceptionRecord).where(ExceptionRecord.id.in_(body.exception_ids))
    )
    exceptions = list(result.scalars().all())
    for exception in exceptions:
        exception.assigned_to = body.assignee_id

    await AuditService(session).record(
        "exceptions_bulk_assigned",
        "exception",
        actor_id=actor.id,
        after={
            "exception_ids": [str(e.id) for e in exceptions],
            "assignee_id": str(body.assignee_id),
        },
    )
    await session.commit()
    return exceptions
