"""
Test configuration and shared fixtures.

Key design decisions:
- asyncio_mode = auto (pytest.ini) — no @pytest.mark.asyncio needed
- asyncio_default_fixture_loop_scope = function — each test gets its own loop
- NullPool on the test engine — no connections are pooled between tests,
  completely eliminating "event loop closed / NoneType.send" errors on Windows
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Pre-seed startup status so the app doesn't try real startup checks
from app.core import startup as _startup

_startup.startup_status.update(
    pgvector="not_installed",
    database="ok",
    ollama="ok (test)",
    embeddings="ok",
    ready=True,
)


@pytest.fixture(autouse=True)
async def fresh_db_engine():
    """
    Replace the SQLAlchemy engine with a NullPool engine for this test.

    NullPool = every execute() opens a fresh connection and closes it
    immediately after.  No connections are held open between tests, so
    there is nothing for asyncpg to complain about when the event loop
    is replaced for the next test.
    """
    import sys
    import app.database.engine as _eng_mod  # ensure module is imported
    from sqlalchemy.ext.asyncio import (
        create_async_engine,
        async_sessionmaker,
        AsyncSession,
    )
    from sqlalchemy.pool import NullPool
    from app.core.config import settings

    # Build a NullPool engine — no pooling, every call gets a fresh connection
    test_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # Patch the live engine module
    eng = sys.modules.get("app.database.engine") or _eng_mod
    original_engine = eng.engine
    original_factory = eng.AsyncSessionLocal

    eng.engine = test_engine
    eng.AsyncSessionLocal = test_session_factory

    yield

    # Restore originals and dispose the test engine
    eng.engine = original_engine
    eng.AsyncSessionLocal = original_factory
    await test_engine.dispose()


@pytest_asyncio.fixture
async def client():
    """HTTP test client wired to the FastAPI app (no real server)."""
    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
