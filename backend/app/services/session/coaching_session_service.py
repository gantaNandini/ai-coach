# FILE: app/services/session/coaching_session_service.py
"""
CoachingSessionService — coaching session lifecycle, intake, messages, completion.

Responsibilities:
- Create sessions (pin current module version)
- Submit intake data
- Add conversation messages
- Complete/abandon sessions (status transitions)
- List user sessions
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.database.unit_of_work import UnitOfWork
from app.models.session import CoachingSession, ConversationMessage
from app.repositories.base import Page
from app.repositories.session.coaching_session_repository import (
    CoachingSessionCreate,
    ConversationMessageCreate,
)


class CoachingSessionService:
    """
    Coaching session lifecycle management.

    Each method opens its own UnitOfWork.
    """

    # ── Session creation ──────────────────────────────────────────────────────

    async def create_session(
        self, user_id: UUID, module_id: UUID, tenant_id: UUID | None = None
    ) -> CoachingSession:
        """
        Create a new coaching session.

        Pins the current module version (module_version_id) so the
        session remains immutable even if the module is updated later.
        Enforces the tenant's monthly session limit (max_sessions_per_month).

        Raises:
            NotFoundError       — module has no current version
            PermissionDeniedError — tenant has reached their monthly session limit
        """
        from datetime import date
        from sqlalchemy import text as _text

        async with UnitOfWork(tenant_id=tenant_id) as uow:
            # ── Plan limit enforcement ────────────────────────────────────────
            if tenant_id is not None:
                # Read tenant limits using superadmin bypass to access tenants table
                await uow.session.execute(_text("SET LOCAL app.is_superadmin = 'true'"))
                tenant_row = (await uow.session.execute(
                    _text("SELECT max_sessions_per_month FROM tenants WHERE id = :tid"),
                    {"tid": str(tenant_id)},
                )).fetchone()
                await uow.session.execute(_text("SET LOCAL app.is_superadmin = 'false'"))

                if tenant_row:
                    max_sessions = tenant_row[0]
                    # Count sessions started this calendar month
                    month_start = date.today().replace(day=1)  # datetime.date object
                    count_row = (await uow.session.execute(
                        _text(
                            "SELECT COUNT(*) FROM coaching_sessions "
                            "WHERE tenant_id = :tid AND created_at >= :month_start"
                        ),
                        {"tid": str(tenant_id), "month_start": month_start},
                    )).fetchone()
                    current_count = count_row[0] if count_row else 0

                    if current_count >= max_sessions:
                        raise PermissionDeniedError(
                            f"Your plan allows {max_sessions} sessions per month. "
                            f"You have used {current_count} this month. "
                            "Upgrade your plan to continue."
                        )

            version = await uow.module_versions.get_current_version(module_id)
            if version is None:
                raise NotFoundError(
                    "ModuleVersion",
                    f"No current version for module {module_id}",
                )

            session = await uow.coaching_sessions.create(
                CoachingSessionCreate(
                    user_id=user_id,
                    module_id=module_id,
                    module_version_id=version.id,
                    tenant_id=tenant_id,
                )
            )
            await uow.commit()
            return session

    # ── Lookup ────────────────────────────────────────────────────────────────

    async def get_session(
        self,
        session_id: UUID,
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
    ) -> CoachingSession:
        """
        Fetch a coaching session by id.

        When user_id is provided, validates ownership.
        When tenant_id is provided, validates tenant scope.

        Raises:
            NotFoundError       — session not found
            PermissionDeniedError — session does not belong to user_id
        """
        async with UnitOfWork(tenant_id=tenant_id) as uow:
            session = await uow.coaching_sessions.get_by_id(
                session_id, tenant_id=tenant_id
            )
            if session is None:
                raise NotFoundError("CoachingSession", session_id)

            if user_id is not None and session.user_id != user_id:
                raise PermissionDeniedError(
                    "You do not have permission to access this session."
                )

            return session

    async def get_session_detail(self, session_id: UUID) -> CoachingSession:
        """
        Fetch a session with messages + feedback eagerly loaded.

        Raises:
            NotFoundError — session not found
        """
        async with UnitOfWork() as uow:
            session = await uow.coaching_sessions.get_with_messages(session_id)
            if session is None:
                raise NotFoundError("CoachingSession", session_id)
            return session

    # ── Listing ───────────────────────────────────────────────────────────────

    async def list_sessions(
        self,
        user_id: UUID,
        tenant_id: UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[CoachingSession]:
        """
        List sessions for a user, newest first.

        Optionally filtered by tenant_id and/or status.
        """
        async with UnitOfWork(tenant_id=tenant_id) as uow:
            return await uow.coaching_sessions.list_by_user(
                user_id,
                tenant_id=tenant_id,
                status=status,
                page=page,
                page_size=page_size,
            )

    # ── Intake submission ─────────────────────────────────────────────────────

    async def submit_intake(
        self, session_id: UUID, intake_data: dict, user_id: UUID
    ) -> CoachingSession:
        """
        Submit intake form data for a coaching session.

        Validates that intake_data is non-empty and that the session
        belongs to user_id.

        Raises:
            NotFoundError       — session not found
            PermissionDeniedError — session does not belong to user_id
            ValidationError     — intake_data is empty
        """
        if not intake_data:
            raise ValidationError("Intake data must not be empty.")

        async with UnitOfWork() as uow:
            session = await uow.coaching_sessions.get_by_id(session_id)
            if session is None:
                raise NotFoundError("CoachingSession", session_id)

            if session.user_id != user_id:
                raise PermissionDeniedError(
                    "You do not have permission to modify this session."
                )

            # Update intake_data via repository update
            from app.repositories.session.coaching_session_repository import (
                CoachingSessionUpdate,
            )

            session = await uow.coaching_sessions.update(
                session_id,
                CoachingSessionUpdate(intake_data=intake_data),
            )
            await uow.commit()
            return session

    # ── Message management ────────────────────────────────────────────────────

    async def add_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        token_count: int | None = None,
    ) -> ConversationMessage:
        """
        Append a message to a coaching session conversation.

        Auto-increments message_index based on current count.

        Raises:
            NotFoundError — session not found
        """
        async with UnitOfWork() as uow:
            session = await uow.coaching_sessions.get_by_id(session_id)
            if session is None:
                raise NotFoundError("CoachingSession", session_id)

            # Compute next message_index
            current_count = await uow.coaching_sessions.get_message_count(
                session_id
            )
            message_index = current_count

            message = await uow.coaching_sessions.append_message(
                ConversationMessageCreate(
                    session_id=session_id,
                    role=role,
                    content=content,
                    message_index=message_index,
                    token_count=token_count,
                )
            )
            await uow.commit()
            return message

    # ── Status transitions ────────────────────────────────────────────────────

    async def complete_session(
        self, session_id: UUID, final_score: Decimal, user_id: UUID
    ) -> CoachingSession:
        """
        Transition a session from in_progress to completed.

        Computes duration_seconds from created_at to now().

        Raises:
            NotFoundError       — session not found
            PermissionDeniedError — session does not belong to user_id
            ConflictError       — session is already completed (raised by repo)
        """
        async with UnitOfWork() as uow:
            session = await uow.coaching_sessions.get_by_id(session_id)
            if session is None:
                raise NotFoundError("CoachingSession", session_id)

            if session.user_id != user_id:
                raise PermissionDeniedError(
                    "You do not have permission to complete this session."
                )

            # Compute duration
            now = datetime.now(timezone.utc)
            duration_seconds = int((now - session.created_at).total_seconds())

            session = await uow.coaching_sessions.complete_session(
                session_id,
                final_score=final_score,
                duration_seconds=duration_seconds,
                expected_version=session.version,
            )
            await uow.commit()
            return session

    async def abandon_session(
        self, session_id: UUID, user_id: UUID
    ) -> CoachingSession:
        """
        Transition a session from in_progress to abandoned.

        Raises:
            NotFoundError       — session not found
            PermissionDeniedError — session does not belong to user_id
        """
        async with UnitOfWork() as uow:
            session = await uow.coaching_sessions.get_by_id(session_id)
            if session is None:
                raise NotFoundError("CoachingSession", session_id)

            if session.user_id != user_id:
                raise PermissionDeniedError(
                    "You do not have permission to abandon this session."
                )

            session = await uow.coaching_sessions.abandon_session(
                session_id, expected_version=session.version
            )
            await uow.commit()
            return session
