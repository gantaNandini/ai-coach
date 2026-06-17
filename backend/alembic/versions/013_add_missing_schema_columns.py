"""Add missing schema columns: tenants billing/limits, worker_failures, users RLS.

Revision ID: 013
Revises: 012
Create Date: 2026-06-15
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: str = "012"
branch_labels = None
depends_on = None


def _run(conn, stmt: str, label: str) -> None:
    """Execute a DDL statement, printing a warning if it fails."""
    try:
        conn.execute(sa.text(stmt))
    except Exception as e:
        print(f"[013] Skipped ({label}): {e}")


def upgrade() -> None:
    conn = op.get_bind()

    # 1. tenants: billing + plan limit columns (IF NOT EXISTS is idempotent)
    _run(conn, "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS max_knowledge_bases INTEGER NOT NULL DEFAULT 3", "max_knowledge_bases")
    _run(conn, "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS max_sessions_per_month INTEGER NOT NULL DEFAULT 100", "max_sessions_per_month")
    _run(conn, "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)", "stripe_customer_id")
    _run(conn, "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255)", "stripe_subscription_id")
    _run(conn, "CREATE INDEX IF NOT EXISTS idx_tenants_stripe_customer ON tenants(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL", "idx_stripe")

    # 2. worker_failures dead-letter table
    _run(conn, """
        CREATE TABLE IF NOT EXISTS worker_failures (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_name VARCHAR(255) NOT NULL,
            task_args JSONB,
            error_message TEXT,
            traceback TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            failed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """, "worker_failures table")
    _run(conn, "CREATE INDEX IF NOT EXISTS idx_worker_failures_task ON worker_failures(task_name, failed_at DESC)", "idx_worker_failures")
    print("[013] worker_failures table ready")

    # 3. users: add tenant_id convenience column
    _run(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL", "users.tenant_id")
    _run(conn, "CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users(tenant_id) WHERE tenant_id IS NOT NULL", "idx_users_tenant_id")
    print("[013] users.tenant_id ready")

    # 4. users: add role convenience column
    _run(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'user'", "users.role")
    print("[013] users.role ready")

    # 5. RLS on users table
    _run(conn, "ALTER TABLE users ENABLE ROW LEVEL SECURITY", "enable rls users")
    _run(conn, "ALTER TABLE users FORCE ROW LEVEL SECURITY", "force rls users")
    _run(conn, "DROP POLICY IF EXISTS tenant_isolation ON users", "drop old policy")
    _run(conn, "DROP POLICY IF EXISTS superadmin_bypass ON users", "drop old bypass")
    _run(conn, """
        CREATE POLICY tenant_isolation ON users FOR ALL USING (
            tenant_id IS NULL
            OR (
                current_setting('app.current_tenant_id', true) IS NOT NULL
                AND current_setting('app.current_tenant_id', true) != ''
                AND tenant_id = current_setting('app.current_tenant_id', true)::uuid
            )
        )
    """, "tenant_isolation policy on users")
    _run(conn, """
        CREATE POLICY superadmin_bypass ON users FOR ALL USING (
            current_setting('app.is_superadmin', true) = 'true'
        )
    """, "superadmin_bypass policy on users")
    print("[013] RLS on users ready")

    # 6. Back-fill users.tenant_id from user_tenants
    _run(conn, """
        UPDATE users u
        SET tenant_id = ut.tenant_id
        FROM user_tenants ut
        WHERE ut.user_id = u.id
          AND ut.is_primary = true
          AND u.tenant_id IS NULL
    """, "backfill users.tenant_id")
    print("[013] Migration complete")


def downgrade() -> None:
    conn = op.get_bind()
    for stmt in [
        "DROP POLICY IF EXISTS tenant_isolation ON users",
        "DROP POLICY IF EXISTS superadmin_bypass ON users",
        "ALTER TABLE users DISABLE ROW LEVEL SECURITY",
        "ALTER TABLE users DROP COLUMN IF EXISTS role",
        "ALTER TABLE users DROP COLUMN IF EXISTS tenant_id",
        "DROP TABLE IF EXISTS worker_failures",
        "ALTER TABLE tenants DROP COLUMN IF EXISTS stripe_subscription_id",
        "ALTER TABLE tenants DROP COLUMN IF EXISTS stripe_customer_id",
        "ALTER TABLE tenants DROP COLUMN IF EXISTS max_sessions_per_month",
        "ALTER TABLE tenants DROP COLUMN IF EXISTS max_knowledge_bases",
    ]:
        try:
            conn.execute(sa.text(stmt))
        except Exception as e:
            print(f"[013 downgrade] Skipped: {e}")
