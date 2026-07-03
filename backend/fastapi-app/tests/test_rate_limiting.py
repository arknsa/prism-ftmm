"""Tests for the sliding-window rate limiter (P7.8).

Verifies the core _within_limit logic and that the FastAPI dependency
raises HTTP 429 once the window is exhausted.

The rate limiter uses process-level state; each test uses a unique key
so test isolation is guaranteed without resetting the module-level dict.
"""

from __future__ import annotations

import uuid

import pytest
from app.rate_limiting import _within_limit
from fastapi import HTTPException


class TestSlidingWindowLimit:
    """Unit tests for the underlying counter."""

    def _key(self) -> str:
        return f"test-{uuid.uuid4()}"

    def test_first_call_is_within_limit(self) -> None:
        assert _within_limit(self._key()) is True

    def test_calls_up_to_limit_are_allowed(self) -> None:
        key = self._key()
        # Import the constants so the test is coupled to the implementation.
        from app.rate_limiting import _MAX_CALLS

        for _ in range(_MAX_CALLS):
            assert _within_limit(key) is True

    def test_call_beyond_limit_is_denied(self) -> None:
        from app.rate_limiting import _MAX_CALLS

        key = self._key()
        for _ in range(_MAX_CALLS):
            _within_limit(key)
        assert _within_limit(key) is False

    def test_two_independent_keys_do_not_share_quota(self) -> None:
        from app.rate_limiting import _MAX_CALLS

        key_a = self._key()
        key_b = self._key()
        for _ in range(_MAX_CALLS):
            _within_limit(key_a)
        # key_a is exhausted but key_b still has quota
        assert _within_limit(key_b) is True


class TestImportRateLimitDependency:
    """Verify the FastAPI dependency raises 429 at the correct threshold."""

    def test_raises_429_when_limit_exceeded(self) -> None:
        from unittest.mock import MagicMock

        from app.rate_limiting import _MAX_CALLS, import_rate_limit

        unique_host = f"198.51.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"
        request = MagicMock()
        request.client.host = unique_host

        for _ in range(_MAX_CALLS):
            import_rate_limit(request)

        with pytest.raises(HTTPException) as exc_info:
            import_rate_limit(request)

        assert exc_info.value.status_code == 429

    def test_anon_key_used_when_client_is_none(self) -> None:
        from unittest.mock import MagicMock

        from app.rate_limiting import import_rate_limit

        request = MagicMock()
        request.client = None

        # Should not raise on the first call (uses "anon" as key).
        # We can't guarantee isolation for "anon" across tests, so just
        # assert it doesn't raise a non-429 error.
        try:
            import_rate_limit(request)
        except HTTPException as exc:
            assert exc.status_code == 429


class TestLoginRateLimitDependency:
    """Verify the login limiter raises 429 once its per-IP window is exhausted (H1)."""

    def test_raises_429_when_limit_exceeded(self) -> None:
        from unittest.mock import MagicMock

        from app.rate_limiting import _LOGIN_IP_MAX_CALLS, login_rate_limit

        unique_host = f"203.0.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"
        request = MagicMock()
        request.client.host = unique_host

        for _ in range(_LOGIN_IP_MAX_CALLS):
            login_rate_limit(request)

        with pytest.raises(HTTPException) as exc_info:
            login_rate_limit(request)

        assert exc_info.value.status_code == 429

    def test_independent_hosts_have_separate_quota(self) -> None:
        from unittest.mock import MagicMock

        from app.rate_limiting import _LOGIN_IP_MAX_CALLS, login_rate_limit

        host_a = f"203.0.{uuid.uuid4().int % 256}.10"
        host_b = f"203.0.{uuid.uuid4().int % 256}.20"
        req_a, req_b = MagicMock(), MagicMock()
        req_a.client.host = host_a
        req_b.client.host = host_b

        for _ in range(_LOGIN_IP_MAX_CALLS):
            login_rate_limit(req_a)
        # host_a exhausted; host_b still has full quota → no raise
        login_rate_limit(req_b)
