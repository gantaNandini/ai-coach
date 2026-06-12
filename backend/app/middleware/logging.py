"""
logging.py — Structured access-log middleware.

In development: logs a compact human-readable line.
In production (ENVIRONMENT != "development"): logs a JSON object so log
aggregators (Datadog, CloudWatch, Loki, etc.) can parse fields directly.

Fields logged per request:
  request_id   — UUID injected by RequestIDMiddleware
  user_id      — extracted from the JWT Bearer token (if present and valid)
  method       — HTTP method
  path         — URL path (no query string)
  status       — response status code
  duration_ms  — wall-clock time to first byte of response
  ip           — client IP address
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("ai_coach.access")


def _extract_user_id(request: Request) -> Optional[str]:
    """
    Try to decode the JWT and return the subject (user_id) without
    raising — this is a best-effort enrichment for access logs.
    """
    try:
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return None
        token = auth.split(" ", 1)[1]
        from app.core.config import settings
        from jose import jwt
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},  # don't fail on expired tokens in logger
        )
        return payload.get("sub")
    except Exception:
        return None


class LoggingMiddleware(BaseHTTPMiddleware):
    """Emit one log record per HTTP request with key observability fields."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = int((time.perf_counter() - start) * 1000)

        request_id: str = getattr(request.state, "request_id", "-")
        user_id: Optional[str] = _extract_user_id(request)
        ip: str = (request.client.host if request.client else "unknown")

        from app.core.config import settings as _settings
        if getattr(_settings, "ENVIRONMENT", "development") != "development":
            # JSON format for production log aggregators
            record = json.dumps(
                {
                    "request_id": request_id,
                    "user_id": user_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "ip": ip,
                },
                default=str,
            )
            logger.info(record)
        else:
            # Human-friendly format for local development
            uid_part = f" uid={user_id}" if user_id else ""
            logger.info(
                "%s %s %s %dms rid=%s%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                request_id,
                uid_part,
            )

        return response
