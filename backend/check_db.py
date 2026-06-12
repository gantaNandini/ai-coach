import psycopg2
conn = psycopg2.connect(host='localhost', dbname='aicoach', user='aicoach', password='aicoach')
cur = conn.cursor()
cur.execute("SET app.is_superadmin = 'true'")
cur.execute("SELECT id, status, tenant_id, final_score FROM coaching_sessions ORDER BY created_at DESC LIMIT 5")
print("Sessions (with tenant_id):", cur.fetchall())
cur.execute("SELECT id, session_id, roleplay_id, overall_score, tenant_id FROM feedback_reports ORDER BY created_at DESC LIMIT 5")
print("Reports:", cur.fetchall())
cur.execute("SELECT tablename, policyname, qual FROM pg_policies WHERE tablename='coaching_sessions'")
print("Coaching sessions RLS policies:")
for r in cur.fetchall():
    print(f"  {r[1]}: {r[2]}")
conn.close()
