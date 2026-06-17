"""
app/services/audit_service.py — Write audit log rows for security-relevant actions.

Usage (non-blocking, fire-and-forget safe):
    from app.services.audit_service import write_audit_log
    await write_audit_log(
        db=uow.session,
        tenant_id=tenant_id,
        user_id=current_user.id,
        action="kb_created",
        resource_type="knowledge_base",
        resource_id=str(kb.id),
        metadata={"name": kb.name},
    )

The function uses the CALLER'S existing async session — it does NOT open a new
connection. The caller is responsible for committing. In routers/services, call
this inside the same UnitOfWork block as the primary operation.

Supported action values (not enforced by DB — keep consistent in code):
    login, login_failed, logout, register
    kb_created, kb_deleted
    source_created, source_deleted
    session_created, session_completed
    module_published, module_unpublished, module_deleted
    plan_changed
    role_changed
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_coach.audit")


async def write_audit_log(
    db: AsyncSession,
    action: str,
    tenant_id: Any = None,
    user_id: Any = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    Write one row to audit_logs using the caller's existing AsyncSession.

    Never opens a new connection. Caller must commit.

    Args:
        db:            Existing async session (from UoW or dependency)
        action:        e.g. "kb_created", "login", "session_completed"
        tenant_id:     UUID or str — scoped to the acting tenant
        user_id:       UUID or str — the user performing the action
        resource_type: e.g. "knowledge_base", "coaching_session"
        resource_id:   UUID string of the resource
        metadata:      Extra context dict stored in after_state JSONB
        before_state:  State snapshot before the change (None for CREATE)
        after_state:   State snapshot after the change (None for DELETE)
        ip_address:    Client IP string (optional)
        user_agent:    HTTP User-Agent string (optional)
    """
    from sqlalchemy import text

    try:
        # Use raw SQL to avoid ORM overhead on a write-hot table
        # and to be safe if the AuditLog model import causes issues
        row_id = str(uuid.uuid4())

        # Normalize IDs
        tid = str(tenant_id) if tenant_id else None
        uid = str(user_id) if user_id else None
        eid = str(resource_id) if resource_id else None

        # Merge metadata into after_state
        after = after_state or {}
        if metadata:
            after = {**after, **metadata}

        # Build the insert using the ORM model to avoid asyncpg type issues
        from app.models.analytics import AuditLog
        import uuid as _uuid

        log = AuditLog(
            actor_user_id=_uuid.UUID(uid) if uid else None,
            tenant_id=_uuid.UUID(tid) if tid else None,
            action=action,
            entity_type=resource_type,
            entity_id=_uuid.UUID(eid) if eid else None,
            before_state=before_state,
            after_state=after,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(log)
        await db.flush()
        logger.debug(
            "[AUDIT] action=%s entity=%s:%s user=%s tenant=%s",
            action, resource_type, eid, uid, tid,
        )
    except Exception as exc:
        # Audit failures must never break the primary operation
        logger.error("[AUDIT] Failed to write audit log: %s", exc, exc_info=True)


async def write_audit_log_background(
    action: str,
    tenant_id: Any = None,
    user_id: Any = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    Write an audit log row in a standalone transaction (no caller session needed).

    Use for background tasks and fire-and-forget contexts where you don't have
    an active UoW session. Opens its own connection and commits immediately.
    """
    from app.database.unit_of_work import UnitOfWork
    try:
        async with UnitOfWork(tenant_id=tenant_id) as uow:
            await uow.session.execute(
                __import__("sqlalchemy").text("SET LOCAL app.is_superadmin = 'true'")
            )
            await write_audit_log(
                db=uow.session,
                action=action,
                tenant_id=tenant_id,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata=metadata,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await uow.commit()
    except Exception as exc:
        logger.error("[AUDIT] Background audit write failed: %s", exc)
