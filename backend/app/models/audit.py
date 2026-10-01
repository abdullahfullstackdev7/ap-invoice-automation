import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class AuditLog(UUIDPKMixin, Base):
    __tablename__ = "audit_log"

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    before_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    after_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(45))
    hash_prev: Mapped[str | None] = mapped_column(String(64))
    hash_self: Mapped[str] = mapped_column(String(64))
