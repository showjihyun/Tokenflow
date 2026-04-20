from __future__ import annotations

import asyncio
import threading

import pytest

from tokenflow.adapters.web.pubsub import EventBus
from tokenflow.adapters.web.routes.events import _as_ticker


@pytest.mark.asyncio
async def test_subscribe_receives_buffered_events_above_last_id() -> None:
    bus = EventBus(buffer_size=10)
    bus.publish({"n": 1})
    bus.publish({"n": 2})
    bus.publish({"n": 3})

    q = await bus.subscribe(last_event_id=1)
    # Should see events 2 and 3 but not 1
    e2 = q.get_nowait()
    e3 = q.get_nowait()
    assert e2 == (2, {"n": 2})
    assert e3 == (3, {"n": 3})
    assert q.empty()


@pytest.mark.asyncio
async def test_publish_fans_out_to_all_subscribers() -> None:
    bus = EventBus(buffer_size=10)
    q1 = await bus.subscribe()
    q2 = await bus.subscribe()
    bus.publish({"msg": "hello"})
    assert q1.get_nowait() == (1, {"msg": "hello"})
    assert q2.get_nowait() == (1, {"msg": "hello"})


@pytest.mark.asyncio
async def test_no_events_dropped_between_snapshot_and_register() -> None:
    """Regression: subscribe must atomically register + snapshot so a publish
    racing with subscribe is delivered either via replay OR directly — never dropped."""
    bus = EventBus(buffer_size=100)
    # Hammer from a background thread while subscribing repeatedly.
    stop = threading.Event()

    def publisher() -> None:
        i = 0
        while not stop.is_set():
            bus.publish({"n": i})
            i += 1

    t = threading.Thread(target=publisher, daemon=True)
    t.start()
    try:
        # Race: subscribe, immediately check we get events.
        for _ in range(5):
            q = await bus.subscribe()
            # Give the publisher a moment so at least one event lands after register.
            await asyncio.sleep(0.01)
            assert q.qsize() > 0, "subscriber received no events despite live publish"
    finally:
        stop.set()
        t.join(timeout=2)


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery() -> None:
    bus = EventBus(buffer_size=10)
    q = await bus.subscribe()
    bus.publish({"n": 1})
    await bus.unsubscribe(q)
    bus.publish({"n": 2})  # should NOT reach q
    # Drain: only the first event should be there.
    assert q.get_nowait() == (1, {"n": 1})
    assert q.empty()


@pytest.mark.asyncio
async def test_buffer_ringbuffer_semantics() -> None:
    bus = EventBus(buffer_size=3)
    for i in range(5):
        bus.publish({"n": i})
    # Newcomer only sees last 3 events (ids 3, 4, 5)
    q = await bus.subscribe()
    assert q.get_nowait() == (3, {"n": 2})
    assert q.get_nowait() == (4, {"n": 3})
    assert q.get_nowait() == (5, {"n": 4})
    assert q.empty()


def test_ticker_uses_stable_event_id() -> None:
    ticker = _as_ticker({"kind": "waste-detected", "severity": "high", "waste_kind": "tool-loop"}, event_id=42)
    assert ticker is not None
    assert ticker["id"] == 42
