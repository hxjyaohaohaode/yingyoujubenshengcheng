import logging

from tasks._helpers import _safe_task_decorator as task_decorator, update_progress, push_progress_via_ws, update_agent_task_status, complete_agent_task, fail_agent_task, mark_agent_task_retrying, run_async, get_db_async

logger = logging.getLogger(__name__)
AGENT_NAME = "伏笔Agent"
TASK_NAME = "伏笔体系设计"


@task_decorator(bind=True, max_retries=2, name="tasks.foreshadow_design.foreshadow_design_task")
def foreshadow_design_task(self, project_id: str, core_truth: str, character_ids: list[str]):
    task_id = self.request.id
    logger.info("foreshadow_design_task started | task_id=%s project_id=%s chars=%d", task_id, project_id, len(character_ids))

    update_progress(task_id, 0, "running", "启动伏笔体系设计...", agent_name=AGENT_NAME, task_name=TASK_NAME)
    push_progress_via_ws(project_id, task_id, 0, "running", "启动伏笔体系设计...", agent_name=AGENT_NAME, task_name=TASK_NAME)

    try:
        update_agent_task_status(project_id, task_id, "foreshadow_design", AGENT_NAME, "running")

        update_progress(task_id, 15, "running", "分析世界观核心真相...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 15, "running", "分析世界观核心真相...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        update_progress(task_id, 30, "running", "提取角色关系图谱...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 30, "running", "提取角色关系图谱...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        update_progress(task_id, 45, "running", "调用伏笔Agent设计三层结构...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 45, "running", "调用伏笔Agent设计三层结构...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        design_result = run_async(_design_foreshadows_async(project_id, core_truth, character_ids))

        update_progress(task_id, 65, "running", "验证伏笔关联关系...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 65, "running", "验证伏笔关联关系...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        foreshadow_records = _build_foreshadow_records(project_id, design_result)

        update_progress(task_id, 80, "running", "持久化伏笔数据...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 80, "running", "持久化伏笔数据...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        _save_foreshadows_to_db(foreshadow_records)
        _save_foreshadow_relations(project_id, design_result, foreshadow_records)

        update_progress(task_id, 95, "running", "生成伏笔健康报告...", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 95, "running", "生成伏笔健康报告...", agent_name=AGENT_NAME, task_name=TASK_NAME)

        health_report = {
            "total_foreshadows": len(foreshadow_records),
            "surface_count": sum(1 for fs in foreshadow_records if fs.get("fs_type") == "surface"),
            "deep_count": sum(1 for fs in foreshadow_records if fs.get("fs_type") == "deep"),
            "truth_count": sum(1 for fs in foreshadow_records if fs.get("fs_type") == "truth"),
            "all_planted": False,
            "suggestion": f"已生成{len(foreshadow_records)}个伏笔，请在场景创作阶段逐步植入",
        }

        result = {"design_result": design_result, "foreshadow_records": foreshadow_records, "health_report": health_report}
        complete_agent_task(project_id, task_id, result)

        update_progress(task_id, 100, "completed", "伏笔体系设计完成", agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 100, "completed", "伏笔体系设计完成", agent_name=AGENT_NAME, task_name=TASK_NAME)

        logger.info("foreshadow_design_task completed | task_id=%s foreshadows=%d", task_id, len(foreshadow_records))
        return {"task_id": task_id, "status": "completed", "project_id": project_id, "foreshadow_count": len(foreshadow_records), "health_report": health_report}

    except Exception as e:
        logger.error("foreshadow_design_task failed | task_id=%s error=%s", task_id, str(e), exc_info=True)
        if self.request.retries < self.max_retries:
            mark_agent_task_retrying(project_id, task_id, str(e))
            update_progress(task_id, 0, "retrying", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
            push_progress_via_ws(project_id, task_id, 0, "retrying", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
            raise self.retry(exc=e)

        fail_agent_task(project_id, task_id, str(e))
        update_progress(task_id, 0, "failed", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
        push_progress_via_ws(project_id, task_id, 0, "failed", str(e)[:200], agent_name=AGENT_NAME, task_name=TASK_NAME)
        raise


async def _design_foreshadows_async(project_id: str, core_truth: str, character_ids: list[str]) -> dict:
    from core.gateway.client import ModelGateway
    from core.rag.retriever import RAGRetriever
    from core.storage.service import StorageService
    from core.agent.base import AgentTask
    from core.agent.registry import get_agent

    async with get_db_async() as db:
        try:
            gateway = ModelGateway()
            storage = StorageService(db)

            chapter_count = len(await storage.get_chapter_outlines(project_id)) or 20

            agent = get_agent("foreshadow", gateway, RAGRetriever(db), storage)

            task = AgentTask(
                task_id=f"{project_id}_fs_design",
                agent_name="foreshadow",
                task_type="foreshadow_designer",
                project_id=project_id,
                payload={"core_truth": core_truth, "character_ids": character_ids, "chapter_count": chapter_count},
                cost_profile="quality",
            )

            result = await agent.execute(task)
            await gateway.close()

            if result.status == "completed" and result.data:
                return result.data

        except Exception as e:
            logger.warning("Foreshadow async design failed: %s", e)

    return {
        "surface_layer": [
            {"name": "角色对话暗示", "description": f"基于核心真相'{core_truth}'设计对话暗示", "plant_strategy": "在日常对话中自然嵌入双关语和潜台词", "involved_characters": character_ids[:3]},
            {"name": "环境线索", "description": "在场景描写中埋设视觉线索", "plant_strategy": "通过物品摆放、天气变化、光影效果暗示", "involved_characters": []},
        ],
        "deep_layer": [
            {"name": "势力关系网", "description": "各方势力之间隐藏的利害关系", "plant_strategy": "通过角色不在场时的消息传递和信息差构建", "depends_on": []},
            {"name": "行为模式伏笔", "description": "角色反复出现的特定行为暗示深层动机", "plant_strategy": "三次重复法则：第一次忽略，第二次注意，第三次揭示", "depends_on": []},
        ],
        "truth_layer": [
            {"name": "核心真相反转", "description": f"最终揭示的核心真相: {core_truth}", "reveal_timing": "最终章", "wow_factor": "真相揭示将颠覆玩家对前期所有事件的理解", "depends_on_all": True},
        ],
    }


def _build_foreshadow_records(project_id: str, design_result: dict) -> list:
    records = []
    fs_counter = 1
    for layer_name in ("surface_layer", "deep_layer", "truth_layer"):
        layer_items = design_result.get(layer_name, []) if isinstance(design_result.get(layer_name, []), list) else []
        for item in layer_items:
            fs_type = "surface" if layer_name == "surface_layer" else "deep" if layer_name == "deep_layer" else "truth"
            records.append({
                "project_id": project_id, "fs_code": f"FS-{fs_type[:1].upper()}-{fs_counter:03d}",
                "name": item.get("name", f"伏笔{fs_counter}"), "fs_type": fs_type,
                "surface_layer": item.get("plant_strategy", item.get("description", "")),
                "deep_layer": "" if fs_type == "surface" else item.get("description", ""),
                "truth_layer": item.get("wow_factor", "") if fs_type == "truth" else item.get("description", ""),
                "current_status": "design", "reinforce_count": 0, "health": "normal",
                "depends_on": item.get("depends_on", []), "enables": [], "reinforce_scenes": [],
            })
            fs_counter += 1
    return records


def _save_foreshadows_to_db(records: list):
    if not records:
        return
    from database import get_db_sync
    from models.foreshadow import Foreshadow
    with get_db_sync() as db:
        for r in records:
            db.add(Foreshadow(project_id=r["project_id"], fs_code=r["fs_code"], name=r["name"], fs_type=r["fs_type"], surface_layer=r["surface_layer"], deep_layer=r["deep_layer"], truth_layer=r["truth_layer"], current_status=r["current_status"], reinforce_count=r["reinforce_count"], health=r["health"], depends_on=r["depends_on"], enables=r["enables"], reinforce_scenes=r["reinforce_scenes"]))
        db.commit()


def _save_foreshadow_relations(project_id: str, design_result: dict, foreshadow_records: list):
    from database import get_db_sync
    from models.foreshadow import Foreshadow, ForeshadowRelation
    fs_map = {fs["name"]: fs["fs_code"] for fs in foreshadow_records if fs.get("name")}
    for layer_name in ("surface_layer", "deep_layer", "truth_layer"):
        for item in (design_result.get(layer_name, []) if isinstance(design_result.get(layer_name, []), list) else []):
            depends_on = item.get("depends_on", []) if isinstance(item.get("depends_on", []), list) else []
            if not depends_on:
                continue
            target_code = fs_map.get(item.get("name"))
            if not target_code:
                continue
            for dep_name in depends_on:
                dep_code = fs_map.get(dep_name)
                if not dep_code:
                    continue
                with get_db_sync() as db:
                    from_fs = db.query(Foreshadow).filter(Foreshadow.project_id == project_id, Foreshadow.fs_code == dep_code).first()
                    to_fs = db.query(Foreshadow).filter(Foreshadow.project_id == project_id, Foreshadow.fs_code == target_code).first()
                    if from_fs and to_fs:
                        existing = db.query(ForeshadowRelation).filter(ForeshadowRelation.from_fs_id == from_fs.id, ForeshadowRelation.to_fs_id == to_fs.id).first()
                        if not existing:
                            db.add(ForeshadowRelation(project_id=project_id, from_fs_id=from_fs.id, to_fs_id=to_fs.id, relation_type="depends_on"))
                            try:
                                db.commit()
                            except Exception:
                                pass
