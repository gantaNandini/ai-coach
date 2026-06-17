"""Debug the full-text search fallback - trace through retrieval service code."""
import asyncio, sys, traceback
sys.path.insert(0, '.')
from app.core import startup
startup.startup_status['pgvector'] = 'not_installed'
startup.startup_status['database'] = 'ok'
startup.startup_status['ready'] = True

async def test():
    import psycopg2
    from uuid import UUID
    conn = psycopg2.connect(host='localhost', dbname='aicoach', user='aicoach', password='aicoach')
    cur = conn.cursor()
    cur.execute("SET app.is_superadmin = 'true'")
    cur.execute("SELECT id FROM tenants LIMIT 1")
    tenant_id = UUID(str(cur.fetchone()[0]))
    conn.close()

    from app.database.unit_of_work import UnitOfWork
    from sqlalchemy import text, select
    from app.models.knowledge import KnowledgeChunk

    async with UnitOfWork() as uow:
        kb_result = await uow.knowledge_bases.list_by_tenant(tenant_id=tenant_id, page=1, page_size=5)
        kb_ids = [kb.id for kb in kb_result.items]
        kb_id_strs = ', '.join(f"'{str(k)}'::uuid" for k in kb_ids)
        tenant_str = str(tenant_id)

        sql_str = f"""
            SELECT id,
                   ts_rank(to_tsvector('english', content), plainto_tsquery('english', :q)) AS rank
            FROM knowledge_chunks
            WHERE tenant_id = '{tenant_str}'::uuid
              AND kb_id = ANY(ARRAY[{kb_id_strs}])
              AND to_tsvector('english', content) @@ plainto_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT 3
        """

        rows = (await uow.session.execute(text(sql_str), {"q": "SBI feedback"})).all()
        print(f"FTS rows: {rows}")

        if rows:
            chunk_ids = [r[0] for r in rows]
            rank_map = {str(r[0]): float(r[1]) for r in rows}
            print(f"chunk_ids: {chunk_ids}")
            print(f"chunk_ids types: {[type(c) for c in chunk_ids]}")

            try:
                print("Executing select by id list...")
                chunks_result = await uow.session.execute(
                    select(KnowledgeChunk).where(KnowledgeChunk.id.in_(chunk_ids))
                )
                print("Got chunks_result, calling scalars()...")
                chunks_list = chunks_result.scalars().all()
                print(f"Got {len(chunks_list)} chunks")
                for c in chunks_list:
                    print(f"  chunk: {c.id}, embedding: {type(c.embedding)}")
            except Exception as e:
                print(f"Error in select by id: {traceback.format_exc()}")

asyncio.run(test())
