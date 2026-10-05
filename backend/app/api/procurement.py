import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_object_or_404
from app.db.session import get_db_session
from app.models.identity import User
from app.models.invoicing import Invoice
from app.models.procurement import GoodsReceipt, POLine, PurchaseOrder
from app.schemas.procurement import (
    GoodsReceiptRead,
)
from app.schemas.procurement_detail import (
    GoodsReceiptListResponse,
    PurchaseOrderDetailRead,
    PurchaseOrderListResponse,
)

router = APIRouter(tags=["procurement"])


@router.get("/purchase-orders", response_model=PurchaseOrderListResponse)
async def list_purchase_orders(
    vendor_id: uuid.UUID | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseOrderListResponse:
    query = select(PurchaseOrder).options(selectinload(PurchaseOrder.lines))
    count_query = select(func.count(PurchaseOrder.id))
    if vendor_id is not None:
        query = query.where(PurchaseOrder.vendor_id == vendor_id)
        count_query = count_query.where(PurchaseOrder.vendor_id == vendor_id)
    if search:
        pattern = f"%{search}%"
        query = query.where(PurchaseOrder.po_number.ilike(pattern))
        count_query = count_query.where(PurchaseOrder.po_number.ilike(pattern))

    total = (await session.execute(count_query)).scalar_one()
    result = await session.execute(
        query.order_by(PurchaseOrder.po_date.desc()).limit(limit).offset(offset)
    )
    return PurchaseOrderListResponse(items=list(result.scalars().all()), total=total)


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderDetailRead)
async def get_purchase_order(
    po_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PurchaseOrderDetailRead:
    po = await get_object_or_404(session, PurchaseOrder, po_id)

    lines_result = await session.execute(select(POLine).where(POLine.po_id == po_id))
    po_lines = list(lines_result.scalars().all())

    receipts_result = await session.execute(
        select(GoodsReceipt)
        .options(selectinload(GoodsReceipt.lines))
        .where(GoodsReceipt.po_id == po_id)
    )
    receipts = list(receipts_result.scalars().all())

    linked_invoices_result = await session.execute(
        select(Invoice.id, Invoice.invoice_no, Invoice.total, Invoice.status).where(
            Invoice.po_number_ref == po.po_number
        )
    )

    return PurchaseOrderDetailRead(
        id=po.id,
        po_number=po.po_number,
        vendor_id=po.vendor_id,
        currency=po.currency,
        status=po.status,
        po_date=po.po_date,
        total=po.total,
        lines=[
            {
                "id": line.id, "line_no": line.line_no, "item_id": line.item_id,
                "description": line.description, "qty": line.qty, "unit_price": line.unit_price,
                "amount": line.amount, "qty_invoiced_cum": line.qty_invoiced_cum,
            }
            for line in po_lines
        ],
        receipts=[GoodsReceiptRead.model_validate(r) for r in receipts],
        linked_invoices=[
            {"id": iid, "invoice_no": no, "total": total, "status": status}
            for iid, no, total, status in linked_invoices_result.all()
        ],
    )


@router.get("/goods-receipts", response_model=GoodsReceiptListResponse)
async def list_goods_receipts(
    po_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> GoodsReceiptListResponse:
    query = select(GoodsReceipt).options(selectinload(GoodsReceipt.lines))
    count_query = select(func.count(GoodsReceipt.id))
    if po_id is not None:
        query = query.where(GoodsReceipt.po_id == po_id)
        count_query = count_query.where(GoodsReceipt.po_id == po_id)

    total = (await session.execute(count_query)).scalar_one()
    result = await session.execute(
        query.order_by(GoodsReceipt.received_date.desc()).limit(limit).offset(offset)
    )
    return GoodsReceiptListResponse(items=list(result.scalars().all()), total=total)
