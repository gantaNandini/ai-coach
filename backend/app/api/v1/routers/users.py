from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from app.schemas.auth.user import UserResponse, UserUpdate
from app.schemas.common import MessageResponse
from app.services.auth.user_service import UserService
from app.api.v1.dependencies.auth import get_current_active_user, get_current_tenant_id
from app.models.user import User

router = APIRouter()
_svc = UserService()


@router.get("/", response_model=list[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """List users. Superadmins see all; others see their tenant's users."""
    result = await _svc.list_users(
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
    )
    return [UserResponse.model_validate(u) for u in result.items]


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Get current user profile."""
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Update current user profile."""
    user = await _svc.update_profile(
        user_id=current_user.id,
        full_name=body.full_name,
        avatar_url=body.avatar_url,
    )
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Get a user by ID."""
    user = await _svc.get_user(user_id)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Admin: update a user's profile."""
    user = await _svc.update_profile(
        user_id=user_id,
        full_name=body.full_name,
        avatar_url=body.avatar_url,
    )
    return UserResponse.model_validate(user)


@router.post("/{user_id}/deactivate", response_model=MessageResponse)
async def deactivate_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Deactivate a user account."""
    await _svc.deactivate_user(user_id, admin_user_id=current_user.id)
    return MessageResponse(message="User deactivated")


@router.post("/{user_id}/reactivate", response_model=MessageResponse)
async def reactivate_user(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Reactivate a deactivated user account."""
    await _svc.reactivate_user(user_id)
    return MessageResponse(message="User reactivated")


@router.delete("/me", response_model=MessageResponse)
async def delete_me(
    current_user: User = Depends(get_current_active_user),
):
    """Deactivate (soft-delete) the current user's own account."""
    await _svc.deactivate_user(current_user.id, admin_user_id=current_user.id)
    return MessageResponse(message="Account deleted")


@router.post("/me/change-password", response_model=MessageResponse)
async def change_my_password(
    body: dict,
    current_user: User = Depends(get_current_active_user),
):
    """Change password via /users/me/change-password (alias for /auth/change-password)."""
    from app.schemas.auth.auth_request import PasswordChangeRequest
    from app.services.auth.auth_service import AuthService
    svc = AuthService()
    await svc.change_password(
        user_id=current_user.id,
        current_password=body.get("current_password", ""),
        new_password=body.get("new_password", ""),
    )
    return MessageResponse(message="Password changed successfully")
