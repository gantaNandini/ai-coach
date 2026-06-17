"""
recrawl_scheduler.py — Hourly cron job that enqueues re-crawl for due URL sources.

Runs as an arq cron job every hour. Checks knowledge_sources WHERE
source_type='url' AND crawl_frequency IS NOT NULL AND
(last_crawled_at IS NULL OR last_crawled_at < NOW() - interval).

Sets last_crawled_at = NOW() immediately to prevent double-enqueue.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone

logger = logging.getLogger("ai_coach.recrawl")


async def check_url_recrawl(ctx) -> dict:
    """
    arq cron job — find URL sources due for re-crawl and enqueue them.
    Runs every hour via WorkerSettings.cron_jobs.
    """
    from app.database.unit_of_work import UnitOfWork
    from sqlalchemy import text

    logger.info("[RECRAWL] Starting scheduled URL re-crawl check")
    enqueued = 0

    try:
        # Use superadmin to read across all tenants
        async with UnitOfWork() as uow:
            await uow.session.execute(text("SET LOCAL app.is_superadmin = 'true'"))
            rows = (await uow.session.execute(text("""
                SELECT
                    ks.id           AS source_id,
                    ks.kb_id        AS kb_id,
                    kb.tenant_id    AS tenant_id,
                    ks.crawl_frequency
                FROM knowledge_sources ks
                JOIN knowledge_bases kb ON kb.id = ks.kb_id
                WHERE ks.type = 'url'
                  AND ks.crawl_frequency IS NOT NULL
                  AND ks.crawl_frequency != 'never'
                  AND ks.deleted_at IS NULL
                  AND (
                    ks.last_crawled_at IS NULL
                    OR (
                        ks.crawl_frequency = 'daily'   AND ks.last_crawled_at < NOW() - INTERVAL '1 day'
                    ) OR (
                        ks.crawl_frequency = 'weekly'  AND ks.last_crawled_at < NOW() - INTERVAL '7 days'
                    ) OR (
                        ks.crawl_frequency = 'monthly' AND ks.last_crawled_at < NOW() - INTERVAL '30 days'
                    )
                  )
                LIMIT 50
            """))).fetchall()

            if not rows:
                logger.info("[RECRAWL] No sources due for re-crawl")
                return {"enqueued": 0}

            # Mark last_crawled_at immediately (prevents duplicate enqueue on next tick)
            source_ids = [str(row[0]) for row in rows]
            await uow.session.execute(
                text("UPDATE knowledge_sources SET last_crawled_at = NOW() WHERE id = ANY(:ids::uuid[])"),
                {"ids": source_ids},
            )
            await uow.commit()

        # Enqueue crawl_url jobs via arq
        from arq.connections import RedisSettings, create_pool
        from app.core.config import settings as app_settings
        redis = await create_pool(RedisSettings.from_dsn(app_settings.REDIS_URL))

        for row in rows:
            source_id, kb_id, tenant_id, freq = row
            await redis.enqueue_job(
                "crawl_url",
                tenant_id=str(tenant_id),
                source_id=str(source_id),
                kb_id=str(kb_id),
            )
            enqueued += 1
            logger.info("[RECRAWL] Enqueued crawl_url source=%s freq=%s", source_id, freq)

        await redis.aclose()

    except Exception as exc:
        logger.error("[RECRAWL] Error in check_url_recrawl: %s", exc, exc_info=True)

    logger.info("[RECRAWL] Done — enqueued %d jobs", enqueued)
    return {"enqueued": enqueued}
