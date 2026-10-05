import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import queries
from app.analytics.csv_export import rows_to_csv_response
from app.analytics.queries import AnalyticsFilters, Granularity
from app.api.deps import require_role
from app.core.etag import with_etag
from app.db.session import get_db_session
from app.models.enums import UserRole
from app.models.identity import User

router = APIRouter(prefix="/analytics", tags=["analytics"])

can_view = require_role(UserRole.admin, UserRole.finance_manager, UserRole.auditor)

DEFAULT_WINDOW_DAYS = 30
Format = Literal["json", "csv"]


def _filters(
    date_from: date | None, date_to: date | None, vendor_id: uuid.UUID | None, category: str | None
) -> AnalyticsFilters:
    resolved_to = date_to or date.today()
    resolved_from = date_from or (resolved_to - timedelta(days=DEFAULT_WINDOW_DAYS - 1))
    return AnalyticsFilters(resolved_from, resolved_to, vendor_id, category)


@router.get("/kpis")
async def get_kpis(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    payload = await queries.kpis(session, filters)
    return with_etag(request, response, payload)


@router.get("/volume-value-trend")
async def get_volume_value_trend(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    granularity: Granularity = "day",
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    rows = await queries.volume_value_trend(session, filters, granularity)
    if format == "csv":
        return rows_to_csv_response(rows, "volume_value_trend.csv")
    return with_etag(request, response, rows)


@router.get("/spend-by-vendor")
async def get_spend_by_vendor(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    category: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, None, category)
    rows, total = await queries.spend_by_vendor(session, filters, limit, offset)
    if format == "csv":
        return rows_to_csv_response(rows, "spend_by_vendor.csv")
    payload = {"items": rows, "total": total, "limit": limit, "offset": offset}
    return with_etag(request, response, payload)


@router.get("/spend-by-category")
async def get_spend_by_category(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, None)
    rows, total = await queries.spend_by_category(session, filters, limit, offset)
    if format == "csv":
        return rows_to_csv_response(rows, "spend_by_category.csv")
    payload = {"items": rows, "total": total, "limit": limit, "offset": offset}
    return with_etag(request, response, payload)


@router.get("/exceptions-trend")
async def get_exceptions_trend(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    granularity: Granularity = "day",
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    rows = await queries.exceptions_trend(session, filters, granularity)
    if format == "csv":
        return rows_to_csv_response(rows, "exceptions_trend.csv")
    return with_etag(request, response, rows)


@router.get("/exceptions-by-reason")
async def get_exceptions_by_reason(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    rows = await queries.exceptions_by_reason(session, filters)
    if format == "csv":
        return rows_to_csv_response(rows, "exceptions_by_reason.csv")
    return with_etag(request, response, rows)


@router.get("/stp-rate")
async def get_stp_rate(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    granularity: Granularity = "day",
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    rows = await queries.stp_rate(session, filters, granularity)
    if format == "csv":
        return rows_to_csv_response(rows, "stp_rate.csv")
    return with_etag(request, response, rows)


@router.get("/cycle-time")
async def get_cycle_time(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    payload = await queries.cycle_time(session, filters)
    return with_etag(request, response, payload)


@router.get("/aging")
async def get_aging(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    rows = await queries.aging(session, filters)
    if format == "csv":
        return rows_to_csv_response(rows, "aging.csv")
    return with_etag(request, response, rows)


@router.get("/cashflow-forecast")
async def get_cashflow_forecast(
    request: Request,
    response: Response,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    horizon_days: int = Query(90, ge=1, le=365),
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    today = date.today()
    filters = AnalyticsFilters(today, today, vendor_id, category)
    rows = await queries.cashflow_forecast(session, filters, horizon_days)
    if format == "csv":
        return rows_to_csv_response(rows, "cashflow_forecast.csv")
    return with_etag(request, response, rows)


@router.get("/savings")
async def get_savings(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    payload = await queries.savings(session, filters)
    return with_etag(request, response, payload)


@router.get("/vendor-scorecards")
async def get_vendor_scorecards(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, None, None)
    rows, total = await queries.vendor_scorecards(session, filters, limit, offset)
    if format == "csv":
        return rows_to_csv_response(rows, "vendor_scorecards.csv")
    payload = {"items": rows, "total": total, "limit": limit, "offset": offset}
    return with_etag(request, response, payload)


@router.get("/workflow-funnel")
async def get_workflow_funnel(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    rows = await queries.workflow_funnel(session, filters)
    if format == "csv":
        return rows_to_csv_response(rows, "workflow_funnel.csv")
    return with_etag(request, response, rows)


@router.get("/exception-heatmap")
async def get_exception_heatmap(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    format: Format = "json",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    rows = await queries.exception_heatmap(session, filters)
    if format == "csv":
        return rows_to_csv_response(rows, "exception_heatmap.csv")
    return with_etag(request, response, rows)


@router.get("/llm-usage")
async def get_llm_usage(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, None, None)
    payload = await queries.llm_usage(session, filters)
    return with_etag(request, response, payload)


@router.get("/extraction-accuracy")
async def get_extraction_accuracy(
    request: Request,
    response: Response,
    user: User = Depends(can_view),
) -> object:
    payload = queries.extraction_accuracy()
    return with_etag(request, response, payload)


@router.get("/savings-trend")
async def get_savings_trend(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    granularity: Granularity = "month",
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    rows = await queries.savings_trend(session, filters, granularity)
    return with_etag(request, response, rows)


@router.get("/exception-heatmap-time")
async def get_exception_heatmap_time(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    rows = await queries.exception_heatmap_time(session, filters)
    return with_etag(request, response, rows)


@router.get("/sla-compliance")
async def get_sla_compliance(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    vendor_id: uuid.UUID | None = None,
    category: str | None = None,
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, vendor_id, category)
    payload = await queries.sla_compliance(session, filters)
    return with_etag(request, response, payload)


@router.get("/llm-usage-daily")
async def get_llm_usage_daily(
    request: Request,
    response: Response,
    date_from: date | None = None,
    date_to: date | None = None,
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> object:
    filters = _filters(date_from, date_to, None, None)
    rows = await queries.llm_usage_daily(session, filters)
    return with_etag(request, response, rows)
