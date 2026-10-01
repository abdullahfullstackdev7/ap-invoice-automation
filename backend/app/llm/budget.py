import time
from collections import deque
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_usage import LLMUsage


class RateWindow:
    """In-process sliding-window counter for RPM/TPM. Per-process only:
    good enough for a single worker process per Plan.md's free-tier scale
    (Groq: 30 RPM, Gemini: 10 RPM), and RPD is the real cross-restart
    guard, backed by the llm_usage table below.
    """

    def __init__(self, window_seconds: float = 60.0) -> None:
        self.window_seconds = window_seconds
        self._requests: deque[float] = deque()
        self._tokens: deque[tuple[float, int]] = deque()

    def _evict(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._requests and self._requests[0] < cutoff:
            self._requests.popleft()
        while self._tokens and self._tokens[0][0] < cutoff:
            self._tokens.popleft()

    def request_count(self) -> int:
        self._evict(time.monotonic())
        return len(self._requests)

    def token_count(self) -> int:
        self._evict(time.monotonic())
        return sum(t for _, t in self._tokens)

    def record(self, tokens: int) -> None:
        now = time.monotonic()
        self._requests.append(now)
        self._tokens.append((now, tokens))


class BudgetTracker:
    def __init__(
        self,
        provider_name: str,
        rpm: int,
        tpm: int,
        rpd: int,
        daily_stop_pct: int,
    ) -> None:
        self.provider_name = provider_name
        self.rpm = rpm
        self.tpm = tpm
        self.rpd = rpd
        self.daily_stop_pct = daily_stop_pct
        self._window = RateWindow()

    def has_rpm_tpm_budget(self, estimated_tokens: int) -> bool:
        return (
            self._window.request_count() < self.rpm
            and self._window.token_count() + estimated_tokens < self.tpm
        )

    def record_usage(self, tokens: int) -> None:
        self._window.record(tokens)

    async def has_daily_budget(self, session: AsyncSession) -> bool:
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            select(func.count(LLMUsage.id)).where(
                LLMUsage.provider == self.provider_name,
                LLMUsage.ts >= today_start,
                LLMUsage.ts < today_start + timedelta(days=1),
            )
        )
        count_today = result.scalar_one()
        threshold = self.rpd * self.daily_stop_pct / 100
        return count_today < threshold
