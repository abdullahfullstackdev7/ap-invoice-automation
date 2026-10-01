from app.matching.context import ExceptionDraft
from app.matching.engine import determine_outcome
from app.models.enums import ExceptionSeverity, MatchOutcome


def _draft(
    reason_code: str, severity: ExceptionSeverity = ExceptionSeverity.medium
) -> ExceptionDraft:
    return ExceptionDraft(reason_code=reason_code, severity=severity, details={})


def test_no_exceptions_is_auto_approved() -> None:
    outcome = determine_outcome([], is_exact_duplicate=False)
    assert outcome == MatchOutcome.auto_approved


def test_exact_duplicate_is_blocked_even_without_other_exceptions() -> None:
    outcome = determine_outcome([], is_exact_duplicate=True)
    assert outcome == MatchOutcome.blocked


def test_non_blocking_exception_is_exception_outcome() -> None:
    outcome = determine_outcome([_draft("PRICE_VARIANCE")], is_exact_duplicate=False)
    assert outcome == MatchOutcome.exception


def test_po_closed_is_blocked() -> None:
    outcome = determine_outcome([_draft("PO_CLOSED")], is_exact_duplicate=False)
    assert outcome == MatchOutcome.blocked


def test_vendor_mismatch_is_blocked() -> None:
    outcome = determine_outcome([_draft("VENDOR_MISMATCH")], is_exact_duplicate=False)
    assert outcome == MatchOutcome.blocked


def test_po_not_found_is_blocked() -> None:
    outcome = determine_outcome([_draft("PO_NOT_FOUND")], is_exact_duplicate=False)
    assert outcome == MatchOutcome.blocked


def test_blocking_exception_mixed_with_non_blocking_is_still_blocked() -> None:
    outcome = determine_outcome(
        [_draft("PRICE_VARIANCE"), _draft("PO_CLOSED")], is_exact_duplicate=False
    )
    assert outcome == MatchOutcome.blocked


def test_multiple_non_blocking_exceptions_is_exception_outcome() -> None:
    outcome = determine_outcome(
        [_draft("PRICE_VARIANCE"), _draft("QTY_OVER_RECEIVED"), _draft("DUE_DATE_MISMATCH")],
        is_exact_duplicate=False,
    )
    assert outcome == MatchOutcome.exception
