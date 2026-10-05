"""Analytics query functions behind /api/v1/analytics/*, Plan.md section 9.

KPI definitions are documented in docs/analytics.md. The kpis/
volume-value-trend/spend-by-* functions read analytics_daily (the fast
path the table exists for); everything else reads the raw tables
directly since their grain (reason code, cycle time, aging bucket, ...)
doesn't fit a per-day rollup.
"""

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as date_
from decimal import Decimal
from pathlib import Path
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.refresh import _prevented_value
from app.models.analytics import AnalyticsDaily
from app.models.enums import ExceptionStatus, InvoiceStatus, PaymentStatus
from app.models.exceptions import ExceptionRecord
from app.models.invoicing import Document, Invoice
from app.models.llm_usage import LLMUsage
from app.models.masterdata import Vendor
from app.models.payments import Payment

Granularity = Literal["day", "week", "month"]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"


@dataclass(frozen=True)
class AnalyticsFilters:
    date_from: date_
    date_to: date_
    vendor_id: uuid.UUID | None = None
    category: str | None = None


def _period_bucket(d: date_, granularity: Granularity) -> date_:
    if granularity == "day":
        return d
    if granularity == "week":
        return d - timedelta(days=d.weekday())
    return d.replace(day=1)


async def _daily_rows(session: AsyncSession, filters: AnalyticsFilters) -> list[AnalyticsDaily]:
    query = select(AnalyticsDaily).where(
        AnalyticsDaily.date >= filters.date_from, AnalyticsDaily.date <= filters.date_to
    )
    if filters.vendor_id is not None:
        query = query.where(AnalyticsDaily.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.where(AnalyticsDaily.category == filters.category)
    result = await session.execute(query)
    return list(result.scalars().all())


def _previous_period(filters: AnalyticsFilters) -> AnalyticsFilters:
    span = (filters.date_to - filters.date_from).days + 1
    prev_to = filters.date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span - 1)
    return AnalyticsFilters(prev_from, prev_to, filters.vendor_id, filters.category)


def _pct_change(current: Decimal | float, previous: Decimal | float) -> float | None:
    if not previous:
        return None
    return round((float(current) - float(previous)) / float(previous) * 100, 2)


async def _avg_cycle_time_hours(session: AsyncSession, filters: AnalyticsFilters) -> float | None:
    query = (
        select(Document.uploaded_at, Payment.released_at)
        .select_from(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .where(
            Payment.released_at.is_not(None),
            func.date(Document.uploaded_at) >= filters.date_from,
            func.date(Document.uploaded_at) <= filters.date_to,
        )
    )
    if filters.vendor_id is not None:
        query = query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
            Vendor.category == filters.category
        )
    result = await session.execute(query)
    durations_hours = [
        (released - uploaded).total_seconds() / 3600
        for uploaded, released in result.all()
        if released is not None
    ]
    if not durations_hours:
        return None
    return round(sum(durations_hours) / len(durations_hours), 2)


async def _exception_count(session: AsyncSession, filters: AnalyticsFilters) -> int:
    query = (
        select(func.count(ExceptionRecord.id))
        .select_from(ExceptionRecord)
        .join(Invoice, ExceptionRecord.invoice_id == Invoice.id)
        .where(
            func.date(ExceptionRecord.opened_at) >= filters.date_from,
            func.date(ExceptionRecord.opened_at) <= filters.date_to,
        )
    )
    if filters.vendor_id is not None:
        query = query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
            Vendor.category == filters.category
        )
    result = await session.execute(query)
    return result.scalar_one()


async def kpis(session: AsyncSession, filters: AnalyticsFilters) -> dict[str, object]:
    async def _summarize(f: AnalyticsFilters) -> dict[str, object]:
        rows = await _daily_rows(session, f)
        total_invoices = sum(r.invoices_count for r in rows)
        total_value = sum((r.value for r in rows), Decimal("0"))
        stp_count = sum(r.stp_count for r in rows)
        discounts_captured = sum((r.discounts_captured for r in rows), Decimal("0"))
        discounts_missed = sum((r.discounts_missed for r in rows), Decimal("0"))
        exception_count = await _exception_count(session, f)
        cycle_time = await _avg_cycle_time_hours(session, f)
        return {
            "total_invoices": total_invoices,
            "total_value": total_value,
            "stp_rate": round(stp_count / total_invoices * 100, 2) if total_invoices else None,
            "exception_rate": (
                round(exception_count / total_invoices * 100, 2) if total_invoices else None
            ),
            "avg_cycle_time_hours": cycle_time,
            "discounts_captured": discounts_captured,
            "discounts_missed": discounts_missed,
        }

    current = await _summarize(filters)
    previous = await _summarize(_previous_period(filters))

    comparison: dict[str, object] = {}
    for key in (
        "total_invoices",
        "total_value",
        "stp_rate",
        "exception_rate",
        "avg_cycle_time_hours",
        "discounts_captured",
        "discounts_missed",
    ):
        comparison[key] = {
            "current": current[key],
            "previous": previous[key],
            "pct_change": (
                _pct_change(current[key], previous[key])  # type: ignore[arg-type]
                if current[key] is not None and previous[key] is not None
                else None
            ),
        }
    return comparison


async def volume_value_trend(
    session: AsyncSession, filters: AnalyticsFilters, granularity: Granularity
) -> list[dict[str, object]]:
    rows = await _daily_rows(session, filters)
    buckets: dict[date_, dict[str, object]] = defaultdict(
        lambda: {"invoices_count": 0, "value": Decimal("0")}
    )
    for row in rows:
        key = _period_bucket(row.date, granularity)
        buckets[key]["invoices_count"] += row.invoices_count  # type: ignore[operator]
        buckets[key]["value"] += row.value  # type: ignore[operator]
    return [{"period": period, **data} for period, data in sorted(buckets.items())]


async def spend_by_vendor(
    session: AsyncSession, filters: AnalyticsFilters, limit: int, offset: int
) -> tuple[list[dict[str, object]], int]:
    rows = await _daily_rows(session, filters)
    totals: dict[uuid.UUID | None, dict[str, object]] = defaultdict(
        lambda: {"invoices_count": 0, "value": Decimal("0")}
    )
    for row in rows:
        totals[row.vendor_id]["invoices_count"] += row.invoices_count  # type: ignore[operator]
        totals[row.vendor_id]["value"] += row.value  # type: ignore[operator]

    vendor_ids = [vid for vid in totals if vid is not None]
    vendor_names: dict[uuid.UUID, str] = {}
    if vendor_ids:
        result = await session.execute(
            select(Vendor.id, Vendor.name).where(Vendor.id.in_(vendor_ids))
        )
        vendor_names = dict(result.all())

    ranked = sorted(totals.items(), key=lambda kv: kv[1]["value"], reverse=True)  # type: ignore[arg-type,return-value]
    page = ranked[offset : offset + limit]
    return (
        [
            {
                "vendor_id": vid,
                "vendor_name": vendor_names.get(vid, "Unknown") if vid else "Unassigned",
                **data,
            }
            for vid, data in page
        ],
        len(ranked),
    )


async def spend_by_category(
    session: AsyncSession, filters: AnalyticsFilters, limit: int, offset: int
) -> tuple[list[dict[str, object]], int]:
    rows = await _daily_rows(session, filters)
    totals: dict[str | None, dict[str, object]] = defaultdict(
        lambda: {"invoices_count": 0, "value": Decimal("0")}
    )
    for row in rows:
        totals[row.category]["invoices_count"] += row.invoices_count  # type: ignore[operator]
        totals[row.category]["value"] += row.value  # type: ignore[operator]

    ranked = sorted(totals.items(), key=lambda kv: kv[1]["value"], reverse=True)  # type: ignore[arg-type,return-value]
    page = ranked[offset : offset + limit]
    return (
        [{"category": cat or "Uncategorized", **data} for cat, data in page],
        len(ranked),
    )


async def exceptions_trend(
    session: AsyncSession, filters: AnalyticsFilters, granularity: Granularity
) -> list[dict[str, object]]:
    query = (
        select(ExceptionRecord.opened_at)
        .select_from(ExceptionRecord)
        .join(Invoice, ExceptionRecord.invoice_id == Invoice.id)
        .where(
            func.date(ExceptionRecord.opened_at) >= filters.date_from,
            func.date(ExceptionRecord.opened_at) <= filters.date_to,
        )
    )
    if filters.vendor_id is not None:
        query = query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
            Vendor.category == filters.category
        )
    result = await session.execute(query)
    buckets: dict[date_, int] = defaultdict(int)
    for (opened_at,) in result.all():
        buckets[_period_bucket(opened_at.date(), granularity)] += 1
    return [{"period": period, "count": count} for period, count in sorted(buckets.items())]


async def exceptions_by_reason(
    session: AsyncSession, filters: AnalyticsFilters
) -> list[dict[str, object]]:
    query = (
        select(ExceptionRecord.reason_code, func.count(ExceptionRecord.id))
        .select_from(ExceptionRecord)
        .join(Invoice, ExceptionRecord.invoice_id == Invoice.id)
        .where(
            func.date(ExceptionRecord.opened_at) >= filters.date_from,
            func.date(ExceptionRecord.opened_at) <= filters.date_to,
        )
        .group_by(ExceptionRecord.reason_code)
    )
    if filters.vendor_id is not None:
        query = query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
            Vendor.category == filters.category
        )
    result = await session.execute(query)
    rows = result.all()
    total = sum(count for _, count in rows) or 1
    return [
        {"reason_code": code, "count": count, "pct": round(count / total * 100, 2)}
        for code, count in sorted(rows, key=lambda r: r[1], reverse=True)
    ]


async def stp_rate(
    session: AsyncSession, filters: AnalyticsFilters, granularity: Granularity
) -> list[dict[str, object]]:
    rows = await _daily_rows(session, filters)
    buckets: dict[date_, dict[str, int]] = defaultdict(lambda: {"stp_count": 0, "total": 0})
    for row in rows:
        key = _period_bucket(row.date, granularity)
        buckets[key]["stp_count"] += row.stp_count
        buckets[key]["total"] += row.invoices_count
    return [
        {
            "period": period,
            "stp_count": data["stp_count"],
            "total": data["total"],
            "rate": round(data["stp_count"] / data["total"] * 100, 2) if data["total"] else None,
        }
        for period, data in sorted(buckets.items())
    ]


CYCLE_TIME_BUCKETS_HOURS = [24, 48, 72]


async def cycle_time(session: AsyncSession, filters: AnalyticsFilters) -> dict[str, object]:
    query = (
        select(Document.uploaded_at, Payment.released_at)
        .select_from(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .join(Document, Invoice.document_id == Document.id)
        .where(
            Payment.released_at.is_not(None),
            func.date(Document.uploaded_at) >= filters.date_from,
            func.date(Document.uploaded_at) <= filters.date_to,
        )
    )
    if filters.vendor_id is not None:
        query = query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
            Vendor.category == filters.category
        )
    result = await session.execute(query)
    rows = [(uploaded, released) for uploaded, released in result.all() if released is not None]
    hours = sorted((released - uploaded).total_seconds() / 3600 for uploaded, released in rows)

    bucket_labels = (
        [f"under_{CYCLE_TIME_BUCKETS_HOURS[0]}h"]
        + [
            f"{lo}_to_{hi}h"
            for lo, hi in zip(CYCLE_TIME_BUCKETS_HOURS, CYCLE_TIME_BUCKETS_HOURS[1:], strict=False)
        ]
        + [f"over_{CYCLE_TIME_BUCKETS_HOURS[-1]}h"]
    )
    distribution = dict.fromkeys(bucket_labels, 0)
    for h in hours:
        placed = False
        for i, threshold in enumerate(CYCLE_TIME_BUCKETS_HOURS):
            if h < threshold:
                distribution[bucket_labels[i]] += 1
                placed = True
                break
        if not placed:
            distribution[bucket_labels[-1]] += 1

    def _percentile(sorted_values: list[float], pct: float) -> float | None:
        if not sorted_values:
            return None
        idx = min(len(sorted_values) - 1, int(len(sorted_values) * pct))
        return round(sorted_values[idx], 2)

    trend_buckets: dict[date_, list[float]] = defaultdict(list)
    for uploaded, released in rows:
        trend_buckets[uploaded.date()].append((released - uploaded).total_seconds() / 3600)
    trend = [
        {"period": period, "avg_hours": round(sum(vals) / len(vals), 2)}
        for period, vals in sorted(trend_buckets.items())
    ]

    return {
        "distribution": distribution,
        "p50_hours": _percentile(hours, 0.50),
        "p95_hours": _percentile(hours, 0.95),
        "trend": trend,
        "sample_size": len(hours),
    }


AGING_BUCKETS = [30, 60, 90]


async def aging(session: AsyncSession, filters: AnalyticsFilters) -> list[dict[str, object]]:
    as_of = filters.date_to
    query = (
        select(Payment.amount, Invoice.due_date)
        .select_from(Payment)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .where(Payment.status.in_((PaymentStatus.scheduled, PaymentStatus.released)))
    )
    if filters.vendor_id is not None:
        query = query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
            Vendor.category == filters.category
        )
    result = await session.execute(query)

    bucket_labels = ["0_30", "31_60", "61_90", "90_plus"]
    buckets = {label: {"count": 0, "value": Decimal("0")} for label in bucket_labels}
    for amount, due_date in result.all():
        if due_date is None:
            continue
        days_outstanding = (as_of - due_date).days
        if days_outstanding <= 30:
            label = "0_30"
        elif days_outstanding <= 60:
            label = "31_60"
        elif days_outstanding <= 90:
            label = "61_90"
        else:
            label = "90_plus"
        buckets[label]["count"] += 1  # type: ignore[operator]
        buckets[label]["value"] += amount  # type: ignore[operator]

    return [{"bucket": label, **data} for label, data in buckets.items()]


async def cashflow_forecast(
    session: AsyncSession, filters: AnalyticsFilters, horizon_days: int = 90
) -> list[dict[str, object]]:
    today = filters.date_to
    horizon_end = today + timedelta(days=horizon_days)
    query = select(Payment.amount, Payment.scheduled_date).where(
        Payment.status.in_((PaymentStatus.scheduled, PaymentStatus.released)),
        Payment.scheduled_date >= today,
        Payment.scheduled_date <= horizon_end,
    )
    if filters.vendor_id is not None or filters.category is not None:
        query = query.select_from(Payment).join(Invoice, Payment.invoice_id == Invoice.id)
        if filters.vendor_id is not None:
            query = query.where(Invoice.vendor_id == filters.vendor_id)
        if filters.category is not None:
            query = query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
                Vendor.category == filters.category
            )
    result = await session.execute(query)

    buckets: dict[date_, Decimal] = defaultdict(lambda: Decimal("0"))
    for amount, scheduled_date in result.all():
        week_start = scheduled_date - timedelta(days=scheduled_date.weekday())
        buckets[week_start] += amount
    return [
        {"week_starting": period, "amount": amount} for period, amount in sorted(buckets.items())
    ]


async def savings(session: AsyncSession, filters: AnalyticsFilters) -> dict[str, object]:
    exc_query = (
        select(ExceptionRecord)
        .join(Invoice, ExceptionRecord.invoice_id == Invoice.id)
        .where(
            func.date(ExceptionRecord.opened_at) >= filters.date_from,
            func.date(ExceptionRecord.opened_at) <= filters.date_to,
        )
    )
    if filters.vendor_id is not None:
        exc_query = exc_query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        exc_query = exc_query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
            Vendor.category == filters.category
        )
    exceptions = list((await session.execute(exc_query)).scalars().all())

    duplicates = [e for e in exceptions if e.reason_code == "DUPLICATE_EXACT"]
    price_drift = [
        e
        for e in exceptions
        if e.reason_code == "PRICE_VARIANCE" and e.status == ExceptionStatus.resolved
    ]
    over_receipt = [
        e
        for e in exceptions
        if e.reason_code == "QTY_OVER_RECEIVED" and e.status == ExceptionStatus.resolved
    ]

    duplicate_invoice_ids = [e.invoice_id for e in duplicates]
    duplicates_value = Decimal("0")
    if duplicate_invoice_ids:
        inv_result = await session.execute(
            select(Invoice.total).where(Invoice.id.in_(duplicate_invoice_ids))
        )
        duplicates_value = sum((t or Decimal("0") for (t,) in inv_result.all()), Decimal("0"))

    price_drift_value = await _prevented_value(session, price_drift)
    over_receipt_value = await _prevented_value(session, over_receipt)

    rows = await _daily_rows(session, filters)
    discounts_captured = sum((r.discounts_captured for r in rows), Decimal("0"))
    discounts_missed = sum((r.discounts_missed for r in rows), Decimal("0"))

    return {
        "duplicates_blocked": {"count": len(duplicates), "value": duplicates_value},
        "price_drift_prevented": {"count": len(price_drift), "value": price_drift_value},
        "over_receipt_prevented": {"count": len(over_receipt), "value": over_receipt_value},
        "discounts_captured": {"value": discounts_captured},
        "discounts_missed": {"value": discounts_missed},
    }


async def vendor_scorecards(
    session: AsyncSession, filters: AnalyticsFilters, limit: int, offset: int
) -> tuple[list[dict[str, object]], int]:
    rows = await _daily_rows(session, filters)
    totals: dict[uuid.UUID | None, dict[str, object]] = defaultdict(
        lambda: {"invoices_count": 0, "value": Decimal("0"), "stp_count": 0}
    )
    for row in rows:
        totals[row.vendor_id]["invoices_count"] += row.invoices_count  # type: ignore[operator]
        totals[row.vendor_id]["value"] += row.value  # type: ignore[operator]
        totals[row.vendor_id]["stp_count"] += row.stp_count  # type: ignore[operator]

    vendor_ids = [vid for vid in totals if vid is not None]
    vendor_names: dict[uuid.UUID, str] = {}
    if vendor_ids:
        result = await session.execute(
            select(Vendor.id, Vendor.name).where(Vendor.id.in_(vendor_ids))
        )
        vendor_names = dict(result.all())

    scorecards = []
    for vid, data in totals.items():
        if vid is None:
            continue
        vendor_filters = AnalyticsFilters(filters.date_from, filters.date_to, vid, None)
        exception_count = await _exception_count(session, vendor_filters)
        invoices_count = data["invoices_count"]
        scorecards.append(
            {
                "vendor_id": vid,
                "vendor_name": vendor_names.get(vid, "Unknown"),
                "invoices_count": invoices_count,
                "value": data["value"],
                "exception_count": exception_count,
                "exception_rate": (
                    round(exception_count / invoices_count * 100, 2) if invoices_count else None  # type: ignore[operator]
                ),
                "stp_rate": (
                    round(data["stp_count"] / invoices_count * 100, 2) if invoices_count else None  # type: ignore[operator]
                ),
            }
        )

    ranked = sorted(scorecards, key=lambda s: s["value"], reverse=True)  # type: ignore[arg-type,return-value]
    return ranked[offset : offset + limit], len(ranked)


async def workflow_funnel(
    session: AsyncSession, filters: AnalyticsFilters
) -> list[dict[str, object]]:
    query = (
        select(Invoice.status, func.count(Invoice.id))
        .select_from(Invoice)
        .join(Document, Invoice.document_id == Document.id)
        .where(
            func.date(Document.uploaded_at) >= filters.date_from,
            func.date(Document.uploaded_at) <= filters.date_to,
        )
        .group_by(Invoice.status)
    )
    if filters.vendor_id is not None:
        query = query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
            Vendor.category == filters.category
        )
    result = await session.execute(query)
    counts = dict(result.all())
    return [{"status": status.value, "count": counts.get(status, 0)} for status in InvoiceStatus]


async def exception_heatmap(
    session: AsyncSession, filters: AnalyticsFilters
) -> list[dict[str, object]]:
    query = (
        select(ExceptionRecord.reason_code, Vendor.category, func.count(ExceptionRecord.id))
        .select_from(ExceptionRecord)
        .join(Invoice, ExceptionRecord.invoice_id == Invoice.id)
        .outerjoin(Vendor, Invoice.vendor_id == Vendor.id)
        .where(
            func.date(ExceptionRecord.opened_at) >= filters.date_from,
            func.date(ExceptionRecord.opened_at) <= filters.date_to,
        )
        .group_by(ExceptionRecord.reason_code, Vendor.category)
    )
    if filters.vendor_id is not None:
        query = query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.where(Vendor.category == filters.category)
    result = await session.execute(query)
    return [
        {"reason_code": code, "category": category or "Uncategorized", "count": count}
        for code, category, count in result.all()
    ]


async def llm_usage(session: AsyncSession, filters: AnalyticsFilters) -> dict[str, object]:
    usage_result = await session.execute(
        select(LLMUsage).where(
            func.date(LLMUsage.ts) >= filters.date_from, func.date(LLMUsage.ts) <= filters.date_to
        )
    )
    usage_rows = list(usage_result.scalars().all())

    by_provider: dict[str, dict[str, object]] = defaultdict(
        lambda: {"calls": 0, "tokens_in": 0, "tokens_out": 0, "avg_latency_ms": 0.0}
    )
    for row in usage_rows:
        bucket = by_provider[row.provider]
        bucket["calls"] = bucket["calls"] + 1  # type: ignore[operator]
        bucket["tokens_in"] = bucket["tokens_in"] + row.tokens_in  # type: ignore[operator]
        bucket["tokens_out"] = bucket["tokens_out"] + row.tokens_out  # type: ignore[operator]

    for provider, bucket in by_provider.items():
        latencies = [r.latency_ms for r in usage_rows if r.provider == provider]
        bucket["avg_latency_ms"] = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    extraction_result = await session.execute(
        select(func.count()).select_from(
            select(Invoice.id)
            .join(Document, Invoice.document_id == Document.id)
            .where(
                func.date(Document.uploaded_at) >= filters.date_from,
                func.date(Document.uploaded_at) <= filters.date_to,
            )
            .subquery()
        )
    )
    total_invoices = extraction_result.scalar_one()
    calls_avoided_by_rules = max(total_invoices - len(usage_rows), 0)

    return {
        "by_provider": dict(by_provider),
        "total_calls": len(usage_rows),
        "calls_avoided_by_rules": calls_avoided_by_rules,
        "rules_only_rate": (
            round(calls_avoided_by_rules / total_invoices * 100, 2) if total_invoices else None
        ),
    }


def extraction_accuracy() -> dict[str, object]:
    """Reads the latest scripts/evaluate_extraction.py and
    scripts/evaluate_matching.py output files. Plan.md section 9 says
    this should read "evaluation runs stored in DB", but no such table
    exists in section 5's schema; those scripts write to docs/ instead
    (see docs/evaluation.md), so this endpoint serves that file-based
    record rather than inventing an unplanned DB table.
    """
    result: dict[str, object] = {}
    for name, filename in (
        ("extraction", "evaluation_extraction.json"),
        ("matching", "evaluation_matching.json"),
    ):
        path = DOCS_DIR / filename
        if path.exists():
            result[name] = json.loads(path.read_text(encoding="utf-8"))
        else:
            result[name] = None
    result["note"] = (
        "File-based, not DB-backed: no evaluation-run table exists in this project's "
        "schema. Re-run scripts/evaluate_extraction.py and scripts/evaluate_matching.py "
        "to refresh these."
    )
    return result


async def savings_trend(
    session: AsyncSession, filters: AnalyticsFilters, granularity: Granularity
) -> list[dict[str, object]]:
    rows = await _daily_rows(session, filters)
    buckets: dict[date_, dict[str, Decimal]] = defaultdict(
        lambda: {
            "invoice_value": Decimal("0"),
            "savings_prevented": Decimal("0"),
            "discounts_captured": Decimal("0"),
            "discounts_missed": Decimal("0"),
        }
    )
    for row in rows:
        data = buckets[_period_bucket(row.date, granularity)]
        data["invoice_value"] += row.value
        data["savings_prevented"] += row.savings_prevented
        data["discounts_captured"] += row.discounts_captured
        data["discounts_missed"] += row.discounts_missed
    return [{"period": period, **data} for period, data in sorted(buckets.items())]


async def exception_heatmap_time(
    session: AsyncSession, filters: AnalyticsFilters
) -> list[dict[str, object]]:
    """Counts by weekday (0=Mon) and hour of day, UTC. Derived in Python
    from opened_at rather than a DB-specific extract() so it stays portable."""
    query = (
        select(ExceptionRecord.opened_at)
        .select_from(ExceptionRecord)
        .join(Invoice, ExceptionRecord.invoice_id == Invoice.id)
        .where(
            func.date(ExceptionRecord.opened_at) >= filters.date_from,
            func.date(ExceptionRecord.opened_at) <= filters.date_to,
        )
    )
    if filters.vendor_id is not None:
        query = query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
            Vendor.category == filters.category
        )
    result = await session.execute(query)
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for (opened_at,) in result.all():
        counts[(opened_at.weekday(), opened_at.hour)] += 1
    return [
        {"weekday": weekday, "hour": hour, "count": count}
        for (weekday, hour), count in sorted(counts.items())
    ]


async def sla_compliance(session: AsyncSession, filters: AnalyticsFilters) -> dict[str, object]:
    query = (
        select(ExceptionRecord.status, ExceptionRecord.sla_due_at, ExceptionRecord.resolved_at)
        .select_from(ExceptionRecord)
        .join(Invoice, ExceptionRecord.invoice_id == Invoice.id)
        .where(
            func.date(ExceptionRecord.opened_at) >= filters.date_from,
            func.date(ExceptionRecord.opened_at) <= filters.date_to,
        )
    )
    if filters.vendor_id is not None:
        query = query.where(Invoice.vendor_id == filters.vendor_id)
    if filters.category is not None:
        query = query.join(Vendor, Invoice.vendor_id == Vendor.id).where(
            Vendor.category == filters.category
        )
    rows = (await session.execute(query)).all()
    now = datetime.now(UTC)

    resolved = [
        (due, resolved_at)
        for status, due, resolved_at in rows
        if status == ExceptionStatus.resolved and due and resolved_at
    ]
    met = sum(1 for due, resolved_at in resolved if resolved_at <= due)
    overdue_open = sum(
        1
        for status, due, _ in rows
        if status != ExceptionStatus.resolved and due is not None and due < now
    )
    return {
        "resolved_count": len(resolved),
        "sla_met_count": met,
        "sla_compliance_pct": round(met / len(resolved) * 100, 2) if resolved else None,
        "overdue_open_count": overdue_open,
    }


async def llm_usage_daily(
    session: AsyncSession, filters: AnalyticsFilters
) -> list[dict[str, object]]:
    result = await session.execute(
        select(LLMUsage.ts, LLMUsage.provider, LLMUsage.tokens_in, LLMUsage.tokens_out).where(
            func.date(LLMUsage.ts) >= filters.date_from,
            func.date(LLMUsage.ts) <= filters.date_to,
        )
    )
    buckets: dict[tuple[date_, str], dict[str, int]] = defaultdict(
        lambda: {"calls": 0, "tokens_in": 0, "tokens_out": 0}
    )
    for ts, provider, tokens_in, tokens_out in result.all():
        data = buckets[(ts.date(), provider)]
        data["calls"] += 1
        data["tokens_in"] += tokens_in
        data["tokens_out"] += tokens_out
    return [
        {"day": day, "provider": provider, **data}
        for (day, provider), data in sorted(buckets.items())
    ]
