import uuid
from datetime import date, datetime
from decimal import Decimal

from app.models.enums import PaymentBatchStatus, PaymentMethod, PaymentStatus
from app.schemas.base import ORMModel


class PaymentRead(ORMModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    batch_id: uuid.UUID | None
    amount: Decimal
    scheduled_date: date
    released_at: datetime | None
    status: PaymentStatus
    method: PaymentMethod


class PaymentBatchCreate(ORMModel):
    created_by: uuid.UUID


class PaymentBatchRead(ORMModel):
    id: uuid.UUID
    created_by: uuid.UUID
    released_by: uuid.UUID | None
    total: Decimal
    status: PaymentBatchStatus
