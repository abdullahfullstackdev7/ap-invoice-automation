import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.services.audit import AuditService, verify_chain


async def test_verify_chain_valid_on_fresh_entries(db_session: AsyncSession) -> None:
    service = AuditService(db_session)
    await service.record("login_succeeded", "user")
    await service.record("user_created", "user")
    await service.record("password_changed", "user")
    await db_session.commit()

    result = await verify_chain(db_session)

    assert result.valid is True
    assert result.checked == 3
    assert result.broken_at_id is None


async def test_verify_chain_valid_when_empty(db_session: AsyncSession) -> None:
    result = await verify_chain(db_session)
    assert result.valid is True
    assert result.checked == 0


async def test_verify_chain_detects_tampering(
    db_session: AsyncSession, admin_db_session: AsyncSession
) -> None:
    service = AuditService(db_session)
    await service.record("login_succeeded", "user")
    entry = await service.record("user_created", "user")
    await db_session.commit()

    # app_rw cannot UPDATE audit_log (enforced at the database level), so
    # tampering is simulated the only way it could realistically happen:
    # direct admin access bypassing the application entirely.
    select_result = await admin_db_session.execute(
        select(AuditLog).where(AuditLog.id == entry.id)
    )
    row = select_result.scalar_one()
    row.action = "tampered_action"
    await admin_db_session.commit()

    verification = await verify_chain(db_session)

    assert verification.valid is False
    assert verification.broken_at_id == entry.id


async def test_app_rw_cannot_update_audit_log(db_session: AsyncSession) -> None:
    service = AuditService(db_session)
    entry = await service.record("login_succeeded", "user")
    await db_session.commit()

    result = await db_session.execute(select(AuditLog).where(AuditLog.id == entry.id))
    row = result.scalar_one()
    row.action = "tampered_action"

    with pytest.raises(DBAPIError):
        await db_session.commit()
