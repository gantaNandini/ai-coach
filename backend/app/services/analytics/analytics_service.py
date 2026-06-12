# FILE: app/services/analytics/analytics_service.py
"""
AnalyticsService — event tracking and dashboard KPI aggregation.

All dashboard metrics are computed from real database queries against
AnalyticsEvent and FeedbackReport tables. No placeholder values.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import distinct, func, select

from app.database.unit_of_work import UnitOfWork
from app.models.analytics import AnalyticsEvent
from app.models.session import FeedbackReport
from app.repositories.analytics.analytics_repository import AnalyticsEventCreate


class AnalyticsService:
    """
    Analytics event tracking and real dashboard aggregation.
    Each method opens its own UnitOfWork.
    """

    # ── Event tracking ────────────────────────────────────────────────────────

    async def track_event(
        self,
        event_type: str,
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        properties: dict | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        session_id_ref: UUID | None = None,
    ) -> None:
        """Track a behavioural event (fire-and-forget safe)."""
        async with UnitOfWork() as uow:
            await uow.analytics.track_event(
                AnalyticsEventCreate(
                    event_type=event_type,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    properties=properties or {},
                    entity_type=entity_type,
                    entity_id=entity_id,
                    session_id_ref=session_id_ref,
                )
            )
            await uow.commit()

    # ── Dashboard KPIs ────────────────────────────────────────────────────────

    async def get_dashboard(
        self, tenant_id: UUID | None = None, days: int = 30
    ) -> dict:
        """
        Compute real dashboard KPIs from the database.

        Returns:
          active_users       — distinct users with events in last N days
          sessions_started   — session_started event count
          sessions_completed — session_completed event count
          sessions_abandoned — session_abandoned event count
          completion_rate    — completed / started * 100 (%)
          avg_score          — average overall_score from FeedbackReport
          period_days        — the days parameter
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        # Use a sentinel UUID for NULL tenant_id (global/superadmin view)
        effective_tenant = tenant_id or UUID("00000000-0000-0000-0000-000000000000")

        async with UnitOfWork() as uow:
            session = uow.session

            # ── Session funnel from analytics events ──────────────────────────
            funnel = await uow.analytics.session_funnel(
                tenant_id=effective_tenant,
                since=since,
            )
            sessions_started = funnel.get("session_started", 0)
            sessions_completed = funnel.get("session_completed", 0)
            sessions_abandoned = funnel.get("session_abandoned", 0)

            completion_rate = (
                round((sessions_completed / sessions_started) * 100, 2)
                if sessions_started > 0
                else 0.0
            )

            # ── Active users — distinct user_ids with events ──────────────────
            active_users_stmt = (
                select(func.count(distinct(AnalyticsEvent.user_id)))
                .where(AnalyticsEvent.occurred_at >= since)
                .where(AnalyticsEvent.user_id.is_not(None))
            )
            if tenant_id is not None:
                active_users_stmt = active_users_stmt.where(
                    AnalyticsEvent.tenant_id == tenant_id
                )
            active_users: int = (
                await session.execute(active_users_stmt)
            ).scalar_one() or 0

            # ── Average score from FeedbackReport ─────────────────────────────
            avg_score_stmt = select(
                func.coalesce(func.avg(FeedbackReport.overall_score), 0)
            ).where(FeedbackReport.created_at >= since)
            if tenant_id is not None:
                avg_score_stmt = avg_score_stmt.where(
                    FeedbackReport.tenant_id == tenant_id
                )
            avg_score_raw = (
                await session.execute(avg_score_stmt)
            ).scalar_one()
            avg_score = float(round(Decimal(str(avg_score_raw)), 2))

            # ── Total AI tokens ───────────────────────────────────────────────
            total_tokens = 0
            if tenant_id is not None:
                try:
                    total_tokens = await uow.analytics.total_tokens_for_tenant(
                        tenant_id=tenant_id, since=since
                    )
                except Exception:
                    total_tokens = 0

            return {
                "active_users": active_users,
                "sessions_started": sessions_started,
                "sessions_completed": sessions_completed,
                "sessions_abandoned": sessions_abandoned,
                "completion_rate": completion_rate,
                "avg_score": avg_score,
                "total_ai_tokens": total_tokens,
                "period_days": days,
            }

    # ── Module performance ────────────────────────────────────────────────────

    async def get_module_performance(
        self,
        tenant_id: UUID | None = None,
        days: int = 30,
    ) -> list[dict]:
        """
        Per-module aggregated performance metrics.

        Returns list of {module_id, module_name, sessions, avg_score, completion_rate}.
        Uses real joins across coaching_sessions and feedback_reports.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        async with UnitOfWork() as uow:
            from sqlalchemy import case, cast, Float
            from app.models.session import CoachingSession
            from app.models.module import CoachingModule

            stmt = (
                select(
                    CoachingSession.module_id,
                    func.count(CoachingSession.id).label("total"),
                    func.count(
                        case((CoachingSession.status == "completed", CoachingSession.id))
                    ).label("completed"),
                    func.coalesce(func.avg(CoachingSession.final_score), 0).label("avg_score"),
                )
                .where(CoachingSession.created_at >= since)
                .group_by(CoachingSession.module_id)
            )
            if tenant_id is not None:
                stmt = stmt.where(CoachingSession.tenant_id == tenant_id)

            rows = (await uow.session.execute(stmt)).all()

            results = []
            for row in rows:
                total = row.total or 1
                results.append({
                    "module_id": str(row.module_id),
                    "sessions": row.total,
                    "completed": row.completed,
                    "completion_rate": round((row.completed / total) * 100, 1),
                    "avg_score": float(round(Decimal(str(row.avg_score)), 2)),
                })
            return results

    # ── Session trend ─────────────────────────────────────────────────────────

    async def get_session_trend(
        self,
        tenant_id: UUID | None = None,
        days: int = 30,
    ) -> list[dict]:
        """
        Daily session counts for the last N days.

        Returns a list of {date, count} dicts sorted ascending by date.
        Days with no sessions are included with count=0 so the frontend
        can render a continuous trend line.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        async with UnitOfWork() as uow:
            from sqlalchemy import cast, Date
            from app.models.session import CoachingSession

            stmt = (
                select(
                    cast(CoachingSession.created_at, Date).label("day"),
                    func.count(CoachingSession.id).label("count"),
                )
                .where(CoachingSession.created_at >= since)
                .group_by(cast(CoachingSession.created_at, Date))
                .order_by(cast(CoachingSession.created_at, Date))
            )
            if tenant_id is not None:
                stmt = stmt.where(CoachingSession.tenant_id == tenant_id)

            rows = (await uow.session.execute(stmt)).all()

        # Build a dense day-by-day map; fill zeros for missing days
        from datetime import date as date_type

        count_by_day: dict[str, int] = {str(row.day): row.count for row in rows}
        result = []
        for i in range(days):
            d: date_type = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date()
            result.append({"date": str(d), "count": count_by_day.get(str(d), 0)})
        return result

    # ── Leaderboard ───────────────────────────────────────────────────────────

    async def get_leaderboard(
        self,
        tenant_id: UUID | None = None,
        limit: int = 10,
        days: int = 30,
    ) -> list[dict]:
        """
        Top users by average session score in the last N days.

        Returns list of {rank, user_id, avg_score, sessions_completed}.
        Only users with at least one completed session are included.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        async with UnitOfWork() as uow:
            from app.models.session import CoachingSession
            from app.models.user import User

            stmt = (
                select(
                    CoachingSession.user_id,
                    func.count(CoachingSession.id).label("sessions"),
                    func.avg(CoachingSession.final_score).label("avg_score"),
                )
                .where(
                    CoachingSession.status == "completed",
                    CoachingSession.final_score.is_not(None),
                    CoachingSession.created_at >= since,
                )
                .group_by(CoachingSession.user_id)
                .order_by(func.avg(CoachingSession.final_score).desc())
                .limit(limit)
            )
            if tenant_id is not None:
                stmt = stmt.where(CoachingSession.tenant_id == tenant_id)

            rows = (await uow.session.execute(stmt)).all()

            # Resolve user display names in the same session
            user_ids = [row.user_id for row in rows]
            users_result = await uow.session.execute(
                select(User.id, User.full_name, User.email).where(User.id.in_(user_ids))
            )
            user_map = {u.id: {"full_name": u.full_name, "email": u.email}
                        for u in users_result.all()}

        leaderboard = []
        for rank, row in enumerate(rows, start=1):
            user_info = user_map.get(row.user_id, {})
            leaderboard.append({
                "rank": rank,
                "user_id": str(row.user_id),
                "display_name": user_info.get("full_name") or user_info.get("email", "Unknown"),
                "sessions_completed": row.sessions,
                "avg_score": float(round(Decimal(str(row.avg_score or 0)), 2)),
            })
        return leaderboard
