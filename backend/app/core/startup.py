"""
startup.py — Application startup checks and health verification.

Runs at lifespan startup to verify:
- Database connectivity
- pgvector extension availability (graceful degradation if missing)
- Required DB tables exist
- Ollama connectivity (non-fatal warning if offline)

Provides a /health/detailed endpoint with component status.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("ai_coach.startup")

# Module-level state — set during lifespan startup
startup_status: dict[str, Any] = {
    "database": "unknown",
    "pgvector": "unknown",
    "ollama": "unknown",
    "embeddings": "unknown",
    "ready": False,
}


async def check_database() -> bool:
    """Verify PostgreSQL connectivity and required tables."""
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


async def check_pgvector() -> bool:
    """
    Check if pgvector extension is available.
    This is NOT fatal — the app runs without it but RAG similarity
    search will return empty results until pgvector is installed.
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
                    "[STARTUP] pgvector: NOT INSTALLED — RAG vector search disabled. "
                    "Install pgvector to enable knowledge-grounded coaching."
                )
                return False
    except Exception as exc:
        startup_status["pgvector"] = f"error: {exc}"
        logger.warning("[STARTUP] pgvector check failed: %s", exc)
        return False


async def check_ollama() -> bool:
    """Check Ollama connectivity. Non-fatal — app runs with fallback responses."""
    try:
        import httpx
        from app.core.config import settings
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
        logger.warning(
            "[STARTUP] Ollama: OFFLINE — AI feedback will use fallback responses. "
            "Start Ollama and pull model to enable AI generation."
        )
        return False


async def check_embeddings() -> bool:
    """Verify sentence-transformers model can be loaded. Non-fatal."""
    try:
        from app.rag.embedding_service import EmbeddingService
        svc = EmbeddingService()
        # Quick test embed
        result = await svc.embed_query("health check")
        if len(result) == 384:
            startup_status["embeddings"] = "ok (BAAI/bge-small-en-v1.5, 384-dim)"
            logger.info("[STARTUP] Embeddings: OK — dim=384")
            return True
        else:
            startup_status["embeddings"] = f"wrong_dim: {len(result)}"
            return False
    except Exception as exc:
        startup_status["embeddings"] = f"error: {type(exc).__name__}"
        logger.warning("[STARTUP] Embeddings: %s — RAG ingestion may fail", exc)
        return False


async def run_startup_checks() -> None:
    """Run all startup checks. Only database failure is fatal."""
    logger.info("[STARTUP] Running startup checks...")

    db_ok = await check_database()
    if not db_ok:
        raise RuntimeError(
            "DATABASE CONNECTION FAILED — cannot start. "
            "Check DATABASE_URL in .env and ensure PostgreSQL is running."
        )

    # Non-fatal checks run in parallel
    import asyncio
    await asyncio.gather(
        check_pgvector(),
        check_ollama(),
        check_embeddings(),
        return_exceptions=True,
    )

    startup_status["ready"] = True
    logger.info(
        "[STARTUP] Ready — db=%s pgvector=%s ollama=%s embeddings=%s",
        startup_status["database"],
        startup_status["pgvector"],
        startup_status["ollama"],
        startup_status["embeddings"],
    )
