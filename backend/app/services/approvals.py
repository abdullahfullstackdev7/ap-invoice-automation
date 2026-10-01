import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import forbid_same_actor
from app.models.approvals import Approval
from app.models.enums import ApprovalDecision, ExceptionStatus, InvoiceStatus, UserRole
from app.models.exceptions import ExceptionRecord
from app.models.identity import User
from app.models.invoicing import Document, Invoice
from app.services.approval_routing import determine_routing
from app.services.audit import AuditService


@dataclass
class ApprovalOutcome:
    approval: Approval
    rejected: bool
    fully_approved: bool


async def _open_exception_reason_codes(
    session: AsyncSession, invoice_id: uuid.UUID
) -> frozenset[str]:
    result = await session.execute(
        select(ExceptionRecord.reason_code).where(
            ExceptionRecord.invoice_id == invoice_id,
            ExceptionRecord.status.in_((ExceptionStatus.open, ExceptionStatus.in_review)),
        )
    )
    return frozenset(row[0] for row in result.all())


async def apply_approval_decision(
    session: AsyncSession,
    *,
    invoice: Invoice,
    actor: User,
    decision: ApprovalDecision,
    comment: str | None,
) -> ApprovalOutcome:
    document = await session.get(Document, invoice.document_id)
    if document is not None and document.uploaded_by is not None:
        forbid_same_actor(
            document.uploaded_by, actor.id, "The invoice uploader cannot approve their own invoice"
        )

    reason_codes = await _open_exception_reason_codes(session, invoice.id)
    routing = await determine_routing(
        session,
        amount=invoice.total or Decimal("0"),
        has_exceptions=bool(reason_codes),
        exception_reason_codes=reason_codes,
    )
    if routing.auto_approved or not routing.steps:
        raise HTTPException(status.HTTP_409_CONFLICT, "This invoice does not require approval")

    existing = await session.execute(
        select(Approval).where(Approval.invoice_id == invoice.id).order_by(Approval.step)
    )
    existing_approvals = list(existing.scalars().all())
    step_index = len(existing_approvals)
    if step_index >= len(routing.steps):
        raise HTTPException(status.HTTP_409_CONFLICT, "This invoice has already been approved")

    required_role = routing.steps[step_index]
    if actor.role != required_role:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, f"This step requires the {required_role.value} role"
        )
    if required_role == UserRole.ap_clerk and not comment:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "A reason is required to approve an exception"
        )
    invoice_total = invoice.total or Decimal("0")
    if required_role in (UserRole.ap_clerk, UserRole.approver) and (
        actor.approval_limit is None or actor.approval_limit < invoice_total
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Amount exceeds the approver's approval limit"
        )

    now = datetime.now(UTC)
    approval = Approval(
        invoice_id=invoice.id,
        step=step_index + 1,
        approver_id=actor.id,
        decision=decision,
        comment=comment,
        decided_at=now,
    )
    session.add(approval)
    await session.flush()

    rejected = decision == ApprovalDecision.rejected
    fully_approved = False

    if rejected:
        invoice.status = InvoiceStatus.needs_review
        await AuditService(session).record(
            "invoice_rejected",
            "invoice",
            actor_id=actor.id,
            entity_id=invoice.id,
            after={"step": approval.step, "comment": comment},
        )
    else:
        fully_approved = step_index + 1 == len(routing.steps)
        if fully_approved:
            invoice.status = InvoiceStatus.approved
            await AuditService(session).record(
                "invoice_approved",
                "invoice",
                actor_id=actor.id,
                entity_id=invoice.id,
                after={"step": approval.step, "of_steps": len(routing.steps)},
            )
        else:
            await AuditService(session).record(
                "invoice_approval_step_completed",
                "invoice",
                actor_id=actor.id,
                entity_id=invoice.id,
                after={"step": approval.step, "of_steps": len(routing.steps)},
            )

    await session.flush()
    return ApprovalOutcome(approval=approval, rejected=rejected, fully_approved=fully_approved)
