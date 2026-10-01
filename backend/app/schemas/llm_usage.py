import uuid
from datetime import datetime

from app.models.enums import LLMUsageStatus
from app.schemas.base import ORMModel


class LLMUsageRead(ORMModel):
    id: uuid.UUID
    ts: datetime
    provider: str
    model: str
    purpose: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    status: LLMUsageStatus
    invoice_id: uuid.UUID | None
