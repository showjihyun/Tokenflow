"""Tiny in-memory token-bucket rate limiter for local-only routes.

No external dep (slowapi / limits) — we don't need distributed fairness since
the API is single-process and loopback-bound. Thread-safe via a threading.Lock
so both FastAPI worker threads and background tasks can share the state.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class TokenBucketLimiter:
    def __init__(self, *, rate_per_min: float, burst: int | None = None) -> None:
        self._rate_per_sec = rate_per_min / 60.0
        self._capacity = float(burst if burst is not None else max(1, int(rate_per_min)))
        self._buckets: dict[str, _Bucket] = defaultdict(
            lambda: _Bucket(tokens=self._capacity, last_refill=time.monotonic())
        )
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds). Consumes a token on success."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            elapsed = now - bucket.last_refill
            bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._rate_per_sec)
            bucket.last_refill = now
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                return True, 0.0
            # Seconds until the next whole token refills.
            missing = 1.0 - bucket.tokens
            return False, missing / self._rate_per_sec


def make_dependency(
    limiter: TokenBucketLimiter,
    *,
    key_fn: Callable[[Request], str] | None = None,
) -> Callable[[Request], None]:
    """Build a FastAPI dependency that raises 429 when the bucket is empty.

    Default key is the client host; on loopback this is effectively a global limit
    per route which is what we want (single-user local tool).
    """

    def _key(req: Request) -> str:
        if key_fn is not None:
            return key_fn(req)
        client = req.client
        return client.host if client else "unknown"

    def _check(request: Request) -> None:
        ok, retry_after = limiter.check(_key(request))
        if ok:
            return
        raise HTTPException(
            status_code=429,
            detail=f"Too Many Requests. Retry in {retry_after:.1f}s.",
            headers={"Retry-After": str(max(1, int(retry_after + 0.5)))},
        )

    return _check


# Shared limiters for expensive LLM-backed routes. 10 req/min is a sensible
# floor for a solo dev — fast enough for iterative use, slow enough to catch
# runaway loops or buggy clients.
coach_limiter = TokenBucketLimiter(rate_per_min=10, burst=3)
better_prompt_limiter = TokenBucketLimiter(rate_per_min=10, burst=3)
