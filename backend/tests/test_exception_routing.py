from datetime import UTC, datetime, timedelta

from app.models.enums import ExceptionSeverity, UserRole
from app.services.exception_routing import default_assignee_role, sla_due_at


def test_high_severity_sla_is_four_hours() -> None:
    now = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)  # a Monday
    assert sla_due_at(ExceptionSeverity.high, now=now) == now + timedelta(hours=4)


def test_low_severity_sla_is_three_calendar_days() -> None:
    now = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    assert sla_due_at(ExceptionSeverity.low, now=now) == now + timedelta(days=3)


def test_medium_severity_sla_skips_weekend() -> None:
    friday = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
    due = sla_due_at(ExceptionSeverity.medium, now=friday)
    assert due == friday + timedelta(days=3)  # next business day is Monday
    assert due.weekday() == 0


def test_medium_severity_sla_next_business_day_midweek() -> None:
    tuesday = datetime(2026, 9, 22, 10, 0, tzinfo=UTC)
    due = sla_due_at(ExceptionSeverity.medium, now=tuesday)
    assert due == tuesday + timedelta(days=1)


def test_header_reason_codes_default_to_approver() -> None:
    assert default_assignee_role("PO_CLOSED") == UserRole.approver
    assert default_assignee_role("PO_NOT_FOUND") == UserRole.approver
    assert default_assignee_role("VENDOR_MISMATCH") == UserRole.approver
    assert default_assignee_role("DUPLICATE_SUSPECTED") == UserRole.approver
    assert default_assignee_role("DUPLICATE_EXACT") == UserRole.approver


def test_line_variance_reason_codes_default_to_ap_clerk() -> None:
    assert default_assignee_role("PRICE_VARIANCE") == UserRole.ap_clerk
    assert default_assignee_role("QTY_NOT_RECEIVED") == UserRole.ap_clerk
    assert default_assignee_role("TOTAL_MISMATCH") == UserRole.ap_clerk
    assert default_assignee_role("DUE_DATE_MISMATCH") == UserRole.ap_clerk
