from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends
from app.schemas.analytics.events import TrackEventRequest
from app.schemas.common import MessageResponse
from app.services.analytics.analytics_service import AnalyticsService
from app.api.v1.dependencies.auth import get_current_active_user, get_current_tenant_id
from app.api.v1.dependencies.permissions import require_role
from app.models.user import User

router = APIRouter()
_svc = AnalyticsService()


@router.post("/events", response_model=MessageResponse)
async def track_event(
    body: TrackEventRequest,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Track a behavioral analytics event."""
    await _svc.track_event(
        event_type=body.event_type,
        user_id=current_user.id,
        tenant_id=tenant_id,
        properties=body.properties,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        session_id_ref=body.session_id_ref,
    )
    return MessageResponse(message="Event tracked")


@router.get("/dashboard")
async def dashboard(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
    _admin: User = Depends(require_role("admin")),
):
    """Get analytics dashboard metrics — real database aggregation."""
    data = await _svc.get_dashboard(tenant_id=tenant_id, days=days)
    return data


@router.get("/module-performance")
async def module_performance(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Per-module session counts, completion rates and average scores."""
    data = await _svc.get_module_performance(tenant_id=tenant_id, days=days)
    return {"items": data, "period_days": days}


@router.get("/session-trend")
async def session_trend(
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Daily session counts for the last N days — for the line chart."""
    data = await _svc.get_session_trend(tenant_id=tenant_id, days=days)
    return {"items": data, "period_days": days}


@router.get("/leaderboard")
async def leaderboard(
    days: int = 30,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    tenant_id: UUID | None = Depends(get_current_tenant_id),
):
    """Top users by average score."""
    data = await _svc.get_leaderboard(tenant_id=tenant_id, days=days, limit=limit)
    return {"items": data, "period_days": days}
