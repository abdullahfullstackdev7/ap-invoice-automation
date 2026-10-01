from dataclasses import dataclass, field

from app.matching.context import BLOCKING_REASON_CODES, ExceptionDraft, MatchContext
from app.matching.rules.header import check_header
from app.matching.rules.price import check_price
from app.matching.rules.quantity import check_quantity
from app.matching.rules.terms import check_terms
from app.matching.rules.totals_tax import check_totals_and_tax
from app.models.enums import MatchOutcome

# Order matches Plan.md section 7's numbered list (duplicate check, item 1,
# runs separately before this list since it needs async DB access; see
# app/matching/duplicate.py and app/matching/service.py).
RULES = [check_header, check_quantity, check_price, check_totals_and_tax, check_terms]


@dataclass
class MatchDecision:
    outcome: MatchOutcome
    exceptions: list[ExceptionDraft] = field(default_factory=list)


def evaluate_rules(ctx: MatchContext) -> list[ExceptionDraft]:
    """Runs every rule in Plan.md's stated order and collects every
    exception they raise; a rule never short-circuits another (e.g. a
    quantity exception doesn't suppress a price exception), matching
    "each producing zero or more exceptions" (Plan.md section 7).
    """
    drafts: list[ExceptionDraft] = []
    for rule in RULES:
        drafts.extend(rule(ctx))
    return drafts


def determine_outcome(
    exceptions: list[ExceptionDraft],
    *,
    is_exact_duplicate: bool,
) -> MatchOutcome:
    """Plan.md section 7, item 7:
    - BLOCKED: exact duplicate, or PO closed / not found / vendor mismatch
      (nothing valid left to reconcile against).
    - AUTO_APPROVED: no exceptions (the amount-vs-auto-approve-limit
      threshold is a Phase 8 approval-routing decision, not a match
      outcome; a clean match over the limit is still "AUTO_APPROVED" here
      and gets routed to an approver instead of paid automatically).
    - EXCEPTION: one or more non-blocking exceptions.
    """
    if is_exact_duplicate:
        return MatchOutcome.blocked

    if any(draft.reason_code in BLOCKING_REASON_CODES for draft in exceptions):
        return MatchOutcome.blocked

    if exceptions:
        return MatchOutcome.exception

    return MatchOutcome.auto_approved


def run_match(
    ctx: MatchContext, *, is_exact_duplicate: bool, duplicate_draft: ExceptionDraft | None
) -> MatchDecision:
    exceptions = list(evaluate_rules(ctx))
    if duplicate_draft is not None:
        exceptions.insert(0, duplicate_draft)

    outcome = determine_outcome(exceptions, is_exact_duplicate=is_exact_duplicate)
    return MatchDecision(outcome=outcome, exceptions=exceptions)
