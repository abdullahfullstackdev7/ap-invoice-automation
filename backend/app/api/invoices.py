import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_object_or_404, require_role
from app.core.csrf import require_csrf
from app.db.session import get_db_session
from app.models.enums import InvoiceStatus, UserRole
from app.models.identity import User
from app.models.invoicing import Document, Invoice
from app.models.masterdata import Vendor
from app.models.matching import MatchResult
from app.schemas.invoicing import (
    InvoiceFieldUpdate,
    InvoiceListItem,
    InvoiceListResponse,
    InvoiceRead,
    UploadResultItem,
)
from app.schemas.matching import MatchResultRead
from app.services.audit import AuditService
from app.services.storage import read_file, storage_path_for, write_file
from app.services.upload_validation import (
    UploadValidationError,
    compute_sha256,
    validate_upload,
)
from app.workers.tasks import process_invoice

router = APIRouter(prefix="/invoices", tags=["invoices"])

can_upload = require_role(UserRole.admin, UserRole.ap_clerk)
can_edit = require_role(UserRole.admin, UserRole.ap_clerk)


async def _get_invoice_with_lines(session: AsyncSession, invoice_id: uuid.UUID) -> Invoice:
    result = await session.execute(
        select(Invoice)
        .options(selectinload(Invoice.lines))
        .where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoices not found")
    return invoice


@router.post("/upload", response_model=list[UploadResultItem])
async def upload_invoices(
    files: list[UploadFile],
    actor: User = Depends(can_upload),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> list[UploadResultItem]:
    results: list[UploadResultItem] = []

    for upload in files:
        content = await upload.read()
        filename = upload.filename or "upload"

        try:
            mime_type, page_count = validate_upload(content, declared_filename=filename)
        except UploadValidationError as exc:
            results.append(
                UploadResultItem(filename=filename, status="rejected", detail=exc.reason)
            )
            continue

        sha256 = compute_sha256(content)
        existing = await session.execute(select(Document).where(Document.sha256 == sha256))
        if existing.scalar_one_or_none() is not None:
            # Exact duplicate: flagged immediately, no storage write, no OCR
            # job, no processing cost, per Plan.md section 4.3/8.
            results.append(UploadResultItem(filename=filename, status="duplicate_exact"))
            continue

        relative_path, absolute_path = storage_path_for(filename)
        write_file(absolute_path, content)

        document = Document(
            sha256=sha256,
            filename=filename,
            mime=mime_type,
            size=len(content),
            storage_path=relative_path,
            page_count=page_count,
            uploaded_by=actor.id,
            uploaded_at=datetime.now(UTC),
        )
        session.add(document)
        await session.flush()

        invoice = Invoice(
            document_id=document.id,
            currency="USD",
            status=InvoiceStatus.uploaded,
        )
        session.add(invoice)
        await session.flush()

        await session.commit()

        await process_invoice.defer_async(document_id=str(document.id))

        results.append(
            UploadResultItem(
                filename=filename, status="queued", document_id=document.id, invoice_id=invoice.id
            )
        )

    return results


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    invoice_status: InvoiceStatus | None = None,
    vendor_id: uuid.UUID | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> InvoiceListResponse:
    query = select(Invoice, Vendor.name).outerjoin(Vendor, Invoice.vendor_id == Vendor.id)
    count_query = select(func.count(Invoice.id)).select_from(Invoice)

    if invoice_status is not None:
        query = query.where(Invoice.status == invoice_status)
        count_query = count_query.where(Invoice.status == invoice_status)
    if vendor_id is not None:
        query = query.where(Invoice.vendor_id == vendor_id)
        count_query = count_query.where(Invoice.vendor_id == vendor_id)
    if date_from is not None:
        query = query.where(Invoice.invoice_date >= date_from)
        count_query = count_query.where(Invoice.invoice_date >= date_from)
    if date_to is not None:
        query = query.where(Invoice.invoice_date <= date_to)
        count_query = count_query.where(Invoice.invoice_date <= date_to)
    if search:
        pattern = f"%{search}%"
        search_filter = Invoice.invoice_no.ilike(pattern)
        query = query.where(or_(search_filter, Vendor.name.ilike(pattern)))
        count_query = count_query.outerjoin(Vendor, Invoice.vendor_id == Vendor.id).where(
            or_(search_filter, Vendor.name.ilike(pattern))
        )

    total = (await session.execute(count_query)).scalar_one()
    result = await session.execute(
        query.order_by(Invoice.invoice_date.desc().nulls_last()).limit(limit).offset(offset)
    )
    items = [
        InvoiceListItem(
            id=invoice.id,
            invoice_no=invoice.invoice_no,
            invoice_date=invoice.invoice_date,
            due_date=invoice.due_date,
            currency=invoice.currency,
            total=invoice.total,
            status=invoice.status,
            vendor_id=invoice.vendor_id,
            vendor_name=vendor_name,
            extraction_confidence=invoice.extraction_confidence,
        )
        for invoice, vendor_name in result.all()
    ]
    return InvoiceListResponse(items=items, total=total)


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(
    invoice_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Invoice:
    return await _get_invoice_with_lines(session, invoice_id)


@router.patch("/{invoice_id}", response_model=InvoiceRead)
async def update_invoice(
    request: Request,
    invoice_id: uuid.UUID,
    body: InvoiceFieldUpdate,
    actor: User = Depends(can_edit),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> Invoice:
    invoice = await _get_invoice_with_lines(session, invoice_id)

    updates = body.model_dump(exclude_unset=True)
    before = {field: getattr(invoice, field) for field in updates}
    for field, value in updates.items():
        setattr(invoice, field, value)

    await session.flush()
    await AuditService(session).record(
        "invoice_fields_edited", "invoice", actor_id=actor.id, entity_id=invoice.id,
        before=before, after=updates,
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    return invoice


@router.get("/{invoice_id}/match-result", response_model=MatchResultRead)
async def get_invoice_match_result(
    invoice_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MatchResult:
    await get_object_or_404(session, Invoice, invoice_id)
    result = await session.execute(
        select(MatchResult)
        .where(MatchResult.invoice_id == invoice_id)
        .order_by(MatchResult.run_at.desc())
        .limit(1)
    )
    match_result = result.scalar_one_or_none()
    if match_result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No match result for this invoice yet")
    return match_result


@router.get("/{invoice_id}/document")
async def get_invoice_document(
    invoice_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    invoice = await get_object_or_404(session, Invoice, invoice_id)
    document = await get_object_or_404(session, Document, invoice.document_id)

    content = read_file(document.storage_path)
    return Response(
        content=content,
        media_type=document.mime,
        headers={"Content-Disposition": f'inline; filename="{document.filename}"'},
    )
