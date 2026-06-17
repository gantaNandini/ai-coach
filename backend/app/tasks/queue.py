"""
app/tasks/queue.py — arq background job definitions and WorkerSettings.

All jobs accept tenant_id: str as first argument and pass it to
UnitOfWork(tenant_id=tenant_id) so RLS is enforced on every DB access.

CRITICAL RULE: Never hold a DB connection open while running CPU-bound
embedding inference. Pattern:
  1. Open UoW, fetch data, CLOSE UoW
  2. Run inference (no DB connection held)
  3. Open new UoW, write results, CLOSE UoW

Worker startup:
  python -m arq app.tasks.queue.WorkerSettings

Or via docker-compose:
  command: python -m arq app.tasks.queue.WorkerSettings
"""
from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from uuid import UUID

from app.tasks.recrawl_scheduler import check_url_recrawl

logger = logging.getLogger("ai_coach.worker")


# ── Job: document ingestion ────────────────────────────────────────────────────

async def ingest_document(
    ctx,
    *,
    tenant_id: str,
    source_id: str,
    kb_id: str,
    source_type: str,
    title: str,
    content: str | None = None,
    file_path: str | None = None,
    mime_type: str | None = None,
    url: str | None = None,
) -> dict:
    """
    Chunk and store a document. Enqueues generate_embeddings when done.

    Args:
        ctx: arq job context (contains redis connection)
        tenant_id: UUID string — passed to UnitOfWork for RLS
        source_id: KnowledgeSource UUID
        kb_id: KnowledgeBase UUID
        source_type: 'paste' | 'upload' | 'url'
        title: human-readable title
        content: text content (for paste)
        file_path: local path or S3 key (for upload)
        mime_type: MIME type (for upload)
        url: URL to crawl (for url type)
    """
    logger.info("[JOB] ingest_document start — source=%s tenant=%s", source_id, tenant_id)
    from app.tasks.knowledge_ingestion import run_ingestion
    await run_ingestion(
        source_id=UUID(source_id),
        kb_id=UUID(kb_id),
        tenant_id=UUID(tenant_id),
        source_type=source_type,
        title=title,
        content=content,
        file_path=file_path,
        mime_type=mime_type,
        url=url,
    )
    logger.info("[JOB] ingest_document done — source=%s", source_id)
    return {"source_id": source_id, "status": "ingested"}


# ── Job: embedding generation ──────────────────────────────────────────────────

async def generate_embeddings(
    ctx,
    *,
    tenant_id: str,
    source_id: str,
    kb_id: str,
) -> dict:
    """
    Generate and store embeddings for all chunks of a source.

    NEVER holds a DB connection open during model inference.
    See embedding_generation.py for the 3-phase pattern.
    """
    logger.info("[JOB] generate_embeddings start — source=%s tenant=%s", source_id, tenant_id)
    from app.tasks.embedding_generation import generate_embeddings_for_source
    await generate_embeddings_for_source(
        source_id=UUID(source_id),
        kb_id=UUID(kb_id),
        tenant_id=UUID(tenant_id),
    )
    logger.info("[JOB] generate_embeddings done — source=%s", source_id)
    return {"source_id": source_id, "status": "embedded"}


# ── Job: URL re-crawl ──────────────────────────────────────────────────────────

async def crawl_url(
    ctx,
    *,
    tenant_id: str,
    source_id: str,
    kb_id: str,
) -> dict:
    """Re-crawl a URL source and re-index its content."""
    from sqlalchemy import text, update
    from app.database.unit_of_work import UnitOfWork
    from app.models.knowledge import KnowledgeSource

    logger.info("[JOB] crawl_url start — source=%s tenant=%s", source_id, tenant_id)

    async with UnitOfWork(tenant_id=tenant_id) as uow:
        result = await uow.session.execute(
            text("SELECT url, title FROM knowledge_sources WHERE id = :sid"),
            {"sid": source_id},
        )
        row = result.fetchone()
        if not row:
            logger.warning("[JOB] crawl_url: source %s not found", source_id)
            return {"source_id": source_id, "status": "not_found"}
        url, title = row

    if url:
        from app.tasks.knowledge_ingestion import run_ingestion
        await run_ingestion(
            source_id=UUID(source_id),
            kb_id=UUID(kb_id),
            tenant_id=UUID(tenant_id),
            source_type="url",
            title=title or url,
            url=url,
        )

    logger.info("[JOB] crawl_url done — source=%s", source_id)
    return {"source_id": source_id, "status": "crawled"}


# ── Job: achievement evaluation ────────────────────────────────────────────────

async def evaluate_achievements(
    ctx,
    *,
    tenant_id: str,
    user_id: str,
    session_id: str | None = None,
) -> dict:
    """Check and award achievements after session completion."""
    from app.database.unit_of_work import UnitOfWork
    from sqlalchemy import text

    logger.info("[JOB] evaluate_achievements — user=%s tenant=%s", user_id, tenant_id)

    async with UnitOfWork(tenant_id=tenant_id) as uow:
        # Count completed sessions for this user
        result = await uow.session.execute(
            text("""
                SELECT COUNT(*) FROM coaching_sessions
                WHERE user_id = :uid
                  AND tenant_id = :tid
                  AND status = 'completed'
            """),
            {"uid": user_id, "tid": tenant_id},
        )
        session_count = result.scalar_one()

        # Check for best score
        score_result = await uow.session.execute(
            text("""
                SELECT MAX(overall_score) FROM feedback_reports
                WHERE tenant_id = :tid
                  AND session_id IN (
                      SELECT id FROM coaching_sessions
                      WHERE user_id = :uid AND tenant_id = :tid
                  )
            """),
            {"uid": user_id, "tid": tenant_id},
        )
        best_score = score_result.scalar_one_or_none() or 0.0

        # Award achievements based on thresholds
        achieved = []
        if session_count >= 1:
            achieved.append(("first_session", session_count))
        if session_count >= 5:
            achieved.append(("five_sessions", session_count))
        if session_count >= 10:
            achieved.append(("ten_sessions", session_count))
        if best_score >= 75:
            achieved.append(("score_75_plus", best_score))
        if best_score >= 90:
            achieved.append(("score_90_plus", best_score))

        for ach_key, value in achieved:
            # Insert if not already awarded
            await uow.session.execute(
                text("""
                    INSERT INTO user_achievements
                        (id, tenant_id, user_id, achievement_key, awarded_at, metadata)
                    VALUES
                        (gen_random_uuid(), :tid, :uid, :key, now(), :meta)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "tid": tenant_id,
                    "uid": user_id,
                    "key": ach_key,
                    "meta": f'{{"value": {value}}}',
                },
            )
        await uow.commit()

    logger.info("[JOB] evaluate_achievements done — awarded %d", len(achieved))
    return {"user_id": user_id, "achievements_awarded": len(achieved)}


# ── Job: send notification email ───────────────────────────────────────────────

async def send_notification_email(
    ctx,
    *,
    tenant_id: str,
    user_id: str,
    template: str,
    data: dict,
) -> dict:
    """Send transactional email via configured provider (Resend)."""
    from app.database.unit_of_work import UnitOfWork
    from sqlalchemy import text

    logger.info("[JOB] send_notification_email — user=%s template=%s", user_id, template)

    # Fetch user email
    async with UnitOfWork(tenant_id=tenant_id) as uow:
        result = await uow.session.execute(
            text("SELECT email, full_name FROM users WHERE id = :uid"),
            {"uid": user_id},
        )
        row = result.fetchone()

    if not row:
        logger.warning("[JOB] send_notification_email: user %s not found", user_id)
        return {"status": "user_not_found"}

    email, full_name = row

    try:
        from app.core.email import send_email
        await send_email(
            to=email,
            template=template,
            data={"full_name": full_name, **data},
        )
        logger.info("[JOB] Email sent to %s (template=%s)", email, template)
        return {"status": "sent", "email": email}
    except Exception as exc:
        logger.error("[JOB] Email failed for %s: %s", email, exc)
        raise


# ── Lifecycle hooks ───────────────────────────────────────────────────────────

async def on_job_start(ctx) -> None:
    logger.info(
        "[WORKER] Job started: %s (job_id=%s)",
        ctx.get("job_name", "unknown"),
        ctx.get("job_id", "?"),
    )


async def on_job_end(ctx) -> None:
    logger.info(
        "[WORKER] Job ended: %s (job_id=%s)",
        ctx.get("job_name", "unknown"),
        ctx.get("job_id", "?"),
    )


async def on_job_error(ctx, job, error) -> None:
    """Write failed jobs to worker_failures dead-letter table."""
    import traceback as _tb
    tb_str = "".join(_tb.format_exception(type(error), error, error.__traceback__))

    logger.error(
        "[WORKER] Job FAILED: %s — %s\n%s",
        job.function,
        error,
        tb_str,
    )

    # Write to dead-letter table
    try:
        from app.database.unit_of_work import UnitOfWork
        from sqlalchemy import text
        async with UnitOfWork() as uow:
            await uow.session.execute(
                text("""
                    INSERT INTO worker_failures
                        (id, task_name, task_args, error_message, traceback, retry_count, failed_at)
                    VALUES
                        (gen_random_uuid(), :name, :args::jsonb, :err, :tb, :retries, now())
                """),
                {
                    "name": job.function,
                    "args": str(job.kwargs or {}),
                    "err": str(error)[:2000],
                    "tb": tb_str[:5000],
                    "retries": getattr(job, "tries", 1),
                },
            )
            await uow.commit()
    except Exception as exc:
        logger.error("[WORKER] Failed to write to worker_failures: %s", exc)


# ── WorkerSettings ─────────────────────────────────────────────────────────────

def _build_redis_settings():
    """Build arq RedisSettings from app config at import time."""
    try:
        from app.core.config import settings as app_settings
        from arq.connections import RedisSettings
        return RedisSettings.from_dsn(app_settings.REDIS_URL)
    except Exception:
        from arq.connections import RedisSettings
        return RedisSettings(host="redis", port=6379)


class WorkerSettings:
    """arq worker configuration. Start with: python -m arq app.tasks.queue.WorkerSettings"""

    functions = [
        ingest_document,
        generate_embeddings,
        crawl_url,
        evaluate_achievements,
        send_notification_email,
        check_url_recrawl,
    ]

    cron_jobs = [
        __import__('arq').cron(check_url_recrawl, hour=None, minute=0),
    ]

    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
    max_tries = 3
    retry_delay = 5

    on_job_start = on_job_start
    on_job_end = on_job_end
    on_job_error = on_job_error

    # arq reads this as a class attribute — must be a RedisSettings instance
    redis_settings = _build_redis_settings()
