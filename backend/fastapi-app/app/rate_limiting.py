"""Sliding-window rate limiter for write endpoints.

Keyed by client IP address.  Counter resets on process restart — no Redis
required for the MVP (single Railway instance, small curator team).

Exposed as a FastAPI ``Depends`` so tests can override it per test:
    ``app.dependency_overrides[import_rate_limit] = lambda: None``

Limit enforced: POST /api/v1/imports — 10 uploads per minute per IP.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status

_WINDOW_SECONDS: int = 60
_MAX_CALLS: int = 10

_window: dict[str, list[float]] = defaultdict(list)
_lock: Lock = Lock()


def _within_limit(key: str) -> bool:
    """Return True if the caller is within the sliding-window limit."""
    now = time.monotonic()
    cutoff = now - _WINDOW_SECONDS
    with _lock:
        timestamps = [t for t in _window[key] if t > cutoff]
        if len(timestamps) >= _MAX_CALLS:
            _window[key] = timestamps
            return False
        timestamps.append(now)
        _window[key] = timestamps
        return True


def import_rate_limit(request: Request) -> None:
    """FastAPI dependency — raises HTTP 429 after 10 import uploads per minute."""
    key = request.client.host if request.client else "anon"
    if not _within_limit(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: max 10 file uploads per minute.",
        )
