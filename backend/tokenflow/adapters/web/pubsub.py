from __future__ import annotations

import asyncio
import contextlib
import threading
from collections import deque
from typing import Any


class EventBus:
    """In-process pub/sub for SSE fan-out.

    Kept N events for Last-Event-ID replay. Publish happens from the asyncio loop
    (tailer tasks) but is also safe from sync Python code (e.g. repository inserts
    that call ``publish`` directly) via an internal threading.Lock. The subscribe/
    unsubscribe paths additionally take the same lock to prevent a race where a
    publish arrives after the snapshot is taken but before the new subscriber is
    registered, causing a dropped event.
    """

    def __init__(self, buffer_size: int = 100):
        self._buffer_size = buffer_size
        self._buffer: deque[tuple[int, dict[str, Any]]] = deque(maxlen=buffer_size)
        self._seq = 0
        self._subscribers: set[asyncio.Queue[tuple[int, dict[str, Any]]]] = set()
        self._lock = threading.Lock()

    def publish(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._seq += 1
            entry = (self._seq, payload)
            self._buffer.append(entry)
            subscribers = list(self._subscribers)
        for q in subscribers:
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(entry)

    async def subscribe(self, last_event_id: int = 0) -> asyncio.Queue[tuple[int, dict[str, Any]]]:
        q: asyncio.Queue[tuple[int, dict[str, Any]]] = asyncio.Queue(maxsize=256)
        # Atomic under _lock: register first, then drain the current buffer.
        # Any publish that happens after we add to _subscribers will deliver to q;
        # anything already in _buffer is replayed below. No gap, no duplicates.
        with self._lock:
            self._subscribers.add(q)
            snapshot = list(self._buffer)
        for eid, payload in snapshot:
            if eid > last_event_id:
                with contextlib.suppress(asyncio.QueueFull):
                    q.put_nowait((eid, payload))
        return q

    async def unsubscribe(self, q: asyncio.Queue[tuple[int, dict[str, Any]]]) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def last_seq(self) -> int:
        with self._lock:
            return self._seq
