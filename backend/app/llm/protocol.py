from typing import Protocol

from app.llm.types import LLMResult


class LLMProvider(Protocol):
    name: str
    supports_vision: bool
    rpm: int
    tpm: int
    rpd: int

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int,
        image_b64: str | None = None,
    ) -> LLMResult:
        """Raises an app.llm.exceptions.LLMProviderError subclass on failure."""
        ...
