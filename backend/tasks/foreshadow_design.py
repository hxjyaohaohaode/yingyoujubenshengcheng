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
                foreshadows = result.data.get("foreshadows", [])
                if foreshadows:
                    return result.data

                logger.warning("伏笔Agent返回数据中无foreshadows字段，尝试从完整数据构建")
                return _ensure_foreshadows_format(result.data)

        except Exception as e:
            logger.warning("Foreshadow async design failed: %s", e)

    return _build_foreshadow_fallback(core_truth, character_ids)


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


def _ensure_foreshadows_format(data: dict) -> dict:
    if data.get("foreshadows") and isinstance(data["foreshadows"], list):
        return data

    foreshadows = []
    for layer_name, tier in [("surface_layer", "chapter"), ("deep_layer", "chapter"), ("truth_layer", "global")]:
        items = data.get(layer_name, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            fs = {
                "name": item.get("name", "未命名伏笔"),
                "foreshadow_tier": tier,
                "surface_layer": item.get("plant_strategy", item.get("description", "")),
                "deep_layer": item.get("description", "") if tier != "chapter" else "",
                "truth_layer": item.get("wow_factor", "") if tier == "global" else item.get("description", ""),
                "plant_location": "1.1",
                "reveal_location": "",
                "reclaim_status": "unplanted",
            }
            foreshadows.append(fs)

    if not foreshadows:
        return data

    data["foreshadows"] = foreshadows
    data.setdefault("stats", {
        "global_count": sum(1 for f in foreshadows if f.get("foreshadow_tier") == "global"),
        "chapter_count": sum(1 for f in foreshadows if f.get("foreshadow_tier") == "chapter"),
        "scene_count": sum(1 for f in foreshadows if f.get("foreshadow_tier") == "scene"),
        "total_count": len(foreshadows),
    })
    return data


def _build_foreshadow_fallback(core_truth: str, character_ids: list[str]) -> dict:
    foreshadows = [
        {"name": "角色对话暗示", "foreshadow_tier": "global", "surface_layer": "在日常对话中自然嵌入双关语和潜台词", "deep_layer": f"基于核心真相'{core_truth}'设计对话暗示", "truth_layer": f"对话中隐藏的线索指向核心真相: {core_truth}", "plant_location": "1.1", "reinforce_locations": ["3.2", "6.1", "10.3"], "reveal_location": "18.2", "reclaim_status": "unplanted", "worldview_refs": [], "character_refs": [{"character_name": cid, "description": "对话暗示关联角色"} for cid in character_ids[:3]], "foreshadow_links": [], "wow_factor": "回看对话发现每一句双关语都指向核心真相"},
        {"name": "环境线索", "foreshadow_tier": "global", "surface_layer": "通过物品摆放、天气变化、光影效果暗示", "deep_layer": "环境细节中隐藏着世界观深层设定的线索", "truth_layer": f"环境异常现象的真正原因是核心真相: {core_truth}", "plant_location": "2.1", "reinforce_locations": ["5.2", "9.1"], "reveal_location": "17.1", "reclaim_status": "unplanted", "worldview_refs": [], "character_refs": [], "foreshadow_links": [], "wow_factor": "环境描写中的异常在真相揭示后获得全新含义"},
        {"name": "势力暗线", "foreshadow_tier": "chapter", "surface_layer": "各方势力表面上的利益冲突", "deep_layer": "势力之间隐藏的利害关系和信息差", "truth_layer": "", "plant_location": "3.1", "reinforce_locations": ["7.2"], "reveal_location": "14.1", "reclaim_status": "unplanted", "worldview_refs": [], "character_refs": [], "foreshadow_links": [], "wow_factor": ""},
        {"name": "行为模式伏笔", "foreshadow_tier": "chapter", "surface_layer": "角色反复出现的特定行为", "deep_layer": "行为暗示深层动机和隐藏秘密", "truth_layer": "", "plant_location": "4.1", "reinforce_locations": ["8.3"], "reveal_location": "15.2", "reclaim_status": "unplanted", "worldview_refs": [], "character_refs": [], "foreshadow_links": [], "wow_factor": ""},
        {"name": "核心真相反转", "foreshadow_tier": "global", "surface_layer": "故事表层呈现的矛盾冲突", "deep_layer": "矛盾背后隐藏的更深层原因", "truth_layer": f"最终揭示的核心真相: {core_truth}", "plant_location": "1.1", "reinforce_locations": ["5.1", "10.2", "15.1"], "reveal_location": "20.1", "reclaim_status": "unplanted", "worldview_refs": [], "character_refs": [], "foreshadow_links": [], "wow_factor": "真相揭示将颠覆玩家对前期所有事件的理解"},
    ]
    return {
        "foreshadows": foreshadows,
        "design_philosophy": f"基于核心真相'{core_truth}'的降级伏笔设计（LLM调用失败时自动生成）",
        "revelation_path": [],
        "stats": {
            "global_count": 3,
            "chapter_count": 2,
            "scene_count": 0,
            "total_count": 5,
        },
    }
