import logging
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

async def notify_data_changed(project_id: str, change_type: str):
    try:
        from websocket.manager import ws_manager
        await ws_manager.broadcast_to_project(str(project_id), {
            "type": change_type,
            "project_id": str(project_id),
            "timestamp": datetime.now(UTC).isoformat(),
        })
        await ws_manager.broadcast_to_project(str(project_id), {
            "type": "data_sync_required",
            "change_type": change_type,
            "project_id": str(project_id),
            "timestamp": datetime.now(UTC).isoformat(),
        })
    except Exception as e:
        logger.warning(f"notify_data_changed failed: {e}")
