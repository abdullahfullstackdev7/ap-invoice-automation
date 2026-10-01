import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_object_or_404, require_role
from app.core.csrf import require_csrf
from app.db.session import get_db_session
from app.models.approvals import Approval
from app.models.enums import UserRole
from app.models.identity import User
from app.models.invoicing import Invoice
from app.schemas.approvals import ApprovalDecisionRequest, ApprovalRead
from app.services.approvals import apply_approval_decision
from app.workers.tasks import schedule_payment

router = APIRouter(prefix="/invoices/{invoice_id}/approvals", tags=["approvals"])

can_decide = require_role(UserRole.ap_clerk, UserRole.approver, UserRole.finance_manager)


@router.get("", response_model=list[ApprovalRead])
async def list_approvals(
    invoice_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[Approval]:
    result = await session.execute(
        select(Approval).where(Approval.invoice_id == invoice_id).order_by(Approval.step)
    )
    return list(result.scalars().all())


@router.post("/decision", response_model=ApprovalRead)
async def decide_approval(
    invoice_id: uuid.UUID,
    body: ApprovalDecisionRequest,
    actor: User = Depends(can_decide),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> Approval:
    invoice = await get_object_or_404(session, Invoice, invoice_id)

    outcome = await apply_approval_decision(
        session,
        invoice=invoice,
        actor=actor,
        decision=body.decision,
        comment=body.comment,
    )
    await session.commit()

    if outcome.fully_approved:
        await schedule_payment.defer_async(invoice_id=str(invoice.id))

    return outcome.approval
