"""Debug the full-text search fallback."""
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
    print(f"Tenant: {tenant_id}")

    from app.database.unit_of_work import UnitOfWork
    from sqlalchemy import text, select
    from app.models.knowledge import KnowledgeChunk, KnowledgeBase

    async with UnitOfWork() as uow:
        kb_result = await uow.knowledge_bases.list_by_tenant(tenant_id=tenant_id, page=1, page_size=5)
        kb_ids = [kb.id for kb in kb_result.items]
        print('KB IDs:', kb_ids)

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
        print("SQL:", sql_str[:200])
        try:
            rows = (await uow.session.execute(text(sql_str), {"q": "SBI feedback"})).all()
            print('Rows:', rows)
        except Exception as e:
            print('SQL error:', traceback.format_exc())

        # Also try loading a chunk to see its embedding type
        try:
            chunk_result = await uow.session.execute(
                select(KnowledgeChunk).limit(1)
            )
            chunk = chunk_result.scalar_one_or_none()
            if chunk:
                print(f"Chunk embedding type: {type(chunk.embedding)}")
                print(f"Chunk embedding[:3]: {chunk.embedding[:3] if chunk.embedding else 'None'}")
        except Exception as e:
            print("Chunk load error:", traceback.format_exc())

asyncio.run(test())
