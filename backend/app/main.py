from __future__ import annotations
import logging
import time
from contextlib import asynccontextmanager
from collections import defaultdict

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.middleware.logging import LoggingMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.tenant import TenantContextMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── Rate limiting store (in-process, per-IP) ──────────────────────────────────
_rate_store: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 60   # seconds
_RATE_LIMIT   = 200  # requests per window (generous for dev; tighten in prod)
_AUTH_LIMIT   = 20   # strict limit on auth endpoints


def _check_rate_limit(ip: str, limit: int) -> bool:
    """Returns True if request is allowed, False if rate-limited."""
    now = time.time()
    window_start = now - _RATE_WINDOW
    timestamps = _rate_store[ip]
    # Purge old timestamps
    _rate_store[ip] = [t for t in timestamps if t > window_start]
    if len(_rate_store[ip]) >= limit:
        return False
    _rate_store[ip].append(now)
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.startup import run_startup_checks
    await run_startup_checks()
    logger.info("✓ %s v%s ready", settings.APP_NAME, settings.APP_VERSION)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI Coach Platform — Extensible multi-tenant coaching with RAG knowledge base. "
        "Authentication required for all /api/v1/* endpoints."
    ),
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    redirect_slashes=False,
)

# ── Middleware (order matters — outermost first) ───────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


# ── Rate limiting middleware ───────────────────────────────────────────────────
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next) -> Response:
    ip = request.client.host if request.client else "unknown"
    path = request.url.path

    # Strict rate limit on auth endpoints
    if path.startswith("/api/v1/auth/"):
        if not _check_rate_limit(f"auth:{ip}", _AUTH_LIMIT):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait before trying again."},
                headers={"Retry-After": str(_RATE_WINDOW)},
            )
    else:
        if not _check_rate_limit(ip, _RATE_LIMIT):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait before trying again."},
                headers={"Retry-After": str(_RATE_WINDOW)},
            )

    return await call_next(request)


# ── Exception handlers ─────────────────────────────────────────────────────────
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(JWTError)
async def jwt_error_handler(request: Request, exc: JWTError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": "Invalid or expired token."},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )


# ── Routes ─────────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["health"])
async def health_check():
    """Basic liveness check — returns 200 if app is running."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME,
    }


@app.get("/health/detailed", tags=["health"])
async def health_detailed():
    """
    Detailed component health — database, pgvector, ollama, embeddings.
    Use this endpoint to diagnose startup issues.
    """
    from app.core.startup import startup_status
    all_ok = (
        startup_status.get("database") == "ok"
        and startup_status.get("ready") is True
    )
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "healthy" if all_ok else "degraded",
            "components": {
                "database": startup_status.get("database", "unknown"),
                "pgvector": startup_status.get("pgvector", "unknown"),
                "ollama": startup_status.get("ollama", "unknown"),
                "embeddings": startup_status.get("embeddings", "unknown"),
            },
            "version": settings.APP_VERSION,
            "rag_enabled": startup_status.get("pgvector") == "ok",
            "ai_enabled": startup_status.get("ollama", "").startswith("ok"),
        },
    )
