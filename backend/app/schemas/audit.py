import uuid
from datetime import datetime

from app.schemas.base import ORMModel


class AuditLogRead(ORMModel):
    id: uuid.UUID
    ts: datetime
    actor_id: uuid.UUID | None
    action: str
    entity: str
    entity_id: uuid.UUID | None
    hash_prev: str | None
    hash_self: str
