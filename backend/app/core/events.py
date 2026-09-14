from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class EventBus:
    """In-process pub/sub for SSE/WebSocket fan-out."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, channel: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._subscribers[channel].add(queue)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue) -> None:
        self._subscribers[channel].discard(queue)

    async def publish(self, channel: str, payload: dict[str, Any]) -> None:
        dead: list[asyncio.Queue] = []
        for queue in list(self._subscribers[channel]):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    dead.append(queue)
        for queue in dead:
            self._subscribers[channel].discard(queue)


event_bus = EventBus()
