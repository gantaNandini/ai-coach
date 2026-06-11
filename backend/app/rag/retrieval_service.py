# FILE: app/rag/retrieval_service.py
"""
RetrievalService — orchestrate RAG knowledge retrieval.

When pgvector is installed: full HNSW cosine-similarity search.
When pgvector is NOT installed: falls back to BM25-style keyword
search over chunk content using PostgreSQL full-text search (tsvector).
This ensures coaching still works even without the vector extension —
results are less precise but grounded in real knowledge base content.
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.core.config import settings
from app.database.unit_of_work import UnitOfWork
from app.repositories.knowledge.knowledge_chunk_repository import ChunkSearchResult
from app.rag.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def _pgvector_available() -> bool:
    """Check if pgvector extension is loaded at runtime."""
    from app.core.startup import startup_status
    return startup_status.get("pgvector") == "ok"


class RetrievalService:
    """Orchestrate RAG knowledge retrieval with graceful pgvector degradation."""

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedding_service = embedding_service

    async def retrieve(
        self,
        query: str,
        tenant_id: UUID,
        module_id: UUID | None,
        top_k: int | None = None,
        score_threshold: float | None = None,
        uow: UnitOfWork | None = None,
    ) -> list[ChunkSearchResult]:
        """
        Retrieve relevant knowledge chunks for a query.

        Uses pgvector HNSW cosine search when available.
        Falls back to PostgreSQL full-text search (tsvector) otherwise.
        Returns empty list if knowledge base has no chunks.
        """
        if not query or not query.strip():
            return []

        top_k = top_k or settings.RAG_TOP_K
        score_threshold = score_threshold or settings.RAG_SCORE_THRESHOLD

        should_close = uow is None
        if uow is None:
            uow = UnitOfWork()
            await uow.__aenter__()

        try:
            # Resolve KB IDs
            if module_id is not None:
                kb_ids = await uow.knowledge_bases.get_kb_ids_for_retrieval(
                    module_id=module_id, tenant_id=tenant_id,
                )
            else:
                tenant_kbs = await uow.knowledge_bases.list_by_tenant(
                    tenant_id=tenant_id, page=1, page_size=100,
                )
                kb_ids = [kb.id for kb in tenant_kbs.items]

            if not kb_ids:
                return []

            if _pgvector_available():
                # Full vector similarity search
                query_embedding = await self._embedding_service.embed_query(query)
                return await uow.knowledge_chunks.similarity_search(
                    query_embedding=query_embedding,
                    tenant_id=tenant_id,
                    kb_ids=kb_ids,
                    top_k=top_k,
                    score_threshold=score_threshold,
                )
            else:
                # Fallback: full-text keyword search
                logger.debug("[RAG] pgvector not available — using full-text fallback")
                return await self._fulltext_search(
                    query=query,
                    tenant_id=tenant_id,
                    kb_ids=kb_ids,
                    top_k=top_k,
                    uow=uow,
                )
        except Exception as exc:
            logger.warning("[RAG] Retrieval failed: %s — returning empty results", exc)
            return []
        finally:
            if should_close:
                await uow.__aexit__(None, None, None)

    async def _fulltext_search(
        self,
        query: str,
        tenant_id: UUID,
        kb_ids: list[UUID],
        top_k: int,
        uow: UnitOfWork,
    ) -> list[ChunkSearchResult]:
        """
        PostgreSQL full-text search fallback when pgvector is unavailable.
        Uses plainto_tsquery for robust multi-word matching.
        Returns ChunkSearchResult with similarity scored by ts_rank.
        """
        from sqlalchemy import text
        from app.models.knowledge import KnowledgeChunk

        try:
            sql = text("""
                SELECT id,
                       ts_rank(
                           to_tsvector('english', content),
                           plainto_tsquery('english', :query)
                       ) AS rank
                FROM knowledge_chunks
                WHERE tenant_id = :tenant_id
                  AND kb_id = ANY(:kb_ids)
                  AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
                ORDER BY rank DESC
                LIMIT :top_k
            """)

            rows = (await uow.session.execute(sql, {
                "query": query,
                "tenant_id": str(tenant_id),
                "kb_ids": [str(k) for k in kb_ids],
                "top_k": top_k,
            })).all()

            if not rows:
                return []

            from sqlalchemy import select
            chunk_ids = [r[0] for r in rows]
            rank_map = {str(r[0]): float(r[1]) for r in rows}

            chunks_result = await uow.session.execute(
                select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids))
            )
            chunks_by_id = {str(c.id): c for c in chunks_result.scalars().all()}

            results = []
            for chunk_id_str, rank in sorted(rank_map.items(), key=lambda x: x[1], reverse=True):
                chunk = chunks_by_id.get(chunk_id_str)
                if chunk:
                    # Normalize rank to 0-1 range (ts_rank is typically 0-1 already)
                    results.append(ChunkSearchResult(chunk=chunk, similarity=min(1.0, rank)))

            return results

        except Exception as exc:
            logger.warning("[RAG] Full-text fallback failed: %s", exc)
            return []
