"""
rate_limiter.py — Per-endpoint rate limiting utilities.

Used by auth endpoints for brute-force protection.
In-process store — replace with Redis in multi-instance deployments.
"""
from __future__ import annotations
import time
from collections import defaultdict
from fastapi import HTTPException, Request

_store: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, limit: int, window: int = 60) -> None:
    """
    Raises HTTP 429 if key exceeds limit requests within window seconds.
    key should be e.g. f"login:{ip}" or f"register:{ip}"
    """
    now = time.time()
    cutoff = now - window
    _store[key] = [t for t in _store[key] if t > cutoff]
    if len(_store[key]) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait before trying again.",
            headers={"Retry-After": str(window)},
        )
    _store[key].append(now)
