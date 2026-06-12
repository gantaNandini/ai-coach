"""Debug with full traceback from actual RetrievalService."""
import asyncio, sys, logging, traceback
sys.path.insert(0, '.')
logging.basicConfig(level=logging.WARNING)

# Enable debug logging just for RAG
logging.getLogger('app.rag').setLevel(logging.DEBUG)

from app.core import startup
startup.startup_status['pgvector'] = 'not_installed'
startup.startup_status['database'] = 'ok'
startup.startup_status['ready'] = True

import logging as _log
# Monkey-patch logger.warning to print full traceback
_orig_warning = logging.Logger.warning
def _patched_warning(self, msg, *args, **kwargs):
    _orig_warning(self, msg, *args, **kwargs)
    if 'Full-text fallback failed' in str(msg):
        traceback.print_exc()
        import sys; sys.stdout.flush()
logging.Logger.warning = _patched_warning

async def test():
    import psycopg2
    from uuid import UUID
    conn = psycopg2.connect(host='localhost', dbname='aicoach', user='aicoach', password='aicoach')
    cur = conn.cursor()
    cur.execute("SET app.is_superadmin = 'true'")
    cur.execute("SELECT id FROM tenants LIMIT 1")
    tenant_id = UUID(str(cur.fetchone()[0]))
    conn.close()

    from app.rag.retrieval_service import RetrievalService
    from app.rag.embedding_service import EmbeddingService

    svc = EmbeddingService()
    rsvc = RetrievalService(embedding_service=svc)

    results = await rsvc.retrieve(
        query="SBI feedback situation behaviour",
        tenant_id=tenant_id,
        module_id=None,
        top_k=3,
    )
    print(f"Retrieved: {len(results)} chunks")

asyncio.run(test())
