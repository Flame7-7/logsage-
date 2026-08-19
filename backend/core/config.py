"""
LogSage AI — Core Configuration
Pydantic v2 settings with full environment support.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────
    APP_NAME: str = "LogSage AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str = Field(default="change-me-in-production-32chars-min")
    LOG_LEVEL: str = "INFO"

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://logsage:logsage_secret@localhost:5432/logsage"
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50

    # ── AI / Embeddings ───────────────────────────────────────
    ANTHROPIC_API_KEY: str = Field(default="")
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.1

    # ── Processing ────────────────────────────────────────────
    MAX_LOG_FILE_SIZE_MB: int = 100
    BATCH_EMBEDDING_SIZE: int = 64
    CLUSTERING_THRESHOLD: float = 0.75
    ANOMALY_WINDOW_SECONDS: int = 300
    ANOMALY_SPIKE_MULTIPLIER: float = 3.0

    # ── Alerts ────────────────────────────────────────────────
    ALERT_REDIS_FAILURE_THRESHOLD: int = 5
    ALERT_RECONNECT_STORM_THRESHOLD: int = 10
    ALERT_QUEUE_SIZE_THRESHOLD: int = 1000

    # ── WebSocket ─────────────────────────────────────────────
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MAX_CONNECTIONS: int = 100

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_db_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("Only PostgreSQL is supported")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def celery_broker_url(self) -> str:
        return self.REDIS_URL

    @property
    def celery_result_backend(self) -> str:
        return self.REDIS_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
