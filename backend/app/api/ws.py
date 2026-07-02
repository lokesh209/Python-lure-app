from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.ws import ws_manager

router = APIRouter()


@router.websocket("/ws/{channel:path}")
async def channel_ws(websocket: WebSocket, channel: str):
    await ws_manager.connect(channel, websocket)
    try:
        while True:
            # Heartbeat read so disconnects are detected promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(channel, websocket)
    except Exception:
        await ws_manager.disconnect(channel, websocket)
