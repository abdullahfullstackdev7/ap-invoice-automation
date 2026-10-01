import base64
import time
from functools import lru_cache

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.core.settings import get_settings
from app.llm.exceptions import LLMRateLimited, LLMServerError
from app.llm.types import LLMResult

RATE_LIMIT_STATUS = 429


class GeminiProvider:
    name = "gemini"
    supports_vision = True

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.gemini_model
        self.rpm = settings.gemini_rpm
        self.tpm = settings.gemini_tpm
        self.rpd = settings.gemini_rpd
        self._client = genai.Client(api_key=settings.gemini_api_key or "unset")

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int,
        image_b64: str | None = None,
    ) -> LLMResult:
        contents: list[str | genai_types.Part] = [user_prompt]
        if image_b64 is not None:
            contents.insert(
                0,
                genai_types.Part.from_bytes(
                    data=base64.b64decode(image_b64), mime_type="image/jpeg"
                ),
            )

        start = time.perf_counter()
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=contents,  # type: ignore[arg-type]
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                    temperature=0,
                ),
            )
        except genai_errors.ClientError as exc:
            if exc.code == RATE_LIMIT_STATUS:
                raise LLMRateLimited() from exc
            raise
        except genai_errors.ServerError as exc:
            raise LLMServerError(str(exc)) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        text = response.text or ""
        usage = response.usage_metadata
        return LLMResult(
            text=text,
            tokens_in=usage.prompt_token_count if usage and usage.prompt_token_count else 0,
            tokens_out=(
                usage.candidates_token_count if usage and usage.candidates_token_count else 0
            ),
            latency_ms=latency_ms,
            provider=self.name,
            model=self.model,
        )


@lru_cache
def get_gemini_provider() -> GeminiProvider:
    return GeminiProvider()
