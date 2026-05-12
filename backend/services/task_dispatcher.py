import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent_task import AgentTask

TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled", "timeout"}

TASK_DEFINITIONS = {
    "scene_generation": {
        "task_path": "tasks.scene_generation.generate_scene_task",
        "agent_name": "创作Agent",
        "task_name": "场景生成",
        "estimated_time": "预计 8-15 秒",
    },
    "scene_audit": {
        "task_path": "tasks.scene_audit.audit_scene_task",
        "agent_name": "审计Agent",
        "task_name": "场景审计",
        "estimated_time": "预计 5-10 秒",
    },
    "foreshadow_design": {
        "task_path": "tasks.foreshadow_design.foreshadow_design_task",
        "agent_name": "伏笔Agent",
        "task_name": "伏笔体系设计",
        "estimated_time": "预计 15-30 秒",
    },
    "full_audit": {
        "task_path": "tasks.full_audit.full_audit_task",
        "agent_name": "审计Agent",
        "task_name": "全项目审计",
        "estimated_time": "预计 30-60 秒",
    },
}


def _get_task_callable(task_type: str):
    from tasks import audit_scene_task, foreshadow_design_task, full_audit_task, generate_scene_task

    task_map = {
        "scene_generation": generate_scene_task,
        "scene_audit": audit_scene_task,
        "foreshadow_design": foreshadow_design_task,
        "full_audit": full_audit_task,
    }
    if task_type not in task_map:
        raise ValueError(f"未知任务类型: {task_type}")
    return task_map[task_type]


async def enqueue_task(
    db: AsyncSession,
    *,
    project_id: str,
    task_type: str,
    payload: dict,
    task_kwargs: dict,
    priority: int = 5,
) -> dict:
    meta = TASK_DEFINITIONS.get(task_type)
    if meta is None:
        raise HTTPException(status_code=400, detail=f"不支持的任务类型: {task_type}")

    task_callable = _get_task_callable(task_type)
    task_id = str(uuid.uuid4())
    task_kwargs = {**task_kwargs, "task_id": task_id}

    task_record = AgentTask(
        id=task_id,
        project_id=project_id,
        task_type=task_type,
        assigned_to=meta["agent_name"],
        status="queued",
        priority=priority,
        payload=payload,
        created_at=datetime.now(UTC),
    )
    db.add(task_record)

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail=f"任务落库失败: {str(exc)[:200]}") from exc

    from tasks import submit_task, push_progress_via_ws, update_progress

    try:
        submit_task(task_callable, task_id, task_kwargs)
    except Exception as exc:
        task_record.status = "failed"
        task_record.error_message = f"任务派发失败: {str(exc)[:200]}"
        task_record.completed_at = datetime.now(UTC)
        await db.commit()
        raise HTTPException(status_code=503, detail=task_record.error_message) from exc

    update_progress(
        task_id,
        0,
        "queued",
        f"{meta['task_name']}已入队，等待执行",
        agent_name=meta["agent_name"],
        task_name=meta["task_name"],
    )
    push_progress_via_ws(
        project_id,
        task_id,
        0,
        "queued",
        f"{meta['task_name']}已入队，等待执行",
        agent_name=meta["agent_name"],
        task_name=meta["task_name"],
    )

    return {
        "task_id": task_id,
        "status": "queued",
        "progress": 0,
        "estimated_time": meta["estimated_time"],
    }


async def cancel_task(db: AsyncSession, task_id: str) -> dict:
    from tasks import push_progress_via_ws, update_progress, is_celery_available, celery_app

    result = await db.execute(select(AgentTask).where(AgentTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if is_celery_available() and celery_app is not None:
        try:
            celery_app.control.revoke(task_id, terminate=True)
        except Exception:
            pass

    task.status = "cancelled"
    task.error_message = "任务被用户取消"
    task.completed_at = datetime.now(UTC)
    await db.commit()

    update_progress(
        task_id,
        0,
        "cancelled",
        "任务已取消",
        agent_name=task.assigned_to,
        task_name=TASK_DEFINITIONS.get(task.task_type, {}).get("task_name"),
    )
    push_progress_via_ws(
        str(task.project_id),
        task_id,
        0,
        "cancelled",
        "任务已取消",
        agent_name=task.assigned_to,
        task_name=TASK_DEFINITIONS.get(task.task_type, {}).get("task_name"),
    )
    return {"status": "ok", "message": f"任务 {task_id} 已取消"}
