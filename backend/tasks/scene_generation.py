import logging
from datetime import UTC, datetime

from tasks._helpers import _safe_task_decorator as task_decorator, update_progress, push_progress_via_ws, update_agent_task_status, complete_agent_task, fail_agent_task, mark_agent_task_retrying, run_async, get_db_async

logger = logging.getLogger(__name__)
AGENT_NAME = "创作Agent"
TASK_NAME = "场景生成"


@task_decorator(bind=True, max_retries=3, default_retry_delay=30, name="tasks.scene_generation.generate_scene_task")
def generate_scene_task(self, project_id: str, scene_id: str, requirements: dict):
    task_id = self.request.id
    logger.info("generate_scene_task started | task_id=%s project_id=%s scene_id=%s", task_id, project_id, scene_id)

    update_progress(task_id, 0, "running", "初始化场景生成引擎...", agent_name=AGENT_NAME, task_name=TASK_NAME)
    push_progress_via_ws(project_id, task_id, 0, "running", "初始化场景生成引擎...", agent_name=AGENT_NAME, task_name=TASK_NAME)

    try:
        update_agent_task_status(project_id, task_id, "scene_generation", AGENT_NAME, "running")

        update_progress(task_id, 10, "running", "组装上下文...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 10, "running", "组装上下文...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        scene_draft = run_async(_generate_scene_async(project_id, scene_id, requirements))

        logger.info("Scene draft generated, narration length=%d", len(scene_draft.get("narration", "")))

        update_progress(task_id, 60, "running", "解析结构化数据...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 60, "running", "解析结构化数据...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        scene_draft = _parse_scene_draft(scene_draft, requirements, project_id)

        update_progress(task_id, 75, "running", "写入数据库...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 75, "running", "写入数据库...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        _save_scene_to_db(scene_id, scene_draft)

        update_progress(task_id, 85, "running", "同步状态数据...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 85, "running", "同步状态数据...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        _sync_scene_state(project_id, scene_id, scene_draft)

        update_progress(task_id, 90, "running", "更新任务状态...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 90, "running", "更新任务状态...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        complete_agent_task(project_id, task_id, scene_draft)

        update_progress(task_id, 100, "completed", "场景生成完成", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 100, "completed", "场景生成完成", agent_name=AGENT_NAME, task_name=TASK_NAME)

        logger.info("generate_scene_task completed | task_id=%s", task_id)
        return {
            "task_id": task_id,
            "status": "completed",
            "project_id": project_id,
            "scene_id": scene_id,
            "scene_draft": scene_draft,
        }

    except Exception as e:
        logger.error("generate_scene_task failed | task_id=%s error=%s", task_id, str(e), exc_info=True)
        if self.request.retries < self.max_retries:
            mark_agent_task_retrying(project_id, task_id, str(e))
            update_progress(task_id, 0, "retrying", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
            push_progress_via_ws(project_id, task_id, 0, "retrying", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
            raise self.retry(exc=e)

        fail_agent_task(project_id, task_id, str(e))
        update_progress(task_id, 0, "failed", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 0, "failed", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
        raise


async def _generate_scene_async(project_id: str, scene_id: str, requirements: dict) -> dict:
    from core.gateway.client import ModelGateway
    from core.rag.retriever import RAGRetriever
    from core.storage.service import StorageService
    from core.agent.base import AgentTask
    from core.agent.registry import get_agent

    async with get_db_async() as db:
        gateway = ModelGateway()
        rag = RAGRetriever(db)
        storage = StorageService(db)

        try:
            agent = get_agent("creator", gateway, rag, storage)

            task = AgentTask(
                task_id=f"{project_id}_{scene_id}",
                agent_name="creator",
                task_type="scene_writer",
                project_id=project_id,
                payload={
                    **requirements,
                    "scene_id": scene_id,
                },
                cost_profile=_get_cost_profile(requirements),
            )

            result = await agent.execute(task)
        finally:
            await gateway.close()

        if result.status != "completed":
            issues = "; ".join(result.issues) if result.issues else ""
            raise RuntimeError(f"场景生成失败: {issues or result.status}")

        return _validate_scene_result(result.data)


def _get_cost_profile(requirements: dict) -> str:
    is_wow = requirements.get("is_wow_moment", False)
    emotion_target = requirements.get("emotion_target", 5)
    if is_wow and emotion_target >= 8:
        return "quality"
    if is_wow or emotion_target >= 7:
        return "balanced"
    return "economy"


def _validate_scene_result(scene_data: dict) -> dict:
    if not isinstance(scene_data, dict):
        raise ValueError("场景生成结果不是合法对象")

    narration = scene_data.get("narration")
    dialogue = scene_data.get("dialogue")
    actions = scene_data.get("actions")

    if not isinstance(narration, str) or len(narration.strip()) < 200:
        raise ValueError("场景旁白过短或缺失（至少需要200字符）")
    if not isinstance(dialogue, list) or not dialogue:
        raise ValueError("场景对白缺失")
    if not isinstance(actions, list) or not actions:
        raise ValueError("场景动作缺失")

    return scene_data


def _parse_scene_draft(scene_draft: dict, requirements: dict, project_id: str = "") -> dict:
    return {
        "project_id": project_id or requirements.get("project_id", ""),
        "narration": scene_draft.get("narration", ""),
        "dialogue": scene_draft.get("dialogue", []),
        "actions": scene_draft.get("actions", []),
        "emotion_level": scene_draft.get("emotion_level", requirements.get("emotion_target", 5)),
        "foreshadow_ops": scene_draft.get("foreshadow_ops", []),
        "choices": scene_draft.get("choices", []),
        "characters_involved": scene_draft.get("characters_involved", requirements.get("character_ids", [])),
        "location": scene_draft.get("location", requirements.get("location", "")),
        "weather": scene_draft.get("weather", requirements.get("weather", "")),
        "time_start": scene_draft.get("time_start", requirements.get("time_start", "")),
        "time_end": scene_draft.get("time_end", ""),
        "causal_chain": scene_draft.get("causal_chain"),
        "is_wow_moment": requirements.get("is_wow_moment", False),
        "wow_type": requirements.get("wow_type", ""),
        "wow_spec": requirements.get("wow_spec", ""),
    }


def _save_scene_to_db(scene_id: str, scene_draft: dict):
    from database import get_db_sync
    from models.scene import Scene

    with get_db_sync() as db:
        scene = db.query(Scene).filter(Scene.id == scene_id).first()
        if scene is None:
            logger.info("Scene %s not found, creating new record", scene_id)
            scene = Scene(
                id=scene_id,
                project_id=scene_draft.get("project_id", ""),
                scene_code=scene_draft.get("scene_code", scene_id[:8]),
                status="draft",
            )
            db.add(scene)
            db.flush()

        scene.narration = scene_draft.get("narration", scene.narration)
        scene.dialogue = scene_draft.get("dialogue", scene.dialogue)
        scene.actions = scene_draft.get("actions", scene.actions)
        scene.emotion_level = scene_draft.get("emotion_level", scene.emotion_level)
        scene.foreshadow_ops = scene_draft.get("foreshadow_ops", scene.foreshadow_ops)
        scene.choices = scene_draft.get("choices", scene.choices)
        scene.characters_involved = scene_draft.get("characters_involved", scene.characters_involved)
        scene.location = scene_draft.get("location", scene.location)
        scene.weather = scene_draft.get("weather", scene.weather)
        scene.time_start = scene_draft.get("time_start", scene.time_start)
        scene.time_end = scene_draft.get("time_end", scene.time_end)
        scene.causal_chain = scene_draft.get("causal_chain", scene.causal_chain)
        scene.is_wow_moment = scene_draft.get("is_wow_moment", scene.is_wow_moment)
        scene.wow_type = scene_draft.get("wow_type", scene.wow_type)
        scene.wow_spec = scene_draft.get("wow_spec", scene.wow_spec)
        scene.status = "draft"
        scene.updated_at = datetime.now(UTC)

        db.commit()
        logger.info("Scene %s saved to database", scene_id)


def _sync_scene_state(project_id: str, scene_id: str, scene_draft: dict):
    from core.agent.base import AgentTask
    from core.agent.registry import get_agent

    try:
        sync_result = run_async(_sync_scene_state_async(project_id, scene_id, scene_draft))
        logger.info("Scene state sync completed: %s", sync_result)
    except Exception as e:
        logger.warning("Scene state sync failed (non-fatal): %s", str(e))


async def _sync_scene_state_async(project_id: str, scene_id: str, scene_draft: dict):
    from core.gateway.client import ModelGateway
    from core.rag.retriever import RAGRetriever
    from core.storage.service import StorageService
    from core.agent.base import AgentTask
    from core.agent.registry import get_agent

    async with get_db_async() as db:
        gateway = ModelGateway()
        rag = RAGRetriever(db)
        storage = StorageService(db)

        try:
            agent = get_agent("state_manager", gateway, rag, storage)

            scene_data = {
                "id": scene_id,
                **scene_draft,
            }

            task = AgentTask(
                task_id=f"{project_id}_state_sync_{scene_id}",
                agent_name="state_manager",
                task_type="state_updater",
                project_id=project_id,
                payload={
                    "scene_id": scene_id,
                    "operation": "update_from_scene",
                    "previous_result": scene_data,
                },
                cost_profile="economy",
            )

            result = await agent.execute(task)

            if result.status == "completed":
                return result.data
            else:
                logger.warning("StateManager returned non-completed: %s", result.status)
                return {"status": result.status}
        finally:
            await gateway.close()
