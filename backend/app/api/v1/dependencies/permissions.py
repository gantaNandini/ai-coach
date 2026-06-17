"""
Role-based access control dependency for FastAPI routes.

Usage:
    from app.api.v1.dependencies.permissions import require_role

    @router.post("/modules/")
    async def create_module(
        _: None = Depends(require_role("admin")),
        current_user: User = Depends(get_current_active_user),
    ):
        ...

Supported role names (map to the RBAC model):
    "admin"      — tenant_admin or program_owner or superadmin
    "learner"    — learner (or any role)
    "superadmin" — is_superadmin flag only
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.api.v1.dependencies.auth import get_current_active_user
from app.models.user import User


def require_role(role: str):
    """
    FastAPI dependency factory — raises 403 if the current user
    does not have the required role.

    Example:
        @router.post("/", dependencies=[Depends(require_role("admin"))])
    """
    async def _check(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.is_superadmin:
            return current_user

        role_names = {ur.role.name for ur in (current_user.user_roles or []) if ur.role}

        if role == "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Superadmin access required.",
            )

        if role == "admin":
            admin_roles = {"tenant_admin", "program_owner", "superadmin"}
            if not role_names.intersection(admin_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin access required. Contact your tenant administrator.",
                )

        if role == "learner":
            # All authenticated users are allowed learner access
            pass

        return current_user

    return _check
