import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_object_or_404
from app.db.session import get_db_session
from app.models.exceptions import ExceptionRecord
from app.models.identity import User
from app.models.invoicing import Invoice, InvoiceLine
from app.models.masterdata import Vendor
from app.schemas.vendor_detail import (
    VendorDetailRead,
    VendorListResponse,
    VendorPriceHistoryPoint,
    VendorSummaryInvoice,
)

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("", response_model=VendorListResponse)
async def list_vendors(
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> VendorListResponse:
    query = select(Vendor)
    count_query = select(func.count(Vendor.id))
    if search:
        pattern = f"%{search}%"
        query = query.where(Vendor.name.ilike(pattern))
        count_query = count_query.where(Vendor.name.ilike(pattern))

    total = (await session.execute(count_query)).scalar_one()
    result = await session.execute(query.order_by(Vendor.name).limit(limit).offset(offset))
    return VendorListResponse(items=list(result.scalars().all()), total=total)


@router.get("/{vendor_id}", response_model=VendorDetailRead)
async def get_vendor(
    vendor_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> VendorDetailRead:
    vendor = await get_object_or_404(session, Vendor, vendor_id)

    invoices_result = await session.execute(
        select(Invoice).where(Invoice.vendor_id == vendor_id).order_by(Invoice.invoice_date.desc())
    )
    invoices = list(invoices_result.scalars().all())
    invoice_ids = [inv.id for inv in invoices]

    exception_count = 0
    if invoice_ids:
        exception_count = (
            await session.execute(
                select(func.count(ExceptionRecord.id)).where(
                    ExceptionRecord.invoice_id.in_(invoice_ids)
                )
            )
        ).scalar_one()

    total_spend = sum((inv.total or Decimal("0") for inv in invoices), Decimal("0"))
    invoices_count = len(invoices)

    six_months_ago = date.today() - timedelta(days=180)
    history_result = await session.execute(
        select(Invoice.invoice_date, InvoiceLine.description, InvoiceLine.unit_price)
        .join(InvoiceLine, InvoiceLine.invoice_id == Invoice.id)
        .where(Invoice.vendor_id == vendor_id, Invoice.invoice_date >= six_months_ago)
        .order_by(Invoice.invoice_date)
    )
    price_history = [
        VendorPriceHistoryPoint(date=d, description=desc, unit_price=price)
        for d, desc, price in history_result.all()
        if d is not None
    ]

    return VendorDetailRead(
        id=vendor.id,
        code=vendor.code,
        name=vendor.name,
        name_normalized=vendor.name_normalized,
        tax_id=vendor.tax_id,
        address=vendor.address,
        email=vendor.email,
        payment_terms_days=vendor.payment_terms_days,
        discount_pct=vendor.discount_pct,
        discount_days=vendor.discount_days,
        risk_tier=vendor.risk_tier,
        category=vendor.category,
        status=vendor.status,
        invoices_count=invoices_count,
        total_spend=total_spend,
        exception_count=exception_count,
        exception_rate=(
            round(exception_count / invoices_count * 100, 2) if invoices_count else None
        ),
        recent_invoices=[
            VendorSummaryInvoice(
                id=inv.id, invoice_no=inv.invoice_no, invoice_date=inv.invoice_date,
                total=inv.total, status=inv.status,
            )
            for inv in invoices[:10]
        ],
        price_history=price_history,
    )
