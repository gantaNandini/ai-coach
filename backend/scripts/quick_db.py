import psycopg2, sys
try:
    conn = psycopg2.connect(host='localhost', dbname='aicoach', user='aicoach', password='aicoach', connect_timeout=3)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SET app.is_superadmin = 'true'")
    tables = ['users','coaching_sessions','roleplay_sessions','feedback_reports',
              'knowledge_bases','knowledge_sources','knowledge_chunks','analytics_events',
              'user_achievements','module_prompt_templates','module_framework_steps',
              'module_personas','coaching_modules']
    for t in tables:
        cur.execute(f"SELECT count(*) FROM {t}")
        print(f"{t}: {cur.fetchone()[0]}")
    # Check knowledge chunks with embeddings
    cur.execute("SELECT count(*) FROM knowledge_chunks WHERE embedding IS NOT NULL")
    print(f"chunks_with_embeddings: {cur.fetchone()[0]}")
    # Check pgvector
    cur.execute("SELECT extname FROM pg_extension WHERE extname='vector'")
    r = cur.fetchone()
    print(f"pgvector: {'INSTALLED' if r else 'NOT INSTALLED'}")
    # Check RLS policies
    cur.execute("SELECT count(*) FROM pg_policies")
    print(f"rls_policies: {cur.fetchone()[0]}")
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f"DB ERROR: {e}")
    sys.exit(1)
