from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.budget import BudgetTracker, RateWindow
from app.models.enums import LLMUsageStatus
from app.models.llm_usage import LLMUsage


def test_rate_window_allows_under_limit() -> None:
    window = RateWindow()
    for _ in range(5):
        window.record(tokens=100)
    assert window.request_count() == 5
    assert window.token_count() == 500


def test_budget_tracker_rpm_exhausted() -> None:
    tracker = BudgetTracker("groq", rpm=3, tpm=100000, rpd=1000, daily_stop_pct=90)
    for _ in range(3):
        assert tracker.has_rpm_tpm_budget(estimated_tokens=10) is True
        tracker.record_usage(10)
    assert tracker.has_rpm_tpm_budget(estimated_tokens=10) is False


def test_budget_tracker_tpm_exhausted() -> None:
    tracker = BudgetTracker("groq", rpm=100, tpm=50, rpd=1000, daily_stop_pct=90)
    assert tracker.has_rpm_tpm_budget(estimated_tokens=40) is True
    tracker.record_usage(40)
    assert tracker.has_rpm_tpm_budget(estimated_tokens=20) is False


async def test_daily_budget_stops_at_configured_percentage(db_session: AsyncSession) -> None:
    tracker = BudgetTracker("groq", rpm=100, tpm=100000, rpd=10, daily_stop_pct=90)

    assert await tracker.has_daily_budget(db_session) is True

    for _ in range(9):
        db_session.add(
            LLMUsage(
                ts=datetime.now(UTC),
                provider="groq",
                model="test-model",
                purpose="extraction",
                tokens_in=10,
                tokens_out=10,
                latency_ms=5,
                status=LLMUsageStatus.success,
            )
        )
    await db_session.commit()

    # 9 of 10 daily requests used, 90% stop threshold: no budget left.
    assert await tracker.has_daily_budget(db_session) is False


async def test_daily_budget_only_counts_this_provider(db_session: AsyncSession) -> None:
    tracker = BudgetTracker("groq", rpm=100, tpm=100000, rpd=5, daily_stop_pct=90)

    for _ in range(9):
        db_session.add(
            LLMUsage(
                ts=datetime.now(UTC),
                provider="gemini",
                model="other-model",
                purpose="extraction",
                tokens_in=10,
                tokens_out=10,
                latency_ms=5,
                status=LLMUsageStatus.success,
            )
        )
    await db_session.commit()

    assert await tracker.has_daily_budget(db_session) is True
