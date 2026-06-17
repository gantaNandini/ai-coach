"""
reranker.py — Free local cross-encoder reranker.

Uses sentence-transformers CrossEncoder with BAAI/bge-reranker-base
(CPU-only, no API key, ~400MB download on first use).

Falls back gracefully if the model isn't downloaded yet — results are
still returned in embedding similarity order, just not reranked.

Usage:
    from app.rag.reranker import rerank
    results = await rerank(query="my query", results=chunk_results, top_k=5)

PRD note: PRD B.6 specifies Claude Haiku 4.5 as reranker. This build uses
Ollama for generation (deliberate cost-free choice) and this local
cross-encoder as reranker replacement — free, open-source, CPU-only.
No paid API is used anywhere in the inference stack.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.repositories.knowledge.knowledge_chunk_repository import ChunkSearchResult

logger = logging.getLogger(__name__)

# Lazy-load the model — only downloads on first call.
# Module-level singleton prevents repeated cold loads that block the asyncio event loop.
_reranker_model = None
_RERANKER_MODEL_NAME = "BAAI/bge-reranker-base"


def _get_reranker():
    """Load the cross-encoder model lazily (downloaded once, cached locally)."""
    global _reranker_model
    if _reranker_model is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker_model = CrossEncoder(_RERANKER_MODEL_NAME, max_length=512)
            logger.info("[RERANKER] Loaded %s", _RERANKER_MODEL_NAME)
        except Exception as exc:
            logger.warning("[RERANKER] Could not load reranker model: %s — skipping rerank", exc)
            _reranker_model = None
    return _reranker_model


async def rerank(
    query: str,
    results: list["ChunkSearchResult"],
    top_k: int = 5,
) -> list["ChunkSearchResult"]:
    """
    Rerank retrieval results using a local cross-encoder.

    Cross-encoders are more accurate than bi-encoders for relevance
    scoring because they jointly encode the query + passage together.

    The model predict() call is CPU-bound. We run it in an executor thread
    to avoid blocking the asyncio event loop.

    Args:
        query:   the user's search/coaching query
        results: initial retrieval results (sorted by embedding similarity)
        top_k:   how many to return after reranking

    Returns:
        Reranked list, best first. Falls back to original order if
        reranker unavailable.
    """
    if not results:
        return results

    model = _get_reranker()
    if model is None:
        # Reranker unavailable — return top_k from original order
        logger.debug("[RERANKER] Falling back to similarity order (model not loaded)")
        return results[:top_k]

    try:
        import asyncio
        # Build (query, passage) pairs for the cross-encoder
        pairs = [(query, r.chunk.content) for r in results]

        # Run synchronous CPU-bound scoring in a thread pool so we don't
        # block the asyncio event loop (important for Windows Proactor).
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(
            None,  # default ThreadPoolExecutor
            lambda: model.predict(pairs, show_progress_bar=False),
        )

        # Zip scores with results, sort descending
        scored = sorted(
            zip(scores, results),
            key=lambda x: x[0],
            reverse=True,
        )

        # Return top_k, updating similarity to reflect rerank score (0–1 normalized)
        from app.repositories.knowledge.knowledge_chunk_repository import ChunkSearchResult
        reranked = []
        for score, result in scored[:top_k]:
            # Normalize score to [0, 1] using sigmoid approximation
            import math
            normalized = 1.0 / (1.0 + math.exp(-float(score)))
            reranked.append(
                ChunkSearchResult(chunk=result.chunk, similarity=round(normalized, 4))
            )

        logger.debug("[RERANKER] Reranked %d → %d results", len(results), len(reranked))
        return reranked

    except Exception as exc:
        logger.warning("[RERANKER] Reranking failed: %s — using original order", exc)
        return results[:top_k]
