"""Small process-local rate limiter for externally billed API operations."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Result of one rate-limit check."""

    allowed: bool
    retry_after_seconds: int = 0


class InMemoryRateLimiter:
    """Bound request bursts per client and operation within one API process.

    This deliberately avoids infrastructure for the local MVP. A multi-process public
    deployment should replace it with a shared limiter at the hosting edge.
    """

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._requests: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(
        self,
        *,
        client_id: str,
        operation: str,
        limit: int,
        window_seconds: int = 60,
    ) -> RateLimitDecision:
        """Consume one allowance or return the time until the oldest entry expires."""
        if limit < 1 or window_seconds < 1:
            raise ValueError("Rate-limit values must be positive integers.")

        now = self._clock()
        cutoff = now - window_seconds
        key = (client_id, operation)
        with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= limit:
                retry_after = max(1, int(window_seconds - (now - timestamps[0]) + 0.999))
                return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)
            timestamps.append(now)
            return RateLimitDecision(allowed=True)
