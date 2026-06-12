"""Debug create_source_from_text."""
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

    # Create KB
    from app.database.unit_of_work import UnitOfWork
    from app.models.knowledge import KnowledgeBase, KnowledgeSource
    import uuid as _uuid
    
    kb_id = _uuid.uuid4()
    async with UnitOfWork() as uow:
        kb = KnowledgeBase(id=kb_id, tenant_id=tenant_id, name='debug-test', scope='tenant')
        uow.session.add(kb)
        await uow.commit()
    print("KB created")
    
    # Now try create_source_from_text
    from app.services.knowledge.knowledge_service import KnowledgeSourceService
    svc = KnowledgeSourceService()
    
    try:
        source = await svc.create_source_from_text(
            kb_id=kb_id,
            title="Test",
            content="Test content about SBI feedback.",
            tenant_id=tenant_id,
        )
        print(f"Source created: {source}")
        print(f"Source type: {type(source)}")
    except Exception as e:
        print(f"Error: {traceback.format_exc()}")
    
    # Cleanup
    from sqlalchemy import delete
    async with UnitOfWork() as uow:
        await uow.session.execute(delete(KnowledgeSource).where(KnowledgeSource.kb_id == kb_id))
        await uow.session.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        await uow.commit()

asyncio.run(test())
