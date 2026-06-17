"""
Fix RLS policies properly:
- SELECT: allow NULL tenant_id OR matching tenant_id OR empty GUC
- INSERT/UPDATE: allow NULL tenant_id OR matching tenant_id OR empty GUC  
- Separate USING (select/update/delete) from WITH CHECK (insert/update)
"""
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='aicoach', user='aicoach', password='aicoach')
conn.autocommit = True
cur = conn.cursor()

TABLES = [
    "coaching_sessions",
    "roleplay_sessions",
    "feedback_reports",
    "user_progress",
    "user_achievements",
    "notifications",
    "knowledge_bases",
    "knowledge_chunks",
]

for table in TABLES:
    try:
        # Drop all existing policies
        cur.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        cur.execute(f"DROP POLICY IF EXISTS superadmin_bypass ON {table}")
        
        # The core rule:
        # - NULL tenant_id = global row, always visible/writable
        # - Empty GUC = no tenant context set (dev mode / superadmin), allow all
        # - Non-empty GUC = must match tenant_id
        check = (
            "tenant_id IS NULL OR "
            "current_setting('app.current_tenant_id', true) = '' OR "
            "current_setting('app.current_tenant_id', true) IS NULL OR "
            "tenant_id = current_setting('app.current_tenant_id', true)::uuid"
        )
        
        # USING = filter for SELECT/UPDATE/DELETE
        # WITH CHECK = validate for INSERT/UPDATE
        cur.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"FOR ALL "
            f"USING ({check}) "
            f"WITH CHECK ({check})"
        )
        
        # Superadmin bypass
        cur.execute(
            f"CREATE POLICY superadmin_bypass ON {table} "
            f"FOR ALL "
            f"USING (current_setting('app.is_superadmin', true) = 'true') "
            f"WITH CHECK (current_setting('app.is_superadmin', true) = 'true')"
        )
        print(f"OK: {table}")
    except Exception as e:
        print(f"ERROR {table}: {e}")

conn.close()
print("\nRLS policies fixed.")
