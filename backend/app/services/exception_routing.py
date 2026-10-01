"""SLA timers and default assignment rules for a newly created exception,
Plan.md section 8: "assignment rules by reason code; SLA timers by
severity (high 4h, medium 1 business day, low 3 days)."
"""

from datetime import UTC, datetime, timedelta

from app.models.enums import ExceptionSeverity, UserRole

SLA_HOURS_HIGH = 4
SLA_BUSINESS_DAYS_MEDIUM = 1
SLA_CALENDAR_DAYS_LOW = 3

# PO_CLOSED/VENDOR_MISMATCH/PO_NOT_FOUND/DUPLICATE_* are header-level
# problems that need approval authority to resolve (reopen a PO, confirm a
# vendor override, clear a duplicate); everything else is a line-level
# variance an AP clerk can triage first.
_APPROVER_REASON_PREFIXES = ("PO_", "VENDOR_", "DUPLICATE_")


def default_assignee_role(reason_code: str) -> UserRole:
    if reason_code.startswith(_APPROVER_REASON_PREFIXES):
        return UserRole.approver
    return UserRole.ap_clerk


def _next_business_day(start: datetime, business_days: int) -> datetime:
    current = start
    remaining = business_days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Monday=0 .. Friday=4
            remaining -= 1
    return current


def sla_due_at(severity: ExceptionSeverity, *, now: datetime | None = None) -> datetime:
    start = now or datetime.now(UTC)
    if severity == ExceptionSeverity.high:
        return start + timedelta(hours=SLA_HOURS_HIGH)
    if severity == ExceptionSeverity.medium:
        return _next_business_day(start, SLA_BUSINESS_DAYS_MEDIUM)
    return start + timedelta(days=SLA_CALENDAR_DAYS_LOW)
