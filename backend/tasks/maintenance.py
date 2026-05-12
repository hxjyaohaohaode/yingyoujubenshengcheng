import logging
from datetime import UTC, datetime, timedelta

from tasks._helpers import _safe_task_decorator as task_decorator, mark_agent_task_timeout, push_progress_via_ws, update_progress

logger = logging.getLogger(__name__)


@task_decorator(name="tasks.maintenance.reconcile_stale_tasks")
def reconcile_stale_tasks():
    from database import get_db_sync
    from models.agent_task import AgentTask

    now = datetime.now(UTC)
    queued_deadline = now - timedelta(minutes=10)
    running_deadline = now - timedelta(minutes=30)
    reconciled = []

    with get_db_sync() as db:
        queued_tasks = db.query(AgentTask).filter(
            AgentTask.status == "queued",
            AgentTask.created_at < queued_deadline,
        ).all()
        active_tasks = db.query(AgentTask).filter(
            AgentTask.status.in_(["running", "retrying"]),
            AgentTask.started_at.isnot(None),
            AgentTask.started_at < running_deadline,
        ).all()

        for task in [*queued_tasks, *active_tasks]:
            mark_agent_task_timeout(str(task.id), "任务长时间未完成，已自动标记超时")
            update_progress(
                str(task.id),
                0,
                "timeout",
                "任务长时间未完成，已自动标记超时",
                agent_name=task.assigned_to,
            )
            push_progress_via_ws(
                str(task.project_id),
                str(task.id),
                0,
                "timeout",
                "任务长时间未完成，已自动标记超时",
                agent_name=task.assigned_to,
            )
            reconciled.append(str(task.id))

    if reconciled:
        logger.warning("Reconciled stale tasks: %s", ", ".join(reconciled))

    return {"reconciled": reconciled, "count": len(reconciled)}
