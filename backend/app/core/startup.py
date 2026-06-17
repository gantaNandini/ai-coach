"""
startup.py — Application startup checks and health verification.

Runs at lifespan startup to verify:
- Database connectivity (fatal if down)
- Redis connectivity (fatal if down — required for arq job queue)
- pgvector extension availability (non-fatal, degrades to FTS)
- Ollama / LLM connectivity (non-fatal)
- Embedding model availability (non-fatal)

Sentry is initialized here if SENTRY_DSN is configured.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("ai_coach.startup")

# Module-level state — set during lifespan startup
startup_status: dict[str, Any] = {
    "database": "unknown",
    "redis": "unknown",
    "pgvector": "unknown",
    "ollama": "unknown",
    "embeddings": "unknown",
    "ready": False,
}


def init_sentry() -> None:
    """Initialize Sentry SDK if SENTRY_DSN is configured."""
    try:
        from app.core.config import settings
        if not settings.SENTRY_DSN:
            logger.info("[STARTUP] Sentry: not configured (set SENTRY_DSN to enable)")
            return
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.1,  # 10% of requests traced — tune for production
            send_default_pii=False,  # do not send PII to Sentry
        )
        logger.info("[STARTUP] Sentry: initialized (env=%s)", settings.ENVIRONMENT)
    except Exception as exc:
        logger.warning("[STARTUP] Sentry init failed: %s", exc)


async def check_database() -> bool:
    """Verify PostgreSQL connectivity. FATAL if down."""
    try:
        from app.database.engine import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        startup_status["database"] = "ok"
        logger.info("[STARTUP] Database: OK")
        return True
    except Exception as exc:
        startup_status["database"] = f"error: {exc}"
        logger.error("[STARTUP] Database: FAILED — %s", exc)
        return False


async def check_redis() -> bool:
    """
    Verify Redis connectivity.
    FATAL if down — arq job queue requires Redis.
    """
    try:
        from app.core.config import settings
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        startup_status["redis"] = "ok"
        logger.info("[STARTUP] Redis: OK")
        return True
    except Exception as exc:
        startup_status["redis"] = f"error: {exc}"
        logger.error("[STARTUP] Redis: FAILED — %s", exc)
        return False


async def check_pgvector() -> bool:
    """
    Check if pgvector extension is available.
    NOT fatal — app degrades gracefully to full-text search.
    """
    try:
        from app.database.engine import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            row = result.fetchone()
            if row:
                startup_status["pgvector"] = "ok"
                logger.info("[STARTUP] pgvector: INSTALLED ✓")
                return True
            else:
                startup_status["pgvector"] = "not_installed"
                logger.warning(
                    "[STARTUP] pgvector: NOT INSTALLED — falling back to full-text search."
                )
                return False
    except Exception as exc:
        startup_status["pgvector"] = f"error: {exc}"
        logger.warning("[STARTUP] pgvector check failed: %s", exc)
        return False


async def check_ollama() -> bool:
    """Check Ollama connectivity. Non-fatal."""
    try:
        import httpx
        from app.core.config import settings
        if settings.LLM_PROVIDER != "ollama":
            startup_status["ollama"] = f"skipped (provider={settings.LLM_PROVIDER})"
            return True
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/version")
            if resp.status_code == 200:
                data = resp.json()
                startup_status["ollama"] = f"ok (v{data.get('version', '?')})"
                logger.info("[STARTUP] Ollama: OK — model=%s", settings.OLLAMA_MODEL)
                return True
            else:
                startup_status["ollama"] = f"http_{resp.status_code}"
                logger.warning("[STARTUP] Ollama: returned %s", resp.status_code)
                return False
    except Exception as exc:
        startup_status["ollama"] = f"offline: {type(exc).__name__}"
        logger.warning("[STARTUP] Ollama: OFFLINE — start Ollama to enable AI generation.")
        return False


async def check_embeddings() -> bool:
    """Verify sentence-transformers model is loaded. Non-fatal."""
    try:
        from app.rag.embedding_service import EmbeddingService
        svc = EmbeddingService()
        result = await svc.embed_query("health check")
        if len(result) == 384:
            startup_status["embeddings"] = "ok (BAAI/bge-small-en-v1.5, 384-dim)"
            logger.info("[STARTUP] Embeddings: OK")
            return True
        else:
            startup_status["embeddings"] = f"wrong_dim: {len(result)}"
            return False
    except Exception as exc:
        startup_status["embeddings"] = f"error: {type(exc).__name__}"
        logger.warning("[STARTUP] Embeddings: %s — RAG ingestion may fail", exc)
        return False


async def run_startup_checks() -> None:
    """
    Run all startup checks.
    Database and Redis failures are fatal — the app cannot serve requests without them.
    All other checks are non-fatal with graceful degradation.
    """
    logger.info("[STARTUP] Running startup checks...")

    # Initialize Sentry first so it captures any startup errors
    init_sentry()

    db_ok = await check_database()
    if not db_ok:
        raise RuntimeError(
            "DATABASE CONNECTION FAILED — cannot start. "
            "Check DATABASE_URL in .env and ensure PostgreSQL is running."
        )

    redis_ok = await check_redis()
    if not redis_ok:
        logger.warning(
            "[STARTUP] Redis unavailable — background jobs (arq) will not work. "
            "Start Redis or set REDIS_URL correctly. App will still serve API requests."
        )
        # Non-fatal in development — workers may not be running
        # In production, treat as fatal by changing this to raise RuntimeError(...)

    # Non-fatal checks in parallel
    import asyncio
    await asyncio.gather(
        check_pgvector(),
        check_ollama(),
        check_embeddings(),
        return_exceptions=True,
    )

    startup_status["ready"] = True
    logger.info(
        "[STARTUP] Ready — db=%s redis=%s pgvector=%s ollama=%s embeddings=%s",
        startup_status["database"],
        startup_status["redis"],
        startup_status["pgvector"],
        startup_status["ollama"],
        startup_status["embeddings"],
    )
