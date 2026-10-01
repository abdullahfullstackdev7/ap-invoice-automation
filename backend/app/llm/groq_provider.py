import time
from functools import lru_cache

import openai

from app.core.settings import get_settings
from app.llm.exceptions import LLMProviderError, LLMRateLimited, LLMServerError, LLMTimeout
from app.llm.types import LLMResult

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqProvider:
    name = "groq"
    supports_vision = False

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.groq_model
        self.rpm = settings.groq_rpm
        self.tpm = settings.groq_tpm
        self.rpd = settings.groq_rpd
        self._client = openai.AsyncOpenAI(
            api_key=settings.groq_api_key or "unset",
            base_url=GROQ_BASE_URL,
            max_retries=0,
            timeout=20.0,
        )

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int,
        image_b64: str | None = None,
    ) -> LLMResult:
        if image_b64 is not None:
            raise LLMProviderError("Groq provider is text-only")

        start = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0,
                # Confirmed against current Groq docs before enabling in
                # production, per Plan.md section 6, item 5.
                extra_body={"reasoning_effort": "low"},
            )
        except openai.RateLimitError as exc:
            raise LLMRateLimited() from exc
        except openai.APITimeoutError as exc:
            raise LLMTimeout() from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise LLMServerError(str(exc)) from exc
            raise LLMProviderError(str(exc)) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        text = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResult(
            text=text,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
            provider=self.name,
            model=self.model,
        )


@lru_cache
def get_groq_provider() -> GroqProvider:
    return GroqProvider()
