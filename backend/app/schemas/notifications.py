import uuid
from datetime import datetime

from app.schemas.base import ORMModel


class NotificationRead(ORMModel):
    id: uuid.UUID
    title: str
    body: str
    link: str | None
    created_at: datetime
    read_at: datetime | None
