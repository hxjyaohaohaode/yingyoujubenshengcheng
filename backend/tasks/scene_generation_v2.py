"""
场景生成v2 — 使用统一叙事连贯性流水线

流水线: 叙事记忆→规划→写作→5层校验→精炼→记忆更新
"""
import logging
from datetime import UTC, datetime

from tasks._helpers import (
    _safe_task_decorator as task_decorator,
    update_progress,
    push_progress_via_ws,
    update_agent_task_status,
    complete_agent_task,
    fail_agent_task,
    mark_agent_task_retrying,
    run_async,
    get_db_async,
)

logger = logging.getLogger(__name__)
AGENT_NAME = "叙事流水线"
TASK_NAME = "场景生成v2"
PIPELINE_TIMEOUT = 300


@task_decorator(bind=True, max_retries=2, default_retry_delay=60, name="tasks.scene_generation_v2.generate_scene_v2_task")
def generate_scene_v2_task(self, project_id: str, scene_id: str, chapter_id: str,
                           requirements: dict, target_words: int = 3000):
    task_id = self.request.id
    logger.info("generate_scene_v2_task started | task_id=%s project_id=%s scene_id=%s target_words=%d",
                task_id, project_id, scene_id, target_words)

    update_progress(task_id, 0, "running", "初始化叙事流水线...", agent_name=AGENT_NAME, task_name=TASK_NAME)
    push_progress_via_ws(project_id, task_id, 0, "running", "初始化叙事流水线...",
                         agent_name=AGENT_NAME, task_name=TASK_NAME)

    try:
        update_agent_task_status(project_id, task_id, "scene_generation_v2", AGENT_NAME, "running")

        update_progress(task_id, 5, "running", "Step 1/6: 加载全局叙事记忆...",
                        agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 5, "running", "Step 1/6: 加载全局叙事记忆...",
                             agent_name=AGENT_NAME, task_name=TASK_NAME)

        update_progress(task_id, 15, "running", "Step 2/6: 构建场景规划上下文...",
                        agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 15, "running", "Step 2/6: 构建场景规划上下文...",
                             agent_name=AGENT_NAME, task_name=TASK_NAME)

        update_progress(task_id, 25, "running", "Step 3/6: AI生成场景内容...",
                        agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 25, "running", "Step 3/6: AI生成场景内容...",
                             agent_name=AGENT_NAME, task_name=TASK_NAME)

        result = run_async(_run_pipeline(project_id, scene_id, chapter_id, requirements, target_words))

        update_progress(task_id, 60, "running", "Step 4/6: 5层连贯性检查中...",
                        agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 60, "running", "Step 4/6: 5层连贯性检查中...",
                             agent_name=AGENT_NAME, task_name=TASK_NAME)

        update_progress(task_id, 75, "running", "Step 5/6: 精炼修复中...",
                        agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 75, "running", "Step 5/6: 精炼修复中...",
                             agent_name=AGENT_NAME, task_name=TASK_NAME)

        update_progress(task_id, 85, "running", "Step 6/6: 更新叙事记忆...",
                        agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 85, "running", "Step 6/6: 更新叙事记忆...",
                             agent_name=AGENT_NAME, task_name=TASK_NAME)

        update_progress(task_id, 90, "running", "保存到数据库...",
                        agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 90, "running", "保存到数据库...",
                             agent_name=AGENT_NAME, task_name=TASK_NAME)

        scene_draft = _pipeline_result_to_scene_draft(result, requirements, project_id)
        _save_scene_to_db(scene_id, scene_draft)

        if result.get("status") == "failed":
            raise RuntimeError("流水线执行失败")

        complete_agent_task(project_id, task_id, scene_draft)

        coherence_info = ""
        if result.get("coherence_report"):
            cr = result["coherence_report"]
            coherence_info = f", 5层评分={cr.total_score:.0f}, 通过={cr.all_passed}"
        summary = f"场景生成完成: 字数={result.get('word_count', 0)}{coherence_info}, 精炼={result.get('refine_iterations', 0)}轮"

        update_progress(task_id, 100, "completed", summary,
                        agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 100, "completed", summary,
                             agent_name=AGENT_NAME, task_name=TASK_NAME)

        logger.info("generate_scene_v2_task completed | task_id=%s %s", task_id, summary)
        return {
            "task_id": task_id,
            "status": "completed",
            "project_id": project_id,
            "scene_id": scene_id,
            "scene_draft": scene_draft,
            "pipeline_result": result,
        }

    except Exception as e:
        logger.error("generate_scene_v2_task failed | task_id=%s error=%s", task_id, str(e), exc_info=True)
        if self.request.retries < self.max_retries:
            mark_agent_task_retrying(project_id, task_id, str(e))
            update_progress(task_id, 0, "retrying", str(e)[:200],
                            agent_name=AGENT_NAME, task_name=TASK_NAME)
            push_progress_via_ws(project_id, task_id, 0, "retrying", str(e)[:200],
                                 agent_name=AGENT_NAME, task_name=TASK_NAME)
            raise self.retry(exc=e)

        fail_agent_task(project_id, task_id, str(e))
        update_progress(task_id, 0, "failed", str(e)[:200],
                        agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 0, "failed", str(e)[:200],
                             agent_name=AGENT_NAME, task_name=TASK_NAME)
        raise


async def _run_pipeline(project_id: str, scene_id: str, chapter_id: str,
                        requirements: dict, target_words: int) -> dict:
    """执行叙事连贯性流水线"""
    from core.agent.scene_generation_pipeline import SceneGenerationPipeline
    from core.gateway.client import ModelGateway
    from core.rag.retriever import RAGRetriever
    from core.storage.service import StorageService
    from core.context.context_manager import ContextManager
    from core.search.web_search import WebSearchService
    from core.context.intent_analyzer import IntentAnalyzer

    async with get_db_async() as db:
        gateway = ModelGateway()
        rag = RAGRetriever(db)
        storage = StorageService(db)
        search_svc = WebSearchService(db, gateway)
        ctx_mgr = ContextManager(db, gateway, rag, search_svc)

        knowledge_text = ""
        project_brief = ""
        core_contradiction = ""
        try:
            project_brief = requirements.get("project_brief", "")
            genre = requirements.get("genre", "")
            core_contradiction = requirements.get("core_contradiction", "")
            user_intent_text = f"{project_brief} {genre} {core_contradiction}".strip()

            intent = None
            if user_intent_text:
                analyzer = IntentAnalyzer(gateway)
                intent = await analyzer.analyze(user_intent_text)
                if intent and intent.need_search and intent.entities:
                    await search_svc.batch_search(intent.entities, user_intent_text)

            knowledge_text = await ctx_mgr.enrich_prompt(
                agent_name="scene_writer",
                base_prompt="",
                project_id=project_id,
                intent=intent,
                search_cards=None,
                upload_chunks=await ctx_mgr.get_upload_chunks(project_id),
            )
        except Exception as e:
            logger.warning("知识上下文构建失败(非致命): %s", str(e)[:200])

        pipeline = SceneGenerationPipeline(db)
        pipeline.gateway = gateway

        try:
            result = await pipeline.generate(
                project_id=project_id,
                scene_id=scene_id,
                chapter_id=chapter_id,
                context={
                    "project_brief": project_brief,
                    "genre": requirements.get("genre", ""),
                    "style": requirements.get("style", ""),
                    "sub_genre": requirements.get("sub_genre", ""),
                    "theme": requirements.get("theme", ""),
                    "core_contradiction": core_contradiction,
                    "narrative_pov": requirements.get("narrative_pov", "third_person"),
                    "world_settings": requirements.get("world_settings", ""),
                    "character_states": requirements.get("character_states", ""),
                    "previous_scene": requirements.get("previous_scene", ""),
                    "chapter_info": requirements.get("chapter_info", ""),
                    "scene_code": requirements.get("scene_code", ""),
                    "scene_type": requirements.get("scene_type", "transition"),
                    "emotion_target": requirements.get("emotion_target", 5),
                    "location": requirements.get("location", ""),
                    "weather": requirements.get("weather", ""),
                    "foreshadow_tasks": requirements.get("foreshadow_tasks", ""),
                    "rag_context": knowledge_text,
                    "style_guide": requirements.get("style_guide", ""),
                },
                user_requirements=requirements.get("user_requirements", ""),
                target_words=target_words,
            )

            coherence_dict = None
            if result.coherence_report:
                coherence_dict = {
                    "all_passed": result.coherence_report.all_passed,
                    "total_score": result.coherence_report.total_score,
                    "checks": [
                        {"layer": c.layer, "passed": c.passed, "score": c.score,
                         "issues": c.issues, "suggestions": c.suggestions}
                        for c in result.coherence_report.checks
                    ],
                }

            return {
                "status": result.status,
                "narration": result.narration,
                "dialogue": result.dialogue,
                "actions": result.actions,
                "foreshadow_ops": result.foreshadow_ops,
                "choices": result.choices,
                "causal_chain": result.causal_chain,
                "emotion_level": result.emotion_level,
                "word_count": result.word_count,
                "target_words": result.target_words,
                "within_budget": result.within_budget,
                "coherence_report": coherence_dict,
                "refine_iterations": result.refine_iterations,
                "memory_updated": result.memory_updated,
            }
        finally:
            await gateway.close()
            await search_svc.close()


def _pipeline_result_to_scene_draft(pipeline_result: dict, requirements: dict, project_id: str) -> dict:
    return {
        "project_id": project_id or requirements.get("project_id", ""),
        "narration": pipeline_result.get("narration", ""),
        "dialogue": pipeline_result.get("dialogue", []),
        "actions": pipeline_result.get("actions", []),
        "emotion_level": pipeline_result.get("emotion_level", requirements.get("emotion_target", 5)),
        "foreshadow_ops": pipeline_result.get("foreshadow_ops", []),
        "choices": pipeline_result.get("choices", []),
        "characters_involved": requirements.get("character_ids", []),
        "location": requirements.get("location", ""),
        "weather": requirements.get("weather", ""),
        "time_start": requirements.get("time_start", ""),
        "time_end": "",
        "causal_chain": pipeline_result.get("causal_chain"),
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
        logger.info("Scene %s saved to database (v2 pipeline)", scene_id)