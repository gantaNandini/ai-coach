"""
knowledge_ingestion.py — Full ingestion pipeline task.

Pipeline:
  pending → processing → completed | failed

Invoked by FastAPI BackgroundTasks from the knowledge router immediately
after a source record is created.

Stages:
  1. Mark source as 'processing'
  2. Load + clean + chunk document
  3. Store chunks (embedding=None)
  4. Mark source as 'completed'
  5. Generate embeddings for all chunks
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import update

from app.core.exceptions import IngestionError
from app.database.unit_of_work import UnitOfWork
from app.models.knowledge import KnowledgeSource
from app.rag.chunking_service import ChunkingService
from app.rag.document_loader import DocumentLoader
from app.rag.ingestion_service import IngestionService
from app.rag.text_cleaner import TextCleaner
from app.tasks.embedding_generation import generate_embeddings_for_source

logger = logging.getLogger(__name__)


async def run_ingestion(
    source_id: UUID,
    kb_id: UUID,
    tenant_id: UUID,
    source_type: str,
    title: str,
    content: str | None = None,
    file_path: str | None = None,
    mime_type: str | None = None,
    url: str | None = None,
) -> None:
    """
    Run the full ingestion pipeline for a knowledge source.

    Status transitions:
        pending → processing → completed (or failed on error)

    Called via FastAPI BackgroundTasks — runs after the HTTP response is sent.
    """
    logger.info("[INGEST] Starting ingestion: source=%s type=%s", source_id, source_type)

    # Step 1: Mark source as 'processing'
    async with UnitOfWork() as uow:
        await uow.session.execute(
            update(KnowledgeSource)
            .where(KnowledgeSource.id == source_id)
            .values(status="processing")
        )
        await uow.commit()

    # Step 2: Chunk and store
    ingestion_service = IngestionService(
        document_loader=DocumentLoader(),
        text_cleaner=TextCleaner(),
        chunking_service=ChunkingService(),
    )

    async with UnitOfWork() as uow:
        try:
            chunk_count = 0
            if source_type == "paste" and content:
                chunk_count = await ingestion_service.ingest_text(
                    kb_id=kb_id,
                    source_id=source_id,
                    tenant_id=tenant_id,
                    title=title,
                    content=content,
                    uow=uow,
                )
            elif source_type == "upload" and file_path and mime_type:
                chunk_count = await ingestion_service.ingest_file(
                    kb_id=kb_id,
                    source_id=source_id,
                    tenant_id=tenant_id,
                    title=title,
                    file_path=file_path,
                    mime_type=mime_type,
                    uow=uow,
                )
            elif source_type == "url" and url:
                chunk_count = await ingestion_service.ingest_url(
                    kb_id=kb_id,
                    source_id=source_id,
                    tenant_id=tenant_id,
                    title=title,
                    url=url,
                    uow=uow,
                )
            else:
                raise IngestionError(
                    f"Unsupported source_type='{source_type}' or missing required params"
                )

            # Mark completed
            await uow.session.execute(
                update(KnowledgeSource)
                .where(KnowledgeSource.id == source_id)
                .values(status="completed", chunk_count=chunk_count)
            )
            await uow.commit()
            logger.info(
                "[INGEST] Completed: source=%s chunks=%d", source_id, chunk_count
            )

        except IngestionError as exc:
            await uow.session.execute(
                update(KnowledgeSource)
                .where(KnowledgeSource.id == source_id)
                .values(status="failed", error_message=str(exc))
            )
            await uow.commit()
            logger.error("[INGEST] Failed: source=%s error=%s", source_id, exc)
            return
        except Exception as exc:
            try:
                await uow.session.execute(
                    update(KnowledgeSource)
                    .where(KnowledgeSource.id == source_id)
                    .values(status="failed", error_message=f"{type(exc).__name__}: {exc}")
                )
                await uow.commit()
            except Exception:
                pass
            logger.error(
                "[INGEST] Unexpected error: source=%s error=%s",
                source_id,
                exc,
                exc_info=True,
            )
            return

    # Step 3: Generate embeddings (separate UoW — chunking is already committed)
    logger.info("[INGEST] Starting embedding generation: source=%s", source_id)
    try:
        await generate_embeddings_for_source(source_id, kb_id, tenant_id)
        logger.info("[INGEST] Embeddings done: source=%s", source_id)
    except Exception as exc:
        # Embedding failure is non-fatal — chunks are stored, retrieval just returns empty
        logger.error(
            "[INGEST] Embedding generation failed: source=%s error=%s",
            source_id,
            exc,
            exc_info=True,
        )
