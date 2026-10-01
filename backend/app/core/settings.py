from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://app_rw:change_me@localhost:5432/apdb"
    database_admin_url: str = "postgresql+psycopg://apdb_admin:change_me_admin@localhost:5432/apdb"
    database_ro_url: str = "postgresql+psycopg://app_ro:change_me_ro@localhost:5432/apdb"

    jwt_secret: str = "change_me_to_a_random_at_least_32_character_secret"

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_min_length(cls, value: str) -> str:
        if len(value) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters "
                "(HS256 requires a strong key)."
            )
        return value
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    cookie_secure: bool = False

    cors_origins: str = "http://localhost:5173"

    file_storage_path: str = "/data/files"
    field_encryption_key: str = "change_me"
    max_upload_mb: int = 15

    llm_primary: str = "groq"
    llm_secondary: str = "gemini"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_rpm: int = 30
    groq_tpm: int = 8000
    groq_rpd: int = 1000
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_rpm: int = 10
    gemini_tpm: int = 250000
    gemini_rpd: int = 200
    llm_daily_budget_stop_pct: int = 90
    llm_max_tokens_header: int = 250
    llm_max_tokens_lines: int = 600

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    ocr_engine: Literal["rapidocr", "tesseract"] = "rapidocr"
    demo_mode: bool = True
    auto_approve_limit: int = 5000

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
