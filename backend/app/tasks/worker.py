"""
worker.py — Lightweight async background task queue.

For production SaaS: replace with arq or Celery + Redis.
For this deployment: uses asyncio tasks with retry and dead-letter logging.

Features:
- Auto-retry with exponential backoff (3 attempts)
- Per-task error logging with full traceback
- Non-blocking — tasks run concurrently with request handling
- Task registry for monitoring

Usage:
    from app.tasks.worker import enqueue
    await enqueue(run_ingestion, source_id=..., kb_id=...)
"""
from __future__ import annotations

import asyncio
import logging
import traceback
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from uuid import uuid4

logger = logging.getLogger("ai_coach.worker")

# In-memory task registry for /health/tasks monitoring
_task_registry: deque = deque(maxlen=500)  # keep last 500 tasks


def _record_task(task_id: str, name: str, status: str, error: str | None = None) -> None:
    _task_registry.append({
        "id": task_id,
        "name": name,
        "status": status,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def _run_with_retry(
    fn: Callable[..., Coroutine],
    task_id: str,
    fn_name: str,
    max_attempts: int = 3,
    base_delay: float = 2.0,
    **kwargs: Any,
) -> None:
    """Execute a coroutine with exponential backoff retry."""
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            _record_task(task_id, fn_name, "running" if attempt == 1 else f"retry_{attempt}")
            await fn(**kwargs)
            _record_task(task_id, fn_name, "completed")
            logger.info("[WORKER] %s completed (attempt %d)", fn_name, attempt)
            return
        except Exception as exc:
            last_exc = exc
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "[WORKER] %s failed (attempt %d/%d): %s — retrying in %.1fs",
                fn_name, attempt, max_attempts, exc, delay,
            )
            if attempt < max_attempts:
                await asyncio.sleep(delay)

    # All attempts failed
    error_str = f"{type(last_exc).__name__}: {last_exc}"
    _record_task(task_id, fn_name, "failed", error=error_str)
    logger.error(
        "[WORKER] %s permanently failed after %d attempts:\n%s",
        fn_name, max_attempts, traceback.format_exc(),
    )


async def enqueue(fn: Callable[..., Coroutine], **kwargs: Any) -> str:
    """
    Enqueue a background task for async execution with retry.

    Returns the task ID for monitoring.

    Example:
        task_id = await enqueue(run_ingestion, source_id=..., kb_id=...)
    """
    task_id = str(uuid4())[:8]
    fn_name = getattr(fn, "__name__", str(fn))
    _record_task(task_id, fn_name, "queued")

    # Schedule as asyncio task — non-blocking
    asyncio.create_task(
        _run_with_retry(fn, task_id, fn_name, **kwargs),
        name=f"worker_{fn_name}_{task_id}",
    )

    logger.info("[WORKER] Enqueued %s (id=%s)", fn_name, task_id)
    return task_id


def get_recent_tasks(limit: int = 50) -> list[dict]:
    """Return recent task history for monitoring endpoint."""
    tasks = list(_task_registry)
    return sorted(tasks, key=lambda t: t["timestamp"], reverse=True)[:limit]
