from tasks._helpers import (
    celery_app,
    _safe_task_decorator,
    update_progress,
    get_progress,
    TASK_PROGRESS,
    push_progress_via_ws,
    update_agent_task_status,
    complete_agent_task,
    fail_agent_task,
    mark_agent_task_retrying,
    mark_agent_task_timeout,
    run_async,
    get_db_async,
    submit_task,
    is_celery_available,
)

__all__ = [
    "celery_app",
    "_safe_task_decorator",
    "update_progress",
    "get_progress",
    "TASK_PROGRESS",
    "push_progress_via_ws",
    "update_agent_task_status",
    "complete_agent_task",
    "fail_agent_task",
    "mark_agent_task_retrying",
    "mark_agent_task_timeout",
    "run_async",
    "get_db_async",
    "submit_task",
    "is_celery_available",
]


def __getattr__(name):
    _lazy_map = {
        "generate_scene_task": ".scene_generation",
        "audit_scene_task": ".scene_audit",
        "full_audit_task": ".full_audit",
        "foreshadow_design_task": ".foreshadow_design",
        "reconcile_stale_tasks": ".maintenance",
    }
    if name in _lazy_map:
        import importlib
        mod = importlib.import_module(_lazy_map[name], package="tasks")
        return getattr(mod, name)
    raise AttributeError(f"module 'tasks' has no attribute {name!r}")
