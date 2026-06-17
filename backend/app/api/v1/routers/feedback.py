from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends
from app.schemas.session.feedback_report import FeedbackReportResponse, FeedbackRatingRequest
from app.services.session.feedback_service import FeedbackService
from app.api.v1.dependencies.auth import get_current_active_user
from app.models.user import User

router = APIRouter()
_svc = FeedbackService()


@router.get("/{report_id}")
async def get_feedback(
    report_id: UUID,
    current_user: User = Depends(get_current_active_user),
):
    """Get a feedback report by ID. Respects citations_visible tenant setting."""
    from app.database.unit_of_work import UnitOfWork
    from sqlalchemy import text as _t

    report = await _svc.get_feedback(report_id, user_id=current_user.id)
    data = FeedbackReportResponse.model_validate(report).model_dump()

    # Read citations_visible from tenant settings
    citations_visible = True
    try:
        if hasattr(current_user, 'tenant_id') and current_user.tenant_id:
            async with UnitOfWork(tenant_id=current_user.tenant_id) as uow:
                row = (await uow.session.execute(
                    _t("SELECT settings FROM tenant_settings WHERE tenant_id = :tid"),
                    {"tid": str(current_user.tenant_id)},
                )).fetchone()
                if row and row[0]:
                    citations_visible = row[0].get("citations_visible", True)
    except Exception:
        pass

    data["citations_visible"] = citations_visible
    if not citations_visible:
        data["citations"] = []

    return data


@router.post("/{report_id}/rate", response_model=FeedbackReportResponse)
async def rate_feedback(
    report_id: UUID,
    body: FeedbackRatingRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Submit a star rating for a feedback report."""
    report = await _svc.submit_rating(
        report_id=report_id,
        user_id=current_user.id,
        rating=body.rating,
        notes=body.notes,
    )
    return FeedbackReportResponse.model_validate(report)
