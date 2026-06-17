"""WorkerFailure — dead-letter record for failed arq background jobs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class WorkerFailure(UUIDPrimaryKeyMixin, Base):
    """
    Dead-letter record written when an arq job exhausts all retries.

    Written by on_job_error in WorkerSettings. Surface these in the
    admin monitoring endpoint so operators can investigate and replay.
    """
    __tablename__ = "worker_failures"

    task_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    task_args: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    traceback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    def __repr__(self) -> str:
        return f"<WorkerFailure task={self.task_name!r} at={self.failed_at}>"
