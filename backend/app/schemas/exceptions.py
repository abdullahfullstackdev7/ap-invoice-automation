import uuid
from datetime import date, datetime
from decimal import Decimal

from app.models.enums import ExceptionSeverity, ExceptionStatus, InvoiceStatus
from app.schemas.base import ORMModel


class ExceptionRead(ORMModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    reason_code: str
    severity: ExceptionSeverity
    details_json: dict[str, object] | None
    status: ExceptionStatus
    assigned_to: uuid.UUID | None
    opened_at: datetime
    sla_due_at: datetime | None
    resolved_by: uuid.UUID | None
    resolution: str | None
    resolved_at: datetime | None


class ExceptionListItem(ExceptionRead):
    invoice_no: str | None
    invoice_total: Decimal | None
    invoice_date: date | None
    vendor_name: str | None
    invoice_status: InvoiceStatus


class ExceptionListResponse(ORMModel):
    items: list[ExceptionListItem]
    total: int


class ExceptionActionRequest(ORMModel):
    action: str
    comment: str | None = None
    assignee_id: uuid.UUID | None = None


class BulkAssignRequest(ORMModel):
    exception_ids: list[uuid.UUID]
    assignee_id: uuid.UUID
