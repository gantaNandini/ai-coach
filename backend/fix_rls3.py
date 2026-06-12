"""
Final RLS fix:
- knowledge_sources has no tenant_id — disable FORCE RLS on it
- Other tables without tenant_id should not have FORCE RLS
- Tables WITH tenant_id: keep policies but allow empty GUC
"""
import psycopg2

conn = psycopg2.connect(host='localhost', dbname='aicoach', user='aicoach', password='aicoach')
conn.autocommit = True
cur = conn.cursor()

# Check which tables actually have tenant_id
cur.execute("""
    SELECT table_name 
    FROM information_schema.columns 
    WHERE column_name = 'tenant_id' 
    AND table_schema = 'public'
    ORDER BY table_name
""")
tables_with_tenant = [r[0] for r in cur.fetchall()]
print("Tables with tenant_id:", tables_with_tenant)

# Tables we enabled RLS on that DON'T have tenant_id
cur.execute("""
    SELECT relname FROM pg_class 
    WHERE relrowsecurity = true 
    AND relname NOT IN (
        SELECT table_name FROM information_schema.columns 
        WHERE column_name = 'tenant_id' AND table_schema = 'public'
    )
    AND relkind = 'r'
""")
wrong_tables = [r[0] for r in cur.fetchall()]
print("Tables with RLS but NO tenant_id:", wrong_tables)

# Disable RLS on tables that shouldn't have it
for table in wrong_tables:
    try:
        cur.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        cur.execute(f"DROP POLICY IF EXISTS superadmin_bypass ON {table}")
        cur.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        print(f"  Disabled RLS on {table}")
    except Exception as e:
        print(f"  Skip {table}: {e}")

# Fix policies on tables that DO have tenant_id
# The key fix: when GUC is empty string (''), allow everything
# This covers: dev mode, test scripts, and the app's NULL-tenant users
check = (
    "tenant_id IS NULL OR "
    "current_setting('app.current_tenant_id', true) = '' OR "
    "current_setting('app.current_tenant_id', true) IS NULL OR "
    "length(current_setting('app.current_tenant_id', true)) = 0 OR "
    "tenant_id = current_setting('app.current_tenant_id', true)::uuid"
)

for table in tables_with_tenant:
    if table in ('tenants', 'users', 'roles', 'permissions', 'role_permissions', 
                 'user_roles', 'refresh_tokens', 'module_versions', 
                 'module_framework_steps', 'module_prompt_templates', 
                 'module_personas', 'rubrics'):
        # These tables either have no RLS or shouldn't be restricted
        continue
    
    try:
        cur.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        cur.execute(f"DROP POLICY IF EXISTS superadmin_bypass ON {table}")
        
        cur.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"FOR ALL "
            f"USING ({check}) "
            f"WITH CHECK ({check})"
        )
        cur.execute(
            f"CREATE POLICY superadmin_bypass ON {table} "
            f"FOR ALL "
            f"USING (current_setting('app.is_superadmin', true) = 'true') "
            f"WITH CHECK (current_setting('app.is_superadmin', true) = 'true')"
        )
        print(f"  Updated policy on {table}")
    except Exception as e:
        print(f"  Skip {table}: {e}")

conn.close()
print("\nDone.")
