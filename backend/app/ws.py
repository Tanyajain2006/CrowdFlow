import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, analysis_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(analysis_id, set()).add(websocket)

    def disconnect(self, analysis_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(analysis_id)
        if connections:
            connections.discard(websocket)
            if not connections:
                self._connections.pop(analysis_id, None)

    async def broadcast(self, analysis_id: str, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for websocket in self._connections.get(analysis_id, set()):
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(analysis_id, websocket)


manager = ConnectionManager()

