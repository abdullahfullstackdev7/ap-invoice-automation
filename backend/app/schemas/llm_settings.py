from app.schemas.base import ORMModel


class ProviderUsage(ORMModel):
    provider: str
    configured: bool
    rpm: int
    tpm: int
    rpd: int
    calls_today: int
    tokens_in_today: int
    tokens_out_today: int
    rpd_used_pct: float


class LLMSettingsRead(ORMModel):
    primary: str
    secondary: str
    daily_budget_stop_pct: int
    providers: list[ProviderUsage]


class LLMTestCallResult(ORMModel):
    provider: str
    success: bool
    latency_ms: int | None
    detail: str
