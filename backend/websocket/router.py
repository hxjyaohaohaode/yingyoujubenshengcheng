import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from websocket.manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_INTERVAL = 30


async def _send_pipeline_state_on_connect(project_id: str, websocket: WebSocket):
    try:
        from database import async_session_factory
        from core.pipeline.state_machine import PipelineStateMachine, PipelineStatus

        async with async_session_factory() as db:
            sm = PipelineStateMachine(db)
            state = await sm.get_state(project_id)
            if not state:
                return

            from core.pipeline.template_loader import get_template as _get_tpl
            phases_info = []
            if state.template_name:
                try:
                    tpl = _get_tpl(state.template_name)
                    phases_info = [{"name": p.name, "steps": len(p.steps), "human_gate": p.human_gate} for p in tpl.phases]
                except Exception:
                    pass

            await websocket.send_json({
                "type": "pipeline_progress",
                "phase": "",
                "phase_index": state.current_phase_index,
                "step_index": state.current_step_index,
                "total_steps": 0,
                "agent": "系统",
                "skill": "",
                "status": state.status.value,
                "message": state.error_message or f"重连同步：当前状态为 {state.status.value}",
                "progress": 0,
                "phases": phases_info,
                "total_phases": len(phases_info),
                "reconnect_sync": True,
            })
    except Exception as e:
        logger.warning("重连状态同步失败: project_id=%s, error=%s", project_id, e)


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
        await _send_pipeline_state_on_connect(project_id, websocket)
        heartbeat_task = asyncio.create_task(send_heartbeat())
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "pong":
                pass
            elif data.get("type") == "request_state":
                await _send_pipeline_state_on_connect(project_id, websocket)
    except WebSocketDisconnect:
        logger.info(f"客户端主动断开: project_id={project_id}")
    except Exception as e:
        logger.warning(f"WebSocket 异常: project_id={project_id}, error={e}")
    finally:
        if heartbeat_task:
            heartbeat_task.cancel()
        ws_manager.disconnect(project_id, websocket)
