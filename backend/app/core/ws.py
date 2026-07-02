"""Lightweight per-project WebSocket fan-out for progress events."""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WSManager:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, channel: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._channels[channel].add(ws)

    async def disconnect(self, channel: str, ws: WebSocket) -> None:
        async with self._lock:
            self._channels[channel].discard(ws)

    async def broadcast(self, channel: str, payload: dict[str, Any]) -> None:
        msg = json.dumps(payload)
        dead: list[WebSocket] = []
        for ws in list(self._channels.get(channel, ())):
            try:
                await asyncio.wait_for(ws.send_text(msg), timeout=2.0)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._channels[channel].discard(ws)


ws_manager = WSManager()
