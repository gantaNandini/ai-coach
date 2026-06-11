"""
tenant.py — Per-request tenant context middleware.

Sets app.current_tenant_id PostgreSQL GUC on every database connection
so RLS policies can enforce tenant isolation at the DB layer.

Architecture:
  1. JWT is decoded to extract tenant_id (from user's active tenant role)
  2. GUC is set via SET LOCAL app.current_tenant_id = '<uuid>'
  3. All subsequent queries in this request inherit the GUC
  4. GUC is automatically reset when the connection is returned to pool

Note: RLS policies in migration 010 reference this GUC. If you skipped
enabling RLS (current state), this middleware still sets the GUC safely —
it becomes a no-op until RLS is enabled on each table.

For production:
  - Enable RLS on tables by running: ALTER TABLE <t> ENABLE ROW LEVEL SECURITY
  - Create service_account role that bypasses RLS for admin operations
  - This middleware handles all learner/admin API requests automatically
"""
from __future__ import annotations

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("ai_coach.tenant")

# Paths that don't need tenant context
_SKIP_PATHS = {"/health", "/health/detailed", "/docs", "/redoc", "/openapi.json"}


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Extract tenant_id from JWT and store on request.state.
    The UnitOfWork reads request.state.tenant_id to set the GUC.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS or not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Try to extract tenant from Authorization header
        tenant_id = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            try:
                from app.core.security.jwt import decode_access_token
                payload = decode_access_token(token)
                tenant_id = payload.get("tenant_id")
            except Exception:
                pass  # Invalid token — let auth middleware handle it

        request.state.tenant_id = tenant_id
        return await call_next(request)
