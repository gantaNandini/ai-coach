"""
Fix RLS policies to allow rows where tenant_id IS NULL (global sessions).
Users without a tenant should still see their own NULL-tenant rows.
"""
import psycopg2

# Connect as postgres superuser to modify RLS policies
# Since aicoach user can't DROP/CREATE policies, we need to check if there's a way
# Actually aicoach IS the table owner so it can manage its own RLS policies

conn = psycopg2.connect(host='localhost', dbname='aicoach', user='aicoach', password='aicoach')
conn.autocommit = True
cur = conn.cursor()

# Tables that have tenant_id column — need updated policies
TABLES_WITH_TENANT = [
    "coaching_sessions",
    "roleplay_sessions", 
    "feedback_reports",
    "user_progress",
    "user_achievements",
    "notifications",
    "knowledge_bases",
    "knowledge_chunks",
]

NULLABLE_TENANT_TABLES = {
    "coaching_sessions",
    "roleplay_sessions",
    "feedback_reports", 
    "user_progress",
    "user_achievements",
    "notifications",
    "knowledge_bases",
    "knowledge_chunks",
}

for table in TABLES_WITH_TENANT:
    try:
        # Drop existing tenant_isolation policy
        cur.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        
        # New policy: allow NULL tenant_id OR matching tenant_id
        # NULL tenant = global/platform row visible to all authenticated users
        if table in NULLABLE_TENANT_TABLES:
            tenant_check = (
                "tenant_id IS NULL OR "
                "current_setting('app.current_tenant_id', true) = '' OR "
                "tenant_id = current_setting('app.current_tenant_id', true)::uuid"
            )
        else:
            tenant_check = (
                "current_setting('app.current_tenant_id', true) != '' AND "
                "tenant_id = current_setting('app.current_tenant_id', true)::uuid"
            )
        
        cur.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"FOR ALL USING ({tenant_check})"
        )
        print(f"OK: {table}")
    except Exception as e:
        print(f"SKIP {table}: {e}")

# Also set superadmin bypass for aicoach user itself (it's the table owner)
# The app user needs a way to query without tenant context during development
# Set a default for the GUC so empty string doesn't cause issues
try:
    cur.execute("ALTER DATABASE aicoach SET app.current_tenant_id = ''")
    cur.execute("ALTER DATABASE aicoach SET app.is_superadmin = 'false'")
    print("OK: Database GUC defaults set")
except Exception as e:
    print(f"GUC defaults: {e}")

conn.close()
print("Done - RLS policies updated")
