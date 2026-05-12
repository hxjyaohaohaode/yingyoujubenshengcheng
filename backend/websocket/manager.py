import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, project_id: str, websocket: WebSocket):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)
        logger.info(f"WebSocket 连接已建立: project_id={project_id}, 当前连接数={len(self.active_connections[project_id])}")

    def disconnect(self, project_id: str, websocket: WebSocket):
        if project_id in self.active_connections:
            connections = self.active_connections[project_id]
            if websocket in connections:
                connections.remove(websocket)
                logger.info(f"WebSocket 连接已断开: project_id={project_id}, 剩余连接数={len(connections)}")
            if not connections:
                del self.active_connections[project_id]

    async def broadcast_to_project(self, project_id: str, message: dict):
        if project_id not in self.active_connections:
            return
        data = json.dumps(message, ensure_ascii=False)
        disconnected: list[WebSocket] = []
        for websocket in self.active_connections[project_id]:
            try:
                await websocket.send_text(data)
            except Exception:
                disconnected.append(websocket)
        for ws in disconnected:
            self.disconnect(project_id, ws)

    async def send_task_progress(self, project_id: str, task_id: str, progress: int, status: str):
        await self.broadcast_to_project(project_id, {
            "type": "task_progress",
            "task_id": task_id,
            "progress": progress,
            "status": status,
        })

    async def send_agent_update(self, project_id: str, agent_name: str, status: str, current_task: str | None = None):
        await self.broadcast_to_project(project_id, {
            "type": "agent_status",
            "agent_name": agent_name,
            "status": status,
            "current_task": current_task,
        })

    async def send_notification(self, project_id: str, level: str, message: str):
        await self.broadcast_to_project(project_id, {
            "type": "notification",
            "level": level,
            "message": message,
        })

    async def send_data_change(self, project_id: str, change_type: str, entity_id: str, action: str = "updated"):
        await self.broadcast_to_project(project_id, {
            "type": change_type,
            "entity_id": entity_id,
            "action": action,
        })

    async def send_scene_created(self, project_id: str, scene_id: str):
        await self.send_data_change(project_id, "scene_created", scene_id, "created")

    async def send_scene_updated(self, project_id: str, scene_id: str):
        await self.send_data_change(project_id, "scene_updated", scene_id, "updated")

    async def send_scene_deleted(self, project_id: str, scene_id: str):
        await self.send_data_change(project_id, "scene_deleted", scene_id, "deleted")

    async def send_scene_finalized(self, project_id: str, scene_id: str):
        await self.send_data_change(project_id, "scene_finalized", scene_id, "finalized")

    async def send_chapter_created(self, project_id: str, chapter_id: str):
        await self.send_data_change(project_id, "chapter_created", chapter_id, "created")

    async def send_chapter_updated(self, project_id: str, chapter_id: str):
        await self.send_data_change(project_id, "chapter_updated", chapter_id, "updated")

    async def send_chapter_deleted(self, project_id: str, chapter_id: str):
        await self.send_data_change(project_id, "chapter_deleted", chapter_id, "deleted")

    async def send_character_created(self, project_id: str, character_id: str):
        await self.send_data_change(project_id, "character_created", character_id, "created")

    async def send_character_updated(self, project_id: str, character_id: str):
        await self.send_data_change(project_id, "character_updated", character_id, "updated")

    async def send_character_deleted(self, project_id: str, character_id: str):
        await self.send_data_change(project_id, "character_deleted", character_id, "deleted")

    async def send_foreshadow_created(self, project_id: str, foreshadow_id: str):
        await self.send_data_change(project_id, "foreshadow_created", foreshadow_id, "created")

    async def send_foreshadow_updated(self, project_id: str, foreshadow_id: str):
        await self.send_data_change(project_id, "foreshadow_updated", foreshadow_id, "updated")

    async def send_foreshadow_deleted(self, project_id: str, foreshadow_id: str):
        await self.send_data_change(project_id, "foreshadow_deleted", foreshadow_id, "deleted")

    async def send_pipeline_status(self, project_id: str, pipeline_status: str):
        await self.broadcast_to_project(project_id, {
            "type": "pipeline_status",
            "status": pipeline_status,
        })

    async def send_world_config_updated(self, project_id: str, config_key: str):
        await self.broadcast_to_project(project_id, {
            "type": "world_config_updated",
            "config_key": config_key,
        })


ws_manager = WebSocketManager()
