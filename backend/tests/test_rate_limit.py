"""Tests for process-local protection of externally billed operations."""

from pathlib import Path

import pytest
from app.core.config import Settings
from app.core.rate_limit import InMemoryRateLimiter
from app.main import create_app
from fastapi.testclient import TestClient


def test_rate_limiter_blocks_then_recovers_after_window() -> None:
    now = 100.0
    limiter = InMemoryRateLimiter(clock=lambda: now)

    assert limiter.check(client_id="client", operation="ask", limit=2).allowed
    assert limiter.check(client_id="client", operation="ask", limit=2).allowed
    blocked = limiter.check(client_id="client", operation="ask", limit=2)
    assert not blocked.allowed
    assert blocked.retry_after_seconds == 60

    now = 161.0
    assert limiter.check(client_id="client", operation="ask", limit=2).allowed


def test_rate_limiter_isolates_clients_and_operations() -> None:
    limiter = InMemoryRateLimiter(clock=lambda: 100.0)

    assert limiter.check(client_id="first", operation="ask", limit=1).allowed
    assert limiter.check(client_id="second", operation="ask", limit=1).allowed
    assert limiter.check(client_id="first", operation="refresh", limit=1).allowed


@pytest.mark.parametrize(("limit", "window"), [(0, 60), (1, 0)])
def test_rate_limiter_rejects_invalid_policy(limit: int, window: int) -> None:
    limiter = InMemoryRateLimiter()

    with pytest.raises(ValueError, match="positive integers"):
        limiter.check(
            client_id="client",
            operation="ask",
            limit=limit,
            window_seconds=window,
        )


def test_ask_endpoint_returns_retry_after_when_limit_is_exhausted(tmp_path: Path) -> None:
    settings = Settings(
        REGLENS_DATABASE_PATH=tmp_path / "rate-limit.db",
        REGLENS_DATA_PROVIDER="fixture",
        REGLENS_ASK_RATE_LIMIT=1,
        OPENROUTER_API_KEY=None,
    )

    with TestClient(create_app(settings)) as client:
        first = client.post("/api/ask", json={"question": "Which drink has least caffeine?"})
        second = client.post("/api/ask", json={"question": "Which drink has least caffeine?"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"] == "60"
