import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ApprovalDecision, ExceptionStatus
from app.models.exceptions import ExceptionRecord
from app.models.identity import User
from app.models.invoicing import Invoice
from app.services.approvals import apply_approval_decision
from app.services.audit import AuditService

ACTIONS = frozenset(
    {
        "approve",
        "reject",
        "request_credit_note",
        "request_corrected_invoice",
        "hold",
        "reassign",
        "add_comment",
        "re_match",
    }
)

_MANDATORY_COMMENT_ACTIONS = frozenset({"approve", "reject"})


@dataclass
class ExceptionActionResult:
    re_match_requested: bool
    fully_approved: bool


async def apply_exception_action(
    session: AsyncSession,
    *,
    exception: ExceptionRecord,
    invoice: Invoice,
    actor: User,
    action: str,
    comment: str | None,
    assignee_id: uuid.UUID | None,
) -> ExceptionActionResult:
    if action not in ACTIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown action: {action}")
    if action in _MANDATORY_COMMENT_ACTIONS and not comment:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A reason is required")
    if action == "reassign" and assignee_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "assignee_id is required")

    now = datetime.now(UTC)
    re_match_requested = False
    fully_approved = False

    if action == "approve":
        outcome = await apply_approval_decision(
            session,
            invoice=invoice,
            actor=actor,
            decision=ApprovalDecision.approved,
            comment=comment,
        )
        fully_approved = outcome.fully_approved
        exception.status = ExceptionStatus.resolved
        exception.resolution = comment
        exception.resolved_by = actor.id
        exception.resolved_at = now

    elif action == "reject":
        await apply_approval_decision(
            session,
            invoice=invoice,
            actor=actor,
            decision=ApprovalDecision.rejected,
            comment=comment,
        )
        exception.status = ExceptionStatus.resolved
        exception.resolution = f"rejected: {comment}"
        exception.resolved_by = actor.id
        exception.resolved_at = now

    elif action == "request_credit_note":
        exception.status = ExceptionStatus.in_review
        exception.resolution = (
            f"credit note requested: {comment}" if comment else "credit note requested"
        )

    elif action == "request_corrected_invoice":
        exception.status = ExceptionStatus.in_review
        exception.resolution = (
            f"corrected invoice requested: {comment}" if comment else "corrected invoice requested"
        )

    elif action == "hold":
        exception.status = ExceptionStatus.in_review
        exception.resolution = f"on hold: {comment}" if comment else "on hold"

    elif action == "reassign":
        exception.assigned_to = assignee_id

    elif action == "add_comment":
        details = dict(exception.details_json or {})
        existing_comments = details.get("comments")
        comments: list[object] = (
            list(existing_comments) if isinstance(existing_comments, list) else []
        )
        comments.append({"actor_id": str(actor.id), "comment": comment, "at": now.isoformat()})
        details["comments"] = comments
        exception.details_json = details

    elif action == "re_match":
        re_match_requested = True

    await AuditService(session).record(
        "exception_action",
        "exception",
        actor_id=actor.id,
        entity_id=exception.id,
        after={"action": action, "comment": comment},
    )
    await session.flush()

    return ExceptionActionResult(
        re_match_requested=re_match_requested, fully_approved=fully_approved
    )
