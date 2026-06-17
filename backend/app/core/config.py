"""
Application configuration via environment variables.
Uses pydantic-settings for validation and type coercion.
All secrets come from environment — never hardcoded.
Fails fast at import time if any required variable is missing.
"""
from __future__ import annotations

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

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "AI Coach"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:5173"
    APP_BASE_URL: str = "http://localhost:5173"

    # ── Security ─────────────────────────────────────────────────────────────
    # Required — no default. Startup fails if not set.
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ─────────────────────────────────────────────────────────────
    # Required — no default. Startup fails if not set.
    DATABASE_URL: str = Field(
        ...,
        description="Async PostgreSQL DSN. Must use asyncpg driver.",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── LLM Provider ─────────────────────────────────────────────────────────
    LLM_PROVIDER: Literal["ollama", "claude"] = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma3:latest"
    OLLAMA_TIMEOUT: int = 600
    OLLAMA_MAX_TOKENS: int = 2048
    OLLAMA_TEMPERATURE: float = 0.3
    # Claude (only used when LLM_PROVIDER=claude)
    ANTHROPIC_API_KEY: str | None = None
    CLAUDE_MODEL: str = "claude-sonnet-4-5"

    # ── Embeddings ───────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_BATCH_SIZE: int = 32

    # ── RAG ──────────────────────────────────────────────────────────────────
    RAG_CHUNK_SIZE: int = 512
    RAG_CHUNK_OVERLAP: int = 64
    RAG_TOP_K: int = 6
    RAG_SCORE_THRESHOLD: float = 0.35
    RAG_TOKEN_BUDGET: int = 2048

    # ── Object Storage ────────────────────────────────────────────────────────
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_UPLOAD_EXTENSIONS: list[str] = [
        ".pdf", ".docx", ".pptx", ".txt", ".md"
    ]
    # S3 / MinIO settings (used when STORAGE_BACKEND=s3)
    S3_ENDPOINT_URL: str | None = None      # None = use AWS; set for MinIO
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    S3_BUCKET: str = "aicoach-uploads"
    S3_REGION: str = "us-east-1"

    # ── Email ─────────────────────────────────────────────────────────────────
    EMAIL_PROVIDER: Literal["resend", "postmark", "smtp", "none"] = "none"
    RESEND_API_KEY: str | None = None
    POSTMARK_SERVER_TOKEN: str | None = None
    EMAIL_FROM: str = "noreply@aicoach.example.com"

    # ── Billing (Stripe) ─────────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_PRICE_ID_STARTER: str | None = None
    STRIPE_PRICE_ID_PRO: str | None = None

    # ── Observability ────────────────────────────────────────────────────────
    SENTRY_DSN: str | None = None
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"

    # ── Pagination ───────────────────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # ── Rate Limiting ────────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL DSN")
        if "asyncpg" not in v and "postgresql://" in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://")
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v.startswith("redis"):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return v


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — reads .env once at startup."""
    return Settings()


settings = get_settings()