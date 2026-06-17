from __future__ import annotations
import logging
from uuid import UUID

from app.core.config import settings
from app.database.unit_of_work import UnitOfWork
from app.rag.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


async def generate_embeddings_for_source(
    source_id: UUID,
    kb_id: UUID,
    tenant_id: UUID,
) -> None:
    """
    Generate embeddings for all unembedded chunks of a source.

    Architecture note:
      embed_batch() runs synchronous CPU-bound inference on the event loop thread.
      Holding an open asyncpg connection across that CPU work causes [WinError 64]
      TCP resets on Windows (server kills the stalled idle connection).

      We solve this by splitting into three phases:
        1. READ phase  — open UoW, fetch chunks, close UoW (releases DB connection)
        2. CPU phase   — run embed_batch() with no DB connection open
        3. WRITE phase — open a new UoW, bulk-write embeddings, close UoW
    """
    try:
        embedding_service = EmbeddingService()
    except Exception as exc:
        logger.error("Failed to init EmbeddingService: %s", exc)
        return

    # ── Phase 1: READ — fetch chunks, then release DB connection ─────────
    async with UnitOfWork(tenant_id=tenant_id) as uow:
        page = await uow.knowledge_chunks.list_by_source(
            source_id=source_id,
            embedded_only=False,
            page=1,
            page_size=10000,
        )
        chunks_to_embed = [c for c in page.items if c.embedding is None]
    # UoW exits here — DB connection released before any CPU work

    if not chunks_to_embed:
        return

    # ── Phase 2: CPU — generate embeddings with no DB connection held ─────
    batch_size = settings.EMBEDDING_BATCH_SIZE
    chunk_embeddings: list[tuple[UUID, list[float]]] = []

    for i in range(0, len(chunks_to_embed), batch_size):
        batch = chunks_to_embed[i : i + batch_size]
        texts = [c.content for c in batch]
        try:
            embeddings = await embedding_service.embed_batch(texts)
            for chunk, embedding in zip(batch, embeddings):
                chunk_embeddings.append((chunk.id, embedding))
        except Exception as exc:
            logger.error("Embedding batch failed: %s", exc)
            continue

    if not chunk_embeddings:
        return

    # ── Phase 3: WRITE — persist embeddings in a fresh DB connection ──────
    async with UnitOfWork(tenant_id=tenant_id) as uow:
        for chunk_id, embedding in chunk_embeddings:
            await uow.knowledge_chunks.set_embedding(chunk_id, embedding)
        await uow.commit()

    logger.info("Embedded %d chunks for source %s", len(chunk_embeddings), source_id)
