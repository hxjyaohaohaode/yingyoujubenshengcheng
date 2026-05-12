import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from websocket.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_INTERVAL = 30


@router.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await ws_manager.connect(project_id, websocket)
    heartbeat_task = None

    async def send_heartbeat():
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                try:
                    await websocket.send_json({"type": "heartbeat", "ts": __import__("time").time()})
                except Exception:
                    break
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    try:
        heartbeat_task = asyncio.create_task(send_heartbeat())
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "pong":
                pass
    except WebSocketDisconnect:
        logger.info(f"客户端主动断开: project_id={project_id}")
    except Exception as e:
        logger.warning(f"WebSocket 异常: project_id={project_id}, error={e}")
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
        ws_manager.disconnect(project_id, websocket)
