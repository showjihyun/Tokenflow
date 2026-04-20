from __future__ import annotations

import time

from tokenflow.adapters.web.rate_limit import TokenBucketLimiter


def test_bucket_allows_up_to_burst() -> None:
    b = TokenBucketLimiter(rate_per_min=60, burst=3)
    for _ in range(3):
        ok, _ = b.check("k")
        assert ok
    ok, retry = b.check("k")
    assert not ok
    assert retry > 0


def test_bucket_refills_over_time() -> None:
    b = TokenBucketLimiter(rate_per_min=6000, burst=1)  # 100/sec
    ok1, _ = b.check("k")
    assert ok1
    ok2, _ = b.check("k")
    assert not ok2
    time.sleep(0.025)
    ok3, _ = b.check("k")
    assert ok3


def test_bucket_isolates_keys() -> None:
    b = TokenBucketLimiter(rate_per_min=6, burst=1)
    ok_a, _ = b.check("a")
    ok_b, _ = b.check("b")
    assert ok_a and ok_b
    ok_a2, _ = b.check("a")
    assert not ok_a2
