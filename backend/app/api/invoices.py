import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_object_or_404, require_role
from app.core.csrf import require_csrf
from app.db.session import get_db_session
from app.models.enums import InvoiceStatus, UserRole
from app.models.identity import User
from app.models.invoicing import Document, Invoice
from app.schemas.invoicing import InvoiceRead, UploadResultItem
from app.services.storage import read_file, storage_path_for, write_file
from app.services.upload_validation import (
    UploadValidationError,
    compute_sha256,
    validate_upload,
)
from app.workers.tasks import process_invoice

router = APIRouter(prefix="/invoices", tags=["invoices"])

can_upload = require_role(UserRole.admin, UserRole.ap_clerk)


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


@router.get("/{invoice_id}", response_model=InvoiceRead)
async def get_invoice(
    invoice_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Invoice:
    return await get_object_or_404(session, Invoice, invoice_id)


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
