import re
import time
import uuid
from datetime import UTC, datetime
from typing import TypeVar

import structlog
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.budget import BudgetTracker
from app.llm.exceptions import LLMAllProvidersFailed, LLMProviderError
from app.llm.prompts import build_repair_prompt
from app.llm.protocol import LLMProvider
from app.llm.token_estimate import estimate_tokens
from app.llm.types import LLMResult
from app.models.enums import LLMUsageStatus
from app.models.llm_usage import LLMUsage

logger = structlog.get_logger(__name__)

CIRCUIT_BREAKER_SECONDS = 60
MAX_FAILURES_BEFORE_SWITCH = 2

SchemaT = TypeVar("SchemaT", bound=BaseModel)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json_text(raw: str) -> str:
    match = _JSON_FENCE_RE.search(raw)
    return match.group(1) if match else raw.strip()


class Router:
    """Text-task failover: primary -> secondary, budget-gated, with a
    60-second circuit breaker after repeated failures and one schema-repair
    retry before giving up on a provider. Vision tasks always go to
    whichever configured provider supports vision (Gemini), never text-only
    Groq. See Plan.md section 6.1.
    """

    def __init__(
        self,
        session: AsyncSession,
        providers: dict[str, LLMProvider],
        primary: str,
        secondary: str,
        purpose: str = "extraction",
    ) -> None:
        self.session = session
        self.providers = providers
        self.primary = primary
        self.secondary = secondary
        self.purpose = purpose
        self._budgets = {
            name: BudgetTracker(name, p.rpm, p.tpm, p.rpd, daily_stop_pct=90)
            for name, p in providers.items()
        }
        self._circuit_open_until: dict[str, float] = {}
        self._consecutive_failures: dict[str, int] = {}

    def _order_for_task(self, require_vision: bool) -> list[str]:
        if require_vision:
            return [name for name, p in self.providers.items() if p.supports_vision]
        return [self.primary, self.secondary]

    def _circuit_is_open(self, provider_name: str) -> bool:
        until = self._circuit_open_until.get(provider_name)
        return until is not None and time.monotonic() < until

    def _open_circuit(self, provider_name: str, seconds: float = CIRCUIT_BREAKER_SECONDS) -> None:
        self._circuit_open_until[provider_name] = time.monotonic() + seconds
        self._consecutive_failures[provider_name] = 0
        logger.warning("llm_circuit_opened", provider=provider_name, seconds=seconds)

    async def _log_usage(
        self,
        provider_name: str,
        model: str,
        result: LLMResult | None,
        status: LLMUsageStatus,
        invoice_id: uuid.UUID | None,
    ) -> None:
        self.session.add(
            LLMUsage(
                ts=datetime.now(UTC),
                provider=provider_name,
                model=model,
                purpose=self.purpose,
                tokens_in=result.tokens_in if result else 0,
                tokens_out=result.tokens_out if result else 0,
                latency_ms=result.latency_ms if result else 0,
                status=status,
                invoice_id=invoice_id,
            )
        )
        await self.session.flush()

    async def _call_once(
        self,
        provider_name: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        image_b64: str | None,
        invoice_id: uuid.UUID | None,
    ) -> LLMResult | None:
        if self._circuit_is_open(provider_name):
            return None

        budget = self._budgets[provider_name]
        estimated = estimate_tokens(system_prompt + user_prompt)
        if not budget.has_rpm_tpm_budget(estimated):
            logger.info("llm_rpm_tpm_budget_exhausted", provider=provider_name)
            return None
        if not await budget.has_daily_budget(self.session):
            logger.info("llm_daily_budget_exhausted", provider=provider_name)
            return None

        provider = self.providers[provider_name]
        try:
            result = await provider.complete(
                system_prompt, user_prompt, max_tokens=max_tokens, image_b64=image_b64
            )
        except LLMProviderError as exc:
            self._consecutive_failures[provider_name] = (
                self._consecutive_failures.get(provider_name, 0) + 1
            )
            await self._log_usage(
                provider_name, provider.name, None, LLMUsageStatus.error, invoice_id
            )
            if self._consecutive_failures[provider_name] >= MAX_FAILURES_BEFORE_SWITCH:
                retry_after = getattr(exc, "retry_after_seconds", None) or CIRCUIT_BREAKER_SECONDS
                self._open_circuit(provider_name, retry_after)
            return None

        budget.record_usage(result.tokens_in + result.tokens_out)
        self._consecutive_failures[provider_name] = 0
        await self._log_usage(
            provider_name, provider.name, result, LLMUsageStatus.success, invoice_id
        )
        return result

    async def extract(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_cls: type[SchemaT],
        *,
        max_tokens: int,
        require_vision: bool = False,
        image_b64: str | None = None,
        invoice_id: uuid.UUID | None = None,
    ) -> SchemaT | None:
        """Returns a validated schema instance, or None if every provider
        failed or budget-exhausted (caller should mark needs_review).
        """
        for provider_name in self._order_for_task(require_vision):
            # A network-level failure (429/5xx/timeout) gets one same-
            # provider retry before moving on, per Plan.md section 6.1:
            # "twice -> switch provider ... open a circuit breaker."
            result = await self._call_once(
                provider_name, system_prompt, user_prompt, max_tokens, image_b64, invoice_id
            )
            if result is None:
                result = await self._call_once(
                    provider_name, system_prompt, user_prompt, max_tokens, image_b64, invoice_id
                )
            if result is None:
                continue

            parsed = self._try_parse(result.text, schema_cls)
            if parsed is not None:
                return parsed

            # One repair retry: send only the validation error and the
            # previous output, per Plan.md section 6.1.
            repair_prompt = build_repair_prompt(
                result.text, "output did not match the required JSON shape"
            )
            repair_result = await self._call_once(
                provider_name, system_prompt, repair_prompt, max_tokens, image_b64, invoice_id
            )
            if repair_result is not None:
                parsed = self._try_parse(repair_result.text, schema_cls)
                if parsed is not None:
                    return parsed
            # Escalate to the next provider in the order.

        return None

    @staticmethod
    def _try_parse(raw_text: str, schema_cls: type[SchemaT]) -> SchemaT | None:
        try:
            return schema_cls.model_validate_json(_extract_json_text(raw_text))
        except ValidationError:
            return None


def build_router(session: AsyncSession, providers: dict[str, LLMProvider]) -> Router:
    from app.core.settings import get_settings

    settings = get_settings()
    if settings.llm_primary not in providers or settings.llm_secondary not in providers:
        raise LLMAllProvidersFailed(
            f"Configured primary/secondary ({settings.llm_primary}/"
            f"{settings.llm_secondary}) not in available providers {list(providers)}"
        )
    return Router(session, providers, settings.llm_primary, settings.llm_secondary)
