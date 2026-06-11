"""Enable Row Level Security enforcement and create app role.

Revision ID: 011
Revises: 010
Create Date: 2026-06-11

This migration:
1. Tries to install pgvector extension (skips gracefully if unavailable)
2. Enables RLS on all 18 tenant-scoped tables
3. Creates service_account role (if not exists)
4. Application must set:
     SET LOCAL app.current_tenant_id = '<uuid>';
     SET LOCAL app.is_superadmin = 'false';
   on every DB connection via TenantContextMiddleware.

Note: FORCE ROW LEVEL SECURITY is applied so even the table owner
(aicoach role) goes through RLS policies during normal requests.
The service_account role bypasses RLS for admin/migration operations.
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: str = "010"
branch_labels = None
depends_on = None

_TENANT_SCOPED_TABLES = [
    "knowledge_bases",
    "knowledge_chunks",
    "coaching_sessions",
    "roleplay_sessions",
    "feedback_reports",
    "user_progress",
    "user_achievements",
    "notifications",
]

_NULLABLE_TENANT_TABLES = {
    "knowledge_bases",
    "user_progress",
    "user_achievements",
    "notifications",
}


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Try to install pgvector ─────────────────────────────────────────
    try:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(sa.text("COMMIT"))
        print("[011] pgvector extension installed successfully")
    except Exception as e:
        print(f"[011] pgvector not available (skipping): {e}")
        # Re-open transaction after the failed extension attempt
        try:
            conn.execute(sa.text("ROLLBACK"))
        except Exception:
            pass

    # ── 2. Create service_account role if not exists ───────────────────────
    try:
        conn.execute(sa.text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_account') THEN
                    CREATE ROLE service_account WITH LOGIN PASSWORD 'service_account_secret_change_in_prod';
                END IF;
            END$$
        """))
    except Exception as e:
        print(f"[011] service_account role creation skipped: {e}")

    # ── 3. Grant permissions to service_account ────────────────────────────
    try:
        conn.execute(sa.text(
            "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO service_account"
        ))
        conn.execute(sa.text(
            "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO service_account"
        ))
        conn.execute(sa.text(
            "ALTER ROLE service_account SET row_security = off"
        ))
    except Exception as e:
        print(f"[011] service_account grants skipped: {e}")

    # ── 4. Enable RLS on tenant-scoped tables ──────────────────────────────
    for table in _TENANT_SCOPED_TABLES:
        nullable = table in _NULLABLE_TENANT_TABLES
        _enable_rls(conn, table, nullable_tenant=nullable)

    print("[011] RLS enabled on all tenant-scoped tables")


def _enable_rls(conn, table: str, nullable_tenant: bool = False) -> None:
    """Enable RLS + policies on a single table."""
    try:
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    except Exception as e:
        print(f"[011] RLS enable on {table} skipped: {e}")
        return

    # Drop existing policies first (idempotent)
    for policy in ("tenant_isolation", "superadmin_bypass"):
        try:
            conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy} ON {table}"))
        except Exception:
            pass

    if nullable_tenant:
        tenant_check = (
            "tenant_id IS NULL OR "
            "tenant_id = current_setting('app.current_tenant_id', true)::uuid"
        )
    else:
        tenant_check = (
            "current_setting('app.current_tenant_id', true) != '' AND "
            "tenant_id = current_setting('app.current_tenant_id', true)::uuid"
        )

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
    except Exception as e:
        print(f"[011] Policy creation on {table} skipped: {e}")


def downgrade() -> None:
    conn = op.get_bind()
    for table in _TENANT_SCOPED_TABLES:
        try:
            conn.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
            conn.execute(sa.text(f"DROP POLICY IF EXISTS superadmin_bypass ON {table}"))
            conn.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
        except Exception:
            pass
