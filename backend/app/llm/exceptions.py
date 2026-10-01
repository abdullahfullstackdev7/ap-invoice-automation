class LLMProviderError(Exception):
    """Base class for provider-level failures the router can react to."""


class LLMRateLimited(LLMProviderError):
    def __init__(self, retry_after_seconds: int | None = None) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("rate limited")


class LLMServerError(LLMProviderError):
    pass


class LLMTimeout(LLMProviderError):
    pass


class LLMBudgetExhausted(LLMProviderError):
    pass


class LLMSchemaValidationFailed(LLMProviderError):
    def __init__(self, errors: str) -> None:
        self.errors = errors
        super().__init__(f"schema validation failed: {errors}")


class LLMAllProvidersFailed(LLMProviderError):
    pass
