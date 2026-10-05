from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.settings import get_settings
from app.db.session import get_db_session
from app.extraction.llm_fallback import build_router_from_settings
from app.models.enums import UserRole
from app.models.identity import User
from app.models.llm_usage import LLMUsage
from app.schemas.llm_settings import LLMSettingsRead, LLMTestCallResult, ProviderUsage

router = APIRouter(prefix="/settings/llm", tags=["settings"])

can_view = require_role(UserRole.admin, UserRole.finance_manager)
can_manage = require_role(UserRole.admin)


class _PingSchema(BaseModel):
    ok: bool


@router.get("", response_model=LLMSettingsRead)
async def get_llm_settings(
    user: User = Depends(can_view),
    session: AsyncSession = Depends(get_db_session),
) -> LLMSettingsRead:
    settings = get_settings()
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    provider_configs = {
        "groq": {
            "configured": bool(settings.groq_api_key), "rpm": settings.groq_rpm,
            "tpm": settings.groq_tpm, "rpd": settings.groq_rpd,
        },
        "gemini": {
            "configured": bool(settings.gemini_api_key), "rpm": settings.gemini_rpm,
            "tpm": settings.gemini_tpm, "rpd": settings.gemini_rpd,
        },
    }

    providers = []
    for name, config in provider_configs.items():
        result = await session.execute(
            select(
                func.count(LLMUsage.id), func.coalesce(func.sum(LLMUsage.tokens_in), 0),
                func.coalesce(func.sum(LLMUsage.tokens_out), 0),
            ).where(LLMUsage.provider == name, LLMUsage.ts >= today_start)
        )
        calls_today, tokens_in_today, tokens_out_today = result.one()
        rpd = config["rpd"]
        providers.append(
            ProviderUsage(
                provider=name,
                configured=config["configured"],
                rpm=config["rpm"],
                tpm=config["tpm"],
                rpd=rpd,
                calls_today=calls_today,
                tokens_in_today=tokens_in_today,
                tokens_out_today=tokens_out_today,
                rpd_used_pct=round(calls_today / rpd * 100, 1) if rpd else 0.0,
            )
        )

    return LLMSettingsRead(
        primary=settings.llm_primary,
        secondary=settings.llm_secondary,
        daily_budget_stop_pct=settings.llm_daily_budget_stop_pct,
        providers=providers,
    )


@router.post("/test-call", response_model=LLMTestCallResult)
async def test_llm_call(
    actor: User = Depends(can_manage),
    session: AsyncSession = Depends(get_db_session),
) -> LLMTestCallResult:
    """A real call, not a mock: exercises the same Router.extract() path
    extraction uses, with a trivial schema. Honestly reports "no provider
    configured" rather than faking success when no API key is set.
    """
    settings = get_settings()
    router_instance = build_router_from_settings(session)
    if router_instance is None:
        return LLMTestCallResult(
            provider=settings.llm_primary, success=False, latency_ms=None,
            detail="No LLM API key is configured (GROQ_API_KEY / GEMINI_API_KEY both empty).",
        )

    start = datetime.now(UTC)
    result = await router_instance.extract(
        "Respond with JSON only.",
        'Reply with exactly: {"ok": true}',
        _PingSchema,
        max_tokens=20,
    )
    await session.commit()
    latency_ms = int((datetime.now(UTC) - start) / timedelta(milliseconds=1))

    if result is None or not result.ok:
        return LLMTestCallResult(
            provider=settings.llm_primary, success=False, latency_ms=latency_ms,
            detail="The provider did not return a valid response.",
        )
    return LLMTestCallResult(
        provider=settings.llm_primary, success=True, latency_ms=latency_ms, detail="ok",
    )
