import json
import logging
import uuid
from datetime import UTC, datetime

from config import REDIS_URL

logger = logging.getLogger(__name__)

_CELERY_AVAILABLE = False
celery_app = None


def _safe_task_decorator(bind=True, **kwargs):
    def decorator(func):
        if _CELERY_AVAILABLE and celery_app is not None:
            return celery_app.task(bind=bind, **kwargs)(func)
        func._is_task = True
        func._bind = bind
        return func
    return decorator


try:
    from celery import Celery
    from redis import Redis

    _test_redis = Redis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=3)
    _test_redis.ping()
    _test_redis.close()

    celery_app = Celery(
        "script_engine",
        broker=REDIS_URL,
        backend=REDIS_URL,
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=600,
        task_soft_time_limit=540,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_default_queue="script_engine",
        task_routes={
            "tasks.scene_generation.generate_scene_task": {"queue": "script_engine"},
            "tasks.scene_audit.audit_scene_task": {"queue": "script_engine"},
            "tasks.full_audit.full_audit_task": {"queue": "script_engine"},
            "tasks.foreshadow_design.foreshadow_design_task": {"queue": "script_engine"},
            "tasks.maintenance.reconcile_stale_tasks": {"queue": "script_engine"},
        },
        beat_schedule={
            "reconcile-stale-agent-tasks": {
                "task": "tasks.maintenance.reconcile_stale_tasks",
                "schedule": 300.0,
            },
        },
    )
    _CELERY_AVAILABLE = True
    logger.info("Celery + Redis available, async task mode enabled")
except Exception:
    logger.warning("Redis/Celery unavailable, using synchronous task mode")
    _CELERY_AVAILABLE = False


TASK_PROGRESS: dict[str, dict] = {}
PROGRESS_TTL_SECONDS = 3600
_progress_store = None
_progress_store_failed = False


def _progress_key(task_id: str) -> str:
    return f"task_progress:{task_id}"


def _get_progress_store():
    global _progress_store, _progress_store_failed
    if _progress_store_failed:
        return None
    if _progress_store is None:
        try:
            from redis import Redis
            _progress_store = Redis.from_url(REDIS_URL, decode_responses=True)
            _progress_store.ping()
        except Exception:
            logger.warning("Redis progress store unavailable, fallback to in-memory progress")
            _progress_store_failed = True
            _progress_store = None
    return _progress_store


def _persist_progress(payload: dict) -> None:
    store = _get_progress_store()
    if store is None:
        return
    try:
        store.setex(
            _progress_key(payload["task_id"]),
            PROGRESS_TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False),
        )
    except Exception:
        logger.warning("Failed to persist task progress to Redis")


def _load_progress(task_id: str) -> dict | None:
    store = _get_progress_store()
    if store is None:
        return None
    try:
        raw = store.get(_progress_key(task_id))
    except Exception:
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def update_progress(task_id: str, progress: int, status: str, message: str = "",
                    agent_name: str | None = None, task_name: str | None = None):
    payload = {
        "task_id": task_id,
        "progress": min(progress, 100),
        "status": status,
        "message": message,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if agent_name:
        payload["agent_name"] = agent_name
    if task_name:
        payload["task_name"] = task_name
    TASK_PROGRESS[task_id] = payload
    _persist_progress(payload)


def get_progress(task_id: str) -> dict:
    progress = _load_progress(task_id)
    if progress:
        TASK_PROGRESS[task_id] = progress
        return progress
    return TASK_PROGRESS.get(task_id, {
        "task_id": task_id,
        "progress": 0,
        "status": "unknown",
        "message": "任务未找到",
    })


try:
    from websocket.manager import ws_manager
except ImportError:
    ws_manager = None


def push_progress_via_ws(project_id: str, task_id: str, progress: int, status: str, message: str = "",
                         agent_name: str | None = None, task_name: str | None = None):
    if ws_manager is None:
        return
    try:
        import asyncio
        payload = {
            "type": "task_progress",
            "project_id": project_id,
            "task_id": task_id,
            "progress": progress,
            "status": status,
            "message": message,
        }
        if agent_name:
            payload["agent_name"] = agent_name
        if task_name:
            payload["task_name"] = task_name
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(ws_manager.broadcast_to_project(project_id, payload))
        except RuntimeError:
            asyncio.run(ws_manager.broadcast_to_project(project_id, payload))
    except Exception:
        logger.debug("WebSocket push failed (non-critical)")


def update_agent_task_status(project_id: str, task_id: str, task_type: str, agent_name: str, status: str):
    from database import get_db_sync
    from models.agent_task import AgentTask
    with get_db_sync() as db:
        now = datetime.now(UTC)
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if task:
            task.project_id = project_id
            task.task_type = task_type
            task.assigned_to = agent_name
            task.status = status
            task.started_at = task.started_at or now
        else:
            db.add(AgentTask(
                id=task_id, project_id=project_id, task_type=task_type,
                assigned_to=agent_name, status=status, priority=5,
                payload={}, started_at=now,
            ))
        db.commit()


def complete_agent_task(project_id: str, task_id: str, result: dict):
    from database import get_db_sync
    from models.agent_task import AgentTask
    with get_db_sync() as db:
        at = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if at:
            at.status = "completed"
            at.result = result
            at.completed_at = datetime.now(UTC)
            at.error_message = None
            db.commit()


def fail_agent_task(project_id: str, task_id: str, error_message: str):
    from database import get_db_sync
    from models.agent_task import AgentTask
    with get_db_sync() as db:
        at = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if at:
            at.status = "failed"
            at.error_message = error_message
            at.retry_count = (at.retry_count or 0) + 1
            at.completed_at = datetime.now(UTC)
            db.commit()


def mark_agent_task_retrying(project_id: str, task_id: str, error_message: str):
    from database import get_db_sync
    from models.agent_task import AgentTask
    with get_db_sync() as db:
        at = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if at:
            at.status = "retrying"
            at.error_message = error_message
            at.retry_count = (at.retry_count or 0) + 1
            db.commit()


def mark_agent_task_timeout(task_id: str, error_message: str):
    from database import get_db_sync
    from models.agent_task import AgentTask
    with get_db_sync() as db:
        at = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if at:
            at.status = "timeout"
            at.error_message = error_message
            at.completed_at = datetime.now(UTC)
            db.commit()


import asyncio


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def get_db_async():
    from database import async_session_factory
    return async_session_factory()


def _run_sync_task(func, task_id: str, kwargs: dict):
    try:
        func(_SyncSelf(task_id), **kwargs)
    except Exception as e:
        logger.error("Sync task %s failed: %s", task_id, e, exc_info=True)


class _SyncSelf:
    def __init__(self, task_id: str):
        self.request = _SyncRequest(task_id)


class _SyncRequest:
    def __init__(self, task_id: str):
        self.id = task_id
        self.retries = 0


def submit_task(func, task_id: str, kwargs: dict):
    if _CELERY_AVAILABLE and celery_app is not None:
        try:
            func.apply_async(task_id=task_id, kwargs=kwargs)
            return
        except Exception:
            logger.warning("Celery dispatch failed, falling back to sync mode")

    import threading
    thread = threading.Thread(
        target=_run_sync_task,
        args=(func, task_id, kwargs),
        daemon=True,
    )
    thread.start()


def is_celery_available() -> bool:
    return _CELERY_AVAILABLE
