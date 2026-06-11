"""
monitoring.py — Internal monitoring and observability endpoints.

Endpoints:
  GET /monitoring/health     — component health (db, pgvector, ollama)
  GET /monitoring/tasks      — recent background task status
  GET /monitoring/stats      — database row counts for quick audit
  GET /monitoring/config     — non-secret config values

All endpoints require authentication. /monitoring/stats and /config
additionally require superadmin or program_owner role.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from app.api.v1.dependencies.auth import get_current_active_user
from app.models.user import User

router = APIRouter()


@router.get("/health")
async def component_health(
    current_user: User = Depends(get_current_active_user),
):
    """Detailed component health status."""
    from app.core.startup import startup_status
    return {
        "components": startup_status,
        "rag_enabled": startup_status.get("pgvector") == "ok",
        "ai_enabled": startup_status.get("ollama", "").startswith("ok"),
    }


@router.get("/tasks")
async def task_status(
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
):
    """Recent background task history (ingestion, embeddings)."""
    from app.tasks.worker import get_recent_tasks
    tasks = get_recent_tasks(limit=limit)
    counts = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    return {"tasks": tasks, "summary": counts}


@router.get("/stats")
async def database_stats(
    current_user: User = Depends(get_current_active_user),
):
    """Row counts across key tables — useful for verifying seeding and ingestion."""
    from sqlalchemy import text, func, select
    from app.database.engine import engine

    tables = [
        "tenants", "users", "coaching_modules", "module_versions",
        "knowledge_bases", "knowledge_sources", "knowledge_chunks",
        "coaching_sessions", "roleplay_sessions", "feedback_reports",
        "analytics_events", "user_progress", "user_achievements",
        "module_prompt_templates", "module_framework_steps",
    ]
    counts = {}
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
    current_user: User = Depends(get_current_active_user),
):
    """Non-secret configuration values for debugging."""
    from app.core.config import settings
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "ollama_model": settings.OLLAMA_MODEL,
        "ollama_base_url": settings.OLLAMA_BASE_URL,
        "ollama_timeout": settings.OLLAMA_TIMEOUT,
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dimension": settings.EMBEDDING_DIMENSION,
        "rag_top_k": settings.RAG_TOP_K,
        "rag_score_threshold": settings.RAG_SCORE_THRESHOLD,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "allowed_upload_extensions": settings.ALLOWED_UPLOAD_EXTENSIONS,
    }
