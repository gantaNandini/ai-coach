"""
Retrieval evaluation harness — run: python tests/eval/retrieval_eval.py
Measures precision@3 for fixed question/chunk pairs. Regression baseline.
"""
import asyncio, os, sys, uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import psycopg2

conn = psycopg2.connect(host='localhost', dbname='aicoach', user='aicoach', password='aicoach')
cur = conn.cursor()
cur.execute("SET app.is_superadmin = 'true'")
cur.execute("SELECT id FROM tenants LIMIT 1")
row = cur.fetchone()
conn.close()
TENANT_ID = str(row[0]) if row else None

EVAL_PAIRS = [
    {
        "question": "What is the SBI feedback model?",
        "expected_keywords": ["situation", "behaviour", "impact"],
        "source_text": (
            "The SBI feedback framework stands for Situation, Behaviour, Impact. "
            "Situation describes the context. Behaviour is the observable action. "
            "Impact explains the effect on others."
        )
    },
    {
        "question": "How should a coach handle resistance?",
        "expected_keywords": ["resistance", "empathy", "listen"],
        "source_text": (
            "When a coachee shows resistance, the coach should first listen with empathy. "
            "Resistance often signals an unmet need. "
            "Effective coaches acknowledge feelings before offering solutions."
        )
    },
    {
        "question": "What makes feedback actionable?",
        "expected_keywords": ["specific", "actionable", "observable"],
        "source_text": (
            "Actionable feedback is specific and focused on observable behaviour. "
            "Vague feedback is not actionable. "
            "Specific examples and suggested next steps make feedback useful."
        )
    },
]

async def run_eval():
    if not TENANT_ID:
        print("No tenant found — create a tenant first")
        return

    from app.core import startup as _s
    _s.startup_status.update(pgvector="not_installed", database="ok",
        redis="ok", ollama="ok", embeddings="ok", ready=True)
    import app.rag.reranker as _rr
    async def _noop(q,r,t=5): return r[:t]
    _rr.rerank = _noop

    from app.rag.embedding_service import EmbeddingService
    from app.rag.retrieval_service import RetrievalService
    from app.tasks.knowledge_ingestion import run_ingestion
    from app.database.unit_of_work import UnitOfWork
    from app.models.knowledge import KnowledgeBase

    emb = EmbeddingService()
    svc = RetrievalService(embedding_service=emb)

    print("=" * 60)
    print("RETRIEVAL EVALUATION HARNESS")
    print(f"Tenant: {TENANT_ID}")
    print("=" * 60)

    results_summary = []
    cleanup_kb_ids = []

    for pair in EVAL_PAIRS:
        print(f"\nQ: {pair['question']}")
        kb_id = uuid.uuid4()
        src_id = uuid.uuid4()
        cleanup_kb_ids.append(str(kb_id))

        async with UnitOfWork(tenant_id=TENANT_ID) as uow:
            kb = KnowledgeBase(id=kb_id, tenant_id=uuid.UUID(TENANT_ID),
                               name=f"eval-{str(kb_id)[:8]}", scope="tenant")
            uow.session.add(kb)
            await uow.commit()

        await run_ingestion(
            source_id=src_id, kb_id=kb_id, tenant_id=uuid.UUID(TENANT_ID),
            source_type="paste", title="eval-source", content=pair["source_text"]
        )

        results = await svc.retrieve(
            query=pair["question"], tenant_id=TENANT_ID, module_id=None, top_k=3
        )

        combined = " ".join(getattr(r.chunk, "content", "") for r in results).lower()
        hits = sum(1 for kw in pair["expected_keywords"] if kw.lower() in combined)
        precision = hits / len(pair["expected_keywords"])
        print(f"  Retrieved: {len(results)} chunks")
        print(f"  Keywords:  {hits}/{len(pair['expected_keywords'])} = {precision:.0%}")
        results_summary.append(precision)

    # Cleanup
    conn2 = psycopg2.connect(host="localhost", dbname="aicoach", user="aicoach", password="aicoach")
    cur2 = conn2.cursor()
    cur2.execute("SET app.is_superadmin = 'true'")
    for kid in cleanup_kb_ids:
        cur2.execute("DELETE FROM knowledge_chunks WHERE kb_id=%s", (kid,))
        cur2.execute("DELETE FROM knowledge_sources WHERE kb_id=%s", (kid,))
        cur2.execute("DELETE FROM knowledge_bases WHERE id=%s", (kid,))
    conn2.commit()
    conn2.close()

    avg = sum(results_summary) / len(results_summary) if results_summary else 0
    print()
    print("=" * 60)
    print(f"AVERAGE PRECISION@3: {avg:.0%}")
    print("=" * 60)
    print("Baseline recorded. Compare future runs against this number.")

if __name__ == "__main__":
    asyncio.run(run_eval())
