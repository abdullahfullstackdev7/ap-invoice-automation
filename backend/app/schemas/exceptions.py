import uuid
from datetime import datetime

from app.models.enums import ExceptionSeverity, ExceptionStatus
from app.schemas.base import ORMModel


class ExceptionRead(ORMModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    reason_code: str
    severity: ExceptionSeverity
    status: ExceptionStatus
    assigned_to: uuid.UUID | None
    sla_due_at: datetime | None
    resolved_by: uuid.UUID | None
    resolution: str | None
    resolved_at: datetime | None


class ExceptionActionRequest(ORMModel):
    action: str
    comment: str | None = None
