from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..ws import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/analysis/{analysis_id}")
async def analysis_socket(websocket: WebSocket, analysis_id: str) -> None:
    await manager.connect(analysis_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(analysis_id, websocket)
