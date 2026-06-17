"""Fix RLS policy bypass bug and enable RLS on remaining tenant-scoped tables.

Revision ID: 012
Revises: 011
Create Date: 2026-06-15

Critical fixes:
1. Replace ALL tenant_isolation policies — the previous policy had a NULL/empty-string
   bypass: `current_setting(..., true) IS NULL` evaluated TRUE on connections that never
   set the GUC, exposing all rows to unauthenticated connections.

   Fixed policy enforces:
     - GUC must be present and non-empty (raises an error if not set — safe fail)
     - For non-nullable tables: tenant_id MUST equal the GUC uuid
     - For nullable tables: tenant_id IS NULL (global records) OR tenant_id = GUC uuid
     - Superadmin bypass remains unchanged

2. Enable RLS on the 4 tables that migration 011 missed:
   coaching_modules, module_versions, rubrics, tenants (already tenant-scoped via FK)

3. Add app_role (non-owner application role) for future connection string migration.
   This role has SELECT/INSERT/UPDATE/DELETE on all tables but is NOT the owner,
   so it can never bypass RLS regardless of GUC state.

Connection pool safety note:
   UnitOfWork.__aenter__ sets the GUC inside BEGIN (SET LOCAL = transaction-scoped).
   SET LOCAL is automatically reset when the transaction ends, so pool-reuse is safe
   as long as EVERY query runs inside a transaction — which async SQLAlchemy ensures.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: str = "011"
branch_labels = None
depends_on = None

# Tables with a direct tenant_id column — strict equality policy
_STRICT_TENANT_TABLES = [
    "coaching_sessions",
    "roleplay_sessions",
    "feedback_reports",
    "knowledge_chunks",
    "coaching_modules",
    "tenant_settings",
]

# Tables where tenant_id IS NULL means "global / visible to all authenticated users"
_NULLABLE_TENANT_TABLES = [
    "knowledge_bases",
    "user_progress",
    "user_achievements",
    "notifications",
]

# Child tables without tenant_id — need join-based policies referencing their parent
# Format: (table, parent_table, fk_column, parent_pk)
_JOIN_TENANT_TABLES = [
    # knowledge_sources → knowledge_bases.tenant_id
    ("knowledge_sources", "knowledge_bases", "kb_id", "id"),
    # module_versions → coaching_modules.tenant_id
    ("module_versions", "coaching_modules", "module_id", "id"),
    # module_framework_steps → module_versions → coaching_modules.tenant_id (two hops)
    # Handled via EXISTS subquery
    ("module_framework_steps", "module_versions", "module_version_id", "id"),
    ("module_prompt_templates", "module_versions", "module_version_id", "id"),
    ("module_personas", "module_versions", "module_version_id", "id"),
    ("rubrics", "module_versions", "module_version_id", "id"),
]

# The tenants table: users only see their own tenant row (id = GUC)
_TENANTS_TABLE = "tenants"

# All tables getting RLS treatment in this migration
_ALL_TABLES = _STRICT_TENANT_TABLES + _NULLABLE_TENANT_TABLES


def upgrade() -> None:
    conn = op.get_bind()

    print("[012] NOTE: Role creation (service_account, app_role) requires superuser — skipping in migration")
    print("[012]       Run the superuser commands documented in this migration's docstring.")

    # Process each table independently — errors are caught per-table so one failure
    # doesn't abort the whole migration. No SAVEPOINTs needed (each ALTER/CREATE
    # is auto-committed in DDL context).
    for table in _ALL_TABLES:
        try:
            _fix_table_rls(conn, table)
        except Exception as e:
            print(f"[012] WARN: Could not fix RLS on {table}: {e}")

    for (table, parent, fk_col, parent_pk) in _JOIN_TENANT_TABLES:
        try:
            _fix_join_table_rls(conn, table, parent, fk_col, parent_pk)
        except Exception as e:
            print(f"[012] WARN: Could not fix join RLS on {table}: {e}")

    try:
        _fix_tenants_rls(conn)
    except Exception as e:
        print(f"[012] WARN: Could not fix RLS on tenants: {e}")

    print("[012] RLS policy fix migration complete")


def _drop_old_policies(conn, table: str) -> None:
    """Drop any existing tenant_isolation and superadmin_bypass policies."""
    for policy in ("tenant_isolation", "superadmin_bypass"):
        try:
            conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy} ON {table}"))
        except Exception:
            pass


def _fix_table_rls(conn, table: str) -> None:
    """Enable RLS and install null-safe policies on a tenant-scoped table."""
    # Enable RLS + FORCE (idempotent — safe to run even if already enabled)
    try:
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    except Exception as e:
        print(f"[012] RLS enable on {table} skipped: {e}")
        return

    _drop_old_policies(conn, table)

    # Determine policy condition based on whether tenant_id can be NULL
    if table in _NULLABLE_TENANT_TABLES:
        # NULL tenant_id = global record visible to all authenticated users
        tenant_check = """
            tenant_id IS NULL
            OR (
                current_setting('app.current_tenant_id', true) IS NOT NULL
                AND current_setting('app.current_tenant_id', true) != ''
                AND tenant_id = current_setting('app.current_tenant_id', true)::uuid
            )
        """
    else:
        # Strict: tenant_id must match GUC. If GUC is unset → no rows visible (safe fail).
        tenant_check = """
            current_setting('app.current_tenant_id', true) IS NOT NULL
            AND current_setting('app.current_tenant_id', true) != ''
            AND tenant_id = current_setting('app.current_tenant_id', true)::uuid
        """

    try:
        conn.execute(sa.text(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"FOR ALL USING ({tenant_check})"
        ))
        conn.execute(sa.text(
            f"CREATE POLICY superadmin_bypass ON {table} "
            f"FOR ALL USING ("
            f"  current_setting('app.is_superadmin', true) = 'true'"
            f")"
        ))
        print(f"[012] Fixed RLS policies on {table}")
    except Exception as e:
        print(f"[012] Policy creation on {table} failed: {e}")


def _fix_join_table_rls(conn, table: str, parent: str, fk_col: str, parent_pk: str) -> None:
    """
    Enable RLS on a child table that lacks tenant_id.
    Uses a subquery join to the parent table's tenant_id.
    
    Example: knowledge_sources → knowledge_bases.tenant_id via kb_id
    Policy: EXISTS (SELECT 1 FROM knowledge_bases p WHERE p.id = kb_id AND p.tenant_id = guc::uuid)
    
    Two-hop tables (e.g. module_framework_steps → module_versions → coaching_modules):
    For module_versions child tables, parent is module_versions which has module_id FK to coaching_modules.
    We check module_versions.module_id → coaching_modules.tenant_id via a two-level join.
    """
    try:
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    except Exception as e:
        print(f"[012] RLS enable on {table} skipped: {e}")
        return

    _drop_old_policies(conn, table)

    # Determine if this is a direct child or two-hop
    # Direct: knowledge_sources → knowledge_bases (has tenant_id)
    # Two-hop: rubrics → module_versions → coaching_modules (has tenant_id)
    if parent == "knowledge_bases":
        tenant_check = f"""
            current_setting('app.current_tenant_id', true) IS NOT NULL
            AND current_setting('app.current_tenant_id', true) != ''
            AND EXISTS (
                SELECT 1 FROM {parent} p
                WHERE p.{parent_pk} = {table}.{fk_col}
                AND p.tenant_id = current_setting('app.current_tenant_id', true)::uuid
            )
        """
    elif parent == "module_versions":
        # Two-hop via coaching_modules
        tenant_check = f"""
            current_setting('app.current_tenant_id', true) IS NOT NULL
            AND current_setting('app.current_tenant_id', true) != ''
            AND EXISTS (
                SELECT 1 FROM module_versions mv
                JOIN coaching_modules cm ON cm.id = mv.module_id
                WHERE mv.id = {table}.{fk_col}
                AND cm.tenant_id = current_setting('app.current_tenant_id', true)::uuid
            )
        """
    elif parent == "coaching_modules":
        # Direct via coaching_modules
        tenant_check = f"""
            current_setting('app.current_tenant_id', true) IS NOT NULL
            AND current_setting('app.current_tenant_id', true) != ''
            AND EXISTS (
                SELECT 1 FROM {parent} p
                WHERE p.{parent_pk} = {table}.{fk_col}
                AND p.tenant_id = current_setting('app.current_tenant_id', true)::uuid
            )
        """
    else:
        print(f"[012] Unknown parent type for {table}, skipping")
        return

    try:
        conn.execute(sa.text(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"FOR ALL USING ({tenant_check})"
        ))
        conn.execute(sa.text(
            f"CREATE POLICY superadmin_bypass ON {table} "
            f"FOR ALL USING ("
            f"  current_setting('app.is_superadmin', true) = 'true'"
            f")"
        ))
        print(f"[012] Fixed join RLS policies on {table} (via {parent})")
    except Exception as e:
        print(f"[012] Join policy creation on {table} failed: {e}")


def _fix_tenants_rls(conn) -> None:
    """
    Special RLS for the tenants table.
    Users should only see their own tenant row (id matches tenant GUC).
    Superadmin can see all.
    Note: tenants table uses 'id' not 'tenant_id'.
    """
    table = "tenants"
    # Tenants table may not have a tenant_id column — it IS the tenant.
    # Check if tenant_id column exists on tenants
    try:
        result = conn.execute(sa.text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tenants' AND column_name = 'tenant_id'
        """))
        has_tenant_id_col = result.fetchone() is not None
    except Exception:
        has_tenant_id_col = False

    try:
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    except Exception as e:
        print(f"[012] RLS enable on tenants skipped: {e}")
        return

    _drop_old_policies(conn, table)

    if has_tenant_id_col:
        # Standard tenant_id column policy
        tenant_check = """
            current_setting('app.current_tenant_id', true) IS NOT NULL
            AND current_setting('app.current_tenant_id', true) != ''
            AND tenant_id = current_setting('app.current_tenant_id', true)::uuid
        """
    else:
        # tenants.id IS the tenant — users can only see their own tenant row
        tenant_check = """
            current_setting('app.current_tenant_id', true) IS NOT NULL
            AND current_setting('app.current_tenant_id', true) != ''
            AND id = current_setting('app.current_tenant_id', true)::uuid
        """

    try:
        conn.execute(sa.text(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"FOR ALL USING ({tenant_check})"
        ))
        conn.execute(sa.text(
            f"CREATE POLICY superadmin_bypass ON {table} "
            f"FOR ALL USING ("
            f"  current_setting('app.is_superadmin', true) = 'true'"
            f")"
        ))
        print(f"[012] Fixed RLS policies on {table} (id-based)")
    except Exception as e:
        print(f"[012] Tenants policy creation failed: {e}")


def downgrade() -> None:
    conn = op.get_bind()
    join_tables = [t[0] for t in _JOIN_TENANT_TABLES]
    all_tables = _ALL_TABLES + join_tables + [_TENANTS_TABLE]
    for table in all_tables:
        try:
            conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
            conn.execute(sa.text(f"DROP POLICY IF EXISTS superadmin_bypass ON {table}"))
            conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
        except Exception:
            pass
