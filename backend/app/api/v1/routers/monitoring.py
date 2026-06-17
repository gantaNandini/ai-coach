"""
monitoring.py — Internal monitoring and observability endpoints.

Endpoints:
  GET /monitoring/health     — component health (db, pgvector, llm)  — any authenticated user
  GET /monitoring/tasks      — recent background task status          — any authenticated user
  GET /monitoring/stats      — database row counts                    — superadmin only
  GET /monitoring/config     — non-secret config values               — superadmin only
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from app.api.v1.dependencies.auth import get_current_active_user
from app.models.user import User

router = APIRouter()


def _require_superadmin(current_user: User = Depends(get_current_active_user)) -> User:
    if not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return current_user


@router.get("/health")
async def component_health(
    current_user: User = Depends(get_current_active_user),
):
    """Detailed component health status — available to all authenticated users."""
    from app.core.startup import startup_status
    from app.core.config import settings
    return {
        "components": startup_status,
        "rag_enabled": startup_status.get("pgvector") == "ok",
        "ai_enabled": startup_status.get("llm_provider", startup_status.get("ollama", "")).startswith("ok")
                      or startup_status.get("llm_provider", "") == "claude",
        "llm_provider": settings.LLM_PROVIDER,
    }


@router.get("/tasks")
async def task_status(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
):
    """Recent background task history (ingestion, embeddings)."""
    from app.tasks.worker import get_recent_tasks
    tasks = get_recent_tasks(limit=limit)
    counts: dict = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    return {"tasks": tasks, "summary": counts}


@router.get("/stats")
async def database_stats(
    current_user: User = Depends(_require_superadmin),
):
    """Row counts across key tables — superadmin only."""
    from sqlalchemy import text
    from app.database.engine import engine

    tables = [
        "tenants", "users", "coaching_modules", "module_versions",
        "knowledge_bases", "knowledge_sources", "knowledge_chunks",
        "coaching_sessions", "roleplay_sessions", "feedback_reports",
        "analytics_events", "user_progress", "user_achievements",
        "module_prompt_templates", "module_framework_steps",
    ]
    counts: dict = {}
    async with engine.connect() as conn:
        for table in tables:
            try:
                result = await conn.execute(text(f"SELECT count(*) FROM {table}"))
                counts[table] = result.scalar()
            except Exception:
                counts[table] = "error"

    return {"table_counts": counts}


@router.get("/config")
async def app_config(
    current_user: User = Depends(_require_superadmin),
):
    """Non-secret configuration values for debugging — superadmin only."""
    from app.core.config import settings
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.CLAUDE_MODEL if settings.LLM_PROVIDER == "claude" else settings.OLLAMA_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dimension": settings.EMBEDDING_DIMENSION,
        "rag_top_k": settings.RAG_TOP_K,
        "rag_score_threshold": settings.RAG_SCORE_THRESHOLD,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "allowed_upload_extensions": settings.ALLOWED_UPLOAD_EXTENSIONS,
    }
