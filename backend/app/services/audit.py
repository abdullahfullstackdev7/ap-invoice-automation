import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

GENESIS_HASH = "0" * 64


def _json_safe(value: Any) -> Any:
    """Recursively converts values the JSONB column can't store natively.

    Decimal becomes a string, not a float, since the audit trail must
    preserve exact money values rather than lose precision to float.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def compute_entry_hash(
    hash_prev: str,
    ts: datetime,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: uuid.UUID | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> str:
    payload = _canonical(
        {
            "hash_prev": hash_prev,
            "ts": ts.isoformat(),
            "actor_id": str(actor_id) if actor_id else None,
            "action": action,
            "entity": entity,
            "entity_id": str(entity_id) if entity_id else None,
            "before": before,
            "after": after,
        }
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _latest_hash(self) -> str:
        result = await self.session.execute(
            select(AuditLog.hash_self).order_by(AuditLog.ts.desc()).limit(1)
        )
        latest = result.scalar_one_or_none()
        return latest or GENESIS_HASH

    async def record(
        self,
        action: str,
        entity: str,
        *,
        actor_id: uuid.UUID | None = None,
        entity_id: uuid.UUID | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        ip: str | None = None,
    ) -> AuditLog:
        before = _json_safe(before)
        after = _json_safe(after)

        ts = datetime.now(UTC)
        hash_prev = await self._latest_hash()
        hash_self = compute_entry_hash(
            hash_prev, ts, actor_id, action, entity, entity_id, before, after
        )
        entry = AuditLog(
            ts=ts,
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before_json=before,
            after_json=after,
            ip=ip,
            hash_prev=hash_prev,
            hash_self=hash_self,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry


class ChainVerificationResult:
    def __init__(self, valid: bool, broken_at_id: uuid.UUID | None, checked: int) -> None:
        self.valid = valid
        self.broken_at_id = broken_at_id
        self.checked = checked


async def verify_chain(session: AsyncSession) -> ChainVerificationResult:
    # populate_existing so a caller's identity map (e.g. from just having
    # written entries in this same session) never masks a row that was
    # changed out from under it, since this is a security verifier and
    # must trust the database over in-memory state.
    result = await session.execute(
        select(AuditLog).order_by(AuditLog.ts.asc()).execution_options(populate_existing=True)
    )
    entries = list(result.scalars().all())

    expected_prev = GENESIS_HASH
    for entry in entries:
        if entry.hash_prev != expected_prev:
            return ChainVerificationResult(False, entry.id, len(entries))
        recomputed = compute_entry_hash(
            entry.hash_prev,
            entry.ts,
            entry.actor_id,
            entry.action,
            entry.entity,
            entry.entity_id,
            entry.before_json,
            entry.after_json,
        )
        if recomputed != entry.hash_self:
            return ChainVerificationResult(False, entry.id, len(entries))
        expected_prev = entry.hash_self

    return ChainVerificationResult(True, None, len(entries))
