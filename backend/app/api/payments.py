import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import forbid_same_actor, get_current_user, get_object_or_404, require_role
from app.core.csrf import require_csrf
from app.core.settings import get_settings
from app.db.session import get_db_session
from app.models.enums import PaymentBatchStatus, PaymentStatus, UserRole
from app.models.identity import User
from app.models.invoicing import Invoice
from app.models.masterdata import Vendor
from app.models.payments import Payment, PaymentBatch
from app.schemas.payments import PaymentBatchRead, PaymentRead
from app.services.audit import AuditService
from app.services.payment_batch import batch_total, render_batch_csv
from app.services.storage import read_file, write_file
from app.workers.tasks import settle_payment_batch

router = APIRouter(prefix="/payments", tags=["payments"])

finance_only = require_role(UserRole.finance_manager, UserRole.admin)
finance_or_auditor = require_role(UserRole.finance_manager, UserRole.admin, UserRole.auditor)


@router.get("", response_model=list[PaymentRead])
async def list_payments(
    payment_status: PaymentStatus | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[Payment]:
    query = select(Payment)
    if payment_status is not None:
        query = query.where(Payment.status == payment_status)
    result = await session.execute(query.order_by(Payment.scheduled_date))
    return list(result.scalars().all())


@router.post("/batches", response_model=PaymentBatchRead, status_code=status.HTTP_201_CREATED)
async def create_batch(
    actor: User = Depends(finance_only),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> PaymentBatch:
    result = await session.execute(
        select(Payment).where(Payment.status == PaymentStatus.scheduled, Payment.batch_id.is_(None))
    )
    payments = list(result.scalars().all())
    if not payments:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No scheduled payments are eligible")

    batch = PaymentBatch(
        created_by=actor.id, total=batch_total(payments), status=PaymentBatchStatus.draft
    )
    session.add(batch)
    await session.flush()

    for payment in payments:
        payment.batch_id = batch.id

    rows = []
    for payment in payments:
        invoice = await session.get(Invoice, payment.invoice_id)
        vendor = (
            await session.get(Vendor, invoice.vendor_id)
            if invoice is not None and invoice.vendor_id is not None
            else None
        )
        if invoice is not None and vendor is not None:
            rows.append((payment, invoice, vendor))

    csv_bytes = render_batch_csv(rows)
    relative_path = f"payment_batches/{batch.id}.csv"
    absolute_path = Path(get_settings().file_storage_path) / relative_path
    write_file(absolute_path, csv_bytes)
    batch.file_path = relative_path

    await AuditService(session).record(
        "payment_batch_created",
        "payment_batch",
        actor_id=actor.id,
        entity_id=batch.id,
        after={"payment_count": len(payments), "total": str(batch.total)},
    )
    await session.commit()
    return batch


@router.get("/batches/{batch_id}", response_model=PaymentBatchRead)
async def get_batch(
    batch_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaymentBatch:
    return await get_object_or_404(session, PaymentBatch, batch_id)


@router.get("/batches/{batch_id}/file")
async def get_batch_file(
    batch_id: uuid.UUID,
    user: User = Depends(finance_or_auditor),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    batch = await get_object_or_404(session, PaymentBatch, batch_id)
    if batch.file_path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No file for this batch")
    content = read_file(batch.file_path)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="batch-{batch.id}.csv"'},
    )


@router.post("/batches/{batch_id}/release", response_model=PaymentBatchRead)
async def release_batch(
    batch_id: uuid.UUID,
    actor: User = Depends(finance_only),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> PaymentBatch:
    batch = await get_object_or_404(session, PaymentBatch, batch_id)
    if batch.status != PaymentBatchStatus.draft:
        raise HTTPException(status.HTTP_409_CONFLICT, "Batch has already been released")

    forbid_same_actor(batch.created_by, actor.id, "The batch creator cannot also release it")

    batch.released_by = actor.id
    batch.status = PaymentBatchStatus.released

    result = await session.execute(select(Payment).where(Payment.batch_id == batch.id))
    now = datetime.now(UTC)
    for payment in result.scalars().all():
        payment.status = PaymentStatus.released
        payment.released_at = now

    await AuditService(session).record(
        "payment_batch_released",
        "payment_batch",
        actor_id=actor.id,
        entity_id=batch.id,
    )
    await session.commit()

    await settle_payment_batch.defer_async(batch_id=str(batch.id))
    return batch
