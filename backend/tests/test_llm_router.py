from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.exceptions import LLMRateLimited
from app.llm.router import Router
from app.llm.types import LLMResult


class EchoSchema(BaseModel):
    value: str


class FakeProvider:
    """Implements the LLMProvider protocol without any network access, so
    router logic (failover, circuit breaker, repair retry, budget gating)
    can be proven deterministically.
    """

    def __init__(
        self,
        name: str,
        *,
        responses: list[str | Exception] | None = None,
        supports_vision: bool = False,
        rpm: int = 30,
        tpm: int = 8000,
        rpd: int = 1000,
    ) -> None:
        self.name = name
        self.supports_vision = supports_vision
        self.rpm = rpm
        self.tpm = tpm
        self.rpd = rpd
        self._responses = list(responses or [])
        self.calls: list[str] = []

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int,
        image_b64: str | None = None,
    ) -> LLMResult:
        self.calls.append(user_prompt)
        next_response = self._responses.pop(0) if self._responses else '{"value": "default"}'
        if isinstance(next_response, Exception):
            raise next_response
        return LLMResult(
            text=next_response,
            tokens_in=10,
            tokens_out=10,
            latency_ms=5,
            provider=self.name,
            model="fake-model",
        )


async def test_primary_success_no_failover(db_session: AsyncSession) -> None:
    primary = FakeProvider("groq", responses=['{"value": "ok"}'])
    secondary = FakeProvider("gemini", responses=['{"value": "should not be called"}'])
    router = Router(db_session, {"groq": primary, "gemini": secondary}, "groq", "gemini")

    result = await router.extract("sys", "user", EchoSchema, max_tokens=100)

    assert result is not None
    assert result.value == "ok"
    assert len(primary.calls) == 1
    assert len(secondary.calls) == 0


async def test_forced_429_on_primary_fails_over_to_secondary(db_session: AsyncSession) -> None:
    primary = FakeProvider("groq", responses=[LLMRateLimited(), LLMRateLimited()])
    secondary = FakeProvider("gemini", responses=['{"value": "from secondary"}'])
    router = Router(db_session, {"groq": primary, "gemini": secondary}, "groq", "gemini")

    result = await router.extract("sys", "user", EchoSchema, max_tokens=100)

    assert result is not None
    assert result.value == "from secondary"
    assert len(secondary.calls) == 1


async def test_repeated_429_opens_circuit_breaker(db_session: AsyncSession) -> None:
    primary = FakeProvider(
        "groq", responses=[LLMRateLimited(), LLMRateLimited(), '{"value": "should not reach"}']
    )
    secondary = FakeProvider("gemini", responses=['{"value": "secondary"}', '{"value": "again"}'])
    router = Router(db_session, {"groq": primary, "gemini": secondary}, "groq", "gemini")

    await router.extract("sys", "user", EchoSchema, max_tokens=100)
    assert router._circuit_is_open("groq") is True

    # A second call should skip the open-circuit primary entirely.
    await router.extract("sys", "user", EchoSchema, max_tokens=100)
    assert len(primary.calls) == 2  # only the two calls that tripped the breaker


async def test_schema_failure_triggers_repair_retry_then_succeeds(
    db_session: AsyncSession,
) -> None:
    primary = FakeProvider(
        "groq", responses=["not valid json at all", '{"value": "repaired"}']
    )
    secondary = FakeProvider("gemini")
    router = Router(db_session, {"groq": primary, "gemini": secondary}, "groq", "gemini")

    result = await router.extract("sys", "user", EchoSchema, max_tokens=100)

    assert result is not None
    assert result.value == "repaired"
    assert len(primary.calls) == 2
    assert len(secondary.calls) == 0


async def test_schema_failure_on_repair_escalates_to_secondary(db_session: AsyncSession) -> None:
    primary = FakeProvider("groq", responses=["garbage", "still garbage"])
    secondary = FakeProvider("gemini", responses=['{"value": "from secondary"}'])
    router = Router(db_session, {"groq": primary, "gemini": secondary}, "groq", "gemini")

    result = await router.extract("sys", "user", EchoSchema, max_tokens=100)

    assert result is not None
    assert result.value == "from secondary"


async def test_all_providers_fail_returns_none(db_session: AsyncSession) -> None:
    primary = FakeProvider("groq", responses=[LLMRateLimited(), LLMRateLimited()])
    secondary = FakeProvider("gemini", responses=[LLMRateLimited(), LLMRateLimited()])
    router = Router(db_session, {"groq": primary, "gemini": secondary}, "groq", "gemini")

    result = await router.extract("sys", "user", EchoSchema, max_tokens=100)

    assert result is None


async def test_vision_task_only_routes_to_vision_capable_provider(
    db_session: AsyncSession,
) -> None:
    text_only = FakeProvider("groq", supports_vision=False)
    vision_capable = FakeProvider("gemini", supports_vision=True, responses=['{"value": "seen"}'])
    router = Router(
        db_session, {"groq": text_only, "gemini": vision_capable}, "groq", "gemini"
    )

    result = await router.extract(
        "sys", "user", EchoSchema, max_tokens=100, require_vision=True, image_b64="Zm9v"
    )

    assert result is not None
    assert result.value == "seen"
    assert len(text_only.calls) == 0
    assert len(vision_capable.calls) == 1


async def test_llm_usage_rows_written_for_success_and_failure(db_session: AsyncSession) -> None:
    from sqlalchemy import select

    from app.models.llm_usage import LLMUsage

    primary = FakeProvider("groq", responses=[LLMRateLimited()])
    secondary = FakeProvider("gemini", responses=['{"value": "ok"}'])
    router = Router(db_session, {"groq": primary, "gemini": secondary}, "groq", "gemini")

    await router.extract("sys", "user", EchoSchema, max_tokens=100)
    await db_session.commit()

    result = await db_session.execute(select(LLMUsage))
    rows = list(result.scalars().all())
    assert len(rows) == 2
    statuses = {row.status for row in rows}
    assert "error" in statuses
    assert "success" in statuses
