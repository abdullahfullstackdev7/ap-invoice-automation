import uuid
from datetime import datetime

from app.models.enums import ApprovalDecision
from app.schemas.base import ORMModel


class ApprovalDecisionRequest(ORMModel):
    decision: ApprovalDecision
    comment: str | None = None


class ApprovalRead(ORMModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    step: int
    approver_id: uuid.UUID
    decision: ApprovalDecision
    comment: str | None
    decided_at: datetime
